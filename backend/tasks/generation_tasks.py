"""
Tasks for full batch voice generation.
"""
from backend.celery_app import celery
from backend import models
from backend import utils_elevenlabs
from backend import utils_r2
from sqlalchemy.orm import Session
import time
import json
import random
from datetime import datetime, timezone
from celery.exceptions import Ignore, Retry
import logging
from sqlalchemy.orm import joinedload, selectinload

print("Celery Worker: Loading generation_tasks.py...")

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