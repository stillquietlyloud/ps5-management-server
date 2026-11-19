"""Module 1: FTP Connection to PS5 - Discover game files on PS5."""
import ftplib
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import PS5System, Game, GameLocation, GameFormat, PS5StorageLocation, GameType
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class FTPModule(BaseModule):
    """FTP Module for connecting to PS5 and discovering game files."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._connection: Optional[ftplib.FTP] = None
        self._current_system: Optional[PS5System] = None
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="ftp_module",
            version="1.0.0",
            description="FTP connection to PS5 for discovering game files (pkg, fpkg, exfat, folders)",
            dependencies=[],
        )
    
    async def initialize(self) -> bool:
        """Initialize the FTP module."""
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing FTP Module")
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        """Shutdown the FTP module."""
        self.disconnect()
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the FTP module."""
        return {
            "status": self.get_status().value,
            "connected": self._connection is not None,
            "current_system": self._current_system.name if self._current_system else None,
        }
    
    def connect(self, system: PS5System) -> Dict[str, Any]:
        """Connect to PS5 via FTP."""
        try:
            logger.info(f"Connecting to PS5 {system.name} at {system.ip_address}:{system.ftp_port}")
            
            self._connection = ftplib.FTP()
            self._connection.connect(system.ip_address, system.ftp_port, timeout=30)
            self._connection.login(system.ftp_username, system.ftp_password)
            self._connection.set_pasv(True)
            
            # Test connection
            self._connection.pwd()
            
            self._current_system = system
            logger.info(f"Successfully connected to {system.name}")
            
            return {"success": True, "message": f"Connected to {system.name}"}
        
        except Exception as e:
            logger.error(f"Failed to connect to {system.name}: {e}")
            self._connection = None
            self._current_system = None
            return {"success": False, "error": str(e)}
    
    def disconnect(self) -> bool:
        """Disconnect from PS5."""
        if self._connection:
            try:
                self._connection.quit()
            except Exception:
                try:
                    self._connection.close()
                except Exception:
                    pass
            self._connection = None
            self._current_system = None
            logger.info("Disconnected from PS5")
        return True
    
    def scan(self, system: PS5System) -> Dict[str, Any]:
        """Scan PS5 for game files."""
        result = self.connect(system)
        if not result.get("success"):
            return result
        
        try:
            logger.info(f"Scanning PS5 {system.name} for games")
            
            found_games = []
            
            # Scan all PS5 storage paths
            for storage_path in settings.PS5_STORAGE_PATHS:
                games_in_path = self._scan_path(storage_path, system)
                found_games.extend(games_in_path)
            
            # Update database with found games
            db = get_db_session()
            try:
                self._update_database(found_games, system, db)
            finally:
                db.close()
            
            self.disconnect()
            
            return {
                "success": True,
                "games_found": len(found_games),
                "games": found_games,
            }
        
        except Exception as e:
            logger.error(f"Error scanning PS5: {e}")
            self.disconnect()
            return {"success": False, "error": str(e)}
    
    def _scan_path(self, path: str, system: PS5System, depth: int = 0) -> List[Dict[str, Any]]:
        """Scan a specific path for game files recursively."""
        games = []
        
        # Limit recursion depth to avoid infinite loops
        if depth > 5:
            return games
        
        try:
            # Try to change to the path
            self._connection.cwd(path)
            current_path = path
        except Exception as e:
            logger.debug(f"Cannot access {path}: {e}")
            return games
        
        try:
            # List directory contents
            files = []
            self._connection.retrlines('LIST', files.append)
            
            for line in files:
                # Parse FTP LIST output
                parts = line.split()
                if len(parts) < 9:
                    continue
                
                permissions = parts[0]
                name = ' '.join(parts[8:])
                
                if name in ['.', '..']:
                    continue
                
                full_path = f"{current_path}/{name}"
                
                if permissions.startswith('d'):
                    # Directory - check if it's a game folder
                    game_info = self._analyze_game_folder(full_path, system)
                    if game_info:
                        games.append(game_info)
                    else:
                        # Not a game folder, recurse into it (but limit depth)
                        subdir_games = self._scan_path(full_path, system, depth + 1)
                        games.extend(subdir_games)
                else:
                    # File - check if it's a game file
                    game_info = self._analyze_game_file(full_path, name, system)
                    if game_info:
                        games.append(game_info)
        
        except Exception as e:
            logger.debug(f"Error scanning {path}: {e}")
        
        return games
    
    def _analyze_game_file(self, full_path: str, filename: str, system: PS5System) -> Optional[Dict[str, Any]]:
        """Analyze a file to determine if it's a game file."""
        # Check file extension
        ext = Path(filename).suffix.lower()
        filename_lower = filename.lower()
        
        # Extended format map with additional homebrew formats
        format_map = {
            '.pkg': GameFormat.PKG,
            '.fpkg': GameFormat.FPKG,
            '.exfat': GameFormat.EXFAT,
            '.iso': GameFormat.ISO,
            '.zip': GameFormat.ZIP,
            '.rar': GameFormat.RAR,
            '.7z': GameFormat.SEVEN_ZIP,
            '.tar': GameFormat.TAR,
            '.gz': GameFormat.GZ,
            '.ffpfsc': GameFormat.FFPFSC,
        }
        
        game_format = format_map.get(ext)
        
        # Also check for special file names that indicate game formats
        if not game_format:
            if 'ffpfsc' in filename_lower:
                game_format = GameFormat.FFPFSC
            elif filename_lower.endswith('.app') or 'ps5app' in filename_lower:
                game_format = GameFormat.PS5_APP
        
        if not game_format:
            return None
        
        # Try to get file size
        size = 0
        try:
            size = self._connection.size(full_path)
        except Exception:
            pass
        
        # Extract potential PPSA from filename
        ppsa = self._extract_ppsa(filename)
        title_id = self._extract_title_id(filename)
        
        # Determine game type based on PPSA and other indicators
        game_type = self._classify_game_type(filename_lower, ppsa, game_format)
        
        # Determine storage location
        storage = self._get_storage_location(full_path)
        
        return {
            "path": full_path,
            "filename": filename,
            "format": game_format.value,
            "size_bytes": size,
            "ppsa": ppsa,
            "title_id": title_id,
            "game_type": game_type.value,
            "storage": storage.value if storage else None,
            "is_folder": False,
        }
    
    def _classify_game_type(self, filename_lower: str, ppsa: Optional[str], game_format: GameFormat) -> GameType:
        """Classify game type based on filename, PPSA, and format."""
        # If it has a PPSA, it's a commercial game
        if ppsa:
            return GameType.GAME
        
        # Check for homebrew/application indicators
        homebrew_indicators = ['homebrew', 'brew', 'retroarch', 'ppsspp', 'duckstation', 'melonds', 'mugen', 'scummvm']
        exploit_indicators = ['exploit', 'payload', 'kernel', 'webkit', 'hen', 'jailbreak', 'elfloader']
        tool_indicators = ['tool', 'utility', 'manager', 'dumper', 'extractor', 'converter', 'ftp', 'server']
        emulator_indicators = ['emu', 'retroarch', 'ppsspp', 'duckstation', 'melonds', 'mugen', 'scummvm', 'citra', 'ryujinx']
        mod_indicators = ['mod', 'patch', 'cheat', 'trainer', 'save_wizard']
        theme_indicators = ['theme', 'skin', 'wallpaper', 'icon', 'boot', 'splash']
        
        for indicator in exploit_indicators:
            if indicator in filename_lower:
                return GameType.EXPLOIT
        
        for indicator in emulator_indicators:
            if indicator in filename_lower:
                return GameType.EMULATOR
        
        for indicator in tool_indicators:
            if indicator in filename_lower:
                return GameType.TOOL
        
        for indicator in homebrew_indicators:
            if indicator in filename_lower:
                return GameType.HOMEBREW_APP
        
        for indicator in mod_indicators:
            if indicator in filename_lower:
                return GameType.GAME_MOD
        
        for indicator in theme_indicators:
            if indicator in filename_lower:
                return GameType.THEME
        
        # If it's an ELF/BIN/SELF, likely an exploit or homebrew
        if game_format in [GameFormat.PS5_APP]:
            return GameType.HOMEBREW_APP
        
        # Default to GAME for PKG/FPKG without PPSA (could be region-free games)
        if game_format in [GameFormat.PKG, GameFormat.FPKG]:
            return GameType.GAME
        
        return GameType.OTHER
    
    def _analyze_game_folder(self, full_path: str, system: PS5System) -> Optional[Dict[str, Any]]:
        """Analyze a folder to determine if it's a game folder."""
        # Check if folder contains game-like files
        try:
            self._connection.cwd(full_path)
            files = []
            self._connection.retrlines('LIST', files.append)
            
            # Look for common game folder indicators
            has_eboot = False
            has_param = False
            has_pfs = False
            has_game_files = False
            game_file_format = None
            
            for line in files:
                parts = line.split()
                if len(parts) < 9:
                    continue
                name = ' '.join(parts[8:]).lower()
                if 'eboot' in name:
                    has_eboot = True
                if 'param.sfo' in name:
                    has_param = True
                if 'sce_sys' in name or 'pfs' in name:
                    has_pfs = True
                # Check for game files inside folder
                if any(name.endswith(ext) for ext in ['.pkg', '.fpkg', '.exfat', '.iso', '.ffpfsc']):
                    has_game_files = True
                    if name.endswith('.fpkg'):
                        game_file_format = GameFormat.FPKG
                    elif name.endswith('.pkg'):
                        game_file_format = GameFormat.PKG
                    elif name.endswith('.exfat'):
                        game_file_format = GameFormat.EXFAT
                    elif name.endswith('.iso'):
                        game_file_format = GameFormat.ISO
                    elif name.endswith('.ffpfsc'):
                        game_file_format = GameFormat.FFPFSC
            
            # Also consider folders with "homebrew" in path or folders that contain many game files
            folder_name_lower = os.path.basename(full_path).lower()
            path_lower = full_path.lower()
            is_homebrew = 'homebrew' in path_lower or 'homebrew' in folder_name_lower
            
            # Skip obvious container/parent folders that are not individual games
            # These are typically organizing folders, not actual game installations
            skip_folders = ['homebrew', 'downloads', 'extracted', 'packages', 'games', 'apps', 'tools']
            if folder_name_lower in skip_folders:
                return None
            
            # A folder is a game folder if it has:
            # 1. Standard PS4/PS5 indicators (eboot, param.sfo, sce_sys)
            # 2. Contains game files directly
            # 3. Is NOT just a container folder
            if has_eboot or has_param or has_pfs or has_game_files:
                # This looks like a game folder
                folder_name = os.path.basename(full_path)
                ppsa = self._extract_ppsa(folder_name)
                title_id = self._extract_title_id(folder_name)
                storage = self._get_storage_location(full_path)
                
                # Calculate folder size recursively
                size = self._calculate_folder_size(full_path)
                
                # Use detected format or default to FOLDER
                format_value = game_file_format.value if game_file_format else GameFormat.FOLDER.value
                
                # Determine game type
                game_type = self._classify_game_type(folder_name_lower, ppsa, game_file_format or GameFormat.FOLDER)
                
                return {
                    "path": full_path,
                    "filename": folder_name,
                    "format": format_value,
                    "size_bytes": size,
                    "ppsa": ppsa,
                    "title_id": title_id,
                    "game_type": game_type.value,
                    "storage": storage.value if storage else None,
                    "is_folder": True,
                }
        
        except Exception as e:
            logger.debug(f"Error analyzing folder {full_path}: {e}")
        
        return None
    
    def _calculate_folder_size(self, path: str) -> int:
        """Calculate total size of a folder recursively."""
        try:
            total_size = 0
            self._connection.cwd(path)
            files = []
            self._connection.retrlines('LIST', files.append)
            
            for line in files:
                parts = line.split()
                if len(parts) < 9:
                    continue
                name = ' '.join(parts[8:])
                if name in ['.', '..']:
                    continue
                
                full_item = f"{path}/{name}"
                permissions = parts[0]
                
                if permissions.startswith('d'):
                    # Recursively calculate subdirectory size
                    total_size += self._calculate_folder_size(full_item)
                else:
                    # File - get size
                    try:
                        size = self._connection.size(full_item)
                        total_size += size
                    except Exception:
                        pass
            
            return total_size
        except Exception as e:
            logger.debug(f"Error calculating size for {path}: {e}")
            return 0
    
    def _extract_ppsa(self, name: str) -> Optional[str]:
        """Extract PPSA number from filename/foldername."""
        import re
        # PPSA format: PPSA followed by numbers
        match = re.search(r'PPSA(\d+)', name, re.IGNORECASE)
        if match:
            return f"PPSA{match.group(1)}"
        return None
    
    def _extract_title_id(self, name: str) -> Optional[str]:
        """Extract Title ID from filename/foldername."""
        import re
        # Title ID format: CUSAxxxxx, PCSAxxxxx, etc.
        match = re.search(r'[A-Z]{4}\d{5}', name, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        return None
    
    def _get_storage_location(self, path: str) -> Optional[PS5StorageLocation]:
        """Determine storage location from path."""
        path_lower = path.lower()
        # External storage (common on homebrew PS5s)
        if '/mnt/ext10' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_10
        elif '/mnt/ext9' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_9
        elif '/mnt/ext8' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_8
        elif '/mnt/ext7' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_7
        elif '/mnt/ext6' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_6
        elif '/mnt/ext5' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_5
        elif '/mnt/ext4' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_4
        elif '/mnt/ext3' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_3
        elif '/mnt/ext2' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_2
        elif '/mnt/ext1' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_1
        # USB storage
        elif '/mnt/usb7' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_7
        elif '/mnt/usb6' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_6
        elif '/mnt/usb5' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_5
        elif '/mnt/usb4' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_4
        elif '/mnt/usb3' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_3
        elif '/mnt/usb2' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_2
        elif '/mnt/usb1' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_1
        elif '/mnt/usb0' in path_lower:
            return PS5StorageLocation.EXTERNAL_USB_0
        elif '/mnt/pfs' in path_lower:
            return PS5StorageLocation.MNT_PFS
        elif '/user/app' in path_lower:
            return PS5StorageLocation.USER_APP
        return None
    
    def _update_database(self, found_games: List[Dict], system: PS5System, db) -> None:
        """Update database with found games."""
        for game_data in found_games:
            # Find or create game entry
            game = None
            
            if game_data.get("ppsa"):
                game = db.query(Game).filter_by(ppsa=game_data["ppsa"]).first()
            
            if not game and game_data.get("title_id"):
                game = db.query(Game).filter_by(title_id=game_data["title_id"]).first()
            
            if not game:
                # Create new game entry
                game = Game(
                    ppsa=game_data.get("ppsa"),
                    title_id=game_data.get("title_id"),
                    name=game_data.get("filename", "Unknown"),
                    game_type=GameType(game_data.get("game_type", GameType.GAME.value)),
                    format=GameFormat(game_data.get("format", GameFormat.UNKNOWN.value)),
                    size_bytes=game_data.get("size_bytes", 0),
                )
                db.add(game)
                db.flush()
            else:
                # Update existing game with new info
                if game_data.get("size_bytes") and game_data["size_bytes"] > 0:
                    game.size_bytes = game_data["size_bytes"]
                if game_data.get("format"):
                    game.format = GameFormat(game_data.get("format", GameFormat.UNKNOWN.value))
            
            # Update game availability
            game.is_on_any_ps5 = True
            if game_data.get("ppsa") and not game.ppsa:
                game.ppsa = game_data["ppsa"]
            if game_data.get("title_id") and not game.title_id:
                game.title_id = game_data["title_id"]
            
            # Update or create location
            location = db.query(GameLocation).filter_by(
                game_id=game.id,
                ps5_system_id=system.id,
                ps5_path=game_data["path"]
            ).first()
            
            if not location:
                location = GameLocation(
                    game_id=game.id,
                    ps5_system_id=system.id,
                    ps5_path=game_data["path"],
                    ps5_storage=game_data.get("storage"),
                    format=GameFormat(game_data.get("format", GameFormat.UNKNOWN.value)),
                    size_bytes=game_data.get("size_bytes", 0),
                    is_installed=True,
                )
                db.add(location)
            else:
                location.is_installed = True
                location.size_bytes = game_data.get("size_bytes", 0)
                location.last_verified = datetime.utcnow()
                location.verified = True
        
        db.commit()
        logger.info(f"Updated database with {len(found_games)} games from {system.name}")
    
    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents."""
        if not self._connection:
            return []
        
        try:
            self._connection.cwd(path)
            files = []
            self._connection.retrlines('LIST', files.append)
            
            result = []
            for line in files:
                parts = line.split()
                if len(parts) < 9:
                    continue
                permissions = parts[0]
                name = ' '.join(parts[8:])
                
                if name in ['.', '..']:
                    continue
                
                result.append({
                    "name": name,
                    "is_dir": permissions.startswith('d'),
                    "permissions": permissions,
                    "path": f"{path}/{name}",
                })
            
            return result
        
        except Exception as e:
            logger.error(f"Error listing {path}: {e}")
            return []
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from PS5."""
        if not self._connection:
            return False
        
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'wb') as f:
                self._connection.retrbinary(f'RETR {remote_path}', f.write)
            return True
        except Exception as e:
            logger.error(f"Error downloading {remote_path}: {e}")
            return False
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to PS5."""
        if not self._connection:
            return False
        
        try:
            with open(local_path, 'rb') as f:
                self._connection.storbinary(f'STOR {remote_path}', f)
            return True
        except Exception as e:
            logger.error(f"Error uploading {local_path}: {e}")
            return False