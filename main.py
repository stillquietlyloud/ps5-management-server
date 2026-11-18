"""Main entry point for PS5 Management Server."""
from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    from config import settings
    socketio.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        debug=settings.DEBUG,
        allow_unsafe_werkzeug=True
    )