# backend/app.py
from flask import Flask, jsonify, request, current_app, Response, send_from_directory, send_file
from dotenv import load_dotenv
import os
from celery.result import AsyncResult
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import zipfile
import io
import base64

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
    next_page_token = request.args.get('next_page_token', None)
    print(f"API Route /api/voices received search='{search}'")

    try:
        voices = utils_elevenlabs.get_available_voices(
            search=search,
            category=category,
            voice_type=voice_type,
            sort=sort,
            sort_direction=sort_direction,
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

@app.route('/api/models', methods=['GET'])
def get_models():
    """Endpoint to get available models, supports capability filtering."""
    capability = request.args.get('capability', None)
    require_sts = capability == 'sts'
    print(f"API Route /api/models received capability='{capability}', require_sts={require_sts}")
    
    try:
        models_list = utils_elevenlabs.get_available_models(require_sts=require_sts)
        
        model_options = [
            {"model_id": m.get('model_id'), "name": m.get('name')}
            for m in models_list if m.get('model_id') and m.get('name')
        ]
        return make_api_response(data=model_options)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching models via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/models route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

# --- Job History API Endpoint --- #

@app.route('/api/jobs', methods=['GET'])
def list_generation_jobs():
    """Lists previously submitted generation jobs from the database."""
    db: Session = next(models.get_db())
    try:
        jobs = db.query(models.GenerationJob).order_by(models.GenerationJob.submitted_at.desc()).all()
        job_list = [
            {
                "id": job.id,
                "celery_task_id": job.celery_task_id,
                "status": job.status,
                "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "parameters_json": job.parameters_json, 
                "result_message": job.result_message,
                "result_batch_ids_json": job.result_batch_ids_json, 
                "job_type": job.job_type,
                "target_batch_id": job.target_batch_id,
                "target_line_key": job.target_line_key
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

@app.route('/api/batch/<batch_id>/download', methods=['GET'])
def download_batch_zip(batch_id):
    """Creates and returns a ZIP archive of the batch directory contents."""
    try:
        batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not batch_dir or not batch_dir.is_dir():
            return make_api_response(error=f"Batch '{batch_id}' not found", status_code=404)

        # Get the parent directory name (VoiceName-VoiceID) for the zip filename
        zip_filename_base = batch_dir.parent.name
        zip_download_name = f"{zip_filename_base}.zip"

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add metadata.json and LOCKED if they exist
            meta_file = batch_dir / 'metadata.json'
            lock_file = batch_dir / 'LOCKED'
            if meta_file.is_file():
                 zf.write(meta_file, arcname=meta_file.name)
            if lock_file.is_file():
                 zf.write(lock_file, arcname=lock_file.name)

            # Add contents of takes/
            takes_dir = batch_dir / 'takes'
            if takes_dir.is_dir():
                for root, _, files in os.walk(takes_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Archive name relative to batch_dir (e.g., takes/file.mp3)
                        arcname = file_path.relative_to(batch_dir).as_posix()
                        zf.write(file_path, arcname=arcname)
            
            # Add contents of ranked/
            ranked_dir = batch_dir / 'ranked'
            if ranked_dir.is_dir():
                 for root, _, files in os.walk(ranked_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Archive name relative to batch_dir (e.g., ranked/01/file.mp3)
                        arcname = file_path.relative_to(batch_dir).as_posix()
                        # Check if it's a symlink and add the *target* file content if possible,
                        # or just add the link itself if adding target fails?
                        # For simplicity and to avoid issues with broken links, let's just add the link itself.
                        # If the target file needs to be included regardless of link, 
                        # we'd need to resolve it and add with its content, being careful about duplicates.
                        # Add the file/link with its relative path
                        zf.write(file_path, arcname=arcname)
                        
        memory_file.seek(0)

        # Consider checking if *anything* was added beyond metadata/lock?

        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_download_name # Use the voice folder name
        )

    except utils_fs.FilesystemError as e:
        print(f"Filesystem error creating zip for {batch_id}: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error creating zip for {batch_id}: {e}")
        return make_api_response(error="Failed to create batch zip file", status_code=500)

@app.route('/api/batch/<batch_id>/regenerate_line', methods=['POST'])
def regenerate_line(batch_id):
    """Endpoint to start a line regeneration task."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    
    data = request.get_json()
    required_keys = ['line_key', 'line_text', 'num_new_takes', 'settings', 'replace_existing']
    if not all(key in data for key in required_keys):
        missing = [key for key in required_keys if key not in data]
        return make_api_response(error=f'Missing required keys for regeneration: {missing}', status_code=400)

    line_key = data['line_key']
    line_text = data['line_text']
    num_new_takes = data['num_new_takes']
    settings = data['settings'] # This should be the GenerationConfig subset
    replace_existing = data['replace_existing']
    settings_json = json.dumps(settings)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check if target batch exists before creating job
        target_batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not target_batch_dir or not target_batch_dir.is_dir():
             return make_api_response(error=f"Target batch '{batch_id}' not found for regeneration", status_code=404)
        
        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING",
            job_type="line_regen", # Mark job type
            target_batch_id=batch_id,
            target_line_key=line_key,
            parameters_json=json.dumps(data) # Store all input params
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        print(f"Created Line Regeneration Job record with DB ID: {db_job_id}")

        # Enqueue Celery task
        task = tasks.regenerate_line_takes.delay(
            db_job_id, batch_id, line_key, line_text, 
            num_new_takes, settings_json, replace_existing
        )
        print(f"Enqueued line regen task: Celery ID {task.id}, DB Job ID {db_job_id}")

        # Update Job record with Celery task ID
        db_job.celery_task_id = task.id
        db.commit()

        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)

    except Exception as e:
        print(f"Error submitting line regeneration job: {e}")
        if db_job and db_job.id:
            try:
                 db_job.status = "SUBMIT_FAILED"
                 db_job.result_message = f"Failed to enqueue Celery task: {e}"
                 db.commit()
            except Exception as db_err:
                 print(f"Failed to update job status after enqueue error: {db_err}")
                 db.rollback()
        return make_api_response(error="Failed to start line regeneration task", status_code=500)
    finally:
        db.close()

@app.route('/api/batch/<batch_id>/speech_to_speech', methods=['POST'])
def start_speech_to_speech_line(batch_id):
    """Endpoint to start a line speech-to-speech task."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    required_keys = [
        'line_key', 'source_audio_b64', 'num_new_takes', 
        'target_voice_id', 'model_id', 'settings', 'replace_existing'
    ]
    if not all(key in data for key in required_keys):
        missing = [key for key in required_keys if key not in data]
        return make_api_response(error=f'Missing required keys for STS: {missing}', status_code=400)

    line_key = data['line_key']
    source_audio_b64 = data['source_audio_b64']
    num_new_takes = data['num_new_takes']
    target_voice_id = data['target_voice_id']
    model_id = data['model_id']
    settings = data['settings'] # Should contain stability, similarity_boost
    replace_existing = data['replace_existing']
    settings_json = json.dumps(settings)

    # Basic validation
    if not source_audio_b64 or not source_audio_b64.startswith('data:audio'):
        return make_api_response(error='Invalid or missing source audio data (expecting base64 data URI)', status_code=400)
    if not isinstance(num_new_takes, int) or num_new_takes <= 0:
        return make_api_response(error='Invalid number of new takes', status_code=400)

    # Extract raw base64 data
    try:
        header, encoded = source_audio_b64.split(';base64,', 1)
        # audio_data_bytes = base64.b64decode(encoded)
        # PASS base64 string directly to Celery task to avoid large memory usage here?
        # Task can decode it.
    except Exception as e:
        print(f"Error decoding base64 audio: {e}")
        return make_api_response(error='Failed to decode source audio data', status_code=400)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check target batch exists
        target_batch_dir = utils_fs.get_batch_dir(AUDIO_ROOT, batch_id)
        if not target_batch_dir or not target_batch_dir.is_dir():
             return make_api_response(error=f"Target batch '{batch_id}' not found for STS", status_code=404)
        
        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING",
            job_type="sts_line_regen", # Mark job type
            target_batch_id=batch_id,
            target_line_key=line_key,
            parameters_json=json.dumps({ # Store specific STS params
                 'target_voice_id': target_voice_id,
                 'model_id': model_id,
                 'num_new_takes': num_new_takes,
                 'settings': settings,
                 'replace_existing': replace_existing,
                 'source_audio_info': header # Store mime type etc.
            })
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        print(f"Created STS Line Job record with DB ID: {db_job_id}")

        # Enqueue Celery task, pass base64 string
        task = tasks.run_speech_to_speech_line.delay(
            db_job_id, batch_id, line_key, source_audio_b64, 
            num_new_takes, target_voice_id, model_id, settings_json, replace_existing
        )
        print(f"Enqueued STS line task: Celery ID {task.id}, DB Job ID {db_job_id}")

        db_job.celery_task_id = task.id
        db.commit()

        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)

    except Exception as e:
        print(f"Error submitting STS line job: {e}")
        if db_job and db_job.id: # Attempt to mark DB job as failed
            try:
                 db_job.status = "SUBMIT_FAILED"
                 db_job.result_message = f"Failed to enqueue Celery task: {e}"
                 db.commit()
            except Exception as db_err:
                 print(f"Failed to update job status after enqueue error: {db_err}")
                 db.rollback()
        return make_api_response(error="Failed to start speech-to-speech task", status_code=500)
    finally:
        db.close()

# --- NEW: Voice Design API Endpoints --- #

@app.route('/api/voice-design/previews', methods=['POST'])
def create_voice_design_previews():
    """Endpoint to generate voice previews based on description and settings."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    
    # Extract parameters from request data
    voice_description = data.get('voice_description')
    text = data.get('text')
    auto_generate_text = data.get('auto_generate_text', False)
    loudness = data.get('loudness')
    quality = data.get('quality')
    seed = data.get('seed')
    guidance_scale = data.get('guidance_scale')
    output_format = data.get('output_format', 'mp3_44100_128')

    if not voice_description:
         return make_api_response(error="Missing required field: voice_description", status_code=400)

    try:
        previews, generated_text = utils_elevenlabs.create_voice_previews(
            voice_description=voice_description,
            text=text,
            auto_generate_text=auto_generate_text,
            loudness=loudness,
            quality=quality,
            seed=seed,
            guidance_scale=guidance_scale,
            output_format=output_format
        )
        return make_api_response(data={"previews": previews, "text": generated_text})
    except ValueError as ve:
        # Catch validation errors from the utility function
        print(f"Validation error creating voice previews: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error creating voice previews: {e}")
        # Determine appropriate status code based on error? (e.g., 422 for validation)
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error creating voice previews: {e}")
        return make_api_response(error="Failed to create voice previews", status_code=500)

@app.route('/api/voice-design/save', methods=['POST'])
def save_voice_design_preview():
    """Endpoint to save a selected voice preview to the library."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    generated_voice_id = data.get('generated_voice_id')
    voice_name = data.get('voice_name')
    voice_description = data.get('voice_description')
    labels = data.get('labels') # Optional

    if not all([generated_voice_id, voice_name, voice_description]):
        missing = [k for k, v in {'generated_voice_id': generated_voice_id, 'voice_name': voice_name, 'voice_description': voice_description}.items() if not v]
        return make_api_response(error=f"Missing required fields: {missing}", status_code=400)
        
    try:
        saved_voice_details = utils_elevenlabs.save_generated_voice(
            generated_voice_id=generated_voice_id,
            voice_name=voice_name,
            voice_description=voice_description,
            labels=labels
        )
        # Maybe map this response to our VoiceOption type before sending?
        # For now, just return the full details.
        return make_api_response(data=saved_voice_details)
    except ValueError as ve:
        print(f"Validation error saving voice: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error saving voice: {e}")
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error saving voice: {e}")
        return make_api_response(error="Failed to save voice", status_code=500)

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