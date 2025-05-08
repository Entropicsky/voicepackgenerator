# backend/routes/batch_routes.py
"""
Routes for batch management, including listing, retrieving, and modifying batches.
"""
from flask import Blueprint, request, send_file, jsonify, Response, stream_with_context, abort
from sqlalchemy.orm import Session
from backend import models, utils_r2, tasks
from backend.models import get_db
from backend.utils.response_utils import make_api_response
from backend.tasks import regenerate_line_takes, run_speech_to_speech_line
import logging
import json
from datetime import datetime, timezone
import io
import zipfile
from urllib.parse import unquote_plus # Use unquote_plus for path decoding

batch_bp = Blueprint('batch', __name__, url_prefix='/api')

@batch_bp.route('/batches', methods=['GET'])
def list_batches():
    """Lists available batches by querying successful jobs from the database."""
    logging.info("--- Entered /api/batches endpoint --- ")
    try:
        db: Session = next(models.get_db())
        batches = []
        try:
            logging.info("Querying successful generation jobs...")
            successful_jobs = (
                db.query(models.GenerationJob)
                .filter(
                    models.GenerationJob.status.in_(["SUCCESS", "COMPLETED_WITH_ERRORS"]),
                    models.GenerationJob.result_batch_ids_json.isnot(None)
                )
                .order_by(models.GenerationJob.completed_at.desc())
                .all()
            )
            logging.info(f"Found {len(successful_jobs)} potential jobs.")

            processed_prefixes = set()
            for job in successful_jobs:
                try:
                    # Prefixes are stored as a JSON list string
                    prefixes_or_ids = json.loads(job.result_batch_ids_json)
                    if isinstance(prefixes_or_ids, list):
                        for item in prefixes_or_ids:
                            # Check if it looks like a prefix (contains slashes)
                            if isinstance(item, str) and '/' in item:
                                prefix = item
                                if prefix not in processed_prefixes:
                                    parts = prefix.split('/')
                                    if len(parts) >= 3:
                                         batch_info = {
                                             'batch_prefix': prefix, # This is the ID now
                                             'skin_name': parts[0],
                                             'voice_name': parts[1],
                                             'id': parts[2], # The original timestamp-id part
                                             'generated_at_utc': None # TODO: Consider fetching this if needed
                                         }
                                         batches.append(batch_info)
                                         processed_prefixes.add(prefix)
                                    else:
                                         logging.warning(f"Unexpected batch prefix format in job {job.id}: {prefix}")
                            elif isinstance(item, str): # Looks like an old batch_id
                                 logging.warning(f"Found old-style batch ID in job {job.id}: {item}. Skipping.")
                            else:
                                 logging.warning(f"Found non-string item in result_batch_ids_json for job {job.id}: {item}")

                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse result_batch_ids_json for job {job.id}: {job.result_batch_ids_json}")

        finally:
             db.close()

        logging.info(f"--- Exiting /api/batches successfully. Returning {len(batches)} batches. ---")
        return make_api_response(data=batches)
    except Exception as e:
        logging.exception(f"--- Error in /api/batches: {e} ---")
        return make_api_response(error="Failed to list batches", status_code=500)

