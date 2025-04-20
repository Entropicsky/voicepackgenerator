# backend/tasks.py
from .celery_app import celery
from backend import models
from backend import utils_elevenlabs
from backend import utils_r2
from sqlalchemy.orm import Session
import time
import json
import csv
import random
from datetime import datetime, timezone
from celery.exceptions import Ignore, Retry
import base64

print("Celery Worker: Loading tasks.py...")

@celery.task(bind=True, name='tasks.run_generation')
def run_generation(self, 
                   generation_job_db_id: int, 
                   config_json: str, 
                   script_id: int | None = None, 
                   script_csv_content: str | None = None):
    """Celery task to generate a batch of voice takes, uploading to R2."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received generation task. Script ID: {script_id}, CSV Provided: {script_csv_content is not None}")
    
    db: Session = next(models.get_db()) # Get DB session for this task execution
    db_job = None
    try:
        # Update DB status to STARTED
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR: GenerationJob record not found.")
            raise Ignore() # Ignore if DB record is missing
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id # Ensure celery task ID is stored
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")

        self.update_state(state='STARTED', meta={'status': 'Parsing configuration...', 'db_id': generation_job_db_id})

        config = json.loads(config_json)
        # --- Config Validation / Setup --- 
        skin_name = config['skin_name']
        voice_ids = config['voice_ids']
        variants_per_line = config['variants_per_line']
        model_id = config.get('model_id', utils_elevenlabs.DEFAULT_MODEL)
        output_format = config.get('output_format', 'mp3_44100_128')
        
        # --- Get Configurable RANGES (with defaults) --- 
        stability_range = config.get('stability_range', [0.5, 0.75])
        similarity_boost_range = config.get('similarity_boost_range', [0.75, 0.9])
        style_range = config.get('style_range', [0.0, 0.45])
        speed_range = config.get('speed_range', [0.95, 1.05])
        # Speaker boost remains fixed for the job
        use_speaker_boost = config.get('use_speaker_boost', True)

        # Ensure ranges are valid lists/tuples of length 2
        # (Add more robust validation if needed)
        if not isinstance(stability_range, (list, tuple)) or len(stability_range) != 2: stability_range = [0.5, 0.75]
        if not isinstance(similarity_boost_range, (list, tuple)) or len(similarity_boost_range) != 2: similarity_boost_range = [0.75, 0.9]
        if not isinstance(style_range, (list, tuple)) or len(style_range) != 2: style_range = [0.0, 0.45]
        if not isinstance(speed_range, (list, tuple)) or len(speed_range) != 2: speed_range = [0.95, 1.05]

        # --- Prepare Script Data ---
        script_data = []
        try:
            if script_id is not None:
                print(f"[Task ID: {task_id}] Fetching script lines from DB for script_id {script_id}")
                lines_from_db = db.query(models.ScriptLine).filter(models.ScriptLine.script_id == script_id).order_by(models.ScriptLine.order_index).all()
                if not lines_from_db:
                    raise ValueError(f"No lines found in database for script_id {script_id}")
                # Format into the expected list of dicts (assuming target format is {'Function': key, 'Line': text})
                script_data = [
                    {'Function': line.line_key, 'Line': line.text}
                    for line in lines_from_db
                ]
                print(f"[Task ID: {task_id}] Loaded {len(script_data)} lines from DB script {script_id}")
            
            elif script_csv_content is not None:
                print(f"[Task ID: {task_id}] Parsing script lines from provided CSV content")
                # Use csv.reader on the string content
                lines = list(csv.reader(script_csv_content.splitlines()))
                if not lines or len(lines[0]) < 2:
                     raise ValueError("CSV content is empty or header missing/invalid")
                header = [h.strip() for h in lines[0]]
                # Assuming header columns are 'Function' and 'Line' (Case-insensitive check?)
                try:
                    # Attempt to find columns, handle potential case issues
                    header_lower = [h.lower() for h in header]
                    func_idx = header_lower.index('function')
                    line_idx = header_lower.index('line')
                except ValueError:
                     raise ValueError("CSV header must contain 'Function' and 'Line' columns")
                
                script_data = [
                    {'Function': row[func_idx].strip(), 'Line': row[line_idx].strip()}
                    for row in lines[1:] if len(row) > max(func_idx, line_idx) and row[func_idx].strip() # Ensure key isn't empty
                ]
                if not script_data:
                     raise ValueError("No valid data rows found in CSV content")
                print(f"[Task ID: {task_id}] Parsed {len(script_data)} lines from CSV.")
            
            else:
                 # This case should have been prevented by the API endpoint validation
                 raise ValueError("Task started without script_id or script_csv_content. This should not happen.")
                 
        except (ValueError, IndexError, Exception) as e:
            status_msg = f'Error preparing script data: {e}'
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
            self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
            # Mark DB job as failed here too?
            db_job.status = "FAILURE"
            db_job.completed_at = datetime.utcnow()
            db_job.result_message = status_msg
            db.commit()
            raise Ignore() # Use Ignore to stop processing without retrying
        # --- END SCRIPT DATA PREPARATION ---

        total_takes_to_generate = len(voice_ids) * len(script_data) * variants_per_line
        generated_takes_count = 0
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Parsed config. Total takes to generate: {total_takes_to_generate}")

        # --- Generation Loop ---
        all_batches_metadata = []
        elevenlabs_failures = 0

        for voice_id in voice_ids:
            self.update_state(state='PROGRESS', meta={
                'status': f'Processing voice: {voice_id}...',
                'current_voice': voice_id,
                'progress': int(100 * generated_takes_count / total_takes_to_generate)
            })

            # --- Get Voice Name & Create Directories ---
            try:
                # TODO: Consider caching voice details? API call per task might be slow.
                voices = utils_elevenlabs.get_available_voices()
                voice_info = next((v for v in voices if v.get('voice_id') == voice_id), None)
                if not voice_info:
                    raise ValueError(f"Voice ID {voice_id} not found.")
                voice_name_human = voice_info.get('name', voice_id)
                voice_folder_name = f"{voice_name_human}-{voice_id}"
            except Exception as e:
                # Log warning but continue if possible, or fail task?
                print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Warning: Could not get voice name for {voice_id}: {e}")
                voice_folder_name = voice_id # Fallback to ID

            batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            batch_id = f"{batch_timestamp}-{voice_id[:4]}"

            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Starting batch generation: {skin_name}/{voice_folder_name}/{batch_id}")

            batch_metadata = {
                "batch_id": batch_id,
                "skin_name": skin_name,
                "voice_name": voice_folder_name,
                "generated_at_utc": None, # Will be set at the end
                "generation_params": config, # Store original config
                "ranked_at_utc": None,
                "takes": []
            }

            voice_has_success = False # Track if *any* take for this voice succeeded
            for line_info in script_data:
                line_func = line_info['Function']
                line_text = line_info['Line']

                for take_num in range(1, variants_per_line + 1):
                    generated_takes_count += 1
                    progress_percent = int(100 * generated_takes_count / total_takes_to_generate)
                    self.update_state(state='PROGRESS', meta={
                        'status': f'Generating: {line_func} Take {take_num}/{variants_per_line} (Voice {voice_id}) Progress: {progress_percent}%',
                        'current_voice': voice_id,
                        'current_line': line_func,
                        'current_take': take_num,
                        'progress': progress_percent
                    })

                    # --- Randomize settings WITHIN the provided ranges --- 
                    stability_take = random.uniform(*stability_range)
                    similarity_boost_take = random.uniform(*similarity_boost_range)
                    style_take = random.uniform(*style_range)
                    speed_take = random.uniform(*speed_range)
                    
                    take_settings = {
                        'stability': stability_take,
                        'similarity_boost': similarity_boost_take,
                        'style': style_take,
                        'use_speaker_boost': use_speaker_boost, # Fixed value
                        'speed': speed_take
                    }

                    output_filename = f"{line_func}_take_{take_num}.mp3"
                    # --- Construct R2 Blob Key --- 
                    r2_blob_key = f"{skin_name}/{voice_folder_name}/{batch_id}/takes/{output_filename}"

                    try:
                        # --- Generate audio bytes --- 
                        audio_bytes = utils_elevenlabs.generate_tts_audio_bytes(
                            text=line_text,
                            voice_id=voice_id,
                            model_id=model_id,
                            output_format=output_format,
                            stability=stability_take,
                            similarity_boost=similarity_boost_take,
                            style=style_take,
                            speed=speed_take,
                            use_speaker_boost=use_speaker_boost
                        )

                        if not audio_bytes:
                             raise utils_elevenlabs.ElevenLabsError("Generation returned empty audio data.")

                        # --- Upload to R2 --- 
                        upload_success = utils_r2.upload_blob(
                            blob_name=r2_blob_key,
                            data=audio_bytes,
                            content_type='audio/mpeg' # Adjust if output_format changes
                        )

                        if not upload_success:
                            # Log error but maybe continue?
                            raise Exception(f"Failed to upload {r2_blob_key} to R2.")

                        # Add take metadata
                        batch_metadata["takes"].append({
                            "file": output_filename, # Store relative filename for reference
                            "r2_key": r2_blob_key,   # Store full R2 key
                            "line": line_func,
                            "script_text": line_text,
                            "take_number": take_num,
                            "generation_settings": take_settings,
                            "rank": None,
                            "ranked_at": None
                        })
                        voice_has_success = True # Mark success for this voice

                    except utils_elevenlabs.ElevenLabsError as e:
                        # Log error for this take, but continue with others
                        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR generating take {r2_blob_key}: {e}")
                        elevenlabs_failures += 1
                    except Exception as e:
                        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] UNEXPECTED ERROR during take {r2_blob_key} generation/upload: {e}")
                        # Decide if unexpected errors should count as failure?
                        elevenlabs_failures += 1 # Count unexpected as failure too

            # --- Post-Voice Processing ---
            if voice_has_success:
                batch_metadata["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
                try:
                    # --- Serialize and Upload Metadata to R2 --- 
                    metadata_blob_key = f"{skin_name}/{voice_folder_name}/{batch_id}/metadata.json"
                    metadata_bytes = json.dumps(batch_metadata, indent=2).encode('utf-8')
                    
                    meta_upload_success = utils_r2.upload_blob(
                        blob_name=metadata_blob_key,
                        data=metadata_bytes,
                        content_type='application/json'
                    )
                    
                    if not meta_upload_success:
                        raise Exception(f"Failed to upload metadata {metadata_blob_key} to R2.")

                    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Saved metadata to R2 for batch: {batch_id}")
                    all_batches_metadata.append(batch_metadata) # Add for final result
                except Exception as e:
                    # If metadata upload fails, this is more serious, consider Retry
                    status_msg = f'ERROR saving metadata to R2 for batch {batch_id}: {e}'
                    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
                    self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
                    raise Retry(exc=e, countdown=60)
            else:
                print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] No successful takes for voice {voice_id}, skipping metadata upload.")

        # --- Task Completion ---
        final_status_msg = f"Generation complete. Processed {len(voice_ids)} voices. Generated {generated_takes_count - elevenlabs_failures}/{total_takes_to_generate} takes ({elevenlabs_failures} failures)."
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {final_status_msg}")

        # --- Update DB Job Record ---
        # Determine final status based on failures
        if elevenlabs_failures > 0 and elevenlabs_failures < total_takes_to_generate:
             final_db_status = "COMPLETED_WITH_ERRORS"
        elif elevenlabs_failures == total_takes_to_generate:
             final_db_status = "FAILURE" # Treat total failure as job failure
             # Optionally refine message if needed
             final_status_msg = f"Generation failed. Processed {len(voice_ids)} voices, generated 0/{total_takes_to_generate} takes ({elevenlabs_failures} failures)."
        else: # No failures
             final_db_status = "SUCCESS"

        db_job.status = final_db_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = final_status_msg
        # Store R2 batch prefixes instead of just IDs?
        generated_batch_prefixes = [f"{b['skin_name']}/{b['voice_name']}/{b['batch_id']}" for b in all_batches_metadata]
        db_job.result_batch_ids_json = json.dumps(generated_batch_prefixes)
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to {final_db_status}.")

        # Celery result payload (can also reflect partial failure)
        return {
            'status': final_db_status, # Return the more granular status
            'message': final_status_msg,
            'generated_batches': [
                {'batch_prefix': f"{b['skin_name']}/{b['voice_name']}/{b['batch_id']}", 'take_count': len(b['takes'])}
                for b in all_batches_metadata
            ]
        }

    except (ValueError, OSError, Exception) as e:
        # Catch expected config/file errors and unexpected errors
        error_msg = f"Task failed: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        # --- Update DB Job Record on FAILURE ---
        if db_job: # Ensure db_job was loaded
            db_job.status = "FAILURE"
            db_job.completed_at = datetime.utcnow()
            db_job.result_message = error_msg
            try:
                db.commit()
            except: 
                db.rollback()
        
        # Update Celery state
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        # Re-raise exception so Celery marks task as failed
        raise e
    finally:
        db.close() # Ensure session is closed for this task execution

# --- New Task for Line Regeneration --- #

@celery.task(bind=True, name='tasks.regenerate_line_takes')
def regenerate_line_takes(self,
                          generation_job_db_id: int,
                          batch_id: str, # This is now the BATCH PREFIX, e.g., skin/voice/batch-ts-id
                          line_key: str,
                          line_text: str,
                          num_new_takes: int,
                          settings_json: str,
                          replace_existing: bool,
                          update_script: bool = False):
    """Generates new takes for a specific line, interacting with R2."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received line regen task for Prefix '{batch_id}', Line '{line_key}'")

    db: Session = next(models.get_db())
    db_job = None
    metadata_blob_key = f"{batch_id}/metadata.json"

    try:
        # Update DB job status
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job: raise Ignore("GenerationJob record not found.")
        db_job.status = "STARTED"; db_job.started_at = datetime.utcnow(); db_job.celery_task_id = task_id
        # Store target batch prefix and line key
        db_job.target_batch_id = batch_id
        db_job.target_line_key = line_key
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")
        self.update_state(state='STARTED', meta={'status': f'Preparing regen for line: {line_key}', 'db_id': generation_job_db_id})

        # Parse settings (same as before)
        settings = json.loads(settings_json)
        stability_range = settings.get('stability_range', [0.5, 0.75])
        similarity_boost_range = settings.get('similarity_boost_range', [0.75, 0.9])
        style_range = settings.get('style_range', [0.0, 0.45])
        speed_range = settings.get('speed_range', [0.95, 1.05])
        use_speaker_boost = settings.get('use_speaker_boost', True)
        model_id = settings.get('model_id', utils_elevenlabs.DEFAULT_MODEL)
        output_format = settings.get('output_format', 'mp3_44100_128')

        # --- Load Metadata from R2 --- 
        print(f"[Task ID: {task_id}] Downloading metadata: {metadata_blob_key}")
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            raise ValueError(f"Metadata blob not found or failed to download: {metadata_blob_key}")
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse metadata JSON from {metadata_blob_key}: {e}")

        # Extract needed info from metadata
        skin_name = metadata.get('skin_name')
        voice_folder_name = metadata.get('voice_name') # This now holds the folder name
        original_voice_id = voice_folder_name.split('-')[-1] if '-' in voice_folder_name else voice_folder_name # Extract original voice ID

        if not skin_name or not voice_folder_name:
             raise ValueError("Metadata is missing skin_name or voice_name (folder name).")

        # Construct base prefix for takes in R2
        takes_prefix = f"{batch_id}/takes/"

        original_takes = metadata.get('takes', [])
        new_metadata_takes = []
        deleted_r2_keys = []
        start_take_num = 1
        current_line_takes = [t for t in original_takes if t.get('line') == line_key]

        if replace_existing:
            print(f"[Task ID: {task_id}] Replacing existing takes for line '{line_key}'")
            self.update_state(state='PROGRESS', meta={'status': f'Deleting old takes for line: {line_key}', 'db_id': generation_job_db_id})

            # --- Delete existing blobs for this line in R2 --- 
            # No need to list first if we know the file naming convention
            # However, listing is safer if take numbers could be sparse.
            # Let's list for safety.
            prefix_to_delete = f"{takes_prefix}{line_key}_take_"
            blobs_to_delete = utils_r2.list_blobs_in_prefix(prefix=prefix_to_delete)
            deleted_count = 0
            for blob_info in blobs_to_delete:
                r2_key_to_delete = blob_info.get('Key')
                if r2_key_to_delete:
                    print(f"[Task ID: {task_id}] Deleting existing take blob: {r2_key_to_delete}")
                    if utils_r2.delete_blob(r2_key_to_delete):
                        deleted_r2_keys.append(r2_key_to_delete)
                        deleted_count += 1
                    else:
                        print(f"[Task ID: {task_id}] Warning: Failed to delete blob {r2_key_to_delete}")
            print(f"[Task ID: {task_id}] Deleted {deleted_count} existing take blobs for line '{line_key}'")

            # Filter out the old takes from the metadata list
            new_metadata_takes = [t for t in original_takes if t.get('line') != line_key]
            # start_take_num remains 1
        else:
            print(f"[Task ID: {task_id}] Adding new takes for line '{line_key}'")
            new_metadata_takes = original_takes # Start with all original takes
            if current_line_takes:
                start_take_num = max(t.get('take_number', 0) for t in current_line_takes) + 1

        # Generate new takes
        newly_generated_takes_meta = []
        failures = 0
        for i in range(num_new_takes):
            take_num = start_take_num + i
            self.update_state(state='PROGRESS', meta={
                'status': f'Generating take {take_num}/{start_take_num + num_new_takes - 1} for line: {line_key}',
                'db_id': generation_job_db_id,
                'progress': int(100 * (i + 1) / num_new_takes)
            })

            stability_take = random.uniform(*stability_range)
            similarity_boost_take = random.uniform(*similarity_boost_range)
            style_take = random.uniform(*style_range)
            speed_take = random.uniform(*speed_range)
            take_settings = { 'stability': stability_take, 'similarity_boost': similarity_boost_take, 'style': style_take, 'use_speaker_boost': use_speaker_boost, 'speed': speed_take }

            output_filename = f"{line_key}_take_{take_num}.mp3"
            r2_blob_key = f"{takes_prefix}{output_filename}"

            try:
                # Generate audio bytes
                audio_bytes = utils_elevenlabs.generate_tts_audio_bytes(
                    text=line_text,
                    voice_id=original_voice_id, # Use the voice ID from the original batch
                    model_id=model_id,
                    output_format=output_format,
                    stability=stability_take,
                    similarity_boost=similarity_boost_take,
                    style=style_take,
                    speed=speed_take,
                    use_speaker_boost=use_speaker_boost
                )
                if not audio_bytes: raise utils_elevenlabs.ElevenLabsError("Generation returned empty audio data.")

                # Upload to R2
                upload_success = utils_r2.upload_blob(
                    blob_name=r2_blob_key,
                    data=audio_bytes,
                    content_type='audio/mpeg'
                )
                if not upload_success: raise Exception(f"Failed to upload {r2_blob_key} to R2.")

                # Add metadata for the new take
                new_take_meta = {
                    "file": output_filename,
                    "r2_key": r2_blob_key,
                    "line": line_key,
                    "script_text": line_text,
                    "take_number": take_num,
                    "generation_settings": take_settings,
                    "rank": None,
                    "ranked_at": None
                }
                new_metadata_takes.append(new_take_meta)
                newly_generated_takes_meta.append(new_take_meta)
            except Exception as e:
                print(f"[Task ID: {task_id}] ERROR generating/uploading take {r2_blob_key} for line regen: {e}")
                failures += 1

        # --- Upload Updated Metadata to R2 (Overwrite) --- 
        metadata['takes'] = new_metadata_takes
        metadata['last_regenerated_line'] = {
            'line': line_key,
            'at': datetime.now(timezone.utc).isoformat(),
            'num_added': len(newly_generated_takes_meta),
            'replaced': replace_existing,
            'deleted_keys': deleted_r2_keys # Record keys that were deleted
        }
        
        try:
            metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
            meta_upload_success = utils_r2.upload_blob(
                blob_name=metadata_blob_key,
                data=metadata_bytes,
                content_type='application/json'
            )
            if not meta_upload_success:
                raise Exception(f"Failed to re-upload metadata {metadata_blob_key} to R2.")
            print(f"[Task ID: {task_id}] Uploaded updated metadata for batch {batch_id} after regenerating line {line_key}.")
        except Exception as e:
             # If metadata upload fails, this is serious
             status_msg = f'ERROR re-uploading metadata to R2 for batch {batch_id}: {e}'
             print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
             self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
             raise Retry(exc=e, countdown=60)

        # Update script in DB if requested (Keep existing logic)
        script_update_message = ""
        if update_script and len(newly_generated_takes_meta) > 0:
            try:
                script_lines = db.query(models.ScriptLine).filter(models.ScriptLine.line_key == line_key).all()
                if script_lines:
                    updated_scripts = []
                    for script_line in script_lines:
                        script = db.query(models.Script).get(script_line.script_id)
                        if script: script_line.text = line_text; updated_scripts.append(script.name)
                    if updated_scripts:
                        db.commit()
                        script_names = ", ".join(f"'{name}'" for name in updated_scripts)
                        script_update_message = f" Script(s) {script_names} updated."
                        print(f"[Task ID: {task_id}] Updated script line '{line_key}' in scripts: {script_names}")
                    else: script_update_message = f" Found matching lines, but no associated scripts."
                else: script_update_message = f" No scripts found with line key '{line_key}'."
            except Exception as e:
                script_update_message = f" Error updating script: {str(e)}"
                print(f"[Task ID: {task_id}] Error updating script for batch {batch_id}: {e}")

        # --- Update DB Job --- 
        final_status = "SUCCESS" if failures == 0 else "COMPLETED_WITH_ERRORS" if failures < num_new_takes else "FAILURE"
        result_msg = f"Regenerated line '{line_key}'. Added {len(newly_generated_takes_meta)} takes ({failures} failures). Replaced: {replace_existing}. Deleted: {len(deleted_r2_keys)} keys.{script_update_message}"
        if final_status == "FAILURE": result_msg = f"Failed to regen any takes for '{line_key}' ({failures} failures).{script_update_message}"
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = result_msg
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to {final_status}.")

        return {'status': final_status, 'message': result_msg}

    except Exception as e:
        error_msg = f"Line regeneration task failed: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        if db_job:
            db_job.status = "FAILURE"; db_job.completed_at = datetime.utcnow(); db_job.result_message = error_msg
            try: db.commit()
            except: db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e
    finally:
        db.close()

