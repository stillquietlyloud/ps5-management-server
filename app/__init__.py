"""Main application factory for PS5 Management Server."""
import logging
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from config import settings
from app.database import init_db
from config import ensure_data_directories


# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)

socketio = SocketIO()

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(settings)
    
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize database
    with app.app_context():
        init_db()
        ensure_data_directories()
        logging.info("Database initialized.")

    # Initialize Socket.IO
    socketio.init_app(app, cors_allowed_origins="*")

    # Register blueprints (modules)
    from app.api import register_blueprints
    register_blueprints(app)
    
    # Basic routes
    @app.route("/")
    def index():
        return render_template("index.html", app_name="PS5 Management Server")

    @app.route("/status")
    def status_page():
        return render_template("status.html", app_name="PS5 Management Server")

    @app.route("/api/health")
    def health_check():
        return jsonify({"status": "ok", "version": "1.0.0"})

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    logging.info(f"Application created and configured.")
    return app