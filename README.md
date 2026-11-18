# PS5 Management Server

A comprehensive web-based management service for jailbroken PS5 consoles. This server provides a modular architecture to manage game libraries, torrent downloads, file transfers, save backups, exploit hosting, and more.

## Features

### Core Modules (13 Modules)

1. **FTP Module** - Connect to PS5 via FTP, discover game files (pkg, fpkg, exfat, folders)
2. **Push Module** - Transfer games from server to PS5 (primary SSD, secondary, external USB)
3. **Pull Module** - Copy games from PS5 to server, option to keep or remove on PS5
4. **Save Backup Module** - Backup save games from PS5 to server
5. **Save Restore Module** - Restore save games from server to PS5
6. **PPSA Module** - Extract PPSA numbers from game files and maintain game database
7. **Artwork Module** - Download game artwork (covers, backgrounds, icons) from web stores
8. **Store DB Module** - Sync game data from Orbit Store, BlackBox, Overdrive
9. **Download Module** - Manage downloads from web stores (torrent, magnet, direct)
10. **Convert Module** - Convert game files between PS5 formats using PS5PKGTool/PS-Multi-Tools
11. **Info Module** - Fetch game metadata from IGDB, RAWG, PSN, ProsperoPatches, HowLongToBeat
12. **Exploit Module** - Host PS5 exploit stack (nanoDNS + ps5-webkit-autoloader)
13. **Web GUI** - Tabbed interface for all functions

### Web Interface Tabs

- **Game Library** - View all games with PPSA-based naming, filter by source/format, see availability
- **Torrent Management** - Configure qBittorrent/Transmission clients
- **Actions & Transfers** - Monitor active tasks and history
- **Settings** - Manage PS5 systems, server paths, API keys
- **Exploit Host** - Start/stop exploit stack, upload payloads, PS5 setup instructions

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for exploit hosting)
- Jailbroken PS5 with FTP enabled

### Installation

```bash
# Clone repository
cd ps5_management_server

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Run server
python main.py
```

### Access Web Interface

Open http://localhost:8080 in your browser.

## Configuration

### Environment Variables (.env)

```bash
# Server
HOST=0.0.0.0
PORT=8080
DEBUG=true
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=sqlite:///ps5_manager.db

# Storage Paths (relative to project root)
SERVER_GAMES_PATH=./data/games
SERVER_SAVES_PATH=./data/saves
SERVER_ARTWORK_PATH=./data/artwork
SERVER_DOWNLOADS_PATH=./data/downloads

# Torrent Clients
QBITTORRENT_HOST=http://localhost:8080
QBITTORRENT_USER=admin
QBITTORRENT_PASS=adminadmin
TRANSMISSION_HOST=http://localhost:9091

# API Keys
IGDB_CLIENT_ID=your_igdb_client_id
IGDB_CLIENT_SECRET=your_igdb_client_secret
RAWG_API_KEY=your_rawg_api_key
PSN_NPSSO=your_psn_npsso

# PS5 Exploit
EXPLOIT_HOST_IP=192.168.8.50
EXPLOIT_DNS_PORT=53
EXPLOIT_HTTPS_PORT=443
```

### PS5 Setup

1. Enable FTP on your PS5 (via Homebrew/Payload)
2. Note your PS5 IP address
3. In the web UI, go to Settings → Add PS5
4. Enter name, IP, FTP credentials
5. Click Connect to test

## Project Structure

```
ps5_management_server/
├── main.py                 # Entry point
├── config.py               # Configuration
├── requirements.txt        # Dependencies
├── .env.example            # Environment template
├── app/
│   ├── __init__.py         # App factory
│   ├── database.py         # DB setup
│   ├── models/             # SQLAlchemy models
│   │   └── __init__.py
│   ├── modules/            # Feature modules
│   │   ├── base.py         # Base module class
│   │   ├── __init__.py     # Module registry
│   │   ├── ftp_module.py   # Module 1
│   │   ├── push_module.py  # Module 2
│   │   ├── pull_module.py  # Module 3
│   │   ├── save_backup_module.py  # Module 4
│   │   ├── save_restore_module.py # Module 5
│   │   ├── ppsa_module.py  # Module 6
│   │   ├── artwork_module.py # Module 7
│   │   ├── store_db_module.py # Module 8
│   │   ├── download_module.py # Module 9
│   │   ├── convert_module.py # Module 10
│   │   ├── info_module.py  # Module 11
│   │   └── exploit_module.py # Module 13
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py       # API endpoints
│   ├── templates/          # Jinja2 templates
│   │   ├── index.html      # Main dashboard
│   │   ├── status.html     # Status page
│   │   └── 404.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js       # Frontend logic
└── tests/                  # Test scripts
```

