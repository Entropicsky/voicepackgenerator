# backend/tests/test_api_generation.py
import pytest
import json
from unittest import mock
from flask import Flask
# Use relative import for app
from ..app import app # Import your Flask app instance
# Use relative import for tasks
from .. import tasks
# Use relative import for utils
from .. import utils_elevenlabs
from .. import models # Import models for DB interaction in tests
from ..models import SessionLocal # To potentially create test data
import uuid # Import uuid

# --- Fixtures ---

@pytest.fixture(scope='function')
def test_db():
    """Fixture to set up and tear down a test database session for each test."""
    # Use the actual test database defined by DATABASE_URL
    # Ensure migrations are applied before running tests
    db = SessionLocal()
    try:
        # Optional: Clean slate or seed data before tests
        # db.query(models.VoScript).delete()
        # db.query(models.VoScriptTemplate).delete() # etc.
        # db.commit()
        
        # Seed necessary data for API tests
        template = models.VoScriptTemplate(id=99, name="API Test Template")
        db.add(template)
        db.flush()
        script = models.VoScript(id=999, name="API Test VO Script", template_id=template.id, character_description="Test Desc")
        db.add(script)
        db.commit()
        
        yield db # Provide the session to tests
    finally:
        # Clean up test data
        db.query(models.VoScript).filter(models.VoScript.id == 999).delete()
        db.query(models.VoScriptTemplate).filter(models.VoScriptTemplate.id == 99).delete()
        db.commit()
        db.close()

@pytest.fixture
def client(test_db): # Depend on the test_db fixture
    """Flask test client fixture."""
    app.config['TESTING'] = True
    # Mock environment variables if needed for app context
    with app.test_client() as client:
        # You might need app_context if using current_app or session
        with app.app_context():
            # Make the test DB session available if needed directly in tests?
            # Not typically needed if API calls handle their own sessions via get_db
            yield client

@pytest.fixture
def mock_celery_task(mocker):
    """Mocks the delay method of the run_generation task."""
    # Adjust mock path for relative import
    mock_delay = mocker.patch('backend.tasks.run_generation.delay')
    # Configure the mock to return a mock AsyncResult with a UNIQUE ID
    mock_async_result = mock.Mock()
    # Generate a unique ID for each test using this fixture
    mock_async_result.id = f"mock-task-id-{uuid.uuid4()}" 
    mock_delay.return_value = mock_async_result
    return mock_delay

@pytest.fixture
def mock_async_result(mocker):
    """Mocks the AsyncResult class to control task status checks."""
    # Adjust mock path for relative import
    mock_result = mocker.patch('backend.app.AsyncResult') # Patch where it's used in app.py
    return mock_result

@pytest.fixture
def mock_get_voices(mocker):
    """Mocks the utility function for getting voices."""
    # Adjust mock path for relative import
    mock_util = mocker.patch('backend.utils_elevenlabs.get_available_voices')
    mock_util.return_value = [
        {'voice_id': 'v1', 'name': 'Mock Voice 1'},
        {'voice_id': 'v2', 'name': 'Mock Voice 2'}
    ]
    return mock_util

# --- API Tests ---

def test_get_voices_api_success(client, mock_get_voices):
    """Test GET /api/voices success."""
    response = client.get('/api/voices')
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert len(json_data['data']) == 2
    assert json_data['data'][0] == {"voice_id": "v1", "name": "Mock Voice 1"}
    mock_get_voices.assert_called_once()

def test_get_voices_api_error(client, mock_get_voices):
    """Test GET /api/voices when util raises error."""
    # Need to reference the exception via the imported module
    mock_get_voices.side_effect = utils_elevenlabs.ElevenLabsError("API Down")
    response = client.get('/api/voices')
    assert response.status_code == 500
    json_data = response.get_json()
    assert 'error' in json_data
    assert "API Down" in json_data['error']

def test_start_generation_api_success_vo_script(client, test_db, mock_celery_task):
    """Test POST /api/generate success with vo_script_id."""
    valid_vo_script_id = 999 # Use ID seeded by test_db fixture
    valid_payload = {
        "skin_name": "APISkin",
        "voice_ids": ["v1"],
        "vo_script_id": valid_vo_script_id,
        "variants_per_line": 1
    }
    response = client.post('/api/generate', json=valid_payload)
    assert response.status_code == 202
    json_data = response.get_json()
    assert 'data' in json_data
    # Assert that the task ID starts with the expected prefix
    assert json_data['data']['task_id'].startswith("mock-task-id-") 
    
    # Verify GenerationJob created with correct params in DB
    db = SessionLocal()
    # Query using the unique ID returned in the response
    returned_task_id = json_data['data']['task_id'] 
    job = db.query(models.GenerationJob).filter(models.GenerationJob.celery_task_id == returned_task_id).first()
    assert job is not None
    params = json.loads(job.parameters_json)
    assert params['script_source']['source_type'] == 'vo_script'
    assert params['script_source']['vo_script_id'] == valid_vo_script_id
    assert params['script_source']['vo_script_name'] == "API Test VO Script"
    db.close()
    
    # Check that delay was called with correct arguments
    # (The config passed includes the added script_source info)
    expected_config = valid_payload.copy()
    expected_config['script_source'] = {"source_type": "vo_script", "vo_script_id": valid_vo_script_id, "vo_script_name": "API Test VO Script"}
    
    # Get actual call args
    actual_call_args = mock_celery_task.call_args
    assert actual_call_args is not None, "tasks.run_generation.delay was not called"
    
    # Compare arguments (ignore job ID, compare loaded JSON config dict)
    assert len(actual_call_args.args) == 2 # Expect 2 positional args (job_id, config_json)
    assert isinstance(actual_call_args.args[0], int) # Check job ID type
    # Load the actual config JSON string passed to the mock
    actual_config_dict = json.loads(actual_call_args.args[1]) 
    assert actual_config_dict == expected_config # Compare dictionaries
    # Check the keyword argument
    assert len(actual_call_args.kwargs) == 1 # Expect 1 keyword arg
    assert actual_call_args.kwargs['vo_script_id'] == valid_vo_script_id # Check vo_script_id kwarg

