# backend/routes/script_routes.py

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import logging
import csv
import io

# Assuming models and helpers are accessible, adjust imports as necessary
from backend import models
from backend.app import make_api_response, model_to_dict

script_bp = Blueprint('script_api', __name__, url_prefix='/api')

# Routes will be moved here... 