# backend/tests/test_tasks.py
import pytest
import json
from unittest import mock
from celery.exceptions import Ignore, Retry
from datetime import datetime, timezone
from sqlalchemy.orm import Session
# Use relative imports or imports from 'backend'
from backend import tasks
from backend import utils_elevenlabs # To mock its functions
from backend import utils_r2       # Use backend.utils_r2
from backend import models # Import models for mocking DB objects
# from backend import utils_fs       # Use backend.utils_fs -> REMOVED as utils_fs was removed

# --- Mock Data Structures ---

def create_mock_voscriptline(id, key, text, status, order_idx=None, template_order_idx=None):
    line = mock.Mock(spec=models.VoScriptLine)
    line.id = id
    line.vo_script_id = 1 # Assuming vo_script_id 1 for tests
    line.line_key = key
    line.generated_text = text
    line.status = status
    line.order_index = order_idx
    line.template_line = mock.Mock(spec=models.VoScriptTemplateLine)
    line.template_line.order_index = template_order_idx
    line.vo_script = mock.Mock(spec=models.VoScript)
    line.vo_script.name = "Test VO Script"
    return line

# Example lines for mocking DB response
mock_db_lines = [
    create_mock_voscriptline(10, "KEY_GEN", "Generated Text", "generated", order_idx=1),
    create_mock_voscriptline(20, "KEY_MAN", "Manual Text", "manual", template_order_idx=2),
    create_mock_voscriptline(30, "KEY_REV", "Review Text", "review", order_idx=0),
    create_mock_voscriptline(40, "KEY_PEND", "Pending Text", "pending"), # Should be excluded
    create_mock_voscriptline(50, "KEY_FAIL", "Failed Text", "failed"), # Should be excluded
    create_mock_voscriptline(60, "KEY_EMPTY", "", "generated"), # Should be excluded
    create_mock_voscriptline(70, "KEY_NULL", None, "generated"), # Should be excluded
    create_mock_voscriptline(80, "KEY_GEN_NO_IDX", "Another Gen Text", "generated", template_order_idx=5), # Use template order
    create_mock_voscriptline(90, "KEY_MAN_NO_IDX", "Another Man Text", "manual") # Fallback to ID order
]

# Expected script data after filtering and mapping
expected_script_data = [
    {'Function': 'KEY_REV', 'Line': 'Review Text'}, # order_idx = 0
    {'Function': 'KEY_GEN', 'Line': 'Generated Text'}, # order_idx = 1
    {'Function': 'KEY_MAN', 'Line': 'Manual Text'}, # template_order_idx = 2
    {'Function': 'KEY_GEN_NO_IDX', 'Line': 'Another Gen Text'}, # template_order_idx = 5
    {'Function': 'KEY_MAN_NO_IDX', 'Line': 'Another Man Text'} # fallback to id (90)
]

# Config used for generation task (simplified, script_id/csv removed)
base_generation_config = {
    "skin_name": "TestSkin",
    "voice_ids": ["voice1"],
    "variants_per_line": 1,
    "model_id": "test_model",
    "stability_range": [0.5, 0.5],
    "similarity_boost_range": [0.8, 0.8],
    "style_range": [0.4, 0.4],
    "speed_range": [1.0, 1.0],
    "use_speaker_boost": True,
    "script_source": {"source_type": "db", "vo_script_id": 1, "vo_script_name": "Test VO Script"} # Example source info
}

# --- Mocks & Fixtures ---

