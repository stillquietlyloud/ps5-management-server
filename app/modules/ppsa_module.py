"""Module 6: Retrieve PPSSA numbers and update game database."""
import os
import re
import csv
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.modules.ftp_module import FTPModule
from app.models import Game, GameLocation, GameFormat
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class PPSAModule(BaseModule):
    """PPSA Module for extracting PPSSA numbers from game files and updating database."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ftp_module = FTPModule()
        self.ppsa_database = {}  # PPSA -> Game Name mapping
        self._load_ppsa_csv()
    
    def _load_ppsa_csv(self):
        """Load PPSA database from CSV file."""
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'ppsa.csv')
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ppsa = row.get('PPSA_Number', '').strip().upper()
                    name = row.get('Game_Name', '').strip()
                    if ppsa and name:
                        self.ppsa_database[ppsa] = name
            logger.info(f"Loaded {len(self.ppsa_database)} PPSA entries from CSV")
        except Exception as e:
            logger.warning(f"Could not load PPSA CSV: {e}")
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="ppsa_module",
            version="1.0.0",
            description="Extract PPSSA numbers from game files and update game database",
            dependencies=["ftp_module"],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing PPSA Module")
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
    
    def update(self, system=None) -> Dict[str, Any]:
        """Update PPSA numbers for all games or from a specific PS5."""
        db = get_db_session()
        try:
            if system:
                # Update games from specific PS5
                locations = db.query(GameLocation).filter_by(
                    ps5_system_id=system.id,
                    is_installed=True
                ).all()
            else:
                # Update all games
                locations = db.query(GameLocation).filter(
                    GameLocation.is_installed == True
                ).all()
            
            updated = 0
            errors = 0
            
            for loc in locations:
                game = db.query(Game).get(loc.game_id)
                if game:
                    result = self._extract_and_update_ppsa(game, loc, db)
                    if result.get("success"):
                        updated += 1
                    else:
                        errors += 1
            
            return {
                "success": True,
                "games_processed": len(locations),
                "updated": updated,
                "errors": errors,
            }
        
        finally:
            db.close()
    
    def _extract_and_update_ppsa(self, game: Game, location: GameLocation, db) -> Dict[str, Any]:
        """Extract PPSA from game file/folder and update database."""
        try:
            ppsa = None
            
            # Try to extract from filename/path
            if location.ps5_path:
                ppsa = self._extract_ppsa_from_name(location.ps5_path)
            elif location.server_path:
                ppsa = self._extract_ppsa_from_name(location.server_path)
            
            # If not found in name, try to read from param.sfo
            if not ppsa:
                if location.ps5_path and location.ps5_system_id:
                    # Would need FTP to read param.sfo
                    pass
                elif location.server_path:
                    ppsa = self._read_ppsa_from_param_sfo(location.server_path)
            
            if ppsa and (not game.ppsa or game.ppsa != ppsa):
                # Check if another game already has this PPSA
                existing = db.query(Game).filter_by(ppsa=ppsa).first()
                if existing and existing.id != game.id:
                    logger.warning(f"PPSA {ppsa} already assigned to game {existing.name}")
                    return {"success": False, "error": f"PPSA {ppsa} already in use"}
                
                game.ppsa = ppsa
                game.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated PPSA for {game.name}: {ppsa}")
                return {"success": True, "ppsa": ppsa}
            
            return {"success": True, "ppsa": game.ppsa, "message": "No update needed"}
        
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def _extract_ppsa_from_name(self, name: str) -> Optional[str]:
        """Extract PPSA from filename or path."""
        # PPSA format: PPSA followed by numbers
        match = re.search(r'PPSA(\d+)', name, re.IGNORECASE)
        if match:
            return f"PPSA{match.group(1)}"
        return None
    
    def _extract_title_id(self, name: str) -> Optional[str]:
        """Extract Title ID from filename or path."""
        # Title ID format: CUSAxxxxx, PCSAxxxxx, etc.
        match = re.search(r'[A-Z]{4}\d{5}', name, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None
    
    def _read_ppsa_from_param_sfo(self, path: str) -> Optional[str]:
        """Read PPSA/Title ID from param.sfo file."""
        try:
            param_path = None
            
            if os.path.isdir(path):
                # Look for param.sfo in common locations
                possible_paths = [
                    os.path.join(path, "sce_sys", "param.sfo"),
                    os.path.join(path, "param.sfo"),
                    os.path.join(path, "PS5_GAME", "param.sfo"),
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        param_path = p
                        break
            else:
                # It's a file - might be a pkg, can't easily read param.sfo without extraction
                return None
            
            if param_path and os.path.exists(param_path):
                return self._parse_param_sfo(param_path)
        
        except Exception as e:
            logger.debug(f"Error reading param.sfo: {e}")
        
        return None
    
    def _parse_param_sfo(self, param_path: str) -> Optional[str]:
        """Parse param.sfo to extract title ID."""
        try:
            # param.sfo format: Sony's SFO format
            # We can use a simple parser or external tool
            # For now, try to read as binary and search for title ID pattern
            with open(param_path, 'rb') as f:
                data = f.read()
            
            # Search for title ID pattern in the binary data
            # Title IDs are usually in the format CUSAxxxxx
            matches = re.findall(rb'[A-Z]{4}\d{5}', data)
            if matches:
                return matches[0].decode('ascii')
        
        except Exception as e:
            logger.debug(f"Error parsing param.sfo: {e}")
        
        return None
    
    def scan_server_files(self) -> Dict[str, Any]:
        """Scan server game files for PPSA numbers."""
        db = get_db_session()
        try:
            # Get all games with server locations but no PPSA
            games = db.query(Game).join(GameLocation).filter(
                GameLocation.server_path.isnot(None),
                GameLocation.ps5_system_id.is_(None),
                Game.ppsa.is_(None)
            ).all()
            
            updated = 0
            for game in games:
                for loc in game.locations:
                    if loc.server_path:
                        ppsa = self._extract_ppsa_from_name(loc.server_path)
                        if ppsa:
                            # Check if PPSA already exists
                            existing = db.query(Game).filter_by(ppsa=ppsa).first()
                            if not existing:
                                game.ppsa = ppsa
                                game.updated_at = datetime.utcnow()
                                updated += 1
                                break
            
            db.commit()
            
            return {
                "success": True,
                "games_scanned": len(games),
                "updated": updated,
            }
        
        finally:
            db.close()
    
    def get_games_without_ppsa(self) -> List[Dict[str, Any]]:
        """Get list of games without PPSA."""
        db = get_db_session()
        try:
            games = db.query(Game).filter(Game.ppsa.is_(None)).all()
            
            return [
                {
                    "id": g.id,
                    "name": g.name,
                    "title_id": g.title_id,
                    "format": g.format.value if g.format else None,
                    "locations": [
                        {
                            "server_path": loc.server_path,
                            "ps5_path": loc.ps5_path,
                            "ps5_system_id": loc.ps5_system_id,
                        }
                        for loc in g.locations
                    ],
                }
                for g in games
            ]
        finally:
            db.close()
    
    def assign_ppsa_manually(self, game_id: int, ppsa: str) -> Dict[str, Any]:
        """Manually assign PPSA to a game."""
        db = get_db_session()
        try:
            game = db.query(Game).get(game_id)
            if not game:
                return {"success": False, "error": "Game not found"}
            
            # Validate PPSA format
            if not re.match(r'^PPSA\d+$', ppsa, re.IGNORECASE):
                return {"success": False, "error": "Invalid PPSA format (expected PPSAxxxxxx)"}
            
            ppsa = ppsa.upper()
            
            # Check if already in use
            existing = db.query(Game).filter_by(ppsa=ppsa).first()
            if existing and existing.id != game_id:
                return {"success": False, "error": f"PPSA {ppsa} already assigned to {existing.name}"}
            
            game.ppsa = ppsa
            game.updated_at = datetime.utcnow()
            db.commit()
            
            return {"success": True, "game_id": game_id, "ppsa": ppsa}
        
        finally:
            db.close()

    def lookup_ppsa_online(self, ppsa: str) -> Optional[str]:
        """Look up game name for a PPSA from online sources."""
        ppsa = ppsa.upper()
        
        # First check local CSV database
        if ppsa in self.ppsa_database:
            return self.ppsa_database[ppsa]
        
        # Try anyps5game.org
        try:
            url = f"https://anyps5game.org/games/ppsa/{ppsa}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Parse HTML for game name
                import re
                # Try to extract title from page
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', response.text, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                    # Clean up common suffixes
                    title = re.sub(r'\s*\|\s*.*$', '', title)
                    title = re.sub(r'\s*-\s*anyps5game\.org.*$', '', title, flags=re.IGNORECASE)
                    if title and title != ppsa:
                        return title
        except Exception as e:
            logger.debug(f"Error looking up {ppsa} on anyps5game.org: {e}")
        
        # Try PS5 Game Database API if available
        try:
            # This is a placeholder for other potential APIs
            pass
        except Exception:
            pass
        
        return None
    
    def enrich_game_with_ppsa(self, game: Game, db) -> Dict[str, Any]:
        """Enrich a game with PPSA information from all sources."""
        updated = False
        ppsa = game.ppsa
        name = game.name
        
        # If game has PPSA but no name, look it up
        if ppsa and not name:
            found_name = self.lookup_ppsa_online(ppsa)
            if found_name:
                game.name = found_name
                updated = True
        
        # If game has name but no PPSA, try to find PPSA
        if not ppsa and name:
            # Try to extract from name/locations
            for loc in game.locations:
                if loc.ps5_path:
                    extracted = self._extract_ppsa_from_name(loc.ps5_path)
                    if extracted:
                        # Check if PPSA is already in use by another game
                        existing = db.query(Game).filter_by(ppsa=extracted).first()
                        if not existing or existing.id == game.id:
                            game.ppsa = extracted
                            ppsa = extracted
                            updated = True
                        break
                elif loc.server_path:
                    extracted = self._extract_ppsa_from_name(loc.server_path)
                    if extracted:
                        # Check if PPSA is already in use by another game
                        existing = db.query(Game).filter_by(ppsa=extracted).first()
                        if not existing or existing.id == game.id:
                            game.ppsa = extracted
                            ppsa = extracted
                            updated = True
                        break
        
        # If we found a PPSA, look up name
        if ppsa and not game.name:
            found_name = self.lookup_ppsa_online(ppsa)
            if found_name:
                game.name = found_name
                updated = True
        
        if updated:
            game.updated_at = datetime.utcnow()
        
        return {"success": True, "updated": updated, "ppsa": game.ppsa, "name": game.name}
    
    def enrich_all_games(self) -> Dict[str, Any]:
        """Enrich all games with PPSA information."""
        db = get_db_session()
        try:
            games = db.query(Game).all()
            updated = 0
            for game in games:
                result = self.enrich_game_with_ppsa(game, db)
                if result.get("updated"):
                    updated += 1
            db.commit()
            return {"success": True, "games_processed": len(games), "updated": updated}
        except Exception as e:
            db.rollback()
            logger.error(f"Error enriching games: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    def get_ppsa_database(self) -> Dict[str, str]:
        """Get the loaded PPSA database."""
        return self.ppsa_database.copy()
    
    def search_ppsa(self, query: str) -> List[Dict[str, str]]:
        """Search PPSA database by game name or PPSA number."""
        query = query.upper()
        results = []
        for ppsa, name in self.ppsa_database.items():
            if query in ppsa or query in name.upper():
                results.append({"ppsa": ppsa, "name": name})
        return results