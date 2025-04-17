# backend/app.py
from flask import Flask, jsonify, request, current_app, Response, send_from_directory
from dotenv import load_dotenv
import os
from celery.result import AsyncResult
import json
from pathlib import Path
from datetime import datetime, timezone

# Import celery app instance from root
from celery_app import celery_app
# Import tasks from root
import tasks
# Import utils from backend package
from . import utils_elevenlabs
from . import utils_fs

# Load environment variables from .env file for local development
# Within Docker, env vars are passed by docker-compose
load_dotenv()

app = Flask(__name__)

# Configure CORS if needed, for example:
# from flask_cors import CORS
# CORS(app) # Allow all origins

# Example: Access an env var
print(f"Flask App: ELEVENLABS_API_KEY loaded? {'Yes' if os.getenv('ELEVENLABS_API_KEY') else 'No'}")

# Get the configured audio root directory
# Ensure this is set correctly in docker-compose.yml environment for the backend service
AUDIO_ROOT = Path(os.getenv('AUDIO_ROOT', './output'))

print(f"Flask App: Using AUDIO_ROOT={AUDIO_ROOT.resolve()}")

# --- Helper Function --- #
def make_api_response(data: dict = None, error: str = None, status_code: int = 200) -> Response:
    if error:
        response_data = {"error": error}
        status_code = status_code if status_code >= 400 else 500
    else:
        response_data = {"data": data if data is not None else {}}
    return jsonify(response_data), status_code

# --- API Endpoints --- #

@app.route('/api/ping')
def ping():
    print("Received request for /api/ping")
    return make_api_response(data={"message": "pong from Flask!"})

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Endpoint to get available voices from ElevenLabs."""
    try:
        # TODO: Add caching for this endpoint
        voices = utils_elevenlabs.get_available_voices()
        # Simplify the response to only include id and name
        voice_list = [
            {"id": v.get('voice_id'), "name": v.get('name')}
            for v in voices if v.get('voice_id') and v.get('name')
        ]
        return make_api_response(data=voice_list)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching voices: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error fetching voices: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

@app.route('/api/generate', methods=['POST'])
def start_generation():
    """Endpoint to start an asynchronous generation task."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    config_data = request.get_json()

    # Basic validation (can be expanded)
    required_keys = ['skin_name', 'voice_ids', 'script_csv_content', 'variants_per_line']
    if not all(key in config_data for key in required_keys):
        missing = [key for key in required_keys if key not in config_data]
        return make_api_response(error=f'Missing required configuration keys: {missing}', status_code=400)

    try:
        # Call the task function directly via the imported module
        task = tasks.run_generation.delay(json.dumps(config_data))
        print(f"Enqueued generation task with ID: {task.id}")
        return make_api_response(data={'task_id': task.id}, status_code=202)
    except Exception as e:
        print(f"Error enqueueing generation task: {e}")
        return make_api_response(error="Failed to start generation task", status_code=500)

