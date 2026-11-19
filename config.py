"""Configuration management for PS5 Management Server."""
import os
from pathlib import Path
from typing import Optional, List


class Settings:
    """Application settings."""
    
    def __init__(self):
        # Load .env file if it exists
        self._load_env()
        
        # Base directory for data
        self.BASE_DIR = Path(__file__).parent.parent
        self.DATA_DIR = self.BASE_DIR / "data"
        
        # Server
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        self.PORT: int = int(os.getenv("PORT", "8080"))
        self.DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
        
        # Database
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{self.BASE_DIR / 'ps5_manager.db'}")
        
        # Server Storage
        self.SERVER_GAMES_PATH: str = os.getenv("SERVER_GAMES_PATH", str(self.DATA_DIR / "games"))
        self.SERVER_SAVES_PATH: str = os.getenv("SERVER_SAVES_PATH", str(self.DATA_DIR / "saves"))
        self.SERVER_ARTWORK_PATH: str = os.getenv("SERVER_ARTWORK_PATH", str(self.DATA_DIR / "artwork"))
        self.SERVER_DOWNLOADS_PATH: str = os.getenv("SERVER_DOWNLOADS_PATH", str(self.DATA_DIR / "downloads"))
        
        # FTP Default
        self.DEFAULT_FTP_PORT: int = int(os.getenv("DEFAULT_FTP_PORT", "21"))
        self.DEFAULT_FTP_USER: str = os.getenv("DEFAULT_FTP_USER", "ftp")
        self.DEFAULT_FTP_PASS: str = os.getenv("DEFAULT_FTP_PASS", "ftp")
        
        # Torrent Clients
        self.QBITTORRENT_HOST: str = os.getenv("QBITTORRENT_HOST", "http://localhost:8080")
        self.QBITTORRENT_USER: str = os.getenv("QBITTORRENT_USER", "admin")
        self.QBITTORRENT_PASS: str = os.getenv("QBITTORRENT_PASS", "adminadmin")
        self.TRANSMISSION_HOST: str = os.getenv("TRANSMISSION_HOST", "http://localhost:9091")
        self.TRANSMISSION_USER: str = os.getenv("TRANSMISSION_USER", "")
        self.TRANSMISSION_PASS: str = os.getenv("TRANSMISSION_PASS", "")
        
        # API Keys
        self.IGDB_CLIENT_ID: Optional[str] = os.getenv("IGDB_CLIENT_ID")
        self.IGDB_CLIENT_SECRET: Optional[str] = os.getenv("IGDB_CLIENT_SECRET")
        self.RAWG_API_KEY: Optional[str] = os.getenv("RAWG_API_KEY")
        self.PSN_NPSSO: Optional[str] = os.getenv("PSN_NPSSO")
        
        # PS5 Exploit
        self.EXPLOIT_HOST_IP: str = os.getenv("EXPLOIT_HOST_IP", "192.168.8.50")
        self.EXPLOIT_DNS_PORT: int = int(os.getenv("EXPLOIT_DNS_PORT", "53"))
        self.EXPLOIT_HTTPS_PORT: int = int(os.getenv("EXPLOIT_HTTPS_PORT", "443"))
        
        # Web Stores
        self.ORBIT_STORE_API: str = os.getenv("ORBIT_STORE_API", "https://api.orbit-store.com")
        self.BLACKBOX_API: str = os.getenv("BLACKBOX_API", "https://api.blackbox.com")
        self.OVERDRIVE_API: str = os.getenv("OVERDRIVE_API", "https://api.overdrive.com")
        
        # File Formats
        self.SUPPORTED_GAME_FORMATS: List[str] = [
            ".pkg", ".fpkg", ".exfat", ".iso", ".bin", ".cue",
            ".zip", ".rar", ".7z", ".tar", ".gz",
            ".ffpfsc", ".app",  # Additional homebrew formats
        ]
        
        self.PS5_STORAGE_PATHS: List[str] = [
            "/user/app",           # Primary games location (internal SSD)
            "/mnt/ext1",           # External storage 1 (common homebrew location)
            "/mnt/ext2",           # External storage 2
            "/mnt/ext3",           # External storage 3
            "/mnt/ext4",           # External storage 4
            "/mnt/ext5",           # External storage 5
            "/mnt/ext6",           # External storage 6
            "/mnt/ext7",           # External storage 7
            "/mnt/ext8",           # External storage 8
            "/mnt/ext9",           # External storage 9
            "/mnt/ext10",          # External storage 10
            "/mnt/usb0",           # External USB 0
            "/mnt/usb1",           # External USB 1
            "/mnt/usb2",           # External USB 2
            "/mnt/usb3",           # External USB 3
            "/mnt/usb4",           # External USB 4
            "/mnt/usb5",           # External USB 5
            "/mnt/usb6",           # External USB 6
            "/mnt/usb7",           # External USB 7
            "/mnt/pfs",            # Mounted game images
        ]
    
    def _load_env(self):
        """Load environment variables from .env file."""
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip())
            except Exception:
                pass


settings = Settings()


def ensure_data_directories():
    """Ensure data directories exist at runtime."""
    for path in [
        settings.SERVER_GAMES_PATH,
        settings.SERVER_SAVES_PATH,
        settings.SERVER_ARTWORK_PATH,
        settings.SERVER_DOWNLOADS_PATH,
    ]:
        Path(path).mkdir(parents=True, exist_ok=True)