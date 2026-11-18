"""Module 11: Retrieve game info from internet APIs (IGDB, RAWG, PSN, ProsperoPatches, HowLongToBeat)."""
import os
import logging
import requests
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import Game
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class InfoModule(BaseModule):
    """Info Module for fetching game metadata from external APIs."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PS5-Management-Server/1.0'
        })
        self._igdb_token = None
        self._igdb_token_expiry = 0
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="info_module",
            version="1.0.0",
            description="Retrieve game info from IGDB, RAWG, PSN, ProsperoPatches, HowLongToBeat",
            dependencies=[],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Info Module")
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        self.session.close()
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "igdb_configured": bool(settings.IGDB_CLIENT_ID and settings.IGDB_CLIENT_SECRET),
            "rawg_configured": bool(settings.RAWG_API_KEY),
        }
    
    def fetch(self, game: Game) -> Dict[str, Any]:
        """Fetch game info from all available sources."""
        results = {
            "igdb": None,
            "rawg": None,
            "psn": None,
            "prospero": None,
            "hltb": None,
            "errors": [],
        }
        
        # Try multiple sources
        sources = [
            self._fetch_from_igdb,
            self._fetch_from_rawg,
            self._fetch_from_psn,
            self._fetch_from_prospero,
            self._fetch_from_howlongtobeat,
        ]
        
        for source_func in sources:
            try:
                source_result = source_func(game)
                if source_result:
                    results.update(source_result)
            except Exception as e:
                results["errors"].append(f"{source_func.__name__}: {str(e)}")
        
        # Update database
        self._update_database(game, results)
        
        success = any(v for k, v in results.items() if k != "errors" and v is not None)
        return {
            "success": success,
            "results": results,
        }
    
    def _get_igdb_token(self) -> Optional[str]:
        """Get IGDB OAuth token."""
        if not settings.IGDB_CLIENT_ID or not settings.IGDB_CLIENT_SECRET:
            return None
        
        now = time.time()
        if self._igdb_token and now < self._igdb_token_expiry:
            return self._igdb_token
        
        try:
            token_url = "https://id.twitch.tv/oauth2/token"
            params = {
                "client_id": settings.IGDB_CLIENT_ID,
                "client_secret": settings.IGDB_CLIENT_SECRET,
                "grant_type": "client_credentials",
            }
            response = self.session.post(token_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self._igdb_token = data["access_token"]
                self._igdb_token_expiry = now + data.get("expires_in", 3600) - 60
                return self._igdb_token
        except Exception as e:
            logger.debug(f"IGDB token error: {e}")
        
        return None
    
    def _fetch_from_igdb(self, game: Game) -> Optional[Dict[str, Any]]:
        """Fetch game info from IGDB."""
        token = self._get_igdb_token()
        if not token:
            return None
        
        try:
            # Search by name
            query = f'fields name,genres.name,platforms.name,release_dates,cover.url,screenshots.url; search "{game.name}"; where version_parent = null; limit 1;'
            
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
                    
                    result = {
                        "igdb": {
                            "igdb_id": game_data.get("id"),
                            "name": game_data.get("name"),
                            "genres": [g.get("name") for g in game_data.get("genres", [])],
                            "platforms": [p.get("name") for p in game_data.get("platforms", [])],
                        }
                    }
                    
                    # Handle cover URL
                    cover = game_data.get("cover")
                    if cover:
                        cover_url = f"https:{cover.get('url', '')}".replace('t_thumb', 't_cover_big')
                        result["igdb"]["cover_url"] = cover_url
                        result["cover_url"] = cover_url
                    
                    # Handle release date
                    rd = game_data.get("release_dates")
                    if rd:
                        result["igdb"]["release_date"] = rd[0].get("human") if rd else None
                    
                    return result
        except Exception as e:
            logger.debug(f"IGDB fetch error: {e}")
        
        return None
    
    def _fetch_from_rawg(self, game: Game) -> Optional[Dict[str, Any]]:
        """Fetch game info from RAWG."""
        if not settings.RAWG_API_KEY:
            return None
        
        try:
            url = "https://api.rawg.io/api/games"
            params = {
                "key": settings.RAWG_API_KEY,
                "search": game.name,
                "page_size": 1,
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    game_data = results[0]
                    
                    result = {
                        "rawg": {
                            "rawg_id": game_data.get("id"),
                            "name": game_data.get("name"),
                            "rating": game_data.get("rating"),
                            "metacritic": game_data.get("metacritic"),
                            "released": game_data.get("released"),
                        }
                    }
                    
                    # Background image
                    bg = game_data.get("background_image")
                    if bg:
                        result["rawg"]["background_url"] = bg
                        result["background_url"] = bg
                    
                    # Genres
                    genres = [g.get("name") for g in game_data.get("genres", [])]
                    if genres:
                        result["rawg"]["genres"] = genres
                    
                    return result
        except Exception as e:
            logger.debug(f"RAWG fetch error: {e}")
        
        return None
    
    def _fetch_from_psn(self, game: Game) -> Optional[Dict[str, Any]]:
        """Fetch game info from PSN (psnawp)."""
        try:
            # Try PSN store search
            # This would need proper psnawp integration with NPSSO
            # For now, try public PSN store API
            
            url = "https://store.playstation.com/en-us/grid/SIZE-30/NSID-0/"
            # Simplified - would need proper PSN API integration
            return None
        except Exception as e:
            logger.debug(f"PSN fetch error: {e}")
        
        return None
    
    def _fetch_from_prospero(self, game: Game) -> Optional[Dict[str, Any]]:
        """Fetch game info from ProsperoPatches via web scraping."""
        try:
            # Search by title ID or PPSA
            query = game.title_id or game.ppsa or game.name
            url = "https://prosperopatches.com/api/internal"
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
                        return {
                            "prospero": {
                                "prospero_id": result_data.get("id"),
                                "name": result_data.get("title"),
                                "description": result_data.get("description", ""),
                            },
                            "description": result_data.get("description", ""),
                        }
                except Exception:
                    pass
            
            # Fallback: try GET search
            url = f"https://prosperopatches.com/search?q={query}"
            response = self.session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if response.status_code == 200:
                # Basic HTML parsing for title match
                import re
                title_match = re.search(r'<title>([^<]+)</title>', response.text)
                if title_match:
                    return {
                        "prospero": {
                            "prospero_id": query,
                            "name": title_match.group(1).strip(),
                        },
                        "name": title_match.group(1).strip(),
                    }
        except Exception as e:
            logger.debug(f"Prospero fetch error: {e}")
        
        return None
    
    def _fetch_from_howlongtobeat(self, game: Game) -> Optional[Dict[str, Any]]:
        """Fetch playtime from HowLongToBeat."""
        try:
            # Use community HLTB API
            url = "https://howlongtobeat.com/api/search"
            params = {
                "q": game.name,
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if results:
                    game_data = results[0]
                    
                    result = {
                        "hltb": {
                            "main_story": game_data.get("gameplayMain", 0),
                            "main_extra": game_data.get("gameplayMainExtra", 0),
                            "completionist": game_data.get("gameplayCompletionist", 0),
                        }
                    }
                    
                    return result
        except Exception as e:
            logger.debug(f"HLTB fetch error: {e}")
        
        return None
    
    def _update_database(self, game: Game, results: Dict[str, Any]) -> None:
        """Update game with fetched info."""
        db = get_db_session()
        try:
            game = db.query(Game).get(game.id)
            if not game:
                return
            
            # Update IGDB info
            igdb_data = results.get("igdb")
            if igdb_data:
                game.igdb_id = igdb_data.get("igdb_id")
                if igdb_data.get("cover_url"):
                    game.cover_url = igdb_data["cover_url"]
                if igdb_data.get("genres"):
                    game.genres = igdb_data["genres"]
            
            # Update RAWG info
            rawg_data = results.get("rawg")
            if rawg_data:
                game.rawg_id = rawg_data.get("rawg_id")
                game.metacritic_score = rawg_data.get("metacritic")
                if rawg_data.get("background_url"):
                    game.background_url = rawg_data["background_url"]
                if rawg_data.get("genres"):
                    game.genres = rawg_data["genres"]
                if rawg_data.get("released"):
                    try:
                        game.release_date = datetime.strptime(rawg_data["released"], "%Y-%m-%d")
                    except:
                        pass
            
            # Update HLTB info
            hltb_data = results.get("hltb")
            if hltb_data:
                game.hltb_main_story = hltb_data.get("main_story")
                game.hltb_main_extra = hltb_data.get("main_extra")
                game.hltb_completionist = hltb_data.get("completionist")
            
            # Update prospero info
            prospero_data = results.get("prospero")
            if prospero_data:
                game.prospero_id = str(prospero_data.get("prospero_id"))
            
            game.updated_at = datetime.utcnow()
            db.commit()
        
        finally:
            db.close()
    
    def search_game(self, query: str) -> List[Dict[str, Any]]:
        """Search for a game across all sources."""
        results = []
        
        # Search IGDB
        try:
            token = self._get_igdb_token()
            if token:
                q = f'fields name; search "{query}"; limit 10;'
                headers = {
                    "Client-ID": settings.IGDB_CLIENT_ID,
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                response = self.session.post("https://api.igdb.com/v4/games", data=q, headers=headers, timeout=10)
                if response.status_code == 200:
                    for g in response.json():
                        results.append({"source": "igdb", "id": g.get("id"), "name": g.get("name")})
        except Exception as e:
            logger.debug(f"IGDB search error: {e}")
        
        # Search RAWG
        if settings.RAWG_API_KEY:
            try:
                url = "https://api.rawg.io/api/games"
                params = {"key": settings.RAWG_API_KEY, "search": query, "page_size": 10}
                response = self.session.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    for g in response.json().get("results", []):
                        results.append({"source": "rawg", "id": g.get("id"), "name": g.get("name")})
            except Exception as e:
                logger.debug(f"RAWG search error: {e}")
        
        return results