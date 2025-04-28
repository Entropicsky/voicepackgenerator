# backend/tests/test_tasks.py
import pytest
import json
from unittest import mock
from celery.exceptions import Ignore, Retry
# Use relative imports or imports from 'backend'
from backend import tasks
from backend import utils_elevenlabs # To mock its functions
from backend import utils_r2       # Use backend.utils_r2
# from backend import utils_fs       # Use backend.utils_fs -> REMOVED as utils_fs was removed

# --- Test Data ---
valid_config_dict = {
    "skin_name": "TestSkin",
    "voice_ids": ["voice1", "voice2"],
    "script_csv_content": "Function,Line\nIntro_1,Hello there\nTaunt_1,Get ready",
    "variants_per_line": 2,
    "model_id": "test_model",
    "stability_range": [0.1, 0.2],
    "similarity_boost_range": [0.8, 0.9],
    "style_range": [0.3, 0.4],
    "speed_range": [1.0, 1.1],
    "use_speaker_boost": False
}

# --- Mocks & Fixtures ---

@pytest.fixture(autouse=True) # Apply to all tests in this module
def mock_env_vars(monkeypatch):
    """Mock environment variables needed by tasks."""
    monkeypatch.setenv('AUDIO_ROOT', '/app/output')
    # Assume ELEVENLABS_API_KEY is set via docker-compose/test setup

@pytest.fixture
def mock_task_base(mocker):
    """Mock base Celery task methods like update_state."""
    mock_update = mocker.patch('celery.app.task.Task.update_state')
    # Mock request object as well if needed, e.g., for task_id
    mock_request = mocker.patch('celery.app.task.Task.request', new_callable=mock.PropertyMock)
    mock_request.id = "test-task-id-123"
    return mock_update, mock_request

# --- Tests for run_generation --- #

@mock.patch('backend.utils_r2.upload_blob')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
@mock.patch('backend.utils_elevenlabs.get_available_voices')
@mock.patch('pathlib.Path.mkdir')
def test_run_generation_success(
    mock_mkdir, mock_get_voices, mock_generate_tts, mock_upload_blob,
    mock_task_base
):
    """Test successful run of the generation task (using R2)."""
    mock_update_state, _ = mock_task_base
    mock_get_voices.return_value = [
        {'voice_id': 'voice1', 'name': 'Voice One'},
        {'voice_id': 'voice2', 'name': 'Voice Two'}
    ]
    # Configure generate_tts mock if needed (e.g., check calls)

    config_str = json.dumps(valid_config_dict)
    result = tasks.run_generation(config_str)

    # --- Assertions ---
    # Check final state and result
    assert result['status'] == 'SUCCESS'
    assert len(result['generated_batches']) == 2 # One per voice
    assert result['generated_batches'][0]['voice'] == 'Voice One-voice1'
    assert result['generated_batches'][1]['voice'] == 'Voice Two-voice2'
    assert result['generated_batches'][0]['take_count'] == 4 # 2 lines * 2 variants

    # Check state updates (basic checks)
    mock_update_state.assert_any_call(state='STARTED', meta=mock.ANY)
    mock_update_state.assert_any_call(state='PROGRESS', meta=mock.ANY)
    mock_update_state.assert_called_with(state='SUCCESS', meta=result) # Check final call

    # Check directory creation
    # Expect mkdir for /app/output/TestSkin/Voice One-voice1/<batch_id>/takes
    # and /app/output/TestSkin/Voice Two-voice2/<batch_id>/takes
    assert mock_mkdir.call_count == 2
    mock_mkdir.assert_called_with(parents=True, exist_ok=True)

    # Check TTS calls (4 per voice = 8 total)
    assert mock_generate_tts.call_count == 8
    # Example check on one call's args (can be more specific)
    first_call_args = mock_generate_tts.call_args_list[0][1] # Get kwargs of first call
    assert first_call_args['text'] == 'Hello there'
    assert first_call_args['voice_id'] == 'voice1'
    assert 'TestSkin/Voice One-voice1' in first_call_args['output_path']
    assert 'Intro_1_take_1.mp3' in first_call_args['output_path']

    # Check R2 upload calls instead of fs save
    assert mock_upload_blob.call_count == 10 # 8 takes + 2 metadata files
    # Check metadata upload call
    meta_upload_call = [c for c in mock_upload_blob.call_args_list if 'metadata.json' in c[1]['blob_name']]
    assert len(meta_upload_call) == 2
    # Example check on one metadata upload
    saved_metadata = json.loads(meta_upload_call[0][1]['data'].decode('utf-8'))
    assert saved_metadata['voice_name'] == 'Voice One-voice1'
    assert len(saved_metadata['takes']) == 4
    # Check take upload call
    take_upload_call = [c for c in mock_upload_blob.call_args_list if 'takes/' in c[1]['blob_name']]
    assert len(take_upload_call) == 8

