# backend/routes/generation_routes.py

from flask import Blueprint, request, jsonify, Response, redirect, send_file
from sqlalchemy.orm import Session
from celery.result import AsyncResult
import logging
import json
import zipfile
import io
import openai # Assuming optimize needs this
import os # Assuming optimize needs this

# Assuming models, tasks, helpers, utils are accessible, adjust imports as necessary
from backend import models, tasks, utils_r2 # Added utils_r2
from backend.celery_app import celery
from backend.app import make_api_response, model_to_dict # Example import

generation_bp = Blueprint('generation_api', __name__, url_prefix='/api')

# Routes will be moved here... 