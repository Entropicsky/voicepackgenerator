# backend/tasks/regeneration_tasks.py
"""
Tasks for regenerating specific voice lines, including speech-to-speech.
"""
from backend.celery_app import celery
from backend import models
from backend import utils_elevenlabs
from backend import utils_r2
from sqlalchemy.orm import Session
import json
import random
from datetime import datetime, timezone
from celery.exceptions import Ignore, Retry
import base64
import logging

print("Celery Worker: Loading regeneration_tasks.py...")

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
                    "rank": None, "ranked_at": None
                }
                new_metadata_takes.append(new_take_meta)
                newly_generated_takes_meta.append(new_take_meta)
            except Exception as e:
                print(f"[Task ID: {task_id}] ERROR generating/uploading take {r2_blob_key}: {e}")
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