@batch_bp.route('/batch/<path:batch_prefix>', methods=['GET'])
def get_batch_metadata(batch_prefix):
    """Gets the metadata for a specific batch prefix from R2."""
    # batch_prefix comes URL-decoded automatically by Flask
    if not batch_prefix or '..' in batch_prefix: # Basic security check
        return make_api_response(error="Invalid batch prefix", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    logging.info(f"Attempting to fetch metadata from R2: {metadata_blob_key}") # Use logging

    try:
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            logging.warning(f"Metadata blob not found for prefix '{batch_prefix}'") # Use logging
            return make_api_response(error=f"Metadata not found for batch prefix '{batch_prefix}'", status_code=404)

        # Decode and parse JSON
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            return make_api_response(data=metadata)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Failed to parse metadata JSON for {metadata_blob_key}: {e}")
            return make_api_response(error="Failed to parse batch metadata", status_code=500)

    except Exception as e:
        logging.exception(f"Unexpected error getting metadata for {batch_prefix}: {e}")
        return make_api_response(error="Failed to get batch metadata", status_code=500)

@batch_bp.route('/batch/<path:batch_prefix>/take/<path:filename>', methods=['PATCH'])
def update_take_rank(batch_prefix, filename):
    """Updates the rank of a specific take within a batch by modifying metadata in R2."""
    # Basic security check
    if not batch_prefix or '..' in batch_prefix:
        return make_api_response(error="Invalid batch prefix", status_code=400)
    if not filename or '..' in filename or not filename.endswith('.mp3'):
        return make_api_response(error="Invalid filename", status_code=400)

    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    new_rank = data.get('rank')

    if new_rank is not None:
        try:
            new_rank = int(new_rank)
            if not (1 <= new_rank <= 6): raise ValueError()
        except (ValueError, TypeError):
            return make_api_response(error="Invalid rank value. Must be integer 1-6 or null.", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    logging.info(f"Updating rank for take '{filename}' in prefix '{batch_prefix}'. New rank: {new_rank}") # Use logging

    try:
        # 1. Download current metadata
        logging.info(f"Downloading metadata: {metadata_blob_key}") # Use logging
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            return make_api_response(error=f"Metadata not found for batch '{batch_prefix}'", status_code=404)
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
             logging.error(f"Failed to parse metadata JSON for {metadata_blob_key}: {e}")
             return make_api_response(error="Failed to parse batch metadata for update", status_code=500)

        # 2. Find and update the take
        take_updated = False
        updated_take_info = None
        for take in metadata.get('takes', []):
             if take.get('file') == filename:
                 take['rank'] = new_rank
                 take['ranked_at'] = datetime.now(timezone.utc).isoformat() if new_rank is not None else None
                 take_updated = True
                 updated_take_info = take
                 logging.info(f"Found and updated take metadata for {filename}") # Use logging
                 break

        if not take_updated:
            return make_api_response(error=f"Take '{filename}' not found in batch '{batch_prefix}'", status_code=404)

        # 3. Upload the modified metadata (overwrite)
        logging.info(f"Uploading updated metadata: {metadata_blob_key}") # Use logging
        updated_metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
        upload_success = utils_r2.upload_blob(
            blob_name=metadata_blob_key,
            data=updated_metadata_bytes,
            content_type='application/json'
        )

        if not upload_success:
             logging.error(f"Failed to upload updated metadata for {metadata_blob_key}")
             return make_api_response(error="Failed to save updated rank to storage", status_code=500)

        logging.info(f"Successfully updated rank for {filename} in {batch_prefix}") # Use logging
        return make_api_response(data={
            "status": "Rank updated successfully",
            "updated_take": updated_take_info
        })

    except Exception as e:
        logging.exception(f"Unexpected error updating rank for {filename} in {batch_prefix}: {e}")
        return make_api_response(error="Failed to update take rank", status_code=500)

@batch_bp.route('/batch/<path:batch_prefix>/regenerate_line', methods=['POST'])
def regenerate_line(batch_prefix):
    """Endpoint to start a line regeneration task, using batch prefix."""
    if not request.is_json: return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    required_keys = ['line_key', 'line_text', 'num_new_takes', 'settings', 'replace_existing']
    if not all(key in data for key in required_keys):
        missing = [key for key in required_keys if key not in data]; 
        return make_api_response(error=f'Missing keys: {missing}', status_code=400)

    line_key = data['line_key']
    line_text = data['line_text']
    num_new_takes = data['num_new_takes']
    settings = data['settings']
    replace_existing = data['replace_existing']
    update_script = data.get('update_script', False)
    settings_json = json.dumps(settings)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check if target batch metadata exists in R2
        metadata_blob_key = f"{batch_prefix}/metadata.json"
        if not utils_r2.blob_exists(metadata_blob_key):
             return make_api_response(error=f"Target batch prefix '{batch_prefix}' not found for regeneration", status_code=404)

        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING", job_type="line_regen",
            target_batch_id=batch_prefix, # Store the prefix
            target_line_key=line_key,
            parameters_json=json.dumps(data)
        )
        db.add(db_job); db.commit(); db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created Line Regen Job DB ID: {db_job_id} for prefix {batch_prefix}") # Use logging

        # Enqueue Celery task, passing the BATCH PREFIX
        task = regenerate_line_takes.delay(
            db_job_id, batch_prefix, line_key, line_text, # Pass prefix as batch_id
            num_new_takes, settings_json, replace_existing, update_script
        )
        logging.info(f"Enqueued line regen task: Celery ID {task.id}, DB Job ID {db_job_id}") # Use logging
        
        # Update job record with task ID
        db_job.celery_task_id = task.id; db.commit()
        
        # Prepare response with clear logging
        response_data = {'task_id': task.id, 'job_id': db_job_id}
        logging.info(f"Returning regenerate_line response: {response_data}")
        
        return make_api_response(data=response_data, status_code=202)
    except Exception as e:
        logging.exception(f"Error submitting line regeneration job for prefix {batch_prefix}: {e}")
        if db_job and db_job.id: # Mark job as failed
            try: db_job.status = "SUBMIT_FAILED"; db_job.result_message = f"Enqueue failed: {e}"; db.commit()
            except: db.rollback()
        return make_api_response(error="Failed to start line regeneration task", status_code=500)
    finally: db.close()

@batch_bp.route('/batch/<path:batch_prefix>/speech_to_speech', methods=['POST'])
def start_speech_to_speech_line(batch_prefix):
    """Endpoint to start a line speech-to-speech task, using batch prefix."""
    if not request.is_json: return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    required_keys = ['line_key', 'source_audio_b64', 'num_new_takes', 'target_voice_id', 'model_id', 'settings', 'replace_existing']
    if not all(key in data for key in required_keys): 
        missing = [k for k in required_keys if k not in data]; 
        return make_api_response(error=f'Missing keys: {missing}', status_code=400)

    line_key = data['line_key']
    source_audio_b64 = data['source_audio_b64']
    num_new_takes = data['num_new_takes']
    target_voice_id = data['target_voice_id']
    model_id = data['model_id']
    settings = data['settings']
    replace_existing = data['replace_existing']
    settings_json = json.dumps(settings)
    
    if not source_audio_b64 or not source_audio_b64.startswith('data:audio'): 
        return make_api_response(error='Invalid audio data URI', status_code=400)
    if not isinstance(num_new_takes, int) or num_new_takes <= 0: 
        return make_api_response(error='Invalid num_new_takes', status_code=400)
    try: header, encoded = source_audio_b64.split(';base64,', 1)
    except: return make_api_response(error='Failed to decode source audio data', status_code=400)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check if target batch metadata exists in R2
        metadata_blob_key = f"{batch_prefix}/metadata.json"
        if not utils_r2.blob_exists(metadata_blob_key):
             return make_api_response(error=f"Target batch prefix '{batch_prefix}' not found for STS", status_code=404)

        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING", job_type="sts_line_regen",
            target_batch_id=batch_prefix, # Store the prefix
            target_line_key=line_key,
            parameters_json=json.dumps({ 'target_voice_id': target_voice_id, 'model_id': model_id, 'num_new_takes': num_new_takes, 'settings': settings, 'replace_existing': replace_existing, 'source_audio_info': header })
        )
        db.add(db_job); db.commit(); db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created STS Line Job DB ID: {db_job_id} for prefix {batch_prefix}") # Use logging

        # Enqueue Celery task, passing BATCH PREFIX and base64 string
        task = run_speech_to_speech_line.delay(
            db_job_id, batch_prefix, line_key, source_audio_b64, # Pass prefix
            num_new_takes, target_voice_id, model_id, settings_json, replace_existing
        )
        logging.info(f"Enqueued STS line task: Celery ID {task.id}, DB Job ID {db_job_id}") # Use logging
        db_job.celery_task_id = task.id; db.commit()
        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)
    except Exception as e:
        logging.exception(f"Error submitting STS line job for prefix {batch_prefix}: {e}")
        if db_job and db_job.id: # Mark job as failed
            try: db_job.status = "SUBMIT_FAILED"; db_job.result_message = f"Enqueue failed: {e}"; db.commit()
            except: db.rollback()
        return make_api_response(error="Failed to start speech-to-speech task", status_code=500)
    finally: db.close()