## Module Development

Each module is independent in `app/modules/` and follows the `BaseModule` interface:

```python
class MyModule(BaseModule):
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="my_module",
            version="1.0.0",
            description="Module description",
            dependencies=["ftp"],  # Other module names
        )
    
    async def initialize(self) -> bool:
        # Setup code
        return True
    
    async def shutdown(self) -> bool:
        # Cleanup code
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {"status": self.get_status().value}
```

Register in `app/modules/__init__.py`:
```python
MODULE_REGISTRY["my_module"] = MyModule
MODULE_DEPENDENCIES["my_module"] = ["ftp"]
```

## API Endpoints

### PS5 Systems
- `GET /api/ps5-systems` - List all PS5 systems
- `POST /api/ps5-systems` - Add PS5 system
- `DELETE /api/ps5-systems/<id>` - Remove PS5 system
- `POST /api/ps5-systems/<id>/connect` - Test FTP connection

### Games
- `GET /api/games` - List all games
- `GET /api/games/<id>/locations` - Get game locations

### Module Actions
- `POST /api/modules/<name>/action` - Execute module action

### Exploit
- `POST /api/exploit/start` - Start exploit stack
- `POST /api/exploit/stop` - Stop exploit stack
- `GET /api/exploit/status` - Get status
- `GET /api/exploit/setup` - Get PS5 setup instructions
- `GET /api/exploit/payloads` - List payloads
- `POST /api/exploit/payload` - Upload payload

### System
- `GET /api/system/resources` - CPU, memory, disk, network
- `GET /api/system/storage` - Storage paths usage
- `GET /api/services/status` - Service status tracking

## Exploit Hosting

The server can host the PS5 exploit stack (nanoDNS + ps5-webkit-autoloader) based on the [ps5-exploit-stack](https://git.marcadamalda.de/dev-bot/ps5-exploit-stack).

### Quick Setup

1. Go to Exploit Host tab
2. Click "Start Stack"
3. Configure PS5 DNS to server IP
4. Open User's Guide on PS5
5. Reboot and launch WebKit Autoloader

### Ports Required
- **53** (UDP/TCP) - nanoDNS
- **443** (TCP) - Autoloader HTTPS

## Supported Game Formats

- PKG (official packages)
- FPKG (fake packages)
- EXFAT (exFAT images)
- ISO, BIN/CUE
- ZIP, RAR, 7Z, TAR, GZ
- Folders (extracted games)

## PS5 Storage Locations

- Primary SSD: `/data/app`
- Secondary: `/data/app0`
- External USB: `/mnt/usb0`, `/mnt/usb1`, `/mnt/usb2`

## External Sources Integrated

- **Orbit Store** (orbit-store-ps5) - 2000+ games
- **BlackBox** (D3ATHLY/blackbox) - 1800+ games
- **Overdrive** (overdriveps5/overdrive-releases) - 1600+ games
- **ProsperoPatches** - PS5 game updates
- **IGDB** - Game metadata
- **RAWG** - Game database
- **PSN API** (psnawp) - PlayStation Network data
- **HowLongToBeat** - Game completion times

## Testing

```bash
# Run FTP module test
python tests/test_ftp_module.py

# Run with pytest
pytest tests/
```

## License

This project is for educational purposes only. Use responsibly and in accordance with local laws.

## Credits

- [drakmor/nanoDNS](https://github.com/drakmor/nanoDNS)
- [itsPLK/ps5-webkit-autoloader](https://github.com/itsPLK/ps5-webkit-autoloader)
- [saawant12/orbit-store-ps5](https://github.com/saawant12/orbit-store-ps5)
- [D3ATHLY/blackbox](https://github.com/D3ATHLY/blackbox)
- [overdriveps5/overdrive-releases](https://github.com/overdriveps5/overdrive-releases)
- [pearlxcore/PS5PKGTool](https://github.com/pearlxcore/PS5PKGTool)
- [SvenGDK/PS-Multi-Tools](https://github.com/SvenGDK/PS-Multi-Tools)
- [isFakeAccount/psnawp](https://github.com/isFakeAccount/psnawp)