"""Module 9: Manage downloads from web stores."""
import os
import logging
import threading
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import Game, DownloadTask, TorrentClient, GameSource, TaskStatus, StoreGameEntry
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class DownloadModule(BaseModule):
    """Download Module for managing game downloads from various sources."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.active_downloads: Dict[int, threading.Thread] = {}
        self.stop_flags: Dict[int, bool] = {}
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="download_module",
            version="1.0.0",
            description="Manage downloads from web stores (torrent, direct, magnet links)",
            dependencies=["store_db_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Download Module")
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        # Stop all active downloads
        for task_id in list(self.stop_flags.keys()):
            self.stop_download(task_id)
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "active_downloads": len(self.active_downloads),
        }
    
    def start(self, game: Game, source: str = None) -> Dict[str, Any]:
        """Start a download for a game."""
        try:
            logger.info(f"Starting download for {game.name}")
            
            # Get download info from store database
            db = get_db_session()
            try:
                # Find store entry
                if source:
                    store_source = GameSource(source)
                    entry = db.query(StoreGameEntry).filter_by(
                        store_source=store_source,
                        ppsa=game.ppsa
                    ).first()
                else:
                    # Use first available source
                    entry = db.query(StoreGameEntry).filter_by(
                        ppsa=game.ppsa
                    ).first()
                
                if not entry:
                    return {"success": False, "error": "No download source found for this game"}
                
                # Create download task
                task = DownloadTask(
                    game_id=game.id,
                    source=entry.store_source,
                    torrent_hash=entry.torrent_hash,
                    magnet_link=entry.magnet_link,
                    download_url=entry.download_url,
                    save_path=os.path.join(settings.SERVER_DOWNLOADS_PATH, game.ppsa or game.title_id or game.name),
                    status=TaskStatus.PENDING,
                )
                db.add(task)
                db.commit()
                task_id = task.id
            finally:
                db.close()
            
            # Start download in background thread
            thread = threading.Thread(target=self._run_download, args=(task_id, entry))
            thread.daemon = True
            thread.start()
            
            self.active_downloads[task_id] = thread
            self.stop_flags[task_id] = False
            
            return {
                "success": True,
                "task_id": task_id,
                "message": "Download started",
            }
        
        except Exception as e:
            logger.error(f"Error starting download: {e}")
            return {"success": False, "error": str(e)}
    
    def _run_download(self, task_id: int, entry: StoreGameEntry) -> None:
        """Run download in background thread."""
        db = get_db_session()
        try:
            task = db.query(DownloadTask).get(task_id)
            if not task:
                return
            
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            db.commit()
            
            # Determine download method
            if entry.magnet_link:
                self._download_magnet(task, entry.magnet_link, db)
            elif entry.torrent_hash:
                self._download_torrent_hash(task, entry.torrent_hash, db)
            elif entry.download_url:
                self._download_direct(task, entry.download_url, db)
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "No download method available"
                db.commit()
                return
            
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                task.progress = 100
                db.commit()
                
                # Update game availability
                game = db.query(Game).get(task.game_id)
                if game:
                    game.is_on_server = True
                    game.updated_at = datetime.utcnow()
                    db.commit()
        
        except Exception as e:
            logger.error(f"Download error: {e}")
            if 'task' in locals():
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                db.commit()
        finally:
            self.active_downloads.pop(task_id, None)
            self.stop_flags.pop(task_id, None)
            db.close()
    
    def _download_magnet(self, task: DownloadTask, magnet_link: str, db) -> None:
        """Download via magnet link using torrent client."""
        # This would integrate with qBittorrent or Transmission
        # For now, simulate
        task.status = TaskStatus.RUNNING
        task.progress = 0
        db.commit()
        
        # Simulate progress
        for i in range(0, 101, 10):
            if self.stop_flags.get(task.id):
                task.status = TaskStatus.CANCELLED
                db.commit()
                return
            task.progress = i
            task.downloaded_bytes = int(task.total_bytes * i / 100) if task.total_bytes else 0
            db.commit()
            time.sleep(1)
    
    def _download_torrent_hash(self, task: DownloadTask, torrent_hash: str, db) -> None:
        """Download via torrent hash."""
        # Similar to magnet
        self._download_magnet(task, f"magnet:?xt=urn:btih:{torrent_hash}", db)
    
    def _download_direct(self, task: DownloadTask, url: str, db) -> None:
        """Download via direct HTTP link."""
        import requests
        
        try:
            task.status = TaskStatus.RUNNING
            db.commit()
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            task.total_bytes = total_size
            
            os.makedirs(task.save_path, exist_ok=True)
            filename = url.split('/')[-1] or "download.bin"
            filepath = os.path.join(task.save_path, filename)
            
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.stop_flags.get(task.id):
                        task.status = TaskStatus.CANCELLED
                        db.commit()
                        return
                    
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        task.downloaded_bytes = downloaded
                        if total_size > 0:
                            task.progress = int(downloaded * 100 / total_size)
                        db.commit()
        
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
            raise
    
    def stop_download(self, task_id: int) -> Dict[str, Any]:
        """Stop a running download."""
        if task_id in self.stop_flags:
            self.stop_flags[task_id] = True
            
            # Update database
            db = get_db_session()
            try:
                task = db.query(DownloadTask).get(task_id)
                if task and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.CANCELLED
                    db.commit()
            finally:
                db.close()
            
            return {"success": True, "message": "Download stop requested"}
        
        return {"success": False, "error": "Download not found or not running"}
    
    def get_download_status(self, task_id: int) -> Dict[str, Any]:
        """Get download status."""
        db = get_db_session()
        try:
            task = db.query(DownloadTask).get(task_id)
            if not task:
                return {"error": "Task not found"}
            
            return {
                "id": task.id,
                "game_id": task.game_id,
                "status": task.status.value,
                "progress": task.progress,
                "downloaded_bytes": task.downloaded_bytes,
                "total_bytes": task.total_bytes,
                "download_speed": task.download_speed,
                "eta_seconds": task.eta_seconds,
                "error_message": task.error_message,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
        finally:
            db.close()
    
    def list_downloads(self, status: str = None) -> List[Dict[str, Any]]:
        """List all downloads."""
        db = get_db_session()
        try:
            q = db.query(DownloadTask)
            
            if status:
                q = q.filter_by(status=TaskStatus(status))
            
            tasks = q.order_by(DownloadTask.created_at.desc()).limit(50).all()
            
            return [
                {
                    "id": t.id,
                    "game_id": t.game_id,
                    "source": t.source.value,
                    "status": t.status.value,
                    "progress": t.progress,
                    "downloaded_bytes": t.downloaded_bytes,
                    "total_bytes": t.total_bytes,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tasks
            ]
        finally:
            db.close()
    
    def retry_failed(self, task_id: int) -> Dict[str, Any]:
        """Retry a failed download."""
        db = get_db_session()
        try:
            task = db.query(DownloadTask).get(task_id)
            if not task:
                return {"success": False, "error": "Task not found"}
            
            if task.status != TaskStatus.FAILED:
                return {"success": False, "error": "Task is not in failed state"}
            
            # Reset task
            task.status = TaskStatus.PENDING
            task.progress = 0
            task.downloaded_bytes = 0
            task.error_message = None
            db.commit()
            
            # Get store entry again
            entry = db.query(StoreGameEntry).filter_by(
                store_source=task.source,
                ppsa=db.query(Game).get(task.game_id).ppsa
            ).first()
            
            if not entry:
                return {"success": False, "error": "Source no longer available"}
            
            # Restart download
            return self.start(db.query(Game).get(task.game_id), task.source.value)
        
        finally:
            db.close()