@batch_bp.route('/batch/<path:batch_prefix>/takes/<path:filename>/crop', methods=['POST'])
def crop_take(batch_prefix, filename):
    """Endpoint to start a Celery task to crop an audio take."""
    # Basic security/validation
    if not batch_prefix or '..' in batch_prefix:
        return make_api_response(error="Invalid batch prefix", status_code=400)
    if not filename or '..' in filename or not filename.endswith('.mp3'):
        return make_api_response(error="Invalid filename", status_code=400)
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    
    data = request.get_json()
    start_time = data.get('startTime')
    end_time = data.get('endTime')

    if start_time is None or end_time is None:
        return make_api_response(error="Missing required fields: startTime and endTime", status_code=400)

    try:
        start_seconds = float(start_time)
        end_seconds = float(end_time)
        if start_seconds < 0 or end_seconds <= 0 or start_seconds >= end_seconds:
            raise ValueError("Invalid start/end time values.")
    except (ValueError, TypeError):
        return make_api_response(error="Invalid startTime or endTime format. Must be numbers in seconds.", status_code=400)

    # Construct the full R2 object key for the take
    # Assuming the structure skin/voice/batch/takes/filename
    r2_object_key = f"{batch_prefix}/takes/{filename}"
    logging.info(f"Received crop request for R2 key: {r2_object_key}, Start: {start_seconds}, End: {end_seconds}")

    # Optional: Check if batch is locked (we decided to disallow cropping locked batches in the spec)
    metadata_blob_key = f"{batch_prefix}/metadata.json"
    try:
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if metadata_bytes:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            if metadata.get('ranked_at_utc') is not None:
                logging.warning(f"Attempted to crop take in locked batch: {batch_prefix}")
                return make_api_response(error="Cannot crop takes in a locked batch.", status_code=403) # 403 Forbidden
        else:
             # If metadata doesn't exist, something is wrong, but let task handle R2 key check
             logging.warning(f"Metadata not found for batch {batch_prefix} during crop request, but proceeding.")
    except Exception as meta_err:
        logging.error(f"Error checking batch lock status during crop request for {batch_prefix}: {meta_err}")
        # Decide if this error should prevent the crop or just be logged
        # return make_api_response(error="Failed to check batch lock status", status_code=500)

    try:
        # Import the task here to avoid circular imports
        from backend.tasks import crop_audio_take
        # Enqueue the Celery task
        task = crop_audio_take.delay(r2_object_key, start_seconds, end_seconds)
        logging.info(f"Enqueued crop task with Celery ID: {task.id} for R2 key {r2_object_key}")
        
        # Return task ID immediately (or job ID if we were creating one)
        # Frontend will need to poll task status or just rely on overwrite
        return make_api_response(data={'task_id': task.id, 'message': 'Crop task started.'}, status_code=202)

    except Exception as e:
        logging.exception(f"Error enqueueing crop task for {r2_object_key}: {e}")
        return make_api_response(error="Failed to start audio cropping task", status_code=500)

