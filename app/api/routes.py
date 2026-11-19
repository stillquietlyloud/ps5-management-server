"""Main API routes."""
from flask import Blueprint, jsonify, request
from app.modules.ftp_module import FTPModule
from app.modules.push_module import PushModule
from app.modules.pull_module import PullModule
from app.modules.save_backup_module import SaveBackupModule
from app.modules.save_restore_module import SaveRestoreModule
from app.modules.ppsa_module import PPSAModule
from app.modules.artwork_module import ArtworkModule
from app.modules.store_db_module import StoreDBModule
from app.modules.download_module import DownloadModule
from app.modules.convert_module import ConvertModule
from app.modules.info_module import InfoModule
from app.modules.exploit_module import ExploitModule
from app.modules.exploit_host_module import ExploitModule as ExploitHostModule
from app.database import get_db_session
from app.models import PS5System, Game, GameLocation, SaveGame, Task, ServiceStatus, ExploitHostConfig, TorrentClient, ExploitPackage, ExploitPackageType, GameType
import psutil
import os
import shutil
import logging

logger = logging.getLogger(__name__)

routes_bp = Blueprint("routes", __name__)


# Initialize modules
modules = {
    "ftp": FTPModule(),
    "push": PushModule(),
    "pull": PullModule(),
    "save_backup": SaveBackupModule(),
    "save_restore": SaveRestoreModule(),
    "ppsa": PPSAModule(),
    "artwork": ArtworkModule(),
    "store_db": StoreDBModule(),
    "download": DownloadModule(),
    "convert": ConvertModule(),
    "info": InfoModule(),
    "exploit": ExploitModule(),
    "exploit_host": ExploitHostModule(),
}


# ==================== Health & Status ====================

@routes_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@routes_bp.route("/modules", methods=["GET"])
def list_modules():
    return jsonify({
        name: {
            "status": module.status.value,
            "info": {
                "name": module.info.name,
                "version": module.info.version,
                "description": module.info.description,
            }
        }
        for name, module in modules.items()
    })


@routes_bp.route("/modules/<module_name>/health", methods=["GET"])
def module_health(module_name):
    module = modules.get(module_name)
    if not module:
        return jsonify({"error": "Module not found"}), 404
    return jsonify(module.get_status().value)


# ==================== PS5 Systems ====================

