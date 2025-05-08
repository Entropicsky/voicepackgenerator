"""
Routes for audio serving and streaming.
"""
from flask import Blueprint, redirect
from backend import utils_r2
from backend.utils.response_utils import make_api_response
import logging

audio_bp = Blueprint('audio', __name__)

@audio_bp.route('/audio/<path:blob_key>')
def serve_audio(blob_key):
    """Serves audio files by redirecting to a presigned R2 URL."""
    if not blob_key or '..' in blob_key or not blob_key.endswith('.mp3'):
        return make_api_response(error="Invalid audio path", status_code=400)

    logging.info(f"Request to serve audio for blob key: {blob_key}")
    try:
        presigned_url = utils_r2.generate_presigned_url(blob_key, expiration=3600)
        
        if presigned_url:
            logging.info(f"Redirecting to presigned URL for: {blob_key}")
            return redirect(presigned_url, code=302)
        else:
            if utils_r2.blob_exists(blob_key):
                 logging.error(f"Failed to generate presigned URL for existing blob: {blob_key}")
                 return make_api_response(error="Failed to generate temporary audio URL", status_code=500)
            else:
                 logging.warning(f"Audio blob not found in R2: {blob_key}")
                 return make_api_response(error="Audio file not found", status_code=404)

    except Exception as e:
        logging.exception(f"Error serving audio file {blob_key}: {e}")
        return make_api_response(error="Failed to serve audio file", status_code=500) 