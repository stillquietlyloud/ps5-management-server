"""Module 3: Pull games from PS5 to server."""
import os
import shutil
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.modules.ftp_module import FTPModule
from app.models import PS5System, Game, GameLocation, GameFormat, PS5StorageLocation
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class PullModule(BaseModule):
    """Pull Module for copying games from PS5 to server."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ftp_module = FTPModule()
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="pull_module",
            version="1.0.0",
            description="Copy/pull games from PS5 to server, option to keep or remove on PS5",
            dependencies=["ftp_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Pull Module")
        await self.ftp_module.initialize()
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        await self.ftp_module.shutdown()
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "ftp_status": self.ftp_module.get_status().value,
        }
    
    def pull(self, system: PS5System, game: Game, keep_on_ps5: bool = True) -> Dict[str, Any]:
        """Pull a game from PS5 to server."""
        try:
            logger.info(f"Pulling game {game.name} from {system.name} (keep_on_ps5={keep_on_ps5})")
            
            # Find all game locations on this PS5
            ps5_locations = []
            for loc in game.locations:
                if loc.ps5_system_id == system.id and loc.ps5_path:
                    ps5_locations.append(loc)
            
            if not ps5_locations:
                return {"success": False, "error": "Game not found on this PS5"}
            
            # Select the best location to pull from:
            # Prefer actual game files (pkg, fpkg, exfat, iso, ffpfsc) over folders
            # These formats contain the actual game data
            format_priority = {
                GameFormat.FPKG: 1,
                GameFormat.PKG: 2,
                GameFormat.EXFAT: 3,
                GameFormat.ISO: 4,
                GameFormat.FFPFSC: 5,
                GameFormat.ZIP: 6,
                GameFormat.RAR: 7,
                GameFormat.SEVEN_ZIP: 8,
                GameFormat.FOLDER: 9,  # Lowest priority - often just metadata
            }
            
            # Sort by priority (lower number = higher priority)
            ps5_locations.sort(key=lambda loc: format_priority.get(loc.format, 10))
            
            ps5_location = ps5_locations[0]
            logger.info(f"Selected location: {ps5_location.ps5_path} (format: {ps5_location.format})")
            
            ps5_path = ps5_location.ps5_path
            
            # Determine local server path
            server_path = self._get_server_path(game)
            
            # Connect to PS5
            conn_result = self.ftp_module.connect(system)
            if not conn_result.get("success"):
                return conn_result
            
            try:
                # Transfer file(s)
                if ps5_location.format == GameFormat.FOLDER:
                    result = self._transfer_folder_from_ps5(ps5_path, server_path)
                else:
                    result = self._transfer_file_from_ps5(ps5_path, server_path)
                
                if result.get("success"):
                    # Update database
                    self._update_database_after_pull(game, system, server_path, keep_on_ps5)
                    
                    # If not keeping on PS5, delete from PS5
                    if not keep_on_ps5:
                        self._delete_from_ps5(ps5_path, ps5_location.format)
                
                return result
            
            finally:
                self.ftp_module.disconnect()
        
        except Exception as e:
            logger.error(f"Error pulling game: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_server_path(self, game: Game) -> str:
        """Get target path on server."""
        folder_name = game.title_id or game.ppsa or game.name.replace(" ", "_")
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in "._-")
        return os.path.join(settings.SERVER_GAMES_PATH, folder_name)
    
    def _transfer_file_from_ps5(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        """Transfer a single file from PS5 to server."""
        try:
            filename = os.path.basename(remote_path)
            full_local = os.path.join(local_path, filename)
            
            logger.info(f"Downloading {remote_path} -> {full_local}")
            
            os.makedirs(local_path, exist_ok=True)
            
            success = self.ftp_module.download_file(remote_path, full_local)
            
            if success:
                size = os.path.getsize(full_local)
                return {
                    "success": True,
                    "message": f"Downloaded {filename}",
                    "bytes_transferred": size,
                    "local_path": full_local,
                }
            else:
                return {"success": False, "error": "Download failed"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _transfer_folder_from_ps5(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        """Transfer a folder recursively from PS5 to server."""
        try:
            total_size = 0
            files_transferred = 0
            
            # Get remote directory listing recursively
            # We need to use the FTP module to list and download recursively
            logger.info(f"Starting recursive folder download from {remote_path} to {local_path}")
            
            # Create local directory
            os.makedirs(local_path, exist_ok=True)
            
            # Recursively download
            result = self._download_folder_recursive(remote_path, local_path)
            
            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Downloaded {result['files_transferred']} files",
                    "bytes_transferred": result["total_size"],
                    "local_path": local_path,
                }
            else:
                return {"success": False, "error": result.get("error", "Unknown error")}
        
        except Exception as e:
            logger.error(f"Error downloading folder: {e}")
            return {"success": False, "error": str(e)}
    
    def _download_folder_recursive(self, remote_path: str, local_path: str) -> Dict[str, Any]:
        """Recursively download a folder from PS5 via FTP."""
        try:
            total_size = 0
            files_transferred = 0
            
            # List remote directory
            items = self.ftp_module.list_directory(remote_path)
            if not items:
                return {"success": False, "error": "Failed to list remote directory or empty"}
            
            for item in items:
                if item['name'] in ['.', '..']:
                    continue
                
                remote_item = f"{remote_path}/{item['name']}"
                local_item = os.path.join(local_path, item['name'])
                
                if item['is_dir']:
                    # Recursively download subdirectory
                    os.makedirs(local_item, exist_ok=True)
                    result = self._download_folder_recursive(remote_item, local_item)
                    if result.get("success"):
                        total_size += result.get("total_size", 0)
                        files_transferred += result.get("files_transferred", 0)
                    else:
                        logger.warning(f"Failed to download subdirectory {remote_item}: {result.get('error')}")
                else:
                    # Download file
                    success = self.ftp_module.download_file(remote_item, local_item)
                    if success:
                        size = os.path.getsize(local_item)
                        total_size += size
                        files_transferred += 1
                    else:
                        logger.warning(f"Failed to download file {remote_item}")
            
            return {
                "success": True,
                "files_transferred": files_transferred,
                "total_size": total_size,
            }
        
        except Exception as e:
            logger.error(f"Error in recursive download: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_database_after_pull(self, game: Game, system: PS5System, 
                                    server_path: str, keep_on_ps5: bool) -> None:
        """Update database after successful pull."""
        db = get_db_session()
        try:
            # Check if server location already exists
            location = db.query(GameLocation).filter_by(
                game_id=game.id,
                server_path=server_path,
                ps5_system_id=None
            ).first()
            
            if not location:
                location = GameLocation(
                    game_id=game.id,
                    ps5_system_id=None,  # Server location
                    server_path=server_path,
                    format=game.format,
                    size_bytes=game.size_bytes,
                    is_installed=True,
                    verified=True,
                    last_verified=datetime.utcnow(),
                )
                db.add(location)
            else:
                location.is_installed = True
                location.verified = True
                location.last_verified = datetime.utcnow()
            
            # Update game availability
            game.is_on_server = True
            game.updated_at = datetime.utcnow()
            
            # Update PS5 location if not keeping
            if not keep_on_ps5:
                ps5_loc = db.query(GameLocation).filter_by(
                    game_id=game.id,
                    ps5_system_id=system.id
                ).first()
                if ps5_loc:
                    ps5_loc.is_installed = False
            
            db.commit()
            logger.info(f"Database updated for game {game.name} pulled from {system.name}")
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating database: {e}")
        finally:
            db.close()
    
    def _delete_from_ps5(self, remote_path: str, format: GameFormat) -> bool:
        """Delete game from PS5."""
        try:
            if format == GameFormat.FOLDER:
                # Would need recursive delete
                logger.warning("Folder deletion from PS5 not implemented")
                return False
            else:
                self.ftp_module._connection.delete(remote_path)
                return True
        except Exception as e:
            logger.error(f"Error deleting from PS5: {e}")
            return False
    
    def list_ps5_games(self, system: PS5System) -> list:
        """List games available on a specific PS5 for pulling."""
        db = get_db_session()
        try:
            locations = db.query(GameLocation).filter_by(
                ps5_system_id=system.id,
                is_installed=True
            ).all()
            
            games = []
            for loc in locations:
                game = db.query(Game).get(loc.game_id)
                if game:
                    games.append({
                        "id": game.id,
                        "name": game.name,
                        "ppsa": game.ppsa,
                        "title_id": game.title_id,
                        "format": game.format.value if game.format else None,
                        "size_bytes": loc.size_bytes,
                        "ps5_path": loc.ps5_path,
                        "ps5_storage": loc.ps5_storage.value if loc.ps5_storage else None,
                    })
            
            return games
        finally:
            db.close()