@pytest.fixture(autouse=True)
def mock_db_session(mocker):
    """Mocks the database session and query chaining."""
    mock_session = mocker.MagicMock(spec=Session)
    
    # --- Mock GenerationJob Handling --- 
    job_mock_storage = {'instance': None}
    def get_job_mock(*args, **kwargs):
        if job_mock_storage['instance'] is None:
            job_mock_storage['instance'] = mock.Mock(spec=models.GenerationJob)
            job_mock_storage['instance'].id = 999
            job_mock_storage['instance'].status = "PENDING"
            job_mock_storage['instance'].parameters_json = json.dumps(base_generation_config)
            job_mock_storage['instance'].result_message = None
            job_mock_storage['instance'].completed_at = None
        return job_mock_storage['instance']

    mock_job_filter = mocker.MagicMock()
    mock_job_filter.first.side_effect = get_job_mock
    
    # --- Mock VoScriptLine Query Handling --- 
    mock_line_orderby = mocker.MagicMock()
    mock_line_filter = mocker.MagicMock()
    mock_line_filter.order_by.return_value = mock_line_orderby
    mock_line_options = mocker.MagicMock()
    mock_line_options.filter.return_value = mock_line_filter
    
    # --- Mock VoScript Name Query Handling --- 
    mock_script_name_filter = mocker.MagicMock()
    mock_script_name_query = mocker.MagicMock()
    mock_script_name_query.filter.return_value = mock_script_name_filter
    
    # Configure the main query mock to return specific mocks based on model
    def query_side_effect(model_cls):
        if model_cls == models.GenerationJob:
            mock_job_query = mocker.MagicMock()
            mock_job_query.filter.return_value = mock_job_filter
            return mock_job_query
        elif model_cls == models.VoScriptLine:
            mock_line_query = mocker.MagicMock()
            mock_line_query.options.return_value = mock_line_options
            return mock_line_query
        elif model_cls == models.VoScript:
            return mock_script_name_query
        else:
            return mocker.MagicMock()
            
    mock_session.query.side_effect = query_side_effect

    # Make SessionLocal return the mock session
    mocker.patch('backend.models.SessionLocal', return_value=mock_session)
    # Mock the context manager nature of get_db
    mocker.patch('backend.models.get_db', return_value=iter([mock_session]))
    
    # Return necessary mocks for tests to use
    return {
        'session': mock_session, 
        'job_mock_storage': job_mock_storage, 
        'line_query_mock': mock_line_orderby, # The mock whose .all() needs configuring
        'script_name_query_mock': mock_script_name_filter # The mock whose .first() needs configuring
    }

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables needed by tasks."""
    monkeypatch.setenv('AUDIO_ROOT', '/app/output')
    # Assume ELEVENLABS_API_KEY is set via docker-compose/test setup

@pytest.fixture
def mock_task_base(mocker):
    """Mock base Celery task methods like update_state."""
    mock_update = mocker.patch('celery.app.task.Task.update_state')
    mock_request = mocker.PropertyMock(return_value=mock.Mock(id="test-task-id-123"))
    mocker.patch('celery.app.task.Task.request', new_callable=mock_request)
    return mock_update

# --- Tests for run_generation (Updated) --- #

@pytest.mark.skip(reason="Obsolete test for legacy run_generation task")
@mock.patch('backend.utils_r2.upload_blob')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
@mock.patch('backend.utils_elevenlabs.get_available_voices')
def test_run_generation_success_vo_script(
    mock_get_voices, mock_generate_tts, mock_upload_blob,
    mock_db_session, mock_task_base
):
    """Test successful run using VO Script ID."""
    mock_session = mock_db_session['session']
    job_mock_storage = mock_db_session['job_mock_storage']
    line_query_mock = mock_db_session['line_query_mock']
    mock_update_state = mock_task_base

    # Configure DB mock for VoScriptLine query
    line_query_mock.all.return_value = [l for l in mock_db_lines if l.status in ['generated', 'manual', 'review'] and l.generated_text] # Return only valid lines

    # Configure other mocks
    mock_get_voices.return_value = [{'voice_id': 'voice1', 'name': 'Voice One'}]
    mock_generate_tts.return_value = b"audio_data"
    mock_upload_blob.return_value = True # Simulate successful upload

    config_str = json.dumps(base_generation_config)
    vo_script_id_to_run = 1
    
    # Run the task
    result = tasks.run_generation(999, config_str, vo_script_id=vo_script_id_to_run)
    
    # Retrieve the job mock instance that was modified by the task
    mock_db_job_obj = job_mock_storage['instance']

    # --- Assertions ---
    # Check DB Job Update
    mock_session.commit.assert_called()
    assert mock_db_job_obj.status == "SUCCESS"
    assert mock_db_job_obj.result_message.startswith("Generation complete.")
    assert json.loads(mock_db_job_obj.result_batch_ids_json)[0].startswith("TestSkin/Voice One-voice1/")

    # Check Celery State Update
    mock_update_state.assert_any_call(state='STARTED', meta=mock.ANY)
    mock_update_state.assert_any_call(state='PROGRESS', meta=mock.ANY)
    # Use assert_any_call for SUCCESS state as other updates might happen after
    mock_update_state.assert_any_call(state='SUCCESS', meta=result)

    # Check Final Result
    assert result['status'] == 'SUCCESS'
    assert len(result['generated_batches']) == 1
    assert result['generated_batches'][0]['take_count'] == len(expected_script_data) # 1 variant per valid line

    # Check TTS calls (Should match number of valid lines)
    assert mock_generate_tts.call_count == len(expected_script_data)
    # Verify text passed corresponds to the filtered/ordered lines
    assert mock_generate_tts.call_args_list[0][1]['text'] == expected_script_data[0]['Line'] # KEY_REV
    assert mock_generate_tts.call_args_list[1][1]['text'] == expected_script_data[1]['Line'] # KEY_GEN
    # ... potentially check all calls ...

    # Check R2 Uploads (Num valid lines + 1 metadata)
    assert mock_upload_blob.call_count == len(expected_script_data) + 1
    # Check metadata includes source_vo_script_id
    meta_upload_call = [c for c in mock_upload_blob.call_args_list if 'metadata.json' in c[1]['blob_name']][0]
    saved_metadata = json.loads(meta_upload_call[1]['data'].decode('utf-8'))
    assert saved_metadata['source_vo_script_id'] == vo_script_id_to_run
    assert saved_metadata['source_vo_script_name'] == "Test VO Script"
    assert len(saved_metadata['takes']) == len(expected_script_data)


@pytest.mark.skip(reason="Obsolete test for legacy run_generation task")
@mock.patch('backend.utils_r2.upload_blob')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
@mock.patch('backend.utils_elevenlabs.get_available_voices')
def test_run_generation_no_valid_lines(
    mock_get_voices, mock_generate_tts, mock_upload_blob,
    mock_db_session, mock_task_base
):
    """Test task failure when VO script has no lines with valid status/text."""
    mock_session = mock_db_session['session']
    job_mock_storage = mock_db_session['job_mock_storage']
    line_query_mock = mock_db_session['line_query_mock']
    script_name_query_mock = mock_db_session['script_name_query_mock']
    mock_update_state = mock_task_base

    # Configure DB mock to return NO valid lines
    line_query_mock.all.return_value = []
    # Mock the vo_script name lookup for the error message
    script_name_query_mock.first.return_value = mock.Mock(name="Empty Script")

    config_str = json.dumps(base_generation_config)
    vo_script_id_to_run = 2 # Different ID for clarity

    with pytest.raises(Ignore):
        tasks.run_generation(999, config_str, vo_script_id=vo_script_id_to_run)
        
    # Retrieve the job mock instance that was modified by the task
    mock_db_job_obj = job_mock_storage['instance']

    # Assertions
    # Verify the commit happened after setting status to FAILURE
    assert mock_db_job_obj.status == "FAILURE"
    mock_session.commit.assert_called()
    assert "No lines with valid status" in mock_db_job_obj.result_message
    # Check the name from the mocked script name query
    assert "Empty Script" in mock_db_job_obj.result_message 
    
    # Check Celery state update
    mock_update_state.assert_any_call(state='FAILURE', meta=mock.ANY)
    # Ensure TTS/Upload were not called
    mock_generate_tts.assert_not_called()
    mock_upload_blob.assert_not_called()

# TODO: Add tests for:
# - Partial failures (some TTS calls fail)
# - R2 upload failures (both take and metadata)
# - Error getting voice name
# - Different ordering scenarios

# --- Tests for regenerate_line_takes --- #
# (These tests would also need updating to use vo_script_id potentially,
# or be verified if they only rely on batch_prefix/R2 metadata)

# --- Tests for run_speech_to_speech_line --- #
# (Similar check needed as regenerate_line_takes)

# --- Tests for crop_audio_take --- #
# (Likely unaffected as it uses R2 keys directly)

# --- Tests for run_script_creation_agent --- #
# (Existing tests likely need adjustment if inputs change)

# --- Tests for run_generation --- #

@pytest.mark.skip(reason="Obsolete test for legacy run_generation task using CSV")
@mock.patch('backend.utils_r2.upload_blob')
@mock.patch('backend.utils_elevenlabs.generate_tts_audio_bytes')
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

@pytest.mark.skip(reason="Obsolete test for legacy run_generation task")
def test_run_generation_invalid_json_config(mock_task_base):
    mock_update_state, _ = mock_task_base
    with pytest.raises(Ignore):
        tasks.run_generation("this is not json")
    mock_update_state.assert_called_with(state='FAILURE', meta=mock.ANY)

@pytest.mark.skip(reason="Obsolete test for legacy run_generation task")
def test_run_generation_missing_keys(mock_task_base):
    mock_update_state, _ = mock_task_base
    invalid_config = valid_config_dict.copy()
    del invalid_config['voice_ids']
    with pytest.raises(Ignore):
        tasks.run_generation(json.dumps(invalid_config))
    # Check if the failure message contains the missing key
    failure_meta = mock_update_state.call_args.kwargs['meta']
    assert "Missing required configuration keys: ['voice_ids']" in failure_meta['status']

@pytest.mark.skip(reason="Obsolete test for legacy run_generation task using CSV")
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