# backend/app.py
from flask import Flask, jsonify, request, current_app, Response, send_from_directory
from dotenv import load_dotenv
import os
from celery.result import AsyncResult
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session

# Import celery app instance from root
from celery_app import celery_app
# Import tasks from root
import tasks
# Import utils from backend package
from . import utils_elevenlabs
from . import utils_fs
from . import models # Import the models module

# Load environment variables from .env file for local development
# Within Docker, env vars are passed by docker-compose
load_dotenv()

app = Flask(__name__)

# Initialize Database
try:
    models.init_db()
except Exception as e:
    # Log the error but allow app to continue if possible?
    # Or should failure to init DB be fatal?
    print(f"CRITICAL: Database initialization failed: {e}")
    # Depending on requirements, might exit here: sys.exit(1)

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
    """Endpoint to get available voices, supports filtering/sorting."""
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    voice_type = request.args.get('voice_type', None)
    sort = request.args.get('sort', None)
    sort_direction = request.args.get('sort_direction', None)
    page_size = request.args.get('page_size', 100, type=int)
    next_page_token = request.args.get('next_page_token', None)
    print(f"API Route /api/voices received search='{search}'")

    try:
        voices = utils_elevenlabs.get_available_voices(
            search=search,
            category=category,
            voice_type=voice_type,
            sort=sort,
            sort_direction=sort_direction,
            page_size=page_size,
            next_page_token=next_page_token
        )
        # V2 response includes more details, potentially filter/map here if needed
        # For now, return the full voice objects from V2
        return make_api_response(data=voices)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching voices via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/voices route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

@app.route('/api/generate', methods=['POST'])
def start_generation():
    """Endpoint to start an asynchronous generation task and record it."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    config_data = request.get_json()
    config_data_json = json.dumps(config_data) # For storing and passing

    required_keys = ['skin_name', 'voice_ids', 'script_csv_content', 'variants_per_line']
    if not all(key in config_data for key in required_keys):
        missing = [key for key in required_keys if key not in config_data]
        return make_api_response(error=f'Missing required configuration keys: {missing}', status_code=400)

    db: Session = next(models.get_db()) # Get DB session
    db_job = None
    try:
        # 1. Create Job record in DB
        db_job = models.GenerationJob(
            status="PENDING",
            parameters_json=config_data_json
            # submitted_at is default
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        print(f"Created GenerationJob record with DB ID: {db_job_id}")

        # 2. Enqueue Celery task, passing DB ID
        # Note: Pass primitive types to Celery tasks if possible
        task = tasks.run_generation.delay(db_job_id, config_data_json)
        print(f"Enqueued generation task with Celery ID: {task.id} for DB Job ID: {db_job_id}")

        # 3. Update Job record with Celery task ID
        db_job.celery_task_id = task.id
        db.commit()

        # 4. Return IDs to frontend
        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)

    except Exception as e:
        print(f"Error during job submission/enqueueing: {e}")
        # Attempt to rollback DB changes if job was created but task failed?
        # (Complex, maybe just mark DB job as FAILED here?)
        if db_job and db_job.id:
            try:
                 # Mark DB job as failed if Celery enqueue failed
                 db_job.status = "SUBMIT_FAILED"
                 db_job.result_message = f"Failed to enqueue Celery task: {e}"
                 db.commit()
            except Exception as db_err:
                 print(f"Failed to update job status after enqueue error: {db_err}")
                 db.rollback() # Rollback any partial changes

        return make_api_response(error="Failed to start generation task", status_code=500)
    finally:
        db.close() # Ensure session is closed

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

# --- Job History API Endpoint --- #

@app.route('/api/jobs', methods=['GET'])
def list_generation_jobs():
    """Lists previously submitted generation jobs from the database."""
    db: Session = next(models.get_db())
    try:
        # Query jobs, order by most recent submission
        jobs = db.query(models.GenerationJob).order_by(models.GenerationJob.submitted_at.desc()).all()
        
        # Convert SQLAlchemy objects to dictionaries for JSON response
        # Handle potential JSON parsing for results/params if needed on frontend
        job_list = [
            {
                "id": job.id,
                "celery_task_id": job.celery_task_id,
                "status": job.status,
                "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "parameters_json": job.parameters_json, # Keep as string for now
                "result_message": job.result_message,
                "result_batch_ids_json": job.result_batch_ids_json # Keep as string for now
            }
            for job in jobs
        ]
        return make_api_response(data=job_list)
    except Exception as e:
        print(f"Error listing jobs: {e}")
        return make_api_response(error="Failed to list generation jobs", status_code=500)
    finally:
        db.close()

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