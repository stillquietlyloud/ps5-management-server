"""API blueprints registration."""
from flask import Blueprint
from app.api.routes import routes_bp


def register_blueprints(app):
    """Register all API blueprints."""
    app.register_blueprint(routes_bp, url_prefix="/api")