@app.route('/api/generate/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Endpoint to check the status of a generation task."""
    try:
        # Use the celery_app instance imported from root
        task_result = AsyncResult(task_id, app=celery_app)

        response_data = {
            'task_id': task_id,
            'status': task_result.status, # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
            'info': None
        }

        if task_result.status == 'PENDING':
            response_data['info'] = {'status': 'Task is waiting to be processed.'}
        elif task_result.status == 'FAILURE':
            # task_result.info should contain the exception
            response_data['info'] = {'error': str(task_result.info), 'traceback': task_result.traceback}
            # Return 200 OK, but indicate failure in the payload
        elif task_result.status == 'SUCCESS':
            # task_result.info should contain the return value of the task
            response_data['info'] = task_result.info
        else:
            # For STARTED, RETRY, or custom states, info might be a dict (e.g., progress)
            if isinstance(task_result.info, dict):
                response_data['info'] = task_result.info
            else:
                response_data['info'] = {'status': str(task_result.info)}

        return make_api_response(data=response_data)

    except Exception as e:
        print(f"Error checking task status for {task_id}: {e}")
        return make_api_response(error="Failed to retrieve task status", status_code=500)

# --- Ranking API Endpoints --- #

@app.route('/api/batches', methods=['GET'])
def list_batches():
    """Lists available batches by scanning the filesystem."""
    try:
        batches = utils_fs.find_batches(AUDIO_ROOT)
        return make_api_response(data=batches)
    except Exception as e:
        print(f"Error listing batches: {e}")
        return make_api_response(error="Failed to list batches", status_code=500)

@app.route('/api/batch/<batch_id>', methods=['GET'])
def get_batch_metadata(batch_id):
    """Gets the metadata for a specific batch."""
    try:
        batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not batch_dir or not batch_dir.is_dir():
            return make_api_response(error=f"Batch '{batch_id}' not found", status_code=404)
        metadata = utils_fs.load_metadata(batch_dir)
        return make_api_response(data=metadata)
    except utils_fs.FilesystemError as e:
        print(f"Filesystem error getting metadata for {batch_id}: {e}")
        # Could be 404 if metadata file specifically not found
        return make_api_response(error=str(e), status_code=404 if "not found" in str(e).lower() else 500)
    except Exception as e:
        print(f"Unexpected error getting metadata for {batch_id}: {e}")
        return make_api_response(error="Failed to get batch metadata", status_code=500)

@app.route('/api/batch/<batch_id>/take/<path:filename>', methods=['PATCH'])
def update_take_rank(batch_id, filename):
    """Updates the rank of a specific take within a batch."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    new_rank = data.get('rank')

    # Validate rank
    if new_rank is not None:
        try:
            new_rank = int(new_rank)
            if not (1 <= new_rank <= 5):
                raise ValueError()
        except (ValueError, TypeError):
            return make_api_response(error="Invalid rank value. Must be integer 1-5 or null.", status_code=400)
    # Allow rank to be null to un-rank

    try:
        batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not batch_dir or not batch_dir.is_dir():
            return make_api_response(error=f"Batch '{batch_id}' not found", status_code=404)

        # Check if locked
        if utils_fs.is_locked(batch_dir):
            return make_api_response(error="Batch is locked and cannot be modified", status_code=423) # 423 Locked

        metadata = utils_fs.load_metadata(batch_dir)
        take_updated = False
        for take in metadata.get('takes', []):
            # Use Path comparison for robustness, though simple string match works if only basename used
            if Path(take.get('file', '')).name == Path(filename).name:
                take['rank'] = new_rank
                take['ranked_at'] = datetime.now(timezone.utc).isoformat() if new_rank is not None else None
                take_updated = True
                break

        if not take_updated:
            return make_api_response(error=f"Take '{filename}' not found in batch '{batch_id}'", status_code=404)

        # Save updated metadata *before* rebuilding symlinks
        utils_fs.save_metadata(batch_dir, metadata)
        # Rebuild symlinks based on the *entire* updated metadata
        utils_fs.rebuild_symlinks(batch_dir, metadata)

        return make_api_response(data={"status": "Rank updated successfully"})

    except utils_fs.FilesystemError as e:
        print(f"Filesystem error updating rank for {filename} in {batch_id}: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error updating rank for {filename} in {batch_id}: {e}")
        return make_api_response(error="Failed to update take rank", status_code=500)

@app.route('/api/batch/<batch_id>/lock', methods=['POST'])
def lock_batch_endpoint(batch_id):
    """Locks a batch, preventing further rank updates."""
    try:
        batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not batch_dir or not batch_dir.is_dir():
            return make_api_response(error=f"Batch '{batch_id}' not found", status_code=404)

        if utils_fs.is_locked(batch_dir):
            return make_api_response(data={"locked": True, "message": "Batch already locked"})

        # Create LOCK file first
        utils_fs.lock_batch(batch_dir)

        # Then update metadata
        try:
            metadata = utils_fs.load_metadata(batch_dir)
            metadata['ranked_at_utc'] = datetime.now(timezone.utc).isoformat()
            utils_fs.save_metadata(batch_dir, metadata)
        except Exception as meta_e:
            # Attempt to rollback lock file? Or just log error?
            print(f"Warning: Batch {batch_id} LOCK file created, but failed to update metadata timestamp: {meta_e}")
            # Still return success as the lock *file* is the primary mechanism
            pass

        return make_api_response(data={"locked": True})

    except utils_fs.FilesystemError as e:
        print(f"Filesystem error locking batch {batch_id}: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error locking batch {batch_id}: {e}")
        return make_api_response(error="Failed to lock batch", status_code=500)

# --- Audio Streaming Endpoint --- #

@app.route('/audio/<path:relpath>')
def serve_audio(relpath):
    """Serves audio files from the AUDIO_ROOT directory."""
    # Security: Ensure relpath doesn't escape AUDIO_ROOT. Pathlib should help.
    # Construct the full path relative to AUDIO_ROOT
    try:
        # Ensure AUDIO_ROOT is absolute for safe joining
        abs_audio_root = AUDIO_ROOT.resolve()
        full_path = abs_audio_root.joinpath(relpath).resolve()

        # Double-check the requested path is still within AUDIO_ROOT
        if abs_audio_root not in full_path.parents:
             raise ValueError("Attempted path traversal")

        directory = full_path.parent
        filename = full_path.name

        print(f"Serving audio: directory='{directory}', filename='{filename}'")

        # Use send_from_directory for safety and handling Range requests
        return send_from_directory(directory, filename, conditional=True)

    except ValueError as e:
        print(f"Security warning or invalid path: {e} for relpath: {relpath}")
        return make_api_response(error="Invalid audio path", status_code=400)
    except FileNotFoundError:
        return make_api_response(error="Audio file not found", status_code=404)
    except Exception as e:
        print(f"Error serving audio file {relpath}: {e}")
        return make_api_response(error="Failed to serve audio file", status_code=500)

# We don't need the app.run() block here when using 'flask run' or gunicorn/waitress 