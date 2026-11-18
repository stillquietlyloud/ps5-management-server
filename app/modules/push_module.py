"""Module 2: Push ROMs from server to PS5 storage."""
import os
import shutil
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.modules.ftp_module import FTPModule
from app.models import PS5System, Game, GameLocation, GameFormat, PS5StorageLocation
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class PushModule(BaseModule):
    """Push Module for transferring games from server to PS5."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ftp_module = FTPModule()
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="push_module",
            version="1.0.0",
            description="Transfer games from server storage to PS5 (primary SSD, secondary, external)",
            dependencies=["ftp_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Push Module")
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
    
    def push(self, system: PS5System, game: Game, storage: str = "primary_ssd") -> Dict[str, Any]:
        """Push a game from server to PS5."""
        try:
            logger.info(f"Pushing game {game.name} to {system.name} ({storage})")
            
            # Find the game on server
            server_location = None
            for loc in game.locations:
                if loc.server_path and not loc.ps5_system_id:
                    server_location = loc
                    break
            
            if not server_location or not server_location.server_path:
                return {"success": False, "error": "Game not found on server"}
            
            server_path = server_location.server_path
            
            if not os.path.exists(server_path):
                return {"success": False, "error": f"Server file not found: {server_path}"}
            
            # Determine target PS5 path based on storage
            target_path = self._get_target_path(system, storage, game)
            
            # Connect to PS5
            conn_result = self.ftp_module.connect(system)
            if not conn_result.get("success"):
                return conn_result
            
            try:
                # Ensure target directory exists
                self._ensure_remote_dir(target_path)
                
                # Transfer file(s)
                if os.path.isdir(server_path):
                    # Transfer folder recursively
                    result = self._transfer_folder(server_path, target_path)
                else:
                    # Transfer single file
                    result = self._transfer_file(server_path, target_path)
                
                if result.get("success"):
                    # Update database
                    self._update_database_after_push(game, system, target_path, storage)
                
                return result
            
            finally:
                self.ftp_module.disconnect()
        
        except Exception as e:
            logger.error(f"Error pushing game: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_target_path(self, system: PS5System, storage: str, game: Game) -> str:
        """Get target path on PS5 based on storage selection."""
        storage_map = {
            "primary_ssd": "/data/app",
            "secondary_ssd": "/data/app0",
            "external_usb": "/mnt/usb0",
            "external_usb_2": "/mnt/usb1",
            "external_usb_3": "/mnt/usb2",
        }
        
        base_path = storage_map.get(storage, "/data/app")
        
        # Use game's folder name or create one from title_id/ppsa
        folder_name = game.title_id or game.ppsa or game.name.replace(" ", "_")
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in "._-")
        
        return f"{base_path}/{folder_name}"
    
    def _ensure_remote_dir(self, path: str) -> bool:
        """Ensure remote directory exists, create if needed."""
        try:
            # Split path and create each directory
            parts = path.strip("/").split("/")
            current = "/"
            
            for part in parts:
                current = f"{current}/{part}" if current != "/" else f"/{part}"
                try:
                    self.ftp_module._connection.cwd(current)
                except Exception:
                    try:
                        self.ftp_module._connection.mkd(current)
                        self.ftp_module._connection.cwd(current)
                    except Exception as e:
                        logger.warning(f"Could not create directory {current}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Error ensuring remote dir: {e}")
            return False
    
    def _transfer_file(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """Transfer a single file to PS5."""
        try:
            filename = os.path.basename(local_path)
            full_remote = f"{remote_path}/{filename}"
            
            logger.info(f"Transferring {local_path} -> {full_remote}")
            
            success = self.ftp_module.upload_file(local_path, full_remote)
            
            if success:
                size = os.path.getsize(local_path)
                return {
                    "success": True,
                    "message": f"Transferred {filename}",
                    "bytes_transferred": size,
                    "remote_path": full_remote,
                }
            else:
                return {"success": False, "error": "Upload failed"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _transfer_folder(self, local_path: str, remote_path: str) -> Dict[str, Any]:
        """Transfer a folder recursively to PS5."""
        try:
            total_size = 0
            files_transferred = 0
            
            for root, dirs, files in os.walk(local_path):
                # Calculate relative path
                rel_path = os.path.relpath(root, local_path)
                if rel_path == ".":
                    target_remote = remote_path
                else:
                    target_remote = f"{remote_path}/{rel_path}"
                
                # Ensure remote directory exists
                self._ensure_remote_dir(target_remote)
                
                # Transfer files
                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = f"{target_remote}/{file}"
                    
                    success = self.ftp_module.upload_file(local_file, remote_file)
                    if success:
                        total_size += os.path.getsize(local_file)
                        files_transferred += 1
                    else:
                        logger.warning(f"Failed to transfer {local_file}")
            
            return {
                "success": True,
                "message": f"Transferred {files_transferred} files",
                "bytes_transferred": total_size,
                "remote_path": remote_path,
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _update_database_after_push(self, game: Game, system: PS5System, 
                                     remote_path: str, storage: str) -> None:
        """Update database after successful push."""
        db = get_db_session()
        try:
            # Check if location already exists
            location = db.query(GameLocation).filter_by(
                game_id=game.id,
                ps5_system_id=system.id,
                ps5_path=remote_path
            ).first()
            
            if not location:
                storage_enum = PS5StorageLocation(storage) if storage in [s.value for s in PS5StorageLocation] else PS5StorageLocation.PRIMARY_SSD
                
                location = GameLocation(
                    game_id=game.id,
                    ps5_system_id=system.id,
                    ps5_path=remote_path,
                    ps5_storage=storage_enum,
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
            game.is_on_any_ps5 = True
            game.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Database updated for game {game.name} on {system.name}")
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating database: {e}")
        finally:
            db.close()
    
    def get_available_space(self, system: PS5System, storage: str) -> Dict[str, Any]:
        """Get available space on PS5 storage."""
        # This would require executing a command on PS5 via FTP or payload
        # For now, return mock data
        return {
            "total_bytes": 0,
            "free_bytes": 0,
            "used_bytes": 0,
        }
    
    def list_server_games(self) -> List[Dict[str, Any]]:
        """List games available on server for pushing."""
        db = get_db_session()
        try:
            # Find games with server locations
            games = db.query(Game).join(GameLocation).filter(
                GameLocation.server_path.isnot(None),
                GameLocation.ps5_system_id.is_(None)
            ).all()
            
            return [
                {
                    "id": g.id,
                    "name": g.name,
                    "ppsa": g.ppsa,
                    "title_id": g.title_id,
                    "format": g.format.value if g.format else None,
                    "size_bytes": g.size_bytes,
                    "server_path": next((loc.server_path for loc in g.locations if loc.server_path), None),
                }
                for g in games
            ]
        finally:
            db.close()