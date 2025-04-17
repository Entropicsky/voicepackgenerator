# backend/tasks.py
from celery_app import celery_app
from backend import utils_elevenlabs, utils_fs, models # Import models
from sqlalchemy.orm import Session
import time
import json
import os
import csv
import random
from pathlib import Path
from datetime import datetime, timezone
from celery.exceptions import Ignore, Retry
import shutil
import base64

print("Celery Worker: Loading tasks.py...")

@celery_app.task(bind=True, name='tasks.run_generation')
def run_generation(self, generation_job_db_id: int, config_json: str):
    """Celery task to generate a batch of voice takes, updating DB status."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received generation task.")
    
    db: Session = next(models.get_db()) # Get DB session for this task execution
    db_job = None
    try:
        # Update DB status to STARTED
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR: GenerationJob record not found.")
            # Cannot update status, but maybe still proceed? Or raise Ignore?
            from celery.exceptions import Ignore
            raise Ignore() # Ignore if DB record is missing
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id # Ensure celery task ID is stored
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")

        # Update Celery state for intermediate progress (optional but good)
        self.update_state(state='STARTED', meta={'status': 'Parsing configuration...', 'db_id': generation_job_db_id})

        config = json.loads(config_json)
        # --- Config Validation / Setup --- 
        skin_name = config['skin_name']
        voice_ids = config['voice_ids']
        script_csv_content = config['script_csv_content']
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

        # --- Get ROOT dir (from env var within container) ---
        audio_root_str = os.getenv('AUDIO_ROOT')
        if not audio_root_str:
            status_msg = 'AUDIO_ROOT environment variable not set in worker.'
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
            # This is an environment setup error, might retry indefinitely without Ignore
            self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
            from celery.exceptions import Ignore
            raise Ignore()
        audio_root = Path(audio_root_str)

        # --- Prepare Script Data ---
        try:
            # Use csv.reader on the string content
            lines = list(csv.reader(script_csv_content.splitlines()))
            if not lines or len(lines[0]) < 2:
                 raise ValueError("CSV content is empty or header missing/invalid")
            header = [h.strip() for h in lines[0]]
            # Assuming header columns are 'Function' and 'Line'
            func_idx = header.index('Function')
            line_idx = header.index('Line')
            script_data = [
                {'Function': row[func_idx].strip(), 'Line': row[line_idx].strip()}
                for row in lines[1:] if len(row) > max(func_idx, line_idx)
            ]
            if not script_data:
                 raise ValueError("No valid data rows found in CSV content")
        except (ValueError, IndexError, Exception) as e:
            status_msg = f'Error parsing script CSV content: {e}'
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
            self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
            from celery.exceptions import Ignore
            raise Ignore()

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
            batch_dir = audio_root / skin_name / voice_folder_name / batch_id
            takes_dir = batch_dir / "takes"

            try:
                takes_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                status_msg = f'Failed to create directory {takes_dir}: {e}'
                print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {status_msg}")
                self.update_state(state='FAILURE', meta={'status': status_msg, 'db_id': generation_job_db_id})
                from celery.exceptions import Retry
                raise Retry(exc=e, countdown=30) # Retry on filesystem error

            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Created batch directory: {batch_dir}")

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
                    output_path = takes_dir / output_filename

                    try:
                        utils_elevenlabs.generate_tts_audio(
                            text=line_text,
                            voice_id=voice_id,
                            output_path=str(output_path),
                            model_id=model_id,
                            output_format=output_format,
                            # Pass the RANDOMIZED settings for this take
                            stability=stability_take,
                            similarity_boost=similarity_boost_take,
                            style=style_take,
                            speed=speed_take,
                            use_speaker_boost=use_speaker_boost # Pass fixed value
                        )

                        # Add take metadata
                        batch_metadata["takes"].append({
                            "file": output_filename,
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
                        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR generating take {output_filename}: {e}")
                        elevenlabs_failures += 1
                    except Exception as e:
                        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] UNEXPECTED ERROR during take {output_filename} generation: {e}")
                        # Decide if unexpected errors should count as failure?
                        elevenlabs_failures += 1 # Count unexpected as failure too

            # --- Post-Voice Processing ---
            if voice_has_success:
                batch_metadata["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
                try:
                    utils_fs.save_metadata(batch_dir, batch_metadata)
                    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Saved metadata for batch: {batch_id}")
                    all_batches_metadata.append(batch_metadata) # Add for final result
                except utils_fs.FilesystemError as e:
                    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR saving metadata for batch {batch_id}: {e}")
                    # Fail the task if metadata saving fails?
                    self.update_state(state='FAILURE', meta={'status': f'Failed to save metadata for {batch_id}: {e}', 'db_id': generation_job_db_id})
                    from celery.exceptions import Retry
                    raise Retry(exc=e, countdown=60)
            else:
                print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] No successful takes for voice {voice_id}, skipping metadata.")

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
        generated_batch_ids = [b['batch_id'] for b in all_batches_metadata]
        db_job.result_batch_ids_json = json.dumps(generated_batch_ids)
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to {final_db_status}.")

        # Celery result payload (can also reflect partial failure)
        return {
            'status': final_db_status, # Return the more granular status
            'message': final_status_msg,
            'generated_batches': [
                {'batch_id': b['batch_id'], 'voice': b['voice_name'], 'skin': b['skin_name'], 'take_count': len(b['takes'])}
                for b in all_batches_metadata
            ]
        }

    except (ValueError, OSError, utils_fs.FilesystemError, Exception) as e:
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
            except Exception as db_err:
                print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Failed to update job status to FAILURE: {db_err}")
                db.rollback()
        
        # Update Celery state
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        # Re-raise exception so Celery marks task as failed
        raise e
    finally:
        db.close() # Ensure session is closed for this task execution

# --- New Task for Line Regeneration --- #

@celery_app.task(bind=True, name='tasks.regenerate_line_takes')
def regenerate_line_takes(self, 
                          generation_job_db_id: int, 
                          batch_id: str, 
                          line_key: str, 
                          line_text: str, 
                          num_new_takes: int, 
                          settings_json: str, 
                          replace_existing: bool):
    """Generates new takes for a specific line within an existing batch."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received line regeneration task for Batch '{batch_id}', Line '{line_key}'")

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Update DB job status to STARTED
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] ERROR: GenerationJob record not found.")
            raise Ignore()
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id
        # Also store target info if not already set during job creation
        db_job.target_batch_id = batch_id
        db_job.target_line_key = line_key
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")
        self.update_state(state='STARTED', meta={'status': f'Preparing regeneration for line: {line_key}', 'db_id': generation_job_db_id})

        # Get settings from JSON
        settings = json.loads(settings_json)
        stability_range = settings.get('stability_range', [0.5, 0.75])
        similarity_boost_range = settings.get('similarity_boost_range', [0.75, 0.9])
        style_range = settings.get('style_range', [0.0, 0.45])
        speed_range = settings.get('speed_range', [0.95, 1.05])
        use_speaker_boost = settings.get('use_speaker_boost', True)
        model_id = settings.get('model_id', utils_elevenlabs.DEFAULT_MODEL)
        output_format = settings.get('output_format', 'mp3_44100_128')

        # Get batch directory and load metadata
        audio_root = Path(os.getenv('AUDIO_ROOT', '/app/output'))
        batch_dir = utils_fs.get_batch_dir(audio_root, batch_id)
        if not batch_dir or not batch_dir.is_dir():
            raise ValueError(f"Target batch directory not found for batch ID: {batch_id}")
        
        metadata = utils_fs.load_metadata(batch_dir)
        takes_dir = batch_dir / "takes"
        takes_dir.mkdir(exist_ok=True) # Ensure takes dir exists

        original_takes = metadata.get('takes', [])
        new_metadata_takes = []
        archived_files = []
        start_take_num = 1
        current_line_takes = [t for t in original_takes if t.get('line') == line_key]

        if replace_existing:
            print(f"[Task ID: {task_id}] Replacing existing takes for line '{line_key}'")
            self.update_state(state='PROGRESS', meta={'status': f'Archiving old takes for line: {line_key}', 'db_id': generation_job_db_id})
            
            archive_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            archive_dir = takes_dir / f"archived_{line_key.replace(' ', '_')}_{archive_timestamp}"
            try:
                archive_dir.mkdir(parents=True)
                for take in current_line_takes:
                    old_path = takes_dir / take['file']
                    if old_path.is_file():
                        new_path = archive_dir / take['file']
                        shutil.move(str(old_path), str(new_path))
                        archived_files.append(take['file'])
                    elif old_path.is_symlink(): # Handle potential old symlinks in takes?
                         os.unlink(old_path)
            except OSError as e:
                print(f"[Task ID: {task_id}] Warning: Failed to archive old takes: {e}")
                # Decide whether to continue or fail
            
            # Filter out the old takes for this line
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
                'progress': int(100 * (i + 1) / num_new_takes) # Progress within this line regen
            })

            stability_take = random.uniform(*stability_range)
            similarity_boost_take = random.uniform(*similarity_boost_range)
            style_take = random.uniform(*style_range)
            speed_take = random.uniform(*speed_range)
            
            take_settings = { 'stability': stability_take, 'similarity_boost': similarity_boost_take, 'style': style_take, 'use_speaker_boost': use_speaker_boost, 'speed': speed_take }
            output_filename = f"{line_key}_take_{take_num}.mp3"
            output_path = takes_dir / output_filename

            try:
                utils_elevenlabs.generate_tts_audio(
                    text=line_text, voice_id=metadata['voice_name'].split('-')[-1], # Extract voice ID
                    output_path=str(output_path), model_id=model_id,
                    output_format=output_format, stability=stability_take,
                    similarity_boost=similarity_boost_take, style=style_take,
                    speed=speed_take, use_speaker_boost=use_speaker_boost
                )
                new_take_meta = {
                    "file": output_filename, "line": line_key,
                    "script_text": line_text, "take_number": take_num,
                    "generation_settings": take_settings, "rank": None, "ranked_at": None
                }
                new_metadata_takes.append(new_take_meta)
                newly_generated_takes_meta.append(new_take_meta)
            except Exception as e:
                print(f"[Task ID: {task_id}] ERROR generating take {output_filename} for line regen: {e}")
                failures += 1
        
        # Update metadata file
        metadata['takes'] = new_metadata_takes
        # Add note about regeneration?
        metadata['last_regenerated_line'] = {'line': line_key, 'at': datetime.now(timezone.utc).isoformat(), 'num_added': len(newly_generated_takes_meta), 'replaced': replace_existing}
        utils_fs.save_metadata(batch_dir, metadata)
        print(f"[Task ID: {task_id}] Updated metadata for batch {batch_id} after regenerating line {line_key}.")

        # --- Update DB Job --- 
        final_status = "SUCCESS" if failures == 0 else "COMPLETED_WITH_ERRORS" if failures < num_new_takes else "FAILURE"
        result_msg = f"Regenerated line '{line_key}'. Added {len(newly_generated_takes_meta)} takes ({failures} failures). Replaced existing: {replace_existing}. Archived: {len(archived_files)} files."
        if final_status == "FAILURE":
             result_msg = f"Failed to regenerate any takes for line '{line_key}'. ({failures} failures). Replaced existing: {replace_existing}. Archived: {len(archived_files)} files."
             
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = result_msg
        # Store generated filenames?
        # db_job.result_batch_ids_json = json.dumps([t['file'] for t in newly_generated_takes_meta])
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to {final_status}.")

        return {'status': final_status, 'message': result_msg}

    except Exception as e:
        error_msg = f"Line regeneration task failed: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        if db_job:
            db_job.status = "FAILURE"
            db_job.completed_at = datetime.utcnow()
            db_job.result_message = error_msg
            try:
                db.commit()
            except Exception as db_err:
                print(f"[...] Failed to update job status to FAILURE: {db_err}")
                db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e
    finally:
        db.close()

