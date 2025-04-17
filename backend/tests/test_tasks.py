# backend/tests/test_tasks.py
import pytest
import json
from unittest import mock
from celery.exceptions import Ignore, Retry
# Use relative imports
from .. import tasks
from .. import utils_elevenlabs # To mock its functions
from .. import utils_fs       # To mock its functions

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

@mock.patch('backend.utils_fs.save_metadata')
@mock.patch('backend.utils_fs.find_batches')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio')
@mock.patch('backend.utils_elevenlabs.get_available_voices')
@mock.patch('pathlib.Path.mkdir')
def test_run_generation_success(
    mock_mkdir, mock_get_voices, mock_generate_tts, mock_find_batches, mock_save_meta,
    mock_task_base # Use the mocked base task methods
):
    """Test successful run of the generation task."""
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

    # Check metadata saving (once per voice)
    assert mock_save_meta.call_count == 2
    first_save_call_args = mock_save_meta.call_args_list[0][0] # Get args of first call
    saved_metadata = first_save_call_args[1] # The metadata dict
    assert saved_metadata['voice_name'] == 'Voice One-voice1'
    assert len(saved_metadata['takes']) == 4

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

@mock.patch('backend.utils_elevenlabs.generate_tts_audio')
def test_run_generation_elevenlabs_error_continues(mock_generate_tts, mock_task_base, mock_env_vars):
    """Test that an error generating one take doesn't stop the whole batch (by default)."""
    mock_update_state, _ = mock_task_base
    mock_generate_tts.side_effect = [utils_elevenlabs.ElevenLabsError("Test API Error")] * 2 + [None] * 6

    # Need to adjust patch paths here too if they were absolute
    with mock.patch('backend.utils_elevenlabs.get_available_voices') as mock_get_voices, \
         mock.patch('backend.utils_fs.save_metadata') as mock_save_meta, \
         mock.patch('pathlib.Path.mkdir'): # Mock mkdir too

        mock_get_voices.return_value = [
            {'voice_id': 'voice1', 'name': 'Voice One'},
            {'voice_id': 'voice2', 'name': 'Voice Two'}
        ]

        result = tasks.run_generation(json.dumps(valid_config_dict))

    # Should still succeed overall, but generate one less take per voice
    assert result['status'] == 'SUCCESS'
    # Check counts carefully based on side_effect
    assert result['generated_batches'][0]['take_count'] == 3 # voice1: 4 total - 1 failed = 3
    assert result['generated_batches'][1]['take_count'] == 3 # voice2: 4 total - 1 failed = 3
    assert mock_generate_tts.call_count == 8 # Still attempted all
    assert mock_save_meta.call_count == 2 # Metadata still saved
    mock_update_state.assert_called_with(state='SUCCESS', meta=result) 