def test_start_generation_api_missing_vo_script_id(client, mock_celery_task):
    """Test POST /api/generate with missing vo_script_id."""
    invalid_payload = {
        "skin_name": "APISkin",
        "voice_ids": ["v1"],
        "variants_per_line": 1
    }
    response = client.post('/api/generate', json=invalid_payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Missing required field: vo_script_id" in json_data['error']
    mock_celery_task.assert_not_called()
    
def test_start_generation_api_nonexistent_vo_script_id(client, test_db, mock_celery_task):
    """Test POST /api/generate with a vo_script_id that doesn't exist."""
    non_existent_id = 88888
    invalid_payload = {
        "skin_name": "APISkin",
        "voice_ids": ["v1"],
        "vo_script_id": non_existent_id,
        "variants_per_line": 1
    }
    response = client.post('/api/generate', json=invalid_payload)
    assert response.status_code == 404
    json_data = response.get_json()
    assert 'error' in json_data
    assert f"VO Script with ID {non_existent_id} not found" in json_data['error']
    mock_celery_task.assert_not_called()
    
def test_start_generation_api_invalid_vo_script_id_format(client, mock_celery_task):
    """Test POST /api/generate with a non-integer vo_script_id."""
    invalid_payload = {
        "skin_name": "APISkin",
        "voice_ids": ["v1"],
        "vo_script_id": "not-an-int",
        "variants_per_line": 1
    }
    response = client.post('/api/generate', json=invalid_payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Invalid vo_script_id format" in json_data['error']
    mock_celery_task.assert_not_called()

def test_get_task_status_api_pending(client, mock_async_result):
    """Test GET /api/generate/<task_id>/status for PENDING task."""
    mock_instance = mock.Mock()
    mock_instance.status = 'PENDING'
    mock_instance.info = None
    mock_async_result.return_value = mock_instance

    response = client.get('/api/generate/test-id/status')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['data']['status'] == 'PENDING'
    assert json_data['data']['info'] == {'status': 'Task is waiting to be processed.'}
    mock_async_result.assert_called_once_with('test-id', app=mock.ANY)

def test_get_task_status_api_progress(client, mock_async_result):
    """Test GET /api/generate/<task_id>/status for STARTED/PROGRESS task."""
    mock_instance = mock.Mock()
    mock_instance.status = 'PROGRESS' # Or STARTED
    progress_info = {'current': 5, 'total': 10, 'status': 'Generating take 5...'}
    mock_instance.info = progress_info
    mock_async_result.return_value = mock_instance

    response = client.get('/api/generate/test-id/status')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['data']['status'] == 'PROGRESS'
    assert json_data['data']['info'] == progress_info

def test_get_task_status_api_success(client, mock_async_result):
    """Test GET /api/generate/<task_id>/status for SUCCESS task."""
    mock_instance = mock.Mock()
    mock_instance.status = 'SUCCESS'
    success_result = {'status': 'SUCCESS', 'message': 'Done', 'generated_batches': []}
    mock_instance.info = success_result
    mock_async_result.return_value = mock_instance

    response = client.get('/api/generate/test-id/status')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['data']['status'] == 'SUCCESS'
    assert json_data['data']['info'] == success_result

def test_get_task_status_api_failure(client, mock_async_result):
    """Test GET /api/generate/<task_id>/status for FAILURE task."""
    mock_instance = mock.Mock()
    mock_instance.status = 'FAILURE'
    mock_instance.info = ValueError("Something broke") # Example exception
    mock_instance.traceback = "Traceback here..."
    mock_async_result.return_value = mock_instance

    response = client.get('/api/generate/test-id/status')
    assert response.status_code == 200 # API call is successful, status is in payload
    json_data = response.get_json()
    assert json_data['data']['status'] == 'FAILURE'
    assert 'error' in json_data['data']['info']
    assert "Something broke" in json_data['data']['info']['error']
    assert json_data['data']['info']['traceback'] == "Traceback here..." 