# --- New Task for Speech-to-Speech Line Regeneration --- #

@celery.task(bind=True, name='tasks.run_speech_to_speech_line')
def run_speech_to_speech_line(self,
                              generation_job_db_id: int,
                              batch_id: str, # This is now the BATCH PREFIX
                              line_key: str,
                              source_audio_b64: str,
                              num_new_takes: int,
                              target_voice_id: str, # Target voice for STS
                              model_id: str, # STS model
                              settings_json: str,
                              replace_existing: bool):
    """Generates new takes for a line using STS, interacting with R2."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received STS task for Prefix '{batch_id}', Line '{line_key}'")

    db: Session = next(models.get_db())
    db_job = None
    metadata_blob_key = f"{batch_id}/metadata.json"

    try:
        # --- Update Job Status --- 
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job: raise Ignore("GenerationJob record not found.")
        db_job.status = "STARTED"; db_job.started_at = datetime.utcnow(); db_job.celery_task_id = task_id
        # Store target batch prefix and line key
        db_job.target_batch_id = batch_id
        db_job.target_line_key = line_key
        db.commit()
        self.update_state(state='STARTED', meta={'status': f'Preparing STS for line: {line_key}', 'db_id': generation_job_db_id})
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")

        # --- Decode Audio & Settings --- 
        try:
            header, encoded = source_audio_b64.split(';base64,', 1)
            audio_data_bytes = base64.b64decode(encoded)
        except Exception as e:
            raise ValueError(f"Failed to decode source audio base64 data: {e}") from e
        
        settings = json.loads(settings_json)
        sts_voice_settings = { key: settings.get(key) for key in ['stability', 'similarity_boost'] if settings.get(key) is not None }

        # --- Load Metadata from R2 --- 
        print(f"[Task ID: {task_id}] Downloading metadata: {metadata_blob_key}")
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes: raise ValueError(f"Metadata blob not found: {metadata_blob_key}")
        try: metadata = json.loads(metadata_bytes.decode('utf-8'))
        except json.JSONDecodeError as e: raise ValueError(f"Failed to parse metadata JSON: {e}")

        # Extract needed info
        skin_name = metadata.get('skin_name')
        voice_folder_name = metadata.get('voice_name')
        if not skin_name or not voice_folder_name: raise ValueError("Metadata missing skin/voice name.")
        takes_prefix = f"{batch_id}/takes/" # Base R2 prefix for takes

        original_takes = metadata.get('takes', [])
        new_metadata_takes = []
        deleted_r2_keys = []
        start_take_num = 1
        current_line_takes = [t for t in original_takes if t.get('line') == line_key]
        
        if replace_existing:
            print(f"[...] Replacing existing takes for line '{line_key}' before STS.")
            self.update_state(state='PROGRESS', meta={'status': f'Deleting old takes...', 'db_id': generation_job_db_id})
            
            # --- Delete existing blobs for this line in R2 --- 
            prefix_to_delete = f"{takes_prefix}{line_key}_take_"
            blobs_to_delete = utils_r2.list_blobs_in_prefix(prefix=prefix_to_delete)
            deleted_count = 0
            for blob_info in blobs_to_delete:
                r2_key_to_delete = blob_info.get('Key')
                if r2_key_to_delete:
                    if utils_r2.delete_blob(r2_key_to_delete):
                        deleted_r2_keys.append(r2_key_to_delete)
                        deleted_count += 1
                    else: print(f"[...] Warning: Failed to delete blob {r2_key_to_delete}")
            print(f"[...] Deleted {deleted_count} existing take blobs for line '{line_key}'.")
            new_metadata_takes = [t for t in original_takes if t.get('line') != line_key]
        else:
            new_metadata_takes = original_takes
            if current_line_takes: start_take_num = max(t.get('take_number', 0) for t in current_line_takes) + 1

        # --- Generate New Takes via STS --- 
        newly_generated_takes_meta = []
        failures = 0
        for i in range(num_new_takes):
            take_num = start_take_num + i
            self.update_state(state='PROGRESS', meta={
                'status': f'Running STS take {take_num} for line: {line_key}',
                'db_id': generation_job_db_id,
                'progress': int(100 * (i + 1) / num_new_takes)
            })
            
            output_filename = f"{line_key}_take_{take_num}.mp3" # Assuming mp3 output from STS
            r2_blob_key = f"{takes_prefix}{output_filename}"

            try:
                # Generate audio bytes via STS
                result_audio_bytes = utils_elevenlabs.run_speech_to_speech_conversion(
                    audio_data=audio_data_bytes, # The decoded source audio
                    target_voice_id=target_voice_id,
                    model_id=model_id,
                    voice_settings=sts_voice_settings
                )
                if not result_audio_bytes: raise utils_elevenlabs.ElevenLabsError("STS returned empty audio data.")

                # --- Upload result to R2 --- 
                upload_success = utils_r2.upload_blob(
                    blob_name=r2_blob_key,
                    data=result_audio_bytes,
                    content_type='audio/mpeg' # Assuming MP3 output from STS
                )
                if not upload_success: raise Exception(f"Failed to upload STS result {r2_blob_key} to R2.")
                print(f"[...] Successfully uploaded STS audio to {r2_blob_key}")

                # Add metadata for the new take
                new_take_meta = {
                    "file": output_filename,
                    "r2_key": r2_blob_key,
                    "line": line_key,
                    "script_text": "[STS]", # Indicate generated via STS
                    "take_number": take_num,
                    "generation_settings": {**settings, 'source_audio_info': header, 'sts_target_voice': target_voice_id}, # Store STS settings
                    "rank": None, "ranked_at": None
                }
                new_metadata_takes.append(new_take_meta)
                newly_generated_takes_meta.append(new_take_meta)
            except Exception as e:
                print(f"[...] ERROR generating/uploading STS take {r2_blob_key}: {e}")
                failures += 1

        # --- Upload Updated Metadata to R2 (Overwrite) --- 
        metadata['takes'] = new_metadata_takes
        metadata['last_regenerated_line'] = {
            'line': line_key,
            'at': datetime.now(timezone.utc).isoformat(),
            'num_added': len(newly_generated_takes_meta),
            'replaced': replace_existing,
            'type': 'sts',
            'deleted_keys': deleted_r2_keys
        }
        try:
            metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
            meta_upload_success = utils_r2.upload_blob(
                blob_name=metadata_blob_key,
                data=metadata_bytes,
                content_type='application/json'
            )
            if not meta_upload_success: raise Exception(f"Failed to re-upload metadata {metadata_blob_key} to R2.")
            print(f"[...] Uploaded updated metadata for batch {batch_id} after STS for line {line_key}.")
        except Exception as e:
            status_msg = f'ERROR re-uploading metadata to R2 for batch {batch_id}: {e}'
            print(f"[...] {status_msg}")
            self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
            raise Retry(exc=e, countdown=60)

        # --- Update DB Job --- 
        final_status = "SUCCESS" if failures == 0 else "COMPLETED_WITH_ERRORS" if failures < num_new_takes else "FAILURE"
        result_msg = f"STS for line '{line_key}' complete. Added {len(newly_generated_takes_meta)} takes ({failures} failures). Replaced: {replace_existing}. Deleted: {len(deleted_r2_keys)} keys."
        if final_status == "FAILURE": result_msg = f"STS failed for line '{line_key}'. ({failures} failures)."
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = result_msg
        db.commit()
        print(f"[...] Updated job status to {final_status}.")

        return {'status': final_status, 'message': result_msg}

    except Exception as e:
        error_msg = f"STS line task failed: {type(e).__name__}: {e}"
        print(f"[...] {error_msg}")
        if db_job: # Update DB if possible
            db_job.status = "FAILURE"; db_job.completed_at = datetime.utcnow(); db_job.result_message = error_msg
            try: db.commit()
            except: db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e # Re-raise
    finally:
        db.close()

# --- Placeholder Task (Keep or Remove) ---
# @celery.task(bind=True)
# def placeholder_task(self):
#     task_id = self.request.id
#     print(f"Running placeholder_task (ID: {task_id})...")
#     self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100})
#     time.sleep(5)
#     print(f"placeholder_task (ID: {task_id}) finished.")
#     return {"status": "Complete", "result": "Placeholder result"}

# Add other generation tasks here later 