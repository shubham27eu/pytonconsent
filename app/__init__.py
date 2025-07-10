# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from .api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # To create tables if they don't exist
    with app.app_context():
        db.create_all() # This will be moved later to a proper migration setup

    return app
