"""Module 8: Update local database with web store sources (orbit-store-ps5, blackbox, over-drive)."""
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import Game, StoreGameEntry, GameSource, GameFormat
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class StoreDBModule(BaseModule):
    """Store Database Module for syncing game data from web stores."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PS5-Management-Server/1.0'
        })
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="store_db_module",
            version="1.0.0",
            description="Update local database with game sources from Orbit Store, BlackBox, Overdrive",
            dependencies=[],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Store DB Module")
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        self.session.close()
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
        }
    
    def update(self, source: str = "all") -> Dict[str, Any]:
        """Update store database from specified source(s)."""
        results = {}
        
        if source in ["all", "orbit"]:
            results["orbit"] = self._update_from_orbit()
        
        if source in ["all", "blackbox"]:
            results["blackbox"] = self._update_from_blackbox()
        
        if source in ["all", "overdrive"]:
            results["overdrive"] = self._update_from_overdrive()
        
        return {
            "success": True,
            "results": results,
        }
    
    def _update_from_orbit(self) -> Dict[str, Any]:
        """Update from Orbit Store (orbit-store-ps5 / orbit-play-ps5)."""
        try:
            logger.info("Updating from Orbit Store...")
            
            # Orbit Store's catalogue is in orbit-play-ps5 repo
            catalogue_url = "https://raw.githubusercontent.com/saawant12/orbit-play-ps5/main/catalogue.json"
            
            response = self.session.get(catalogue_url, timeout=30)
            
            if response.status_code != 200:
                # Try alternative URL - maybe the catalogue is in releases
                catalogue_url = "https://api.orbit-store.com/catalogue"
                response = self.session.get(catalogue_url, timeout=30)
            
            if response.status_code == 200:
                catalogue = response.json()
                return self._process_catalogue(catalogue, GameSource.ORBIT_STORE)
            else:
                return {"success": False, "error": f"Failed to fetch catalogue: {response.status_code}"}
        
        except Exception as e:
            logger.error(f"Orbit Store update failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_from_blackbox(self) -> Dict[str, Any]:
        """Update from BlackBox."""
        try:
            logger.info("Updating from BlackBox...")
            
            # BlackBox does not host a public game catalogue
            # It's a package installer that uses external sources
            # Check for catalog directory
            catalogue_urls = [
                "https://raw.githubusercontent.com/D3ATHLY/blackbox/main/catalog/catalogue.json",
                "https://raw.githubusercontent.com/D3ATHLY/blackbox/main/catalogue.json",
                "https://raw.githubusercontent.com/D3ATHLY/blackbox/main/catalog/catalog.json",
            ]
            
            for url in catalogue_urls:
                try:
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        catalogue = response.json()
                        return self._process_catalogue(catalogue, GameSource.BLACKBOX)
                except Exception:
                    continue
            
            return {"success": False, "error": "No public catalogue found for BlackBox"}
        
        except Exception as e:
            logger.error(f"BlackBox update failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _update_from_overdrive(self) -> Dict[str, Any]:
        """Update from Overdrive."""
        try:
            logger.info("Updating from Overdrive...")
            
            catalogue_urls = [
                "https://raw.githubusercontent.com/overdriveps5/overdrive-releases/main/catalogue.json",
                "https://raw.githubusercontent.com/FermataRest/over-drive/main/catalogue.json",
                "https://raw.githubusercontent.com/FermataRest/over-drive/main/catalog.json",
            ]
            
            for url in catalogue_urls:
                try:
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        catalogue = response.json()
                        return self._process_catalogue(catalogue, GameSource.OVERDRIVE)
                except Exception:
                    continue
            
            return {"success": False, "error": "No public catalogue found for Overdrive"}
        
        except Exception as e:
            logger.error(f"Overdrive update failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _process_catalogue(self, catalogue: Dict[str, Any], source: GameSource) -> Dict[str, Any]:
        """Process a catalogue and update database."""
        db = get_db_session()
        try:
            games_added = 0
            games_updated = 0
            errors = 0
            
            # Handle different catalogue formats
            games_list = []
            
            if isinstance(catalogue, list):
                games_list = catalogue
            elif isinstance(catalogue, dict):
                # Try common keys
                for key in ['games', 'catalogue', 'data', 'entries']:
                    if key in catalogue:
                        games_list = catalogue[key]
                        break
            
            for game_data in games_list:
                try:
                    result = self._upsert_store_game(game_data, source, db)
                    if result == "added":
                        games_added += 1
                    elif result == "updated":
                        games_updated += 1
                except Exception as e:
                    errors += 1
                    logger.debug(f"Error processing game: {e}")
            
            db.commit()
            
            return {
                "success": True,
                "source": source.value,
                "games_added": games_added,
                "games_updated": games_updated,
                "errors": errors,
            }
        
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    def _upsert_store_game(self, game_data: Dict[str, Any], source: GameSource, db) -> str:
        """Insert or update a store game entry."""
        # Extract common fields
        store_id = str(game_data.get('id') or game_data.get('store_id') or game_data.get('ppsa'))
        ppsa = game_data.get('ppsa')
        title_id = game_data.get('title_id') or game_data.get('titleId')
        name = game_data.get('name') or game_data.get('title')
        
        if not name:
            raise ValueError("Game name required")
        
        # Check if entry exists
        entry = db.query(StoreGameEntry).filter_by(
            store_source=source,
            store_game_id=store_id
        ).first()
        
        if not entry:
            entry = StoreGameEntry(
                store_source=source,
                store_game_id=store_id,
            )
            db.add(entry)
            result = "added"
        else:
            result = "updated"
        
        # Update fields
        entry.ppsa = ppsa
        entry.title_id = title_id
        entry.name = name
        entry.region = game_data.get('region')
        entry.version = game_data.get('version')
        entry.required_firmware = game_data.get('required_firmware') or game_data.get('min_fw')
        entry.size_bytes = game_data.get('size') or game_data.get('size_bytes') or 0
        entry.format = GameFormat(game_data.get('format', GameFormat.UNKNOWN.value))
        entry.download_url = game_data.get('download_url') or game_data.get('url')
        entry.magnet_link = game_data.get('magnet') or game_data.get('magnet_link')
        entry.torrent_hash = game_data.get('torrent_hash') or game_data.get('hash')
        entry.cover_url = game_data.get('cover') or game_data.get('cover_url')
        entry.description = game_data.get('description')
        entry.genres = game_data.get('genres', [])
        entry.release_date = self._parse_date(game_data.get('release_date') or game_data.get('releaseDate'))
        entry.last_updated = datetime.utcnow()
        entry.is_available = game_data.get('available', True)
        
        # Also update main Game table if PPSA matches
        if ppsa:
            game = db.query(Game).filter_by(ppsa=ppsa).first()
            if game:
                # Update game with store info
                if not game.store_urls:
                    game.store_urls = {}
                game.store_urls[source.value] = entry.download_url or ""
                
                if not game.download_links:
                    game.download_links = {}
                if entry.magnet_link:
                    game.download_links[source.value] = entry.magnet_link
                elif entry.download_url:
                    game.download_links[source.value] = entry.download_url
                
                if entry.cover_url and not game.cover_url:
                    game.cover_url = entry.cover_url
                
                # Add source to available_sources
                if source not in (game.available_sources or []):
                    sources = game.available_sources or []
                    sources.append(source)
                    game.available_sources = sources
        
        return result
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%d/%m/%Y",
            "%m/%d/%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def get_store_stats(self) -> Dict[str, Any]:
        """Get statistics about store entries."""
        db = get_db_session()
        try:
            stats = {}
            
            for source in GameSource:
                count = db.query(StoreGameEntry).filter_by(store_source=source).count()
                available = db.query(StoreGameEntry).filter_by(
                    store_source=source, is_available=True
                ).count()
                stats[source.value] = {
                    "total": count,
                    "available": available,
                }
            
            return stats
        finally:
            db.close()
    
    def search_store_games(self, query: str, source: str = None) -> List[Dict[str, Any]]:
        """Search store game entries."""
        db = get_db_session()
        try:
            q = db.query(StoreGameEntry)
            
            if source:
                q = q.filter_by(store_source=GameSource(source))
            
            # Simple search
            q = q.filter(StoreGameEntry.name.ilike(f"%{query}%"))
            
            entries = q.limit(50).all()
            
            return [
                {
                    "id": e.id,
                    "source": e.store_source.value,
                    "store_id": e.store_game_id,
                    "ppsa": e.ppsa,
                    "title_id": e.title_id,
                    "name": e.name,
                    "format": e.format.value,
                    "size_bytes": e.size_bytes,
                    "download_url": e.download_url,
                    "magnet_link": e.magnet_link,
                    "cover_url": e.cover_url,
                    "is_available": e.is_available,
                }
                for e in entries
            ]
        finally:
            db.close()
    
    def get_game_sources(self, ppsa: str) -> List[Dict[str, Any]]:
        """Get all sources for a game by PPSA."""
        db = get_db_session()
        try:
            entries = db.query(StoreGameEntry).filter_by(ppsa=ppsa).all()
            
            return [
                {
                    "source": e.store_source.value,
                    "store_id": e.store_game_id,
                    "name": e.name,
                    "format": e.format.value,
                    "size_bytes": e.size_bytes,
                    "download_url": e.download_url,
                    "magnet_link": e.magnet_link,
                    "is_available": e.is_available,
                    "last_updated": e.last_updated.isoformat() if e.last_updated else None,
                }
                for e in entries
            ]
        finally:
            db.close()