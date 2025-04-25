# backend/routes/voice_design_routes.py

from flask import Blueprint, request, jsonify, Response
import logging

# Assuming utils and helpers are accessible, adjust imports as necessary
from backend import utils_elevenlabs
from backend.app import make_api_response, VOICE_PREVIEW_TEXT # Example imports

voice_design_bp = Blueprint('voice_design_api', __name__, url_prefix='/api')

# Routes will be moved here... 