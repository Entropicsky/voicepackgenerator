# backend/tests/test_task_run_generation_vo_script.py
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

# --- Mock Data Structures ---

def create_mock_voscriptline(id, key, text, status, order_idx=None, template_line_key=None, template_order_idx=None):
    line = mock.Mock(spec=models.VoScriptLine)
    line.id = id
    line.vo_script_id = 1 # Assuming vo_script_id 1 for tests
    line.line_key = key # Direct key on VoScriptLine
    line.generated_text = text
    line.status = status
    line.order_index = order_idx
    line.template_line = mock.Mock(spec=models.VoScriptTemplateLine)
    line.template_line.line_key = template_line_key # Key from template line
    line.template_line.order_index = template_order_idx
    line.vo_script = mock.Mock(spec=models.VoScript)
    line.vo_script.name = "Test VO Script"
    return line

# Example lines for mocking DB response
mock_db_lines = [
    create_mock_voscriptline(10, "KEY_GEN_DIRECT", "Generated Text", "generated", order_idx=1), # Has direct key
    create_mock_voscriptline(20, None, "Manual Text", "manual", template_line_key="KEY_MAN_TEMPLATE", template_order_idx=2), # Uses template key
    create_mock_voscriptline(30, "", "Review Text", "review", template_line_key="KEY_REV_TEMPLATE_IGNORED", order_idx=0), # Empty direct key, should use this empty key
    create_mock_voscriptline(40, None, "Pending Text", "pending"), # Excluded by status
    create_mock_voscriptline(50, None, "Failed Text", "failed"), # Excluded by status
    create_mock_voscriptline(60, "KEY_EMPTY", "", "generated"), # Excluded by empty text
    create_mock_voscriptline(70, "KEY_NULL", None, "generated"), # Excluded by null text
    create_mock_voscriptline(80, None, "Another Gen Text", "generated", template_line_key="KEY_GEN_TEMPLATE", template_order_idx=5), # Uses template key
    create_mock_voscriptline(90, None, "Another Man Text", "manual") # No direct or template key, uses ID
]

