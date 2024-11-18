from flask import Flask
from flask_cors import CORS
from src.application import api_blueprint

def create_app():
    """
    Application factory for creating the Flask app instance.
    """
    app = Flask(__name__)

    CORS(app)

    app.register_blueprint(api_blueprint)

    return app
