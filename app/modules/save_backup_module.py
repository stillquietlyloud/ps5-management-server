"""Module 4: Save game backups from PS5 to server."""
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.modules.ftp_module import FTPModule
from app.models import PS5System, Game, SaveGame
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class SaveBackupModule(BaseModule):
    """Save Backup Module for backing up save games from PS5 to server."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ftp_module = FTPModule()
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="save_backup_module",
            version="1.0.0",
            description="Backup save games from PS5 to server storage",
            dependencies=["ftp_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Save Backup Module")
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
    
    def backup(self, system: PS5System, game: Game, user_id: str = "default") -> Dict[str, Any]:
        """Backup save games for a specific game from PS5 to server."""
        try:
            logger.info(f"Backing up saves for {game.name} from {system.name}")
            
            # PS5 save game locations
            save_paths = self._get_save_paths(game)
            
            if not save_paths:
                return {"success": False, "error": "No save paths found for this game"}
            
            # Connect to PS5
            conn_result = self.ftp_module.connect(system)
            if not conn_result.get("success"):
                return conn_result
            
            try:
                backed_up_saves = []
                
                for save_path in save_paths:
                    # List save files in this path
                    saves = self._list_saves_in_path(save_path, user_id)
                    
                    for save_info in saves:
                        result = self._backup_single_save(
                            system, game, save_info, user_id
                        )
                        if result.get("success"):
                            backed_up_saves.append(result)
                
                return {
                    "success": True,
                    "message": f"Backed up {len(backed_up_saves)} save files",
                    "saves": backed_up_saves,
                }
            
            finally:
                self.ftp_module.disconnect()
        
        except Exception as e:
            logger.error(f"Error backing up saves: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_save_paths(self, game: Game) -> List[str]:
        """Get possible save game paths for a game."""
        # PS5 save games are typically in:
        # /user/home/<user_id>/savedata/<title_id>/
        # We need to find the title_id
        if not game.title_id:
            return []
        
        return [
            f"/user/home/*/savedata/{game.title_id}",
            f"/data/savedata/{game.title_id}",
            f"/mnt/usb*/savedata/{game.title_id}",
        ]
    
    def _list_saves_in_path(self, path: str, user_id: str) -> List[Dict[str, Any]]:
        """List save files in a path."""
        saves = []
        
        try:
            # Handle wildcard in path
            if '*' in path:
                # Need to expand wildcard
                # For simplicity, try common paths
                expanded_paths = self._expand_wildcard_path(path)
                for expanded in expanded_paths:
                    saves.extend(self._list_saves_in_path(expanded, user_id))
                return saves
            
            self.ftp_module._connection.cwd(path)
            files = []
            self.ftp_module._connection.retrlines('LIST', files.append)
            
            for line in files:
                parts = line.split()
                if len(parts) < 9:
                    continue
                permissions = parts[0]
                name = ' '.join(parts[8:])
                
                if name in ['.', '..']:
                    continue
                
                full_path = f"{path}/{name}"
                
                if not permissions.startswith('d'):
                    # It's a file
                    try:
                        size = self.ftp_module._connection.size(full_path)
                    except Exception:
                        size = 0
                    
                    saves.append({
                        "name": name,
                        "path": full_path,
                        "size": size,
                    })
        
        except Exception as e:
            logger.debug(f"Could not list saves in {path}: {e}")
        
        return saves
    
    def _expand_wildcard_path(self, path: str) -> List[str]:
        """Expand wildcard paths."""
        # Simplified - would need proper FTP directory traversal
        if '/user/home/*' in path:
            try:
                self.ftp_module._connection.cwd('/user/home')
                files = []
                self.ftp_module._connection.retrlines('LIST', files.append)
                
                expanded = []
                for line in files:
                    parts = line.split()
                    if len(parts) < 9:
                        continue
                    name = ' '.join(parts[8:])
                    if name not in ['.', '..'] and line.startswith('d'):
                        expanded.append(path.replace('*', name))
                return expanded
            except Exception:
                pass
        return []
    
    def _backup_single_save(self, system: PS5System, game: Game, 
                           save_info: Dict, user_id: str) -> Dict[str, Any]:
        """Backup a single save file."""
        try:
            remote_path = save_info["path"]
            save_name = save_info["name"]
            
            # Create local path
            local_dir = os.path.join(settings.SERVER_SAVES_PATH, game.title_id or game.ppsa or game.name)
            local_dir = os.path.join(local_dir, user_id)
            os.makedirs(local_dir, exist_ok=True)
            
            local_path = os.path.join(local_dir, save_name)
            
            logger.info(f"Backing up save {save_name} from {remote_path}")
            
            success = self.ftp_module.download_file(remote_path, local_path)
            
            if success:
                size = os.path.getsize(local_path)
                
                # Save to database
                self._save_to_database(game, system, user_id, save_name, local_path, remote_path, size)
                
                return {
                    "success": True,
                    "save_name": save_name,
                    "local_path": local_path,
                    "size_bytes": size,
                }
            else:
                return {"success": False, "error": "Download failed", "save_name": save_name}
        
        except Exception as e:
            return {"success": False, "error": str(e), "save_name": save_info.get("name")}
    
    def _save_to_database(self, game: Game, system: PS5System, user_id: str,
                         save_name: str, local_path: str, remote_path: str, size: int):
        """Save backup info to database."""
        db = get_db_session()
        try:
            save_game = SaveGame(
                game_id=game.id,
                ps5_system_id=system.id,
                user_id=user_id,
                save_name=save_name,
                server_path=local_path,
                ps5_path=remote_path,
                size_bytes=size,
                backed_up_at=datetime.utcnow(),
            )
            db.add(save_game)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving to database: {e}")
        finally:
            db.close()
    
    def backup_all_games(self, system: PS5System) -> Dict[str, Any]:
        """Backup saves for all games on a PS5."""
        db = get_db_session()
        try:
            # Get all games on this PS5
            locations = db.query(GameLocation).filter_by(
                ps5_system_id=system.id,
                is_installed=True
            ).all()
            
            results = []
            for loc in locations:
                game = db.query(Game).get(loc.game_id)
                if game:
                    result = self.backup(system, game)
                    results.append({
                        "game": game.name,
                        "result": result,
                    })
            
            return {
                "success": True,
                "games_processed": len(results),
                "results": results,
            }
        finally:
            db.close()
    
    def list_backups(self, game: Game = None, system: PS5System = None) -> List[Dict[str, Any]]:
        """List available save backups."""
        db = get_db_session()
        try:
            query = db.query(SaveGame)
            
            if game:
                query = query.filter_by(game_id=game.id)
            if system:
                query = query.filter_by(ps5_system_id=system.id)
            
            saves = query.all()
            
            return [
                {
                    "id": s.id,
                    "game_id": s.game_id,
                    "game_name": db.query(Game).get(s.game_id).name if s.game_id else "Unknown",
                    "save_name": s.save_name,
                    "server_path": s.server_path,
                    "size_bytes": s.size_bytes,
                    "game_progress": s.game_progress,
                    "backed_up_at": s.backed_up_at.isoformat() if s.backed_up_at else None,
                }
                for s in saves
            ]
        finally:
            db.close()