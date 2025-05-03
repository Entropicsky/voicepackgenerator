"""
Tasks for audio file processing and manipulation.
"""
from backend.celery_app import celery
from backend import utils_r2
from celery.exceptions import Ignore
import base64
import io  # for in-memory file handling
from pydub import AudioSegment  # for audio processing
import tempfile  # for temporary file handling
import logging

print("Celery Worker: Loading audio_tasks.py...")

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