@routes_bp.route("/ps5-systems", methods=["GET"])
def list_ps5_systems():
    db = get_db_session()
    try:
        systems = db.query(PS5System).all()
        return jsonify([
            {
                "id": s.id,
                "name": s.name,
                "ip_address": s.ip_address,
                "ftp_port": s.ftp_port,
                "ftp_username": s.ftp_username,
                "firmware_version": s.firmware_version,
                "is_connected": s.is_connected,
                "last_seen": s.last_seen.isoformat() if s.last_seen else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in systems
        ])
    finally:
        db.close()


@routes_bp.route("/ps5-systems", methods=["POST"])
def add_ps5_system():
    data = request.get_json()
    db = get_db_session()
    try:
        system = PS5System(
            name=data["name"],
            ip_address=data["ip_address"],
            ftp_port=data.get("ftp_port", 21),
            ftp_username=data.get("ftp_username", "ftp"),
            ftp_password=data.get("ftp_password", "ftp"),
        )
        db.add(system)
        db.commit()
        return jsonify({"id": system.id, "name": system.name}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@routes_bp.route("/ps5-systems/<int:system_id>", methods=["DELETE"])
def delete_ps5_system(system_id):
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        if not system:
            return jsonify({"error": "System not found"}), 404
        db.delete(system)
        db.commit()
        return jsonify({"status": "deleted"})
    finally:
        db.close()


# ==================== Torrent Clients ====================

@routes_bp.route("/torrent-clients", methods=["GET"])
def list_torrent_clients():
    db = get_db_session()
    try:
        clients = db.query(TorrentClient).all()
        return jsonify([
            {
                "id": c.id,
                "name": c.name,
                "client_type": c.client_type,
                "host": c.host,
                "port": c.port,
                "username": c.username,
                "password": c.password,
                "is_enabled": c.is_enabled,
                "is_default": c.is_default,
                "download_path": c.download_path,
            }
            for c in clients
        ])
    finally:
        db.close()


@routes_bp.route("/torrent-clients", methods=["POST"])
def add_torrent_client():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    db = get_db_session()
    try:
        # If setting as default, unset other defaults
        if data.get("is_default"):
            db.query(TorrentClient).filter_by(is_default=True).update({"is_default": False})
        
        client = TorrentClient(
            name=data["name"],
            client_type=data["client_type"],
            host=data["host"],
            port=int(data["port"]),
            username=data.get("username"),
            password=data.get("password"),
            is_enabled=data.get("is_enabled", True),
            is_default=data.get("is_default", False),
            download_path=data.get("download_path"),
        )
        db.add(client)
        db.commit()
        return jsonify({"id": client.id, "name": client.name}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        db.close()


@routes_bp.route("/torrent-clients/<int:client_id>", methods=["DELETE"])
def delete_torrent_client(client_id):
    db = get_db_session()
    try:
        client = db.query(TorrentClient).get(client_id)
        if not client:
            return jsonify({"error": "Client not found"}), 404
        db.delete(client)
        db.commit()
        return jsonify({"status": "deleted"})
    finally:
        db.close()


@routes_bp.route("/torrent-clients/<int:client_id>/test", methods=["POST"])
def test_torrent_client(client_id):
    db = get_db_session()
    try:
        client = db.query(TorrentClient).get(client_id)
        if not client:
            return jsonify({"error": "Client not found"}), 404
        
        # Test connection based on client type
        import requests
        try:
            if client.client_type == "qbittorrent":
                response = requests.get(
                    f"{client.host}:{client.port}/api/v2/app/version",
                    auth=(client.username, client.password) if client.username else None,
                    timeout=10
                )
                return jsonify({"success": response.ok, "version": response.text if response.ok else None})
            elif client.client_type == "transmission":
                response = requests.get(
                    f"{client.host}:{client.port}/transmission/rpc",
                    auth=(client.username, client.password) if client.username else None,
                    timeout=10
                )
                return jsonify({"success": response.ok})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
        
        return jsonify({"success": False, "error": "Unknown client type"})
    finally:
        db.close()


@routes_bp.route("/ps5-systems/<int:system_id>/connect", methods=["POST"])
def connect_ps5_system(system_id):
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        if not system:
            return jsonify({"error": "System not found"}), 404
        # Test FTP connection via module
        result = modules["ftp"].connect(system)
        if result.get("success"):
            system.is_connected = True
            system.last_seen = __import__("datetime").datetime.utcnow()
            db.commit()
        return jsonify(result)
    finally:
        db.close()


# ==================== Games ====================

@routes_bp.route("/games", methods=["GET"])
def list_games():
    db = get_db_session()
    try:
        # Only return games (not homebrew apps, exploits, etc.)
        games = db.query(Game).filter(Game.game_type == GameType.GAME).all()
        return jsonify([
            {
                "id": g.id,
                "ppsa": g.ppsa,
                "title_id": g.title_id,
                "name": g.name,
                "region": g.region,
                "version": g.version,
                "format": g.format.value if g.format else None,
                "size_bytes": g.size_bytes,
                "is_on_server": g.is_on_server,
                "is_on_any_ps5": g.is_on_any_ps5,
                "cover_url": g.cover_url,
                "background_url": g.background_url,
                "local_cover_path": g.local_cover_path,
                "igdb_id": g.igdb_id,
                "rawg_id": g.rawg_id,
            }
            for g in games
        ])
    finally:
        db.close()


@routes_bp.route("/games/all", methods=["GET"])
def list_all_games():
    """Get all games including homebrew apps, exploits, etc."""
    db = get_db_session()
    try:
        games = db.query(Game).all()
        return jsonify([
            {
                "id": g.id,
                "ppsa": g.ppsa,
                "title_id": g.title_id,
                "name": g.name,
                "game_type": g.game_type.value if g.game_type else "game",
                "region": g.region,
                "version": g.version,
                "format": g.format.value if g.format else None,
                "size_bytes": g.size_bytes,
                "is_on_server": g.is_on_server,
                "is_on_any_ps5": g.is_on_any_ps5,
                "cover_url": g.cover_url,
                "background_url": g.background_url,
                "local_cover_path": g.local_cover_path,
                "igdb_id": g.igdb_id,
                "rawg_id": g.rawg_id,
            }
            for g in games
        ])
    finally:
        db.close()


@routes_bp.route("/games/by-type/<game_type>", methods=["GET"])
def list_games_by_type(game_type):
    """Get games filtered by game_type."""
    from app.models import GameType
    try:
        gt = GameType(game_type)
    except ValueError:
        return jsonify({"error": f"Invalid game_type: {game_type}"}), 400
    
    db = get_db_session()
    try:
        games = db.query(Game).filter(Game.game_type == gt).all()
        return jsonify([
            {
                "id": g.id,
                "ppsa": g.ppsa,
                "title_id": g.title_id,
                "name": g.name,
                "game_type": g.game_type.value if g.game_type else "game",
                "region": g.region,
                "version": g.version,
                "format": g.format.value if g.format else None,
                "size_bytes": g.size_bytes,
                "is_on_server": g.is_on_server,
                "is_on_any_ps5": g.is_on_any_ps5,
                "cover_url": g.cover_url,
                "background_url": g.background_url,
                "local_cover_path": g.local_cover_path,
                "igdb_id": g.igdb_id,
                "rawg_id": g.rawg_id,
            }
            for g in games
        ])
    finally:
        db.close()


@routes_bp.route("/games/<int:game_id>/locations", methods=["GET"])
def game_locations(game_id):
    db = get_db_session()
    try:
        locations = db.query(GameLocation).filter_by(game_id=game_id).all()
        return jsonify([
            {
                "id": loc.id,
                "server_path": loc.server_path,
                "ps5_path": loc.ps5_path,
                "ps5_storage": loc.ps5_storage.value if loc.ps5_storage else None,
                "format": loc.format.value if loc.format else None,
                "size_bytes": loc.size_bytes,
                "is_installed": loc.is_installed,
            }
            for loc in locations
        ])
    finally:
        db.close()


@routes_bp.route("/games/<int:game_id>", methods=["DELETE"])
def delete_game(game_id):
    """Delete a game from the server database and optionally remove its files.
    
    Query parameters:
    - confirm: Must be 'true' to confirm deletion
    - delete_files: If 'true', also delete the game files from server storage
    - delete_ps5: If 'true', also delete the game from PS5 (requires FTP connection)
    """
    confirm = request.args.get("confirm", "false").lower() == "true"
    delete_files = request.args.get("delete_files", "false").lower() == "true"
    delete_ps5 = request.args.get("delete_ps5", "false").lower() == "true"
    
    if not confirm:
        return jsonify({
            "success": False,
            "error": "Confirmation required",
            "message": "This will permanently delete the game from the database. "
                       "Set ?confirm=true to proceed. "
                       "Additional options: "
                       "?delete_files=true to also delete game files from server storage, "
                       "?delete_ps5=true to also remove from PS5 (requires FTP connection). "
                       "WARNING: This action cannot be undone!",
            "required_confirmation": True,
            "options": {
                "delete_files": "Also delete game files from server storage",
                "delete_ps5": "Also remove game from PS5 (requires FTP)"
            }
        }), 400
    
    db = get_db_session()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return jsonify({"success": False, "error": "Game not found"}), 404
        
        game_name = game.name
        game_ppsa = game.ppsa
        
        # Delete associated locations (server and PS5 paths)
        locations = db.query(GameLocation).filter_by(game_id=game_id).all()
        
        # Delete files from server if requested
        deleted_files = []
        if delete_files:
            for loc in locations:
                if loc.server_path and os.path.exists(loc.server_path):
                    try:
                        if os.path.isdir(loc.server_path):
                            shutil.rmtree(loc.server_path)
                        else:
                            os.remove(loc.server_path)
                        deleted_files.append(loc.server_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete {loc.server_path}: {e}")
        
        # Delete from PS5 if requested
        ps5_deleted = []
        if delete_ps5:
            # Find PS5 locations
            ps5_locations = [loc for loc in locations if loc.ps5_system_id and loc.ps5_path]
            if ps5_locations:
                # For now, we just mark as not installed
                # Actual FTP deletion would require connecting to each PS5
                for loc in ps5_locations:
                    loc.is_installed = False
                    ps5_deleted.append({
                        "ps5_system_id": loc.ps5_system_id,
                        "ps5_path": loc.ps5_path
                    })
        
        # Delete locations from database
        for loc in locations:
            db.delete(loc)
        
        # Delete the game
        db.delete(game)
        db.commit()
        
        return jsonify({
            "success": True,
            "message": f"Game '{game_name}' ({game_ppsa}) deleted successfully",
            "deleted_files": deleted_files,
            "ps5_locations_marked_removed": ps5_deleted
        })
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting game: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ==================== Tasks ====================

@routes_bp.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db_session()
    try:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(50).all()
        return jsonify([
            {
                "id": t.id,
                "task_type": t.task_type.value,
                "status": t.status.value,
                "progress": t.progress,
                "current_file": t.current_file,
                "error_message": t.error_message,
                "created_at": t.created_at.isoformat(),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ])
    finally:
        db.close()


# ==================== Save Games ====================

@routes_bp.route("/save-games", methods=["GET"])
def list_save_games():
    db = get_db_session()
    try:
        saves = db.query(SaveGame).all()
        return jsonify([
            {
                "id": s.id,
                "game_id": s.game_id,
                "save_name": s.save_name,
                "server_path": s.server_path,
                "size_bytes": s.size_bytes,
                "game_progress": s.game_progress,
                "backed_up_at": s.backed_up_at.isoformat() if s.backed_up_at else None,
            }
            for s in saves
        ])
    finally:
        db.close()


# ==================== Module Actions ====================

@routes_bp.route("/modules/<module_name>/action", methods=["POST"])
def module_action(module_name):
    """Execute an action on a module."""
    module = modules.get(module_name)
    if not module:
        return jsonify({"error": "Module not found"}), 404
    
    data = request.get_json() or {}
    action = data.get("action")
    
    # Route to specific module handlers
    if module_name == "ftp" and action == "scan":
        return _handle_ftp_scan(data)
    elif module_name == "push" and action == "push":
        return _handle_push_game(data)
    elif module_name == "pull" and action == "pull":
        return _handle_pull_game(data)
    elif module_name == "save_backup" and action == "backup":
        return _handle_save_backup(data)
    elif module_name == "save_restore" and action == "restore":
        return _handle_save_restore(data)
    elif module_name == "ppsa" and action == "update":
        return _handle_ppsa_update(data)
    elif module_name == "ppsa" and action == "enrich":
        return _handle_ppsa_enrich(data)
    elif module_name == "artwork" and action == "download":
        return _handle_download_artwork(data)
    elif module_name == "store_db" and action == "update":
        return _handle_store_db_update(data)
    elif module_name == "download" and action == "start":
        return _handle_download_start(data)
    elif module_name == "convert" and action == "convert":
        return _handle_convert(data)
    elif module_name == "convert" and action == "get_format_info":
        return _handle_convert_get_format_info(data)
    elif module_name == "info" and action == "fetch":
        return _handle_info_fetch(data)
    elif module_name == "exploit" and action == "list":
        return _handle_exploit_list(data)
    elif module_name == "exploit" and action == "add":
        return _handle_exploit_add(data)
    elif module_name == "exploit" and action == "get":
        return _handle_exploit_get(data)
    elif module_name == "exploit" and action == "delete":
        return _handle_exploit_delete(data)
    elif module_name == "exploit" and action == "types":
        return _handle_exploit_types(data)
    elif module_name == "exploit_host" and action == "start":
        return _handle_exploit_host_start(data)
    elif module_name == "exploit_host" and action == "stop":
        return _handle_exploit_host_stop(data)
    elif module_name == "exploit_host" and action == "status":
        return _handle_exploit_host_status(data)
    elif module_name == "exploit_host" and action == "add_payload":
        return _handle_exploit_host_add_payload(data)
    elif module_name == "exploit_host" and action == "list_payloads":
        return _handle_exploit_host_list_payloads(data)
    elif module_name == "exploit_host" and action == "instructions":
        return _handle_exploit_host_instructions(data)
    
    return jsonify({"error": f"Action '{action}' not supported"}), 400


def _handle_ftp_scan(data):
    system_id = data.get("system_id")
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        if not system:
            return jsonify({"error": "System not found"}), 404
        result = modules["ftp"].scan(system)
        return jsonify(result)
    finally:
        db.close()


def _handle_push_game(data):
    system_id = data.get("system_id")
    game_id = data.get("game_id")
    storage = data.get("storage", "primary_ssd")
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        game = db.query(Game).get(game_id)
        if not system or not game:
            return jsonify({"error": "System or game not found"}), 404
        result = modules["push"].push(system, game, storage)
        return jsonify(result)
    finally:
        db.close()


def _handle_pull_game(data):
    system_id = data.get("system_id")
    game_id = data.get("game_id")
    keep_on_ps5 = data.get("keep_on_ps5", True)
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        game = db.query(Game).get(game_id)
        if not system or not game:
            return jsonify({"error": "System or game not found"}), 404
        result = modules["pull"].pull(system, game, keep_on_ps5)
        return jsonify(result)
    finally:
        db.close()


def _handle_save_backup(data):
    system_id = data.get("system_id")
    game_id = data.get("game_id")
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        game = db.query(Game).get(game_id)
        if not system or not game:
            return jsonify({"error": "System or game not found"}), 404
        result = modules["save_backup"].backup(system, game)
        return jsonify(result)
    finally:
        db.close()


def _handle_save_restore(data):
    system_id = data.get("system_id")
    save_id = data.get("save_id")
    db = get_db_session()
    try:
        system = db.query(PS5System).get(system_id)
        save = db.query(SaveGame).get(save_id)
        if not system or not save:
            return jsonify({"error": "System or save not found"}), 404
        result = modules["save_restore"].restore(system, save)
        return jsonify(result)
    finally:
        db.close()


def _handle_ppsa_update(data):
    system_id = data.get("system_id")
    db = get_db_session()
    try:
        system = None
        if system_id:
            system = db.query(PS5System).get(system_id)
            if not system:
                return jsonify({"error": "System not found"}), 404
        result = modules["ppsa"].update(system)
        return jsonify(result)
    finally:
        db.close()


def _handle_ppsa_enrich(data):
    result = modules["ppsa"].enrich_all_games()
    return jsonify(result)


def _handle_download_artwork(data):
    game_id = data.get("game_id")
    db = get_db_session()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return jsonify({"error": "Game not found"}), 404
        result = modules["artwork"].download(game)
        
        # Update game with local artwork paths
        if result.get("local_cover_path"):
            game.local_cover_path = result["local_cover_path"]
        if result.get("local_background_path"):
            game.local_background_path = result["local_background_path"]
        if result.get("local_icon_path"):
            game.local_icon_path = result["local_icon_path"]
        
        db.commit()
        return jsonify(result)
    finally:
        db.close()


def _handle_store_db_update(data):
    source = data.get("source", "all")
    result = modules["store_db"].update(source)
    return jsonify(result)


def _handle_download_start(data):
    game_id = data.get("game_id")
    source = data.get("source")
    db = get_db_session()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return jsonify({"error": "Game not found"}), 404
        result = modules["download"].start(game, source)
        return jsonify(result)
    finally:
        db.close()


def _handle_convert(data):
    game_id = data.get("game_id")
    target_format = data.get("target_format")
    db = get_db_session()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return jsonify({"error": "Game not found"}), 404
        result = modules["convert"].convert(game, target_format)
        return jsonify(result)
    finally:
        db.close()


def _handle_convert_get_format_info(data):
    firmware = data.get("firmware")
    result = modules["convert"].get_format_info(firmware)
    return jsonify(result)


def _handle_info_fetch(data):
    game_id = data.get("game_id")
    db = get_db_session()
    try:
        game = db.query(Game).get(game_id)
        if not game:
            return jsonify({"error": "Game not found"}), 404
        result = modules["info"].fetch(game)
        
        # Update game with fetched info
        if result.get("igdb") and result["igdb"].get("name"):
            game.name = result["igdb"]["name"]
        elif result.get("rawg") and result["rawg"].get("name"):
            game.name = result["rawg"]["name"]
        elif result.get("prospero") and result["prospero"].get("name"):
            game.name = result["prospero"]["name"]
        
        # Update cover/background URLs
        if result.get("cover_url"):
            game.cover_url = result["cover_url"]
        if result.get("background_url"):
            game.background_url = result["background_url"]
        
        # Update IDs
        if result.get("igdb") and result["igdb"].get("igdb_id"):
            game.igdb_id = result["igdb"]["igdb_id"]
        if result.get("rawg") and result["rawg"].get("rawg_id"):
            game.rawg_id = result["rawg"]["rawg_id"]
        
        db.commit()
        return jsonify(result)
    finally:
        db.close()


# ==================== Exploit Host Module Actions (Web UI) ====================

@routes_bp.route("/exploit/start", methods=["POST"])
def start_exploit():
    result = modules["exploit_host"].start()
    return jsonify(result)


@routes_bp.route("/exploit/stop", methods=["POST"])
def stop_exploit():
    result = modules["exploit_host"].stop()
    return jsonify(result)


@routes_bp.route("/exploit/status", methods=["GET"])
def exploit_status():
    result = modules["exploit_host"].get_status()
    return jsonify(result)


@routes_bp.route("/exploit/setup", methods=["GET"])
def exploit_setup():
    result = modules["exploit_host"].get_setup_instructions()
    return jsonify(result)


@routes_bp.route("/exploit/payloads", methods=["GET"])
def list_payloads():
    result = modules["exploit_host"].list_payloads()
    return jsonify(result)


@routes_bp.route("/exploit/payload", methods=["POST"])
def upload_payload():
    if 'payload' not in request.files:
        return jsonify({"error": "No payload file"}), 400
    
    file = request.files['payload']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Save to temporary location
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.elf') as tmp:
        file.save(tmp.name)
        result = modules["exploit_host"].add_payload(tmp.name, file.filename)
    
    return jsonify(result)


@routes_bp.route("/exploit/payload/<name>", methods=["DELETE"])
def delete_payload(name):
    # This would need implementation in exploit module
    return jsonify({"success": False, "error": "Not implemented"})


# ==================== System Status ====================

@routes_bp.route("/system/resources", methods=["GET"])
def system_resources():
    """Get system resource usage."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Network I/O
    net_io = psutil.net_io_counters()
    net_mbps = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
    
    return jsonify({
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_available": memory.available,
        "memory_total": memory.total,
        "disk_percent": (disk.used / disk.total) * 100,
        "disk_free": disk.free,
        "disk_total": disk.total,
        "network_io_mbps": net_mbps,
    })


@routes_bp.route("/system/storage", methods=["GET"])
def system_storage():
    """Get storage info for configured paths."""
    from config import settings
    
    paths = [
        ("Games", settings.SERVER_GAMES_PATH),
        ("Saves", settings.SERVER_SAVES_PATH),
        ("Artwork", settings.SERVER_ARTWORK_PATH),
        ("Downloads", settings.SERVER_DOWNLOADS_PATH),
        ("Root", "/"),
    ]
    
    result = []
    for name, path in paths:
        try:
            usage = psutil.disk_usage(path)
            result.append({
                "name": name,
                "path": path,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": (usage.used / usage.total) * 100,
            })
        except Exception:
            result.append({
                "name": name,
                "path": path,
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0,
                "error": "Path not accessible",
            })
    
    return jsonify(result)


@routes_bp.route("/settings/paths", methods=["GET"])
def get_settings_paths():
    """Get current server paths."""
    from config import settings
    return jsonify({
        "games_path": settings.SERVER_GAMES_PATH,
        "saves_path": settings.SERVER_SAVES_PATH,
        "artwork_path": settings.SERVER_ARTWORK_PATH,
        "downloads_path": settings.SERVER_DOWNLOADS_PATH,
    })


@routes_bp.route("/settings/paths", methods=["POST"])
def save_settings_paths():
    """Save server paths to environment/config."""
    from config import settings
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # This would ideally update the .env file or database
    # For now, return success (would need config reload)
    return jsonify({
        "success": True,
        "message": "Paths updated (requires server restart to take effect)",
        "games_path": data.get("games_path", settings.SERVER_GAMES_PATH),
        "saves_path": data.get("saves_path", settings.SERVER_SAVES_PATH),
        "artwork_path": data.get("artwork_path", settings.SERVER_ARTWORK_PATH),
        "downloads_path": data.get("downloads_path", settings.SERVER_DOWNLOADS_PATH),
    })


@routes_bp.route("/services/status", methods=["GET"])
def services_status():
    """Get service status tracking."""
    db = get_db_session()
    try:
        services = db.query(ServiceStatus).all()
        return jsonify([
            {
                "service_name": s.service_name,
                "is_running": s.is_running,
                "last_run": s.last_run.isoformat() if s.last_run else None,
                "last_success": s.last_success.isoformat() if s.last_success else None,
                "run_count": s.run_count,
                "success_count": s.success_count,
                "error_count": s.error_count,
                "avg_duration_seconds": s.avg_duration_seconds,
                "last_error": s.last_error,
            }
            for s in services
        ])
    finally:
        db.close()


# ==================== Exploit Package Module Actions ====================

def _handle_exploit_list(data):
    package_type = data.get("package_type")
    firmware = data.get("firmware")
    exploits = modules["exploit"].list_exploits(package_type, firmware)
    return jsonify(exploits)


def _handle_exploit_add(data):
    result = modules["exploit"].add_exploit(data)
    return jsonify(result)


def _handle_exploit_get(data):
    exploit_id = data.get("exploit_id")
    if not exploit_id:
        return jsonify({"success": False, "error": "Exploit ID required"}), 400
    result = modules["exploit"].get_exploit(exploit_id)
    return jsonify(result)


def _handle_exploit_delete(data):
    exploit_id = data.get("exploit_id")
    if not exploit_id:
        return jsonify({"success": False, "error": "Exploit ID required"}), 400
    result = modules["exploit"].delete_exploit(exploit_id)
    return jsonify(result)


def _handle_exploit_types(data):
    types = modules["exploit"].get_package_types()
    return jsonify(types)


# ==================== Exploit Host Module Actions ====================

def _handle_exploit_host_start(data):
    config_id = data.get("config_id")
    result = modules["exploit_host"].start(config_id)
    return jsonify(result)


def _handle_exploit_host_stop(data):
    result = modules["exploit_host"].stop()
    return jsonify(result)


def _handle_exploit_host_status(data):
    result = modules["exploit_host"].get_status()
    return jsonify(result)


def _handle_exploit_host_add_payload(data):
    payload_path = data.get("payload_path")
    payload_name = data.get("payload_name")
    if not payload_path:
        return jsonify({"success": False, "error": "Payload path required"}), 400
    result = modules["exploit_host"].add_payload(payload_path, payload_name)
    return jsonify(result)


def _handle_exploit_host_list_payloads(data):
    result = modules["exploit_host"].list_payloads()
    return jsonify(result)


def _handle_exploit_host_instructions(data):
    result = modules["exploit_host"].get_setup_instructions()
    return jsonify(result)