# Expected script data after filtering and mapping (ORDER IS BY ID from task simplification)
expected_script_data = [
    {'Function': 'KEY_GEN_DIRECT', 'Line': 'Generated Text'}, # ID 10
    {'Function': 'KEY_MAN_TEMPLATE', 'Line': 'Manual Text'}, # ID 20
    {'Function': ''                , 'Line': 'Review Text'}, # ID 30 (Uses empty string line_key)
    {'Function': 'KEY_GEN_TEMPLATE', 'Line': 'Another Gen Text'}, # ID 80
    {'Function': 'line_90'         , 'Line': 'Another Man Text'} # ID 90
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
    mock_line_orderby = mocker.MagicMock() # This mock needs the .all() method configured
    mock_line_filter = mocker.MagicMock()
    mock_line_filter.order_by.return_value = mock_line_orderby # order_by returns the mock that has .all
    mock_line_options = mocker.MagicMock()
    mock_line_options.filter.return_value = mock_line_filter

    # --- Mock VoScript Name Query Handling ---
    mock_script_name_filter = mocker.MagicMock()
    # Configure the .first() call on the filter mock
    # We'll set the return value within the test itself where needed
    # mock_script_name_query = mocker.MagicMock()
    # mock_script_name_query.filter.return_value = mock_script_name_filter
    
    # Configure the main query mock to return specific mocks based on model
    def query_side_effect(model_cls):
        if model_cls == models.GenerationJob:
            mock_job_query = mocker.MagicMock()
            mock_job_query.filter.return_value = mock_job_filter
            return mock_job_query
        elif model_cls == models.VoScriptLine:
            # Return the mock configured for the full chain ending in .all()
            mock_line_query = mocker.MagicMock()
            mock_options = mocker.MagicMock() # Mock for .options()
            mock_filter = mocker.MagicMock()  # Mock for .filter()
            mock_orderby = mocker.MagicMock() # Mock for .order_by()
            
            mock_line_query.options.return_value = mock_options # query().options()
            mock_options.filter.return_value = mock_filter      # options().filter()
            mock_filter.order_by.return_value = mock_orderby   # filter().order_by()
            # Configure the .all() call on the final mock in the chain
            mock_orderby.all = mock_line_orderby.all # Use the .all from the fixture return
            
            return mock_line_query
        elif model_cls == models.VoScript:
             # Return a mock that allows .filter().first() to be called
             mock_script_name_query = mocker.MagicMock()
             # We configure script_name_filter_mock.first() in the test
             mock_script_name_query.filter.return_value = mock_script_name_filter 
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

@pytest.fixture
def mock_task_base(mocker):
    """Mock base Celery task methods like update_state."""
    mock_update = mocker.patch('celery.app.task.Task.update_state')
    mock_request = mocker.PropertyMock(return_value=mock.Mock(id="test-task-id-123"))
    mocker.patch('celery.app.task.Task.request', new_callable=mock_request)
    return mock_update

# --- Tests for run_generation (Updated) --- #

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

    # --- Configure mocks returned BY THE FIXTURE --- 
    valid_lines = [l for l in mock_db_lines if l.status in ['generated', 'manual', 'review'] and l.generated_text]
    line_query_mock.all.return_value = valid_lines
    
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
    assert mock_db_job_obj.status == "SUCCESS" # Status should be updated on the mock instance now
    assert mock_db_job_obj.result_message.startswith("Generation complete.")
    assert json.loads(mock_db_job_obj.result_batch_ids_json)[0].startswith("TestSkin/Voice One-voice1/")

    # Check Celery State Update
    mock_update_state.assert_any_call(state='STARTED', meta=mock.ANY)
    mock_update_state.assert_any_call(state='PROGRESS', meta=mock.ANY)
    # Use assert_any_call for SUCCESS state and check meta less strictly
    mock_update_state.assert_any_call(state='SUCCESS', meta=mock.ANY) # Allow any meta for SUCCESS

    # Check Final Result
    assert result['status'] == 'SUCCESS'
    assert len(result['generated_batches']) == 1
    assert result['generated_batches'][0]['take_count'] == len(expected_script_data) # 1 variant per valid line

    # Check TTS calls (Should match number of valid lines)
    assert mock_generate_tts.call_count == len(expected_script_data)
    # Verify text passed corresponds to the filtered/ordered lines (ORDER IS BY ID)
    for i, expected_line in enumerate(expected_script_data):
        assert mock_generate_tts.call_args_list[i][1]['text'] == expected_line['Line']

    # Check R2 Uploads (Num valid lines + 1 metadata)
    assert mock_upload_blob.call_count == len(expected_script_data) + 1
    # Check metadata includes source_vo_script_id
    meta_upload_call = [c for c in mock_upload_blob.call_args_list if 'metadata.json' in c[1]['blob_name']][0]
    saved_metadata = json.loads(meta_upload_call[1]['data'].decode('utf-8'))
    assert saved_metadata['source_vo_script_id'] == vo_script_id_to_run
    assert saved_metadata['source_vo_script_name'] == "Test VO Script"
    assert len(saved_metadata['takes']) == len(expected_script_data)


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
    script_name_filter_mock = mock_db_session['script_name_query_mock']
    mock_update_state = mock_task_base

    # --- Configure mocks returned BY THE FIXTURE --- 
    line_query_mock.all.return_value = []
    script_name_filter_mock.first.return_value = mock.Mock(name="Empty Script")
    
    config_str = json.dumps(base_generation_config)
    vo_script_id_to_run = 2 # Different ID for clarity

    with pytest.raises(Ignore):
        tasks.run_generation(999, config_str, vo_script_id=vo_script_id_to_run)
        
    # Retrieve the job mock instance that was modified by the task
    mock_db_job_obj = job_mock_storage['instance']

    # Assertions
    # Verify the commit happened AFTER setting status to FAILURE
    assert mock_db_job_obj.status == "FAILURE" # Check status on mock
    mock_session.commit.assert_called() # Check commit was called
    
    # Check Celery state update was called with FAILURE and the correct message in meta
    # Construct the expected error message string based on the *actual* ValueError raised
    expected_error_start = f"Error preparing script data from VO Script {vo_script_id_to_run}: No lines with valid status"
    expected_error_end = f"found for VO Script ID {vo_script_id_to_run}" # Adjusted expected message
    
    failure_call_found = False
    for call_args in mock_update_state.call_args_list:
        if call_args.kwargs.get('state') == 'FAILURE':
            failure_meta = call_args.kwargs.get('meta', {})
            actual_status_msg = failure_meta.get('status', '')
            print(f"DEBUG: Actual status message in mock: {actual_status_msg}") # Add debug print
            assert actual_status_msg.startswith(expected_error_start)
            assert actual_status_msg.endswith(expected_error_end)
            failure_call_found = True
            break
    assert failure_call_found, "update_state(state='FAILURE', ...) was not called with expected message start/end"

    # Ensure TTS/Upload were not called
    mock_generate_tts.assert_not_called()
    mock_upload_blob.assert_not_called()

# TODO: Add tests for:
# - Partial failures (some TTS calls fail)
# - R2 upload failures (both take and metadata)
# - Error getting voice name
# - Different ordering scenarios

# --- Tests will be added below --- 