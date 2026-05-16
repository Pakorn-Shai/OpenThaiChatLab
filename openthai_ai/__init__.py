from flask import Flask

from .config import Config
from .routes.api import api_bp
from .routes.main import main_bp


def create_app(config_object=Config):
    app = Flask(__name__, template_folder="../templates")
    app.config.from_object(config_object)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    return app
