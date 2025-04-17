# backend/tasks.py
from celery_app import celery_app
from backend import utils_elevenlabs
from backend import utils_fs
import time
import json
import os
import csv
import random
from pathlib import Path
from datetime import datetime, timezone

print("Celery Worker: Loading tasks.py...")

@celery_app.task(bind=True, name='tasks.run_generation')
def run_generation(self, config_json: str):
    """Celery task to generate a batch of voice takes."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}] Starting generation task...")
    self.update_state(state='STARTED', meta={'status': 'Parsing configuration...'})

    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        print(f"[Task ID: {task_id}] Error decoding config JSON: {e}")
        self.update_state(state='FAILURE', meta={'status': f'Invalid configuration JSON: {e}'})
        # Use Celery's Ignore to prevent retries for bad input
        from celery.exceptions import Ignore
        raise Ignore()

    # --- Configuration Validation (Basic) ---
    required_keys = ['skin_name', 'voice_ids', 'script_csv_content', 'variants_per_line']
    if not all(key in config for key in required_keys):
        missing = [key for key in required_keys if key not in config]
        status_msg = f'Missing required configuration keys: {missing}'
        print(f"[Task ID: {task_id}] {status_msg}")
        self.update_state(state='FAILURE', meta={'status': status_msg})
        from celery.exceptions import Ignore
        raise Ignore()

    skin_name: str = config['skin_name']
    voice_ids: list[str] = config['voice_ids']
    script_csv_content: str = config['script_csv_content'] # Expect CSV as a string
    variants_per_line: int = config['variants_per_line']
    model_id: str = config.get('model_id', utils_elevenlabs.DEFAULT_MODEL)
    output_format: str = config.get('output_format', 'mp3_44100_128')

    # TTS Parameter Ranges (provide defaults if not specified)
    stability_range = config.get('stability_range', [0.5, 0.75])
    similarity_boost_range = config.get('similarity_boost_range', [0.75, 0.9])
    style_range = config.get('style_range', [0.0, 0.5]) # Adjust default if needed
    speed_range = config.get('speed_range', [0.9, 1.1])
    use_speaker_boost = config.get('use_speaker_boost', True)

    # --- Get ROOT dir (from env var within container) ---
    audio_root_str = os.getenv('AUDIO_ROOT')
    if not audio_root_str:
        status_msg = 'AUDIO_ROOT environment variable not set in worker.'
        print(f"[Task ID: {task_id}] {status_msg}")
        # This is an environment setup error, might retry indefinitely without Ignore
        self.update_state(state='FAILURE', meta={'status': status_msg})
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
        print(f"[Task ID: {task_id}] {status_msg}")
        self.update_state(state='FAILURE', meta={'status': status_msg})
        from celery.exceptions import Ignore
        raise Ignore()

    total_takes_to_generate = len(voice_ids) * len(script_data) * variants_per_line
    generated_takes_count = 0
    print(f"[Task ID: {task_id}] Parsed config. Total takes to generate: {total_takes_to_generate}")

    # --- Generation Loop ---
    all_batches_metadata = [] # Store metadata for all generated batches

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
            print(f"[Task ID: {task_id}] Warning: Could not get voice name for {voice_id}: {e}")
            voice_folder_name = voice_id # Fallback to ID

        batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        batch_id = f"{batch_timestamp}-{voice_id[:4]}"
        batch_dir = audio_root / skin_name / voice_folder_name / batch_id
        takes_dir = batch_dir / "takes"

        try:
            takes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            status_msg = f'Failed to create directory {takes_dir}: {e}'
            print(f"[Task ID: {task_id}] {status_msg}")
            self.update_state(state='FAILURE', meta={'status': status_msg})
            from celery.exceptions import Retry
            raise Retry(exc=e, countdown=30) # Retry on filesystem error

        print(f"[Task ID: {task_id}] Created batch directory: {batch_dir}")

        batch_metadata = {
            "batch_id": batch_id,
            "skin_name": skin_name,
            "voice_name": voice_folder_name,
            "generated_at_utc": None, # Will be set at the end
            "generation_params": config, # Store original config
            "ranked_at_utc": None,
            "takes": []
        }

        # --- Line & Variant Loop ---
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

                # Randomize settings for this take
                stability = random.uniform(*stability_range)
                similarity_boost = random.uniform(*similarity_boost_range)
                style = random.uniform(*style_range)
                speed = random.uniform(*speed_range)

                take_settings = {
                    'stability': stability,
                    'similarity_boost': similarity_boost,
                    'style': style,
                    'use_speaker_boost': use_speaker_boost,
                    'speed': speed
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
                        stability=stability,
                        similarity_boost=similarity_boost,
                        style=style,
                        speed=speed,
                        use_speaker_boost=use_speaker_boost
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

                except utils_elevenlabs.ElevenLabsError as e:
                    # Log error for this take, but continue with others
                    print(f"[Task ID: {task_id}] ERROR generating take {output_filename}: {e}")
                    # TODO: Decide if one failed take should fail the whole batch/task?
                    # For now, we continue.
                except Exception as e:
                    print(f"[Task ID: {task_id}] UNEXPECTED ERROR during take {output_filename} generation: {e}")
                    # Optionally fail the task here if needed

        # --- Post-Voice Processing ---
        if batch_metadata['takes']: # Only save metadata if some takes were successful
             batch_metadata["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
             try:
                 utils_fs.save_metadata(batch_dir, batch_metadata)
                 print(f"[Task ID: {task_id}] Saved metadata for batch: {batch_id}")
                 all_batches_metadata.append(batch_metadata) # Add for final result
             except utils_fs.FilesystemError as e:
                 print(f"[Task ID: {task_id}] ERROR saving metadata for batch {batch_id}: {e}")
                 # Fail the task if metadata saving fails?
                 self.update_state(state='FAILURE', meta={'status': f'Failed to save metadata for {batch_id}: {e}'})
                 from celery.exceptions import Retry
                 raise Retry(exc=e, countdown=60)
        else:
            print(f"[Task ID: {task_id}] No successful takes generated for voice {voice_id}, skipping metadata saving for batch {batch_id}.")


    # --- Task Completion ---
    final_status_msg = f"Generation complete. Processed {len(voice_ids)} voices, generated {generated_takes_count}/{total_takes_to_generate} takes."
    print(f"[Task ID: {task_id}] {final_status_msg}")

    # Return info about generated batches
    result_payload = {
        'status': 'SUCCESS',
        'message': final_status_msg,
        'generated_batches': [
            {'batch_id': b['batch_id'], 'voice': b['voice_name'], 'skin': b['skin_name'], 'take_count': len(b['takes'])}
            for b in all_batches_metadata
        ]
    }
    self.update_state(state='SUCCESS', meta=result_payload)
    return result_payload

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