# --- New Task for Speech-to-Speech Line Regeneration --- #

@celery_app.task(bind=True, name='tasks.run_speech_to_speech_line')
def run_speech_to_speech_line(self,
                              generation_job_db_id: int,
                              batch_id: str,
                              line_key: str,
                              source_audio_b64: str, # Expecting full data URI e.g., data:audio/wav;base64,...
                              num_new_takes: int,
                              target_voice_id: str,
                              model_id: str,
                              settings_json: str,
                              replace_existing: bool):
    """Generates new takes for a line using Speech-to-Speech."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received STS task for Batch '{batch_id}', Line '{line_key}'")

    db: Session = next(models.get_db())
    db_job = None
    try:
        # --- Update Job Status --- 
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job: raise Ignore() # Ignore if DB record missing
        db_job.status = "STARTED"; db_job.started_at = datetime.utcnow(); db_job.celery_task_id = task_id
        db.commit()
        self.update_state(state='STARTED', meta={'status': f'Preparing STS for line: {line_key}', 'db_id': generation_job_db_id})
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Updated job status to STARTED.")

        # --- Decode Audio & Settings --- 
        try:
            header, encoded = source_audio_b64.split(';base64,', 1)
            audio_data_bytes = base64.b64decode(encoded)
            # Can get mime type from header if needed: header.split(':')[1]
        except Exception as e:
            raise ValueError(f"Failed to decode source audio base64 data: {e}") from e
        
        settings = json.loads(settings_json) # Stability, Similarity
        # Extract specific settings for ElevenLabs STS API
        sts_voice_settings = {
            key: settings.get(key) for key in ['stability', 'similarity_boost'] if settings.get(key) is not None
        }

        # --- Prepare Filesystem & Metadata --- 
        audio_root = Path(os.getenv('AUDIO_ROOT', '/app/output'))
        batch_dir = utils_fs.get_batch_dir(audio_root, batch_id)
        if not batch_dir or not batch_dir.is_dir(): raise ValueError(f"Target batch dir not found: {batch_id}")
        metadata = utils_fs.load_metadata(batch_dir)
        takes_dir = batch_dir / "takes"
        takes_dir.mkdir(exist_ok=True)

        original_takes = metadata.get('takes', [])
        new_metadata_takes = []
        archived_files = []
        start_take_num = 1
        current_line_takes = [t for t in original_takes if t.get('line') == line_key]
        
        if replace_existing:
            print(f"[...] Replacing existing takes for line '{line_key}' before STS.")
            self.update_state(state='PROGRESS', meta={'status': f'Archiving old takes...', 'db_id': generation_job_db_id})
            archive_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            archive_dir = takes_dir / f"archived_{line_key.replace(' ', '_')}_{archive_timestamp}"
            try:
                archive_dir.mkdir(parents=True)
                for take in current_line_takes:
                    old_path = takes_dir / take['file']
                    if old_path.is_file(): shutil.move(str(old_path), str(archive_dir / take['file'])); archived_files.append(take['file'])
                    elif old_path.is_symlink(): os.unlink(old_path)
            except OSError as e: print(f"[...] Warning: Failed to archive old takes: {e}")
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
            output_path = takes_dir / output_filename

            try:
                result_audio_bytes = utils_elevenlabs.run_speech_to_speech_conversion(
                    audio_data=audio_data_bytes,
                    target_voice_id=target_voice_id,
                    model_id=model_id,
                    voice_settings=sts_voice_settings
                )
                # Save the resulting audio
                with open(output_path, 'wb') as f:
                    f.write(result_audio_bytes)
                print(f"[...] Successfully saved STS audio to {output_path}")

                new_take_meta = {
                    "file": output_filename, "line": line_key,
                    "script_text": "[STS]", # Indicate it was generated via STS
                    "take_number": take_num,
                    "generation_settings": {**settings, 'source_audio_info': header}, # Store STS settings used
                    "rank": None, "ranked_at": None
                }
                new_metadata_takes.append(new_take_meta)
                newly_generated_takes_meta.append(new_take_meta)
            except Exception as e:
                print(f"[...] ERROR generating STS take {output_filename}: {e}")
                failures += 1

        # --- Update Metadata & DB Job --- 
        metadata['takes'] = new_metadata_takes
        metadata['last_regenerated_line'] = { 'line': line_key, 'at': datetime.now(timezone.utc).isoformat(), 'num_added': len(newly_generated_takes_meta), 'replaced': replace_existing, 'type': 'sts' }
        utils_fs.save_metadata(batch_dir, metadata)
        print(f"[...] Updated metadata for batch {batch_id} after STS for line {line_key}.")

        final_status = "SUCCESS" if failures == 0 else "COMPLETED_WITH_ERRORS" if failures < num_new_takes else "FAILURE"
        result_msg = f"STS for line '{line_key}' complete. Added {len(newly_generated_takes_meta)} takes ({failures} failures). Replaced: {replace_existing}. Archived: {len(archived_files)}."
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
# @celery_app.task(bind=True)
# def placeholder_task(self):
#     task_id = self.request.id
#     print(f"Running placeholder_task (ID: {task_id})...")
#     self.update_state(state='PROGRESS', meta={'current': 50, 'total': 100})
#     time.sleep(5)
#     print(f"placeholder_task (ID: {task_id}) finished.")
#     return {"status": "Complete", "result": "Placeholder result"}

# Add other generation tasks here later 