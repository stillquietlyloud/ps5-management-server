"""Database models for PS5 Management Server."""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, Enum as SQLEnum, JSON, LargeBinary, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

Base = declarative_base()


class PS5StorageLocation(str, Enum):
    """PS5 storage locations."""
    PRIMARY_SSD = "primary_ssd"
    SECONDARY_SSD = "secondary_ssd"
    EXTERNAL_USB = "external_usb"
    EXTERNAL_USB_2 = "external_usb_2"
    EXTERNAL_USB_3 = "external_usb_3"


class GameSource(str, Enum):
    """Source of the game."""
    LOCAL = "local"
    PS5 = "ps5"
    ORBIT_STORE = "orbit_store"
    BLACKBOX = "blackbox"
    OVERDRIVE = "overdrive"
    PROSPERO_PATCHES = "prospero_patches"
    UNKNOWN = "unknown"


class GameFormat(str, Enum):
    """Game file formats."""
    PKG = "pkg"
    FPKG = "fpkg"
    EXFAT = "exfat"
    ISO = "iso"
    FOLDER = "folder"
    ZIP = "zip"
    RAR = "rar"
    SEVEN_ZIP = "7z"
    TAR = "tar"
    GZ = "gz"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Types of tasks."""
    FTP_CONNECT = "ftp_connect"
    PUSH_GAME = "push_game"
    PULL_GAME = "pull_game"
    BACKUP_SAVES = "backup_saves"
    RESTORE_SAVES = "restore_saves"
    FETCH_PPSA = "fetch_ppsa"
    DOWNLOAD_ARTWORK = "download_artwork"
    UPDATE_STORE_DB = "update_store_db"
    MANAGE_DOWNLOAD = "manage_download"
    CONVERT_FORMAT = "convert_format"
    FETCH_GAME_INFO = "fetch_game_info"


class PS5System(Base):
    """Managed PS5 systems."""
    __tablename__ = "ps5_systems"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    ip_address = Column(String(45), nullable=False)
    ftp_port = Column(Integer, default=21)
    ftp_username = Column(String(50), default="ftp")
    ftp_password = Column(String(100), default="ftp")
    firmware_version = Column(String(20))
    is_connected = Column(Boolean, default=False)
    last_seen = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    games = relationship("GameLocation", back_populates="ps5_system", cascade="all, delete-orphan")
    saves = relationship("SaveGame", back_populates="ps5_system", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="ps5_system", cascade="all, delete-orphan")


class Game(Base):
    """Game database with PPSSA and metadata."""
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ppsa = Column(String(20), unique=True, index=True, nullable=True)  # PPSA number
    title_id = Column(String(20), unique=True, index=True, nullable=True)  # e.g., CUSA00001
    name = Column(String(200), nullable=False, index=True)
    region = Column(String(10))
    version = Column(String(20))
    required_firmware = Column(String(20))
    size_bytes = Column(Integer, default=0)
    format = Column(SQLEnum(GameFormat), default=GameFormat.UNKNOWN)
    
    # Metadata from APIs
    igdb_id = Column(Integer, nullable=True)
    rawg_id = Column(Integer, nullable=True)
    psn_id = Column(String(50), nullable=True)
    prospero_id = Column(String(50), nullable=True)
    
    # Artwork
    cover_url = Column(String(500))
    background_url = Column(String(500))
    icon_url = Column(String(500))
    local_cover_path = Column(String(500))
    local_background_path = Column(String(500))
    local_icon_path = Column(String(500))
    
    # Game info
    description = Column(Text)
    genres = Column(SQLiteJSON, default=list)
    platforms = Column(SQLiteJSON, default=list)
    release_date = Column(DateTime)
    developer = Column(String(200))
    publisher = Column(String(200))
    metacritic_score = Column(Integer)
    hltb_main_story = Column(Integer)  # minutes
    hltb_main_extra = Column(Integer)
    hltb_completionist = Column(Integer)
    
    # Availability
    is_on_server = Column(Boolean, default=False)
    is_on_any_ps5 = Column(Boolean, default=False)
    available_sources = Column(SQLiteJSON, default=list)  # List of GameSource
    
    # Store info
    store_urls = Column(SQLiteJSON, default=dict)  # source -> url
    download_links = Column(SQLiteJSON, default=dict)  # source -> link
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked = Column(DateTime)
    
    # Relationships
    locations = relationship("GameLocation", back_populates="game", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_game_name_pssa', 'name', 'ppsa'),
        Index('idx_game_sources', 'available_sources'),
    )


class GameLocation(Base):
    """Where a game is located (server or PS5)."""
    __tablename__ = "game_locations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    ps5_system_id = Column(Integer, ForeignKey("ps5_systems.id", ondelete="CASCADE"), nullable=True)
    server_path = Column(String(500), nullable=True)
    ps5_path = Column(String(500), nullable=True)
    ps5_storage = Column(SQLEnum(PS5StorageLocation), nullable=True)
    format = Column(SQLEnum(GameFormat), default=GameFormat.UNKNOWN)
    size_bytes = Column(Integer, default=0)
    is_installed = Column(Boolean, default=True)
    verified = Column(Boolean, default=False)
    last_verified = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    game = relationship("Game", back_populates="locations")
    ps5_system = relationship("PS5System", back_populates="games")


class SaveGame(Base):
    """Save game backups."""
    __tablename__ = "save_games"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    ps5_system_id = Column(Integer, ForeignKey("ps5_systems.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(50))  # PSN user ID
    save_name = Column(String(200))
    server_path = Column(String(500), nullable=False)
    ps5_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, default=0)
    slot_number = Column(Integer, default=0)
    is_auto_save = Column(Boolean, default=False)
    game_progress = Column(String(100))  # e.g., "Chapter 5", "45%"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    backed_up_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    ps5_system = relationship("PS5System", back_populates="saves")
    game = relationship("Game")


class TorrentClient(Base):
    """Torrent client configurations."""
    __tablename__ = "torrent_clients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)  # qbittorrent, transmission
    client_type = Column(String(20), nullable=False)  # qbittorrent, transmission
    host = Column(String(200), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100))
    password = Column(String(100))
    is_enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    download_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DownloadTask(Base):
    """Download tasks from web stores."""
    __tablename__ = "download_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    source = Column(SQLEnum(GameSource), nullable=False)
    torrent_client_id = Column(Integer, ForeignKey("torrent_clients.id", ondelete="SET NULL"), nullable=True)
    torrent_hash = Column(String(100))
    magnet_link = Column(Text)
    download_url = Column(String(500))
    save_path = Column(String(500))
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(Integer, default=0)  # 0-100
    downloaded_bytes = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    download_speed = Column(Integer, default=0)  # bytes/sec
    eta_seconds = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """Generic task tracking."""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ps5_system_id = Column(Integer, ForeignKey("ps5_systems.id", ondelete="SET NULL"), nullable=True)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    progress = Column(Integer, default=0)
    current_file = Column(String(500))
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    total_bytes = Column(Integer, default=0)
    processed_bytes = Column(Integer, default=0)
    speed_bps = Column(Integer, default=0)  # bytes per second
    eta_seconds = Column(Integer, default=0)
    error_message = Column(Text)
    parameters = Column(SQLiteJSON, default=dict)  # Task-specific parameters
    result = Column(SQLiteJSON, default=dict)  # Task result data
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    ps5_system = relationship("PS5System", back_populates="tasks")


class StoreGameEntry(Base):
    """Game entries from web stores (orbit, blackbox, overdrive)."""
    __tablename__ = "store_game_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_source = Column(SQLEnum(GameSource), nullable=False)
    store_game_id = Column(String(100), nullable=False)  # Store's internal ID
    ppsa = Column(String(20), index=True, nullable=True)
    title_id = Column(String(20), index=True, nullable=True)
    name = Column(String(200), nullable=False)
    region = Column(String(10))
    version = Column(String(20))
    required_firmware = Column(String(20))
    size_bytes = Column(Integer, default=0)
    format = Column(SQLEnum(GameFormat), default=GameFormat.UNKNOWN)
    download_url = Column(String(500))
    magnet_link = Column(Text)
    torrent_hash = Column(String(100))
    cover_url = Column(String(500))
    description = Column(Text)
    genres = Column(SQLiteJSON, default=list)
    release_date = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_available = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_store_game_ppsa', 'ppsa', 'store_source'),
        Index('idx_store_game_title', 'title_id', 'store_source'),
    )


class ServiceStatus(Base):
    """Service status tracking."""
    __tablename__ = "service_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service_name = Column(String(100), unique=True, nullable=False)
    is_running = Column(Boolean, default=False)
    last_run = Column(DateTime)
    last_success = Column(DateTime)
    last_error = Column(Text)
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    avg_duration_seconds = Column(Integer, default=0)
    config = Column(SQLiteJSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExploitHostConfig(Base):
    """Exploit hosting configuration."""
    __tablename__ = "exploit_host_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    host_ip = Column(String(45), nullable=False)
    dns_port = Column(Integer, default=53)
    https_port = Column(Integer, default=443)
    nanodns_config = Column(Text)  # nanodns.ini content
    autoloader_payloads = Column(SQLiteJSON, default=list)  # List of payload paths
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)