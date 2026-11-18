"""Module 5: Restore save games from server to PS5."""
import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.modules.ftp_module import FTPModule
from app.models import PS5System, Game, SaveGame
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class SaveRestoreModule(BaseModule):
    """Save Restore Module for restoring save games from server to PS5."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ftp_module = FTPModule()
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="save_restore_module",
            version="1.0.0",
            description="Restore save game backups from server to PS5",
            dependencies=["ftp_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Save Restore Module")
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
    
    def restore(self, system: PS5System, save: SaveGame, overwrite: bool = True) -> Dict[str, Any]:
        """Restore a specific save game to PS5."""
        try:
            logger.info(f"Restoring save {save.save_name} to {system.name}")
            
            # Check local file exists
            if not os.path.exists(save.server_path):
                return {"success": False, "error": f"Local save file not found: {save.server_path}"}
            
            # Connect to PS5
            conn_result = self.ftp_module.connect(system)
            if not conn_result.get("success"):
                return conn_result
            
            try:
                # Determine target path on PS5
                target_path = save.ps5_path
                
                # Ensure target directory exists
                self._ensure_remote_dir(os.path.dirname(target_path))
                
                # Check if file exists on PS5
                if not overwrite:
                    try:
                        self.ftp_module._connection.size(target_path)
                        return {"success": False, "error": "Save already exists on PS5 (use overwrite=True)"}
                    except Exception:
                        pass  # File doesn't exist, continue
                
                # Upload save file
                success = self.ftp_module.upload_file(save.server_path, target_path)
                
                if success:
                    # Update database
                    db = get_db_session()
                    try:
                        save.updated_at = datetime.utcnow()
                        db.commit()
                    finally:
                        db.close()
                    
                    return {
                        "success": True,
                        "message": f"Restored {save.save_name}",
                        "remote_path": target_path,
                    }
                else:
                    return {"success": False, "error": "Upload failed"}
            
            finally:
                self.ftp_module.disconnect()
        
        except Exception as e:
            logger.error(f"Error restoring save: {e}")
            return {"success": False, "error": str(e)}
    
    def restore_all_for_game(self, system: PS5System, game: Game, 
                            user_id: str = "default", overwrite: bool = True) -> Dict[str, Any]:
        """Restore all saves for a game to PS5."""
        db = get_db_session()
        try:
            saves = db.query(SaveGame).filter_by(
                game_id=game.id,
                ps5_system_id=system.id,
                user_id=user_id
            ).all()
            
            if not saves:
                return {"success": False, "error": "No backups found for this game"}
            
            results = []
            for save in saves:
                result = self.restore(system, save, overwrite)
                results.append({
                    "save_name": save.save_name,
                    "result": result,
                })
            
            successful = sum(1 for r in results if r["result"].get("success"))
            
            return {
                "success": True,
                "message": f"Restored {successful}/{len(results)} saves",
                "results": results,
            }
        finally:
            db.close()
    
    def _ensure_remote_dir(self, path: str) -> bool:
        """Ensure remote directory exists."""
        try:
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
    
    def list_restorable_saves(self, system: PS5System, game: Game = None) -> List[Dict[str, Any]]:
        """List saves that can be restored to a PS5."""
        db = get_db_session()
        try:
            query = db.query(SaveGame).filter_by(ps5_system_id=system.id)
            
            if game:
                query = query.filter_by(game_id=game.id)
            
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
                    "local_exists": os.path.exists(s.server_path),
                }
                for s in saves
            ]
        finally:
            db.close()