# backend/app.py
from flask import Flask, jsonify, request, current_app, Response, redirect, send_file
from dotenv import load_dotenv
import os
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from typing import Dict, List
from datetime import datetime

# Import utility modules
from . import utils_elevenlabs
from . import utils_r2
from . import models

# Load environment variables from .env file for local development
# Within Docker, env vars are passed by docker-compose
load_dotenv()

app = Flask(__name__, instance_relative_config=True)

# Configure logging
# Read log level from environment variable, default to INFO
log_level_name = os.environ.get('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_name, logging.INFO)

# Configure logging with the determined level
logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.info(f"Logging configured with level: {logging.getLevelName(log_level)}")

# Add ProxyFix middleware to handle X-Forwarded-* headers correctly
# Trust 2 proxies (Heroku Router + Nginx Web Dyno)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=2, x_proto=1, x_host=1, x_prefix=1
)

# Initialize Flask-Migrate
from flask_migrate import Migrate
migrate = Migrate(app, models.engine)

# Initialize Database
try:
    models.init_db()
except Exception as e:
    # Log the error but allow app to continue if possible
    print(f"CRITICAL: Database initialization failed: {e}")

# Example: Access an env var
print(f"Flask App: ELEVENLABS_API_KEY loaded? {'Yes' if os.getenv('ELEVENLABS_API_KEY') else 'No'}")

# --- Helper Function --- #
def make_api_response(data: dict | List[dict] = None, error: str = None, status_code: int = 200) -> Response:
    if error:
        response_data = {"error": error}
        status_code = status_code if status_code >= 400 else 500
    else:
        response_data = {"data": data if data is not None else {}}
    return jsonify(response_data), status_code

# --- Helper to convert model instance to dict --- #
def model_to_dict(instance, keys=None):
    """Converts a SQLAlchemy model instance into a dictionary."""
    if instance is None:
        return None
    data = {}
    columns = instance.__table__.columns.keys() if keys is None else keys
    for column in columns:
        value = getattr(instance, column)
        # Convert datetime objects to ISO format string
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column] = value
    return data

# --- API Endpoints --- #

@app.route('/api/ping')
def ping():
    print("Received request for /api/ping")
    return make_api_response(data={"message": "pong from Flask!"})

# --- Register Blueprints --- #
from backend.routes.vo_template_routes import vo_template_bp
from backend.routes.vo_script_routes import vo_script_bp
from backend.routes.voice_routes import voice_bp
from backend.routes.generation_routes import generation_bp
from backend.routes.batch_routes import batch_bp
from backend.routes.audio_routes import audio_bp
from backend.routes.task_routes import task_bp

app.register_blueprint(vo_template_bp)
app.register_blueprint(vo_script_bp)
app.register_blueprint(voice_bp)
app.register_blueprint(generation_bp)
app.register_blueprint(batch_bp)
app.register_blueprint(audio_bp)
app.register_blueprint(task_bp)

# We don't need the app.run() block here when using 'flask run' or gunicorn/waitress