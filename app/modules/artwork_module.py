"""Module 7: Download artwork from web stores."""
import os
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import Game
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class ArtworkModule(BaseModule):
    """Artwork Module for downloading game artwork from various sources."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PS5-Management-Server/1.0'
        })
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="artwork_module",
            version="1.0.0",
            description="Download game artwork (covers, backgrounds, icons) from web stores and APIs",
            dependencies=[],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Artwork Module")
        # Ensure artwork directory exists
        Path(settings.SERVER_ARTWORK_PATH).mkdir(parents=True, exist_ok=True)
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        self.session.close()
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "artwork_path": settings.SERVER_ARTWORK_PATH,
        }
    
    def download(self, game: Game) -> Dict[str, Any]:
        """Download artwork for a game from various sources."""
        try:
            logger.info(f"Downloading artwork for {game.name}")
            
            results = {
                "cover": False,
                "background": False,
                "icon": False,
                "errors": [],
            }
            
            # Try multiple sources in order of preference
            sources = [
                self._download_from_igdb,
                self._download_from_rawg,
                self._download_from_psn,
                self._download_from_prospero,
            ]
            
            for source_func in sources:
                try:
                    source_results = source_func(game)
                    for key in ["cover", "background", "icon"]:
                        if source_results.get(key) and not results[key]:
                            results[key] = True
                except Exception as e:
                    results["errors"].append(f"{source_func.__name__}: {str(e)}")
            
            # Update database with local paths
            self._update_database(game, results)
            
            success = any([results["cover"], results["background"], results["icon"]])
            return {
                "success": success,
                "message": f"Artwork download {'completed' if success else 'failed'}",
                "results": results,
            }
        
        except Exception as e:
            logger.error(f"Error downloading artwork: {e}")
            return {"success": False, "error": str(e)}
    
    def _download_from_igdb(self, game: Game) -> Dict[str, bool]:
        """Download artwork from IGDB (scrape public data)."""
        results = {"cover": False, "background": False, "icon": False}
        
        if not settings.IGDB_CLIENT_ID or not settings.IGDB_CLIENT_SECRET:
            return results
        
        # Use IGDB API if keys are configured
        try:
            from app.modules.info_module import InfoModule
            info_module = InfoModule()
            token = info_module._get_igdb_token()
            if token:
                query = f'fields cover.url,screenshots.url; search "{game.name}"; limit 1;'
                headers = {
                    "Client-ID": settings.IGDB_CLIENT_ID,
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                response = self.session.post(
                    "https://api.igdb.com/v4/games",
                    data=query,
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        game_data = data[0]
                        
                        # Cover
                        cover = game_data.get("cover")
                        if cover:
                            cover_url = f"https:{cover.get('url', '')}".replace('t_thumb', 't_cover_big')
                            if self._save_image(cover_url, game, "cover"):
                                results["cover"] = True
                                game.cover_url = cover_url
                        
                        # Background (screenshot)
                        screenshots = game_data.get("screenshots", [])
                        if screenshots:
                            bg_url = f"https:{screenshots[0].get('url', '')}".replace('t_thumb', 't_1080p')
                            if self._save_image(bg_url, game, "background"):
                                results["background"] = True
                                game.background_url = bg_url
        except Exception as e:
            logger.debug(f"IGDB artwork download failed: {e}")
        
        return results
    
    def _download_from_rawg(self, game: Game) -> Dict[str, bool]:
        """Download artwork from RAWG."""
        results = {"cover": False, "background": False, "icon": False}
        
        if not settings.RAWG_API_KEY:
            return results
        
        try:
            url = "https://api.rawg.io/api/games"
            params = {"key": settings.RAWG_API_KEY, "search": game.name, "page_size": 1}
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results_list = data.get("results", [])
                
                if results_list:
                    game_data = results_list[0]
                    
                    # Background image (RAWG provides high-res backgrounds)
                    bg = game_data.get("background_image")
                    if bg:
                        if self._save_image(bg, game, "background"):
                            results["background"] = True
                            game.background_url = bg
                    
                    # Cover image
                    cover = game_data.get("background_image_additional")
                    if cover:
                        if self._save_image(cover, game, "cover"):
                            results["cover"] = True
                            game.cover_url = cover
        except Exception as e:
            logger.debug(f"RAWG artwork download failed: {e}")
        
        return results
    
    def _download_from_psn(self, game: Game) -> Dict[str, bool]:
        """Download artwork from PSN Store (scrape public pages)."""
        results = {"cover": False, "background": False, "icon": False}
        
        # Try to find game on PSN store
        try:
            # Use PSN store search
            search_query = game.title_id or game.name
            url = f"https://store.playstation.com/en-us/search/{search_query}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                import re
                # Try to extract image URLs from HTML
                # PSN store has JSON data embedded
                json_matches = re.findall(r'"imageUrl":"([^"]+)"', response.text)
                for img_url in json_matches[:3]:
                    if "icon" in img_url.lower() and not results["icon"]:
                        if self._save_image(img_url, game, "icon"):
                            results["icon"] = True
                    elif "cover" in img_url.lower() and not results["cover"]:
                        if self._save_image(img_url, game, "cover"):
                            results["cover"] = True
                    elif ("background" in img_url.lower() or "banner" in img_url.lower()) and not results["background"]:
                        if self._save_image(img_url, game, "background"):
                            results["background"] = True
        except Exception as e:
            logger.debug(f"PSN artwork download failed: {e}")
        
        return results
    
    def _download_from_prospero(self, game: Game) -> Dict[str, bool]:
        """Download artwork from ProsperoPatches via web scraping."""
        results = {"cover": False, "background": False, "icon": False}
        
        if not game.prospero_id and not game.ppsa and not game.title_id:
            return results
        
        # Try to download from prosperopatches.com
        try:
            query = game.prospero_id or game.ppsa or game.title_id
            url = f"https://prosperopatches.com/api/internal"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = f"action=search&query={query}"
            response = self.session.post(url, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("results"):
                        result_data = data["results"][0]
                        # Try to get cover image
                        if result_data.get("cover_url"):
                            if self._save_image(result_data["cover_url"], game, "cover"):
                                results["cover"] = True
                                game.cover_url = result_data["cover_url"]
                        if result_data.get("background_url"):
                            if self._save_image(result_data["background_url"], game, "background"):
                                results["background"] = True
                                game.background_url = result_data["background_url"]
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Prospero artwork download failed: {e}")
        
        return results
    
    def _save_image(self, url: str, game: Game, image_type: str) -> Optional[str]:
        """Download and save an image."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get('Content-Type', '')
            ext = '.jpg'
            if 'png' in content_type:
                ext = '.png'
            elif 'webp' in content_type:
                ext = '.webp'
            
            # Create filename
            safe_name = "".join(c for c in game.name if c.isalnum() or c in "._- ")
            filename = f"{safe_name}_{image_type}{ext}"
            filepath = os.path.join(settings.SERVER_ARTWORK_PATH, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Saved {image_type} for {game.name} to {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error saving {image_type} for {game.name}: {e}")
            return None
    
    def _update_database(self, game: Game, results: Dict[str, Any]) -> None:
        """Update game with local artwork paths."""
        db = get_db_session()
        try:
            game = db.query(Game).get(game.id)
            if not game:
                return
            
            safe_name = "".join(c for c in game.name if c.isalnum() or c in "._- ")
            
            if results.get("cover"):
                path = os.path.join(settings.SERVER_ARTWORK_PATH, f"{safe_name}_cover.jpg")
                if os.path.exists(path):
                    game.local_cover_path = path
            
            if results.get("background"):
                path = os.path.join(settings.SERVER_ARTWORK_PATH, f"{safe_name}_background.jpg")
                if os.path.exists(path):
                    game.local_background_path = path
            
            if results.get("icon"):
                path = os.path.join(settings.SERVER_ARTWORK_PATH, f"{safe_name}_icon.png")
                if os.path.exists(path):
                    game.local_icon_path = path
            
            game.updated_at = datetime.utcnow()
            db.commit()
        
        finally:
            db.close()
    
    def download_all_missing(self) -> Dict[str, Any]:
        """Download artwork for all games missing artwork."""
        db = get_db_session()
        try:
            games = db.query(Game).filter(
                (Game.local_cover_path.is_(None)) |
                (Game.local_background_path.is_(None))
            ).all()
            
            results = {
                "total": len(games),
                "success": 0,
                "failed": 0,
            }
            
            for game in games:
                result = self.download(game)
                if result.get("success"):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            
            return results
        
        finally:
            db.close()
    
    def get_artwork_status(self, game: Game) -> Dict[str, Any]:
        """Get artwork status for a game."""
        return {
            "cover": {
                "url": game.cover_url,
                "local_path": game.local_cover_path,
                "exists": bool(game.local_cover_path and os.path.exists(game.local_cover_path)),
            },
            "background": {
                "url": game.background_url,
                "local_path": game.local_background_path,
                "exists": bool(game.local_background_path and os.path.exists(game.local_background_path)),
            },
            "icon": {
                "url": game.icon_url,
                "local_path": game.local_icon_path,
                "exists": bool(game.local_icon_path and os.path.exists(game.local_icon_path)),
            },
        }