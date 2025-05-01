# backend/tasks.py
from .celery_app import celery
from backend import models
from backend import utils_elevenlabs
from backend import utils_r2
from . import utils_openai
from . import utils_voscript
from sqlalchemy.orm import Session
import time
import json
import csv
import random
from datetime import datetime, timezone
from celery.exceptions import Ignore, Retry
import base64
import io # Added for in-memory file handling
from pydub import AudioSegment # Added for cropping
import tempfile # Added for temporary file handling
from celery import Task # Import base Task class
from backend.script_agents.script_writer import ScriptWriterAgent # Import the agent # UNCOMMENTED
import os # Added for environment variables
import logging
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import case # Added for ordering
from backend.utils_voscript import get_category_lines_context, update_line_in_db
from backend.routes.vo_script_routes import _generate_lines_batch

# --- Constants ---
BATCH_GENERATION_THRESHOLD = 10 # Generate <= this many lines in one go
SMALL_BATCH_SIZE = 8 # Split larger jobs into batches of this size
# --- End Constants ---

print("Celery Worker: Loading tasks.py...")

@celery.task(bind=True, name='tasks.run_generation')
def run_generation(self, 
                   generation_job_db_id: int, 
                   config_json: str, 
                   vo_script_id: int):
    """Celery task to generate a batch of voice takes using VO Script, uploading to R2."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received generation task for VO Script ID: {vo_script_id}")
    
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

        # --- Prepare Script Data from VO Script --- #
        script_data = []
        vo_script_name = "Unknown"
        try:
            print(f"[Task ID: {task_id}] Fetching VO script lines from DB for vo_script_id {vo_script_id}")
            
            # Define statuses valid for generation
            valid_statuses_for_generation = ['generated', 'manual', 'review']
            
            # Query VoScriptLines, joining template line for ordering fallback
            lines_from_db = (
                db.query(models.VoScriptLine)
                .options(selectinload(models.VoScriptLine.template_line)) # Eager load template_line
                .filter(
                    models.VoScriptLine.vo_script_id == vo_script_id,
                    models.VoScriptLine.status.in_(valid_statuses_for_generation),
                    models.VoScriptLine.generated_text.isnot(None), # Ensure text exists
                    models.VoScriptLine.generated_text != '' # Ensure text is not empty
                )
                .order_by(models.VoScriptLine.id) # Order by ID for now
                .all()
            )

            if not lines_from_db:
                # If no lines found, raise error directly without querying name again
                # vo_script = db.query(models.VoScript.name).filter(models.VoScript.id == vo_script_id).first()
                # vo_script_name = vo_script.name if vo_script else f"ID {vo_script_id}"
                # raise ValueError(f"No lines with valid status ({valid_statuses_for_generation}) and non-empty text found for VO Script '{vo_script_name}'")
                raise ValueError(f"No lines with valid status ({valid_statuses_for_generation}) and non-empty text found for VO Script ID {vo_script_id}") # Simplified error
            else:
                # Get script name from the first line's relationship (if needed for logging/metadata)
                vo_script_name = lines_from_db[0].vo_script.name if lines_from_db[0].vo_script else f"ID {vo_script_id}"
                
            # Format into the expected list of dicts {'Function': key, 'Line': text}
            # --- UPDATED: Implement line_key fallback logic --- 
            script_data = []
            for line in lines_from_db:
                final_line_key = line.line_key # Prioritize direct key
                if not final_line_key and line.template_line: # Fallback to template line key
                    final_line_key = line.template_line.line_key
                if not final_line_key: # Fallback to ID if still no key
                    final_line_key = f'line_{line.id}'
                
                script_data.append({
                    'Function': final_line_key,
                    'Line': line.generated_text
                })
            # --- END UPDATED --- 
            print(f"[Task ID: {task_id}] Loaded {len(script_data)} lines from VO Script '{vo_script_name}' ({vo_script_id})")

        except (ValueError, IndexError, Exception) as e:
            status_msg = f'Error preparing script data from VO Script {vo_script_id}: {e}'
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
            db_job.status = "FAILURE"
            db_job.completed_at = datetime.utcnow()
            db_job.result_message = status_msg
            db.commit()
            self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
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
                "source_vo_script_id": vo_script_id, # Store VO Script ID instead
                "source_vo_script_name": vo_script_name, # Store VO Script Name
                "generated_at_utc": None, # Will be set at the end
                "generation_params": config, # Store original config
                "ranked_at_utc": None,
                "takes": []
            }

            voice_has_success = False # Track if *any* take for this voice succeeded
            for line_info in script_data:
                line_func = line_info['Function']
                line_text = line_info['Line']

                # Skip if line_text is empty or None (should be handled by filter, but belt-and-suspenders)
                if not line_text:
                    print(f"[Task ID: {task_id}] Skipping line '{line_func}' due to empty text.")
                    # Adjust total takes expected?
                    total_takes_to_generate -= variants_per_line
                    continue
                
                for take_num in range(1, variants_per_line + 1):
                    generated_takes_count += 1
                    # Adjust progress calculation to avoid division by zero if total becomes 0
                    progress_percent = int(100 * generated_takes_count / (total_takes_to_generate or 1))
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
        # Adjust total takes if some lines were skipped
        actual_total_takes = len(all_batches_metadata) * variants_per_line * len(script_data) if script_data else 0 
        # Recalculate expected based on lines actually processed
        expected_takes_count = len(script_data) * len(voice_ids) * variants_per_line
        
        final_status_msg = f"Generation complete. Processed {len(voice_ids)} voices for {len(script_data)} lines. Generated {generated_takes_count - elevenlabs_failures}/{expected_takes_count} takes ({elevenlabs_failures} failures)."
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {final_status_msg}")

        # --- Update DB Job Record ---
        # Determine final status based on failures vs expected
        if elevenlabs_failures > 0 and (generated_takes_count - elevenlabs_failures) > 0: # Partial success
             final_db_status = "COMPLETED_WITH_ERRORS"
        elif elevenlabs_failures >= expected_takes_count and expected_takes_count > 0: # Total failure for expected lines
             final_db_status = "FAILURE" 
             final_status_msg = f"Generation failed. Processed {len(voice_ids)} voices for {len(script_data)} lines, generated 0/{expected_takes_count} takes ({elevenlabs_failures} failures)."
        elif expected_takes_count == 0: # No valid lines found initially
             final_db_status = "FAILURE"
             final_status_msg = f"Generation failed. No valid script lines found to process for VO Script '{vo_script_name}' ({vo_script_id})."
        else: # No failures and takes generated
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
        result = {
            'status': final_db_status, # Return the more granular status
            'message': final_status_msg,
            'generated_batches': [
                {'batch_prefix': f"{b['skin_name']}/{b['voice_name']}/{b['batch_id']}", 'take_count': len(b['takes'])}
                for b in all_batches_metadata
            ]
        }
        # Update Celery task state before returning
        self.update_state(state=final_db_status, meta=result)
        return result

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
        source_script_id = metadata.get('source_script_id') # Get the source script ID
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
            if source_script_id is not None: # Check if source script ID exists
                try:
                    # Target ONLY the specific line in the source script
                    script_line = db.query(models.ScriptLine).filter(
                        models.ScriptLine.script_id == source_script_id,
                        models.ScriptLine.line_key == line_key
                    ).first()

                    if script_line:
                        script_line.text = line_text
                        db.commit()
                        script = db.query(models.Script).get(source_script_id) # Get script name for message
                        script_name = script.name if script else f"ID {source_script_id}"
                        script_update_message = f" Script '{script_name}' updated."
                        print(f"[Task ID: {task_id}] Updated script line '{line_key}' in source script: {script_name}")
                    else:
                        # Line key not found within the expected source script - this might indicate an issue?
                        script_update_message = f" Warning: Line key '{line_key}' not found in source script ID {source_script_id}. No script updated."
                        print(f"[Task ID: {task_id}] {script_update_message}")
                except Exception as e:
                    script_update_message = f" Error updating script: {str(e)}"
                    print(f"[Task ID: {task_id}] Error updating script for batch {batch_id}: {e}")
            else:
                # Source script ID not found in metadata (e.g., original was CSV)
                script_update_message = " Script not updated (original source was not a tracked script)."
                print(f"[Task ID: {task_id}] Skipped script update for '{line_key}' because source_script_id was not found in metadata.")

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
        source_script_id = metadata.get('source_script_id') # Get the source script ID
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

# --- New Task for Audio Cropping --- #
@celery.task(bind=True, name='tasks.crop_audio_take')
def crop_audio_take(self, r2_object_key: str, start_seconds: float, end_seconds: float):
    """Downloads an audio take from R2, crops it, and overwrites the original."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}] Received cropping task for Key: {r2_object_key}, Start: {start_seconds}s, End: {end_seconds}s")
    
    if start_seconds >= end_seconds:
        error_msg = f"Crop task failed: Start time ({start_seconds}) must be less than end time ({end_seconds})."
        print(f"[Task ID: {task_id}] {error_msg}")
        self.update_state(state='FAILURE', meta={'status': error_msg})
        raise ValueError(error_msg) # Raise to mark task as failed

    try:
        self.update_state(state='STARTED', meta={'status': 'Downloading original audio...'})
        print(f"[Task ID: {task_id}] Downloading {r2_object_key} from R2...")
        
        # 1. Download original audio 
        audio_bytes = utils_r2.download_blob_to_memory(r2_object_key)
        if not audio_bytes:
            raise FileNotFoundError(f"Failed to download audio from R2: {r2_object_key}")

        # <<< Wrap downloaded bytes in a BytesIO stream >>>
        audio_stream = io.BytesIO(audio_bytes)

        self.update_state(state='PROGRESS', meta={'status': 'Loading audio data...'})
        print(f"[Task ID: {task_id}] Loading audio data...")
        
        file_format = r2_object_key.split('.')[-1].lower() if '.' in r2_object_key else "mp3"
        
        with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=True) as tmp_file:
            print(f"[Task ID: {task_id}] Writing audio to temporary file: {tmp_file.name}")
            # <<< Read from the stream, not the original bytes object >>>
            # audio_bytes_io.seek(0) 
            audio_stream.seek(0) # Go to the start of the stream
            tmp_file.write(audio_stream.read()) # Write bytes from stream to temp file
            tmp_file.flush() 

            # 2. Load audio using pydub FROM THE TEMP FILE PATH
            try:
                audio_segment = AudioSegment.from_file(tmp_file.name, format=file_format)
            except Exception as e:
                # Add specific handling for potential file not found errors from ffmpeg/ffprobe
                if "No such file or directory" in str(e):
                     print(f"[Task ID: {task_id}] ERROR: pydub/ffmpeg could not find temp file '{tmp_file.name}' even though it should exist. Check permissions or ffmpeg installation.")
                raise RuntimeError(f"Failed to load audio data with pydub from temp file: {e}") from e

        # Temp file is automatically deleted when exiting the 'with' block

        self.update_state(state='PROGRESS', meta={'status': 'Cropping audio...'})
        print(f"[Task ID: {task_id}] Cropping audio...")

        # 3. Convert times and crop
        start_ms = int(start_seconds * 1000)
        end_ms = int(end_seconds * 1000)

        # Pydub slicing is [start:end]
        cropped_audio = audio_segment[start_ms:end_ms]
        original_duration = len(audio_segment) / 1000.0
        cropped_duration = len(cropped_audio) / 1000.0

        print(f"[Task ID: {task_id}] Cropped audio from {original_duration:.2f}s to {cropped_duration:.2f}s.")
        
        self.update_state(state='PROGRESS', meta={'status': 'Exporting cropped audio...'})
        print(f"[Task ID: {task_id}] Exporting cropped audio...")

        # 4. Export cropped audio to memory buffer
        cropped_buffer = io.BytesIO()
        cropped_audio.export(cropped_buffer, format="mp3")
        cropped_buffer.seek(0)

        self.update_state(state='PROGRESS', meta={'status': 'Uploading cropped audio...'})
        print(f"[Task ID: {task_id}] Uploading cropped audio back to {r2_object_key}...")

        # 5. Upload cropped audio, overwriting original
        upload_success = utils_r2.upload_blob(
            blob_name=r2_object_key,
            data=cropped_buffer,
            content_type='audio/mpeg'
        )

        if not upload_success:
            raise ConnectionError(f"Failed to upload cropped audio to R2: {r2_object_key}")

        # 6. Success
        final_status_msg = f"Successfully cropped {r2_object_key}. New duration: {cropped_duration:.2f}s (Original: {original_duration:.2f}s)."
        print(f"[Task ID: {task_id}] {final_status_msg}")
        self.update_state(state='SUCCESS', meta={'status': final_status_msg})
        return {'status': 'SUCCESS', 'message': final_status_msg}

    except Exception as e:
        error_msg = f"Crop task failed for {r2_object_key}: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}] {error_msg}")
        self.update_state(state='FAILURE', meta={'status': error_msg})
        # Re-raise exception so Celery marks task as failed
        raise e

