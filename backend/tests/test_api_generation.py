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

# --- Fixtures ---

@pytest.fixture
def client():
    """Flask test client fixture."""
    app.config['TESTING'] = True
    # Mock environment variables if needed for app context
    with app.test_client() as client:
        # You might need app_context if using current_app or session
        with app.app_context():
            yield client

@pytest.fixture
def mock_celery_task(mocker):
    """Mocks the delay method of the run_generation task."""
    # Adjust mock path for relative import
    mock_delay = mocker.patch('backend.tasks.run_generation.delay')
    # Configure the mock to return a mock AsyncResult with a specific ID
    mock_async_result = mock.Mock()
    mock_async_result.id = "mock-task-id-456"
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
    assert json_data['data'][0] == {"id": "v1", "name": "Mock Voice 1"}
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

def test_start_generation_api_success(client, mock_celery_task):
    """Test POST /api/generate success."""
    valid_payload = {
        "skin_name": "APISkin",
        "voice_ids": ["v1"],
        "script_csv_content": "Function,Line\nLineA,TextA",
        "variants_per_line": 1
        # Add other optional params if needed by validation
    }
    response = client.post('/api/generate', json=valid_payload)
    assert response.status_code == 202
    json_data = response.get_json()
    assert 'data' in json_data
    assert json_data['data']['task_id'] == "mock-task-id-456"
    # Check that delay was called with the correct config string
    mock_celery_task.assert_called_once_with(json.dumps(valid_payload))

def test_start_generation_api_missing_keys(client, mock_celery_task):
    """Test POST /api/generate with missing required keys."""
    invalid_payload = {
        "skin_name": "APISkin",
        # Missing voice_ids, script_csv_content, variants_per_line
    }
    response = client.post('/api/generate', json=invalid_payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Missing required configuration keys" in json_data['error']
    mock_celery_task.assert_not_called()

def test_start_generation_api_not_json(client, mock_celery_task):
    """Test POST /api/generate with non-JSON data."""
    response = client.post('/api/generate', data="not json")
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Request must be JSON" in json_data['error']
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
    assert "ValueError: Something broke" in json_data['data']['info']['error']
    assert json_data['data']['info']['traceback'] == "Traceback here..." 