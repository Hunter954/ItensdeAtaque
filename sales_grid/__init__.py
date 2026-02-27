from flask import Flask
from .config import Config
from .services.github_store import load_data

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    from .blueprints.auth import bp as auth_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.team import bp as team_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.api import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    return app  # ← sem load_data() aqui