# --- New Task for VO Script Agent --- #

@celery.task(bind=True, base=Task, name='tasks.run_script_creation_agent')
def run_script_creation_agent(self, 
                              generation_job_db_id: int, 
                              vo_script_id: int, 
                              task_type: str, 
                              feedback_data: dict | None,
                              category_name: str | None = None):
    """Celery task to run the ScriptWriterAgent."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received script agent task.")
    print(f"  VO Script ID: {vo_script_id}")
    print(f"  Task Type: {task_type}")
    print(f"  Category Name: {category_name}")
    print(f"  Feedback Data: {feedback_data}")
    
    db: Session = next(models.get_db())
    db_job = None
    try:
        # --- 1. Update Job Status to STARTED --- 
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            raise Ignore("GenerationJob record not found.")
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id
        # Store category name in job parameters if provided
        job_params = {}
        try: 
            job_params = json.loads(db_job.parameters_json) if db_job.parameters_json else {}
        except json.JSONDecodeError:
             logging.warning(f"[Task ID: {task_id}] Could not parse existing job parameters JSON.")

        job_params['task_type'] = task_type # Ensure task_type is always there
        if category_name:
           job_params['category_name'] = category_name
        if feedback_data: # Include feedback if provided
             job_params['feedback'] = feedback_data
             
        db_job.parameters_json = json.dumps(job_params)
        db.commit()
        self.update_state(state='STARTED', meta={'status': f'Agent task started ({task_type}, Category: {category_name or "All"})', 'db_id': generation_job_db_id})
        
        # --- 2. Instantiate Agent --- 
        agent_model_name = os.environ.get('OPENAI_AGENT_MODEL', 'gpt-4o')
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Using Agent Model: {agent_model_name}")
        agent_instance = ScriptWriterAgent(model_name=agent_model_name)
        
        # --- 3. Prepare Agent Input --- 
        initial_prompt = ""
        # user_provided_prompt = None # No longer needed here
        
        # --- Fetch relevant refinement prompt from DB --- #
        # This logic is likely no longer needed for draft generation
        # script = db.query(models.VoScript).options(...).get(vo_script_id)
        # if not script:
        #      raise ValueError(...)
        # if task_type == 'refine_category' and category_name:
        #     # ... fetch category prompt ...
        #     user_provided_prompt = ...
        # elif task_type == 'refine_feedback':
        #     # ... fetch script prompt ...
        #     user_provided_prompt = ...
        # --- End Fetching Prompt --- #

        # --- Construct Agent Prompt --- #
        base_instruction = ""
        target_statuses = []

        if task_type == 'generate_draft':
             base_instruction = f"Generate the initial draft for all 'pending' lines in VO Script ID {vo_script_id}. Focus on fulfilling the core request for each line based on its key, hints, category instructions, and the character description provided by the get_vo_script_details tool."
             target_statuses = ['pending'] # Agent should only ask for pending lines
        # --- Remove refine_category prompt logic --- #
        # elif task_type == 'refine_category' and category_name:
        #      target_statuses = ['generated', 'review']
        #      base_instruction = f"Refine all lines in the '{category_name}' category (statuses: {target_statuses}) for VO Script ID {vo_script_id}. Improve clarity, flow, and ensure they match the character description."
        # --- Remove refine_feedback prompt logic --- #
        # elif task_type == 'refine_feedback':
        #      feedback_str = json.dumps(feedback_data) if feedback_data else "No specific feedback provided."
        #      if user_provided_prompt: # If script prompt exists, refine generated/review lines
        #          target_statuses = ['generated', 'review']
        #          base_instruction = f"Refine all lines (statuses: {target_statuses}) in VO Script ID {vo_script_id}, paying close attention to any line-specific feedback ({feedback_str})."
        #      else: # No script prompt, only refine lines with feedback or status 'review'
        #          target_statuses = ['review'] # Could also fetch lines with non-null feedback directly if tool supports it
        #          base_instruction = f"Refine lines in VO Script ID {vo_script_id} that have status 'review' or have specific feedback ({feedback_str})."
        else:
             # Now only draft is supported by this task
             raise ValueError(f"Unsupported task_type ('{task_type}') for agent task. Only 'generate_draft' allowed.")

        # --- Simplified prompt construction for generate_draft --- #
        # if user_provided_prompt: # No longer using user_provided_prompt here
        #     initial_prompt = f"Follow these instructions carefully: \"{user_provided_prompt}\".\n\n{base_instruction} Target lines with statuses {target_statuses}. Use the available tools to fetch script details and update lines."
        # else:
        #     initial_prompt = f"{base_instruction} Target lines with statuses {target_statuses}. Use the available tools to fetch script details and update lines."
        initial_prompt = f"{base_instruction} Target lines with statuses {target_statuses}. Use the available tools (get_vo_script_details, get_lines_for_processing, update_script_line) to fetch script details and update lines."
        
        logging.info(f"[Task ID: {task_id}] Agent instructed to target statuses: {target_statuses}")
        
        # --- End Construct Agent Prompt --- #

        # --- 4. Run the Agent --- 
        print(f"[Task ID: {task_id}] Running agent with prompt: {initial_prompt[:200]}...")
        agent_result = agent_instance.run(initial_prompt=initial_prompt)

        # --- 5. Process Agent Result --- 
        if hasattr(agent_result, 'final_output') and agent_result.final_output:
             final_status = "SUCCESS"
             result_msg = f"Agent successfully completed task '{task_type}' for script {vo_script_id}. Output: {agent_result.final_output}"
        else:
             final_status = "FAILURE"
             output_for_error = getattr(agent_result, 'final_output', '[No Output]') 
             result_msg = f"Agent task '{task_type}' failed or produced no output for script {vo_script_id}. Last Output: {output_for_error}"

        # --- 6. Update Job Status --- 
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = result_msg
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Agent task finished. Updated job status to {final_status}.")
        
        return {'status': final_status, 'message': result_msg}
        
    except Exception as e:
        error_msg = f"Script agent task failed unexpectedly: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        if db_job:
            db_job.status = "FAILURE"; db_job.completed_at = datetime.utcnow(); db_job.result_message = error_msg
            try: db.commit()
            except: db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e
    finally:
        if db: db.close()

# --- New Task for Category Batch Generation --- #
@celery.task(bind=True, name='tasks.generate_category_lines')
def generate_category_lines(self, 
                            generation_job_db_id: int, 
                            vo_script_id: int, 
                            category_name: str, 
                            target_model: str = None):
    """Celery task to generate all pending lines in a category together, ensuring variety."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received category batch generation task.")
    print(f"  VO Script ID: {vo_script_id}")
    print(f"  Category Name: {category_name}")
    print(f"  Target Model: {target_model or 'Default Model'}")
    
    db: Session = next(models.get_db())
    db_job = None
    try:
        # --- 1. Update Job Status to STARTED --- 
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            raise Ignore("GenerationJob record not found.")
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id
        
        # Store parameters in job
        job_params = {}
        try: 
            job_params = json.loads(db_job.parameters_json) if db_job.parameters_json else {}
        except json.JSONDecodeError:
             logging.warning(f"[Task ID: {task_id}] Could not parse existing job parameters JSON.")

        job_params['task_type'] = 'generate_category'
        job_params['category_name'] = category_name
        if target_model:
            job_params['model'] = target_model
             
        db_job.parameters_json = json.dumps(job_params)
        db.commit()
        self.update_state(state='STARTED', meta={'status': f'Category batch generation started (Category: {category_name})', 'db_id': generation_job_db_id})
        
        # --- 2. Call our batch generation function --- 
        # Import needed utilities here to avoid circular imports
        from backend.utils_voscript import get_category_lines_context, update_line_in_db
        from backend.routes.vo_script_routes import _generate_lines_batch
        
        # Fetch pending lines (current logic is likely fine)
        pending_lines_details = utils_voscript.get_category_lines_details(db, vo_script_id, category_name, status_filter='pending')
        pending_lines = [model_to_dict(line, keys=['line_id', 'line_key', 'prompt_hint', 'category_name', 'character_description', 'template_hint', 'current_text', 'order_index']) for line in pending_lines_details]

        if not pending_lines:
            logging.warning(f"[Task ID: {task_id}] No pending lines found for category '{category_name}'. Task completing.")
            # Update job status to reflect completion (maybe COMPLETED_NO_WORK?)
            try:
                 job = db.query(models.GenerationJob).get(generation_job_db_id)
                 if job:
                     job.status = "SUCCESS" # Or a more specific status
                     job.completed_at = datetime.now(timezone.utc)
                     job.result_message = "No pending lines needed generation."
                     db.commit()
            except Exception as e_job:
                 logging.error(f"[Task ID: {task_id}] Failed to update job status for no pending lines: {e_job}")
                 db.rollback()
            db.close()
            return {'status': 'COMPLETED', 'message': 'No pending lines found to generate.', 'db_id': generation_job_db_id}

        # --- NEW: Fetch ALL lines for context, similar to refine ---
        all_lines_for_context = utils_voscript.get_category_lines_context(db, vo_script_id, category_name)
        # --- END NEW ---

        logging.warning(f"[Task ID: {task_id}] Found {len(pending_lines)} pending lines to generate for category '{category_name}'.")

        # Determine batching strategy
        if len(pending_lines) <= BATCH_GENERATION_THRESHOLD:
            # Batch Generation (Ideal for smaller batches)
            print(f"[Task ID: {task_id}] Processing all {len(pending_lines)} lines in a single batch.")
            self.update_state(state='PROGRESS', meta={
                'status': f'Generating {len(pending_lines)} lines in batch',
                'progress': 50,
                'db_id': generation_job_db_id
            })
            # FIX: Pass all_lines_for_context as the existing_lines argument
            updated_lines_data = _generate_lines_batch(db, vo_script_id, pending_lines, all_lines_for_context, target_model)
        else:
            # Split into smaller batches (For larger sets)
            # ... (logging and state update) ...
            all_updated_lines = []
            total_lines = len(pending_lines)
            processed_count = 0
            
            for i in range(0, total_lines, SMALL_BATCH_SIZE):
                batch_pending = pending_lines[i:min(i + SMALL_BATCH_SIZE, total_lines)]
                batch_start_index = i + 1
                batch_end_index = i + len(batch_pending)
                logging.info(f"[Task ID: {task_id}] Processing small batch {batch_start_index}-{batch_end_index} of {total_lines}...")
                self.update_state(state='PROGRESS', meta={
                    'status': f'Generating lines {batch_start_index}-{batch_end_index} of {total_lines}',
                    'progress': int(50 + (processed_count / total_lines) * 50), # Rough progress update
                    'db_id': generation_job_db_id
                })
                
                # FIX: Pass all_lines_for_context as the existing_lines argument
                batch_results = _generate_lines_batch(db, vo_script_id, batch_pending, all_lines_for_context, target_model)
                all_updated_lines.extend(batch_results)
                processed_count += len(batch_pending)
                
                # Optional: Add a small delay between batches if needed
                # time.sleep(1) 
                
            updated_lines_data = all_updated_lines
            logging.info(f"[Task ID: {task_id}] Finished processing all small batches.")

        # Update the database with the generated text
        # ... (rest of the task - updating DB lines) ...

        # 3. Update Job Status
        if errors_occurred:
            final_status = "COMPLETED_WITH_ERRORS"
            message = f"Category generation completed with some errors. Generated {len(updated_lines_data)} out of {len(pending_lines)} lines."
        else:
            final_status = "SUCCESS"
            message = f"Successfully generated {len(updated_lines_data)} lines for category '{category_name}'."
            
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = message
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Category batch generation finished. Updated job status to {final_status}.")
        
        return {'status': final_status, 'message': message, 'data': updated_lines_data}
        
    except Exception as e:
        error_msg = f"Category batch generation task failed: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        if db_job:
            db_job.status = "FAILURE"
            db_job.completed_at = datetime.utcnow()
            db_job.result_message = error_msg
            try:
                db.commit()
            except:
                db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e
    finally:
        if db:
            db.close()

# --- Placeholder Task (Keep or Remove) --- #
# @celery.task(bind=True)
# def placeholder_task(self):
#     task_id = self.request.id
#     print(f"Running placeholder_task (ID: {task_id})...")
#     self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100})
#     time.sleep(5)
#     print(f"placeholder_task (ID: {task_id}) finished.")
#     return {"status": "Complete", "result": "Placeholder result"}

# Add other generation tasks here later 