def test_run_generation_invalid_json_config(mock_task_base):
    mock_update_state, _ = mock_task_base
    with pytest.raises(Ignore):
        tasks.run_generation("this is not json")
    mock_update_state.assert_called_with(state='FAILURE', meta=mock.ANY)

def test_run_generation_missing_keys(mock_task_base):
    mock_update_state, _ = mock_task_base
    invalid_config = valid_config_dict.copy()
    del invalid_config['voice_ids']
    with pytest.raises(Ignore):
        tasks.run_generation(json.dumps(invalid_config))
    # Check if the failure message contains the missing key
    failure_meta = mock_update_state.call_args.kwargs['meta']
    assert "Missing required configuration keys: ['voice_ids']" in failure_meta['status']

@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
def test_run_generation_elevenlabs_error_continues(mock_generate_tts, mock_task_base, mock_env_vars):
    """Test that an error generating one take doesn't stop the whole batch (by default)."""
    mock_update_state, _ = mock_task_base
    # Simulate failure for first take of each voice
    mock_generate_tts.side_effect = [
        utils_elevenlabs.ElevenLabsError("Fail 1"), b"audio", b"audio", b"audio", # Voice 1
        utils_elevenlabs.ElevenLabsError("Fail 2"), b"audio", b"audio", b"audio"  # Voice 2
    ]

    with mock.patch('backend.utils_elevenlabs.get_available_voices') as mock_get_voices, \
         mock.patch('backend.utils_r2.upload_blob') as mock_upload_blob, \
         mock.patch('pathlib.Path.mkdir'):

        mock_get_voices.return_value = [
            {'voice_id': 'voice1', 'name': 'Voice One'},
            {'voice_id': 'voice2', 'name': 'Voice Two'}
        ]

        result = tasks.run_generation(json.dumps(valid_config_dict))

    # Should complete with errors
    assert result['status'] == 'COMPLETED_WITH_ERRORS'
    assert result['generated_batches'][0]['take_count'] == 3 # 4 attempted - 1 failed
    assert result['generated_batches'][1]['take_count'] == 3 # 4 attempted - 1 failed
    assert mock_generate_tts.call_count == 8
    assert mock_upload_blob.call_count == 8 # 6 takes + 2 metadata
    mock_update_state.assert_called_with(state='COMPLETED_WITH_ERRORS', meta=result)

# --- Tests for regenerate_line_takes --- #
@mock.patch('backend.utils_r2.delete_blob')
@mock.patch('backend.utils_r2.list_blobs_in_prefix')
@mock.patch('backend.utils_r2.upload_blob')
@mock.patch('backend.utils_r2.download_blob_to_memory')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
@mock.patch('backend.models.get_db')
def test_regenerate_line_takes_success_replace(
    mock_get_db, mock_generate_tts, mock_download_meta, mock_upload_blob, mock_list_blobs, mock_delete_blob,
    mock_task_base
):
    # ... setup mocks for DB, R2 download/upload/list/delete, elevenlabs ...
    pass # TODO: Implement test logic

# ... other tests for regenerate_line_takes ...

# --- Tests for crop_audio_take --- #
# ... tests for crop_audio_take ... 