@batch_bp.route('/batch/<path:batch_prefix>/download', methods=['GET'])
def download_batch_zip(batch_prefix):
    """Creates and returns a ZIP archive with takes organized by rank based on metadata."""
    if not batch_prefix or '..' in batch_prefix: # Basic security check
        return make_api_response(error="Invalid batch prefix", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    zip_filename_base = batch_prefix.replace('/', '_')
    zip_download_name = f"{zip_filename_base}.zip"
    logging.info(f"Request to download zip for batch prefix: {batch_prefix}")

    memory_file = io.BytesIO()
    try:
        # 1. Download and parse metadata
        logging.info(f"Downloading metadata: {metadata_blob_key}")
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            logging.warning(f"Metadata blob not found: {metadata_blob_key}")
            return make_api_response(error=f"Batch prefix '{batch_prefix}' metadata not found.", status_code=404)
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Failed to parse metadata JSON for zip: {metadata_blob_key}: {e}")
            return make_api_response(error="Failed to parse batch metadata for zip.", status_code=500)

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 2. Add metadata.json to zip
            zf.writestr("metadata.json", metadata_bytes)
            logging.info("Added metadata.json to zip.")

            # 3. Iterate through takes listed in metadata
            takes_list = metadata.get('takes', [])
            added_files_count = 0
            failed_files_count = 0
            added_ranked_count = 0
            
            logging.info(f"Found {len(takes_list)} takes listed in metadata.")

            # Cache downloaded audio bytes to avoid re-downloading for ranked folder
            audio_data_cache = {}

            for take in takes_list:
                r2_key = take.get('r2_key')
                filename = take.get('file') # This should be just the base filename
                rank = take.get('rank')
                
                if not r2_key or not filename:
                    logging.warning(f"Skipping take due to missing r2_key or file in metadata: {take}")
                    continue
                
                # Ensure the file is in the cache (download if needed)
                if r2_key not in audio_data_cache:
                    logging.info(f"Downloading {r2_key} for zip...") 
                    audio_bytes = utils_r2.download_blob_to_memory(r2_key)
                    if audio_bytes is None:
                        failed_files_count += 1
                        logging.warning(f"Failed to download {r2_key} for zip file. Skipping.")
                        continue # Skip this take entirely if download fails
                    audio_data_cache[r2_key] = audio_bytes
                else:
                    # Should not happen with current loop structure, but good practice
                    audio_bytes = audio_data_cache[r2_key]

                # Add to takes/ folder
                takes_arcname = f"takes/{filename}" 
                zf.writestr(takes_arcname, audio_bytes)
                added_files_count += 1
                logging.debug(f"Added {takes_arcname} to zip.")

                # If ranked (1-5), also add to ranked/0X/ folder
                if isinstance(rank, int) and 1 <= rank <= 5:
                    ranked_arcname = f"ranked/{rank:02d}/{filename}"
                    try:
                        zf.writestr(ranked_arcname, audio_bytes)
                        added_ranked_count += 1
                        logging.debug(f"Added {ranked_arcname} to zip.")
                    except Exception as zip_err:
                        # Log error adding ranked file but continue
                        logging.error(f"Failed to add ranked file {ranked_arcname} to zip: {zip_err}")
                # Rank 6 (Trash) is ignored for zip download
            
            if failed_files_count > 0:
                 logging.warning(f"Failed to download {failed_files_count} audio files listed in metadata for zip.")
                 
            logging.info(f"Added metadata, {added_files_count} takes files, and {added_ranked_count} ranked file copies to zip for {batch_prefix}")

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_download_name
        )

    except Exception as e:
        logging.exception(f"Unexpected error creating zip for {batch_prefix}: {e}")
        return make_api_response(error="Failed to create batch zip file", status_code=500) 