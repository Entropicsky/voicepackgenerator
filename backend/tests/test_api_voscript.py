# backend/tests/test_api_voscript.py
import pytest
import json
# from unittest import mock, MagicMock # Import MagicMock
from unittest import mock
from unittest.mock import MagicMock # Correct import
from flask import Flask
from datetime import datetime, timezone # Ensure datetime is imported

# Import necessary components (adjust imports based on actual structure)
# from backend.app import create_app # Assuming create_app is the factory
from backend.app import app as flask_app # Import the app object directly
from backend import models
from backend.routes import vo_script_routes # Need to import the blueprint

@pytest.fixture(scope='module')
def test_client():
    """Fixture to create a Flask test client."""
    # Use the imported app object
    app = flask_app
    app.config['TESTING'] = True
    # Assume blueprint is already registered on the imported app
    # app.register_blueprint(vo_script_routes.vo_script_bp) 
    
    with app.test_client() as client:
        with app.app_context(): 
            pass
        yield client

# --- Tests for Line Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db') # Mock DB session retrieval
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_line_success(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Test successful line refinement via API."""
    script_id = 1
    line_id = 101
    user_prompt = "Make it punchier."
    
    # Mock context returned by utility
    mock_context = {
        "line_id": line_id,
        "current_text": "This is the original text.",
        "status": "generated",
        "latest_feedback": None,
        "line_key": "KEY_1",
        "line_template_hint": "A hint.",
        "category_name": "CatName",
        "category_instructions": "Category hint.",
        "script_name": "ScriptName",
        "character_description": "A character.",
        "template_name": "TemplateName",
        "template_hint": "Template hint."
    }
    mock_get_context.return_value = mock_context
    
    # Mock OpenAI response
    refined_text = "This is the punchier text!"
    mock_call_openai.return_value = refined_text
    
    # Mock DB update response
    mock_updated_line = models.VoScriptLine(id=line_id, generated_text=refined_text, status="review") # Create a dummy updated object
    mock_update_db.return_value = mock_updated_line
    
    # Mock get_db to return an iterator yielding the mock session
    mock_session = MagicMock()
    # Make get_db return an object that yields mock_session when next() is called
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator 
    
    # Call the API endpoint
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/refine',
        json={'line_prompt': user_prompt}
    )
    
    # Assertions
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    # Check returned data matches updated line (needs serialization)
    # Assuming a simple dict structure for now
    assert json_data['data']['id'] == line_id
    assert json_data['data']['generated_text'] == refined_text
    assert json_data['data']['status'] == "review"
    
    # Verify mocks were called correctly
    mock_get_db.assert_called_once() # get_db itself was called
    mock_get_context.assert_called_once_with(mock_session, line_id) # Check called with the yielded session
    mock_call_openai.assert_called_once()
    mock_update_db.assert_called_once_with(
        mock_session, line_id, refined_text, "review", mock.ANY
    )

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
def test_refine_line_not_found(mock_get_context, mock_get_db, test_client):
    """Test API response when the line context is not found."""
    mock_get_context.return_value = None # Simulate line not found
    # Mock get_db correctly
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post('/api/vo-scripts/1/lines/999/refine', json={'line_prompt': 'Test'})
    
    assert response.status_code == 404
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Line context not found" in json_data['error']

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
def test_refine_line_openai_fails(mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Test API response when the OpenAI call fails."""
    mock_get_context.return_value = {"line_id": 101, "current_text": "Test"}
    mock_call_openai.return_value = None
    # Mock get_db correctly
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post('/api/vo-scripts/1/lines/101/refine', json={'line_prompt': 'Test'})
    
    assert response.status_code == 500
    json_data = response.get_json()
    assert 'error' in json_data
    assert "OpenAI refinement failed" in json_data['error']

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_line_db_update_fails(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Test API response when the database update fails."""
    mock_get_context.return_value = {"line_id": 101, "current_text": "Test"}
    mock_call_openai.return_value = "Refined text."
    mock_update_db.return_value = None
    # Mock get_db correctly
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post('/api/vo-scripts/1/lines/101/refine', json={'line_prompt': 'Test'})
    
    assert response.status_code == 500
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Database update failed" in json_data['error']

def test_refine_line_missing_prompt(test_client):
    """Test API response when line_prompt is missing from request body."""
    response = test_client.post('/api/vo-scripts/1/lines/101/refine', json={}) # Empty JSON
    assert response.status_code == 400
    json_data = response.get_json()
    assert 'error' in json_data
    assert "Missing 'line_prompt' in request body" in json_data['error'] 

# --- Tests for Category Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_category_success(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Test successful category refinement, skipping locked lines."""
    script_id = 1
    category_name = "TestCategory"
    user_prompt = "Make this category more dramatic."
    
    # Mock context: line 101 is NOT locked, line 102 IS locked
    mock_context1 = {"line_id": 101, "current_text": "Line A original.", "character_description": "Char", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Line B original.", "character_description": "Char", "is_locked": True}
    mock_get_context.return_value = [mock_context1, mock_context2]
    
    # Mock OpenAI response (should only be called for line 101)
    refined_text1 = "Line A dramatic!"
    mock_call_openai.return_value = refined_text1 # Only one response needed
    
    # Mock DB update responses (should only be called for line 101)
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1 # Only one needed
    
    # Mock get_db
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    # Call API
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/categories/refine',
        json={'category_name': category_name, 'category_prompt': user_prompt}
    )
    
    # Assertions
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert isinstance(json_data['data'], list)
    assert len(json_data['data']) == 1 # Only line 101 should be updated and returned
    assert json_data['data'][0]['id'] == 101
    assert json_data['data'][0]['generated_text'] == refined_text1
    
    # Verify mocks
    mock_get_context.assert_called_once_with(mock_session, script_id, category_name)
    mock_call_openai.assert_called_once() # Only called for line 101
    # Check prompt for line 101
    call_args, call_kwargs = mock_call_openai.call_args
    prompt_line1 = call_kwargs.get('prompt')
    assert "Current Line Text:\nLine A original." in prompt_line1
    
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY) # Only called for line 101

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
def test_refine_category_no_lines_found(mock_get_context, mock_get_db, test_client):
    """Test refining a category with no matching lines."""
    mock_get_context.return_value = [] # No lines found
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_name': "EmptyCat", 'category_prompt': 'Test'}
    )
    
    assert response.status_code == 200 # Should still be success, just no updates
    json_data = response.get_json()
    assert 'data' in json_data
    assert json_data['data'] == [] # Expect empty list

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_refine_category_missing_params(mock_get_db, test_client):
    """Test API response when category_name or category_prompt is missing."""
    # Missing category_prompt
    response1 = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_name': "TestCategory"}
    )
    assert response1.status_code == 400
    assert "Missing 'category_prompt'" in response1.get_json()['error']
    
    # Missing category_name
    response2 = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_prompt': "Test Prompt"}
    )
    assert response2.status_code == 400
    assert "Missing 'category_name'" in response2.get_json()['error'] 

# --- NEW: Test hierarchical prompt construction for Category --- #
@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_category_prompt_construction(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Verify hierarchical prompt construction for category refinement."""
    script_id = 1
    category_name = "TestCategory"
    category_prompt = "Category-level instruction."
    
    # Mock context with global prompt and line feedback
    mock_context1 = {
        "line_id": 101, 
        "current_text": "Line A original.", 
        "script_refinement_prompt": "Global Instruction!",
        "latest_feedback": "Line A feedback.",
        "character_description": "Test Char"
        # Add other fields if needed by prompt string
    }
    mock_get_context.return_value = [mock_context1]
    mock_call_openai.return_value = "Some refined text"
    mock_update_db.return_value = models.VoScriptLine(id=101)
    # Mock get_db
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    test_client.post(
        f'/api/vo-scripts/{script_id}/categories/refine',
        json={'category_name': category_name, 'category_prompt': category_prompt}
    )
    
    # Assert that call_openai_responses_api was called
    mock_call_openai.assert_called_once()
    # Get the actual prompt passed to the mock
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    
    # Assert that the key prompts are present in the constructed prompt
    assert actual_prompt is not None
    assert "Global Script Prompt: Global Instruction!" in actual_prompt
    assert f"Category Prompt: {category_prompt}" in actual_prompt
    assert "Line Feedback/Prompt: Line A feedback." in actual_prompt
    assert "Current Line Text:\nLine A original." in actual_prompt
    assert "Character Description:\nTest Char" in actual_prompt

# --- Tests for Script Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_script_success(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Test successful script refinement, skipping locked lines."""
    script_id = 1
    global_prompt = "Overall: Make everything more formal."
    
    # Mock context: line 101 NOT locked, line 102 IS locked
    mock_context1 = {"line_id": 101, "current_text": "Hiya!", "character_description": "Char", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Yo!", "character_description": "Char", "is_locked": True}
    mock_get_context.return_value = [mock_context1, mock_context2]
    
    # Mock OpenAI response (only called for line 101)
    refined_text1 = "Greetings."
    mock_call_openai.return_value = refined_text1
    
    # Mock DB update response (only called for line 101)
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1
    
    # Mock get_db
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    # Call API
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/refine',
        json={'global_prompt': global_prompt}
    )
    
    # Assertions
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'data' in json_data
    assert isinstance(json_data['data'], list)
    assert len(json_data['data']) == 1 # Only line 101 updated
    assert json_data['data'][0]['id'] == 101
    assert json_data['data'][0]['generated_text'] == refined_text1
    
    # Verify mocks
    mock_get_context.assert_called_once_with(mock_session, script_id)
    mock_call_openai.assert_called_once() # Only called for line 101
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY) # Only called for line 101

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
def test_refine_script_no_lines_found(mock_get_context, mock_get_db, test_client):
    """Test refining a script with no lines."""
    mock_get_context.return_value = [] # No lines found
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        '/api/vo-scripts/99/refine',
        json={'global_prompt': 'Test'}
    )
    
    assert response.status_code == 200 # Success, nothing done
    json_data = response.get_json()
    assert 'data' in json_data
    assert json_data['data'] == []

def test_refine_script_missing_prompt(test_client):
    """Test API response when global_prompt is missing."""
    response = test_client.post('/api/vo-scripts/1/refine', json={}) # Empty JSON
    assert response.status_code == 400
    assert "Missing 'global_prompt'" in response.get_json()['error'] 

# --- NEW: Test hierarchical prompt construction for Script --- #
@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_script_prompt_construction(mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client):
    """Verify hierarchical prompt construction for script refinement."""
    script_id = 1
    global_prompt = "Make the whole script sound older."
    
    # Mock context including category and line prompts/feedback
    mock_context1 = {
        "line_id": 101, 
        "current_text": "Line A original.", 
        "script_refinement_prompt": "Old Global Prompt (should be ignored)", # Utility returns this, but API uses request body global_prompt
        "category_refinement_prompt": "Category 1 Old Prompt.",
        "latest_feedback": "Line A specific feedback.",
        "character_description": "Test Char"
    }
    mock_get_context.return_value = [mock_context1]
    mock_call_openai.return_value = "Some refined text"
    mock_update_db.return_value = models.VoScriptLine(id=101)
    # Mock get_db
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    test_client.post(
        f'/api/vo-scripts/{script_id}/refine',
        json={'global_prompt': global_prompt}
    )
    
    # Assert that call_openai_responses_api was called
    mock_call_openai.assert_called_once()
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    
    # Assert that the key prompts are present in the constructed prompt
    assert actual_prompt is not None
    assert f"Global Script Prompt: {global_prompt}" in actual_prompt # Uses prompt from request
    assert "Category Prompt: Category 1 Old Prompt." in actual_prompt
    assert "Line Feedback/Prompt: Line A specific feedback." in actual_prompt
    assert "Current Line Text:\nLine A original." in actual_prompt
    assert "Character Description:\nTest Char" in actual_prompt
    # Check that the script prompt fetched by the util (if any) is NOT used directly here
    assert "Global Script Prompt: Old Global Prompt (should be ignored)" not in actual_prompt 

# --- Tests for Line Locking Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_toggle_lock_line_success(mock_get_db, test_client):
    """Test successfully toggling the lock status of a line."""
    script_id = 1
    line_id = 101
    initial_lock_status = False
    
    # Mock the line object found in DB
    mock_line = MagicMock(spec=models.VoScriptLine)
    mock_line.id = line_id
    mock_line.vo_script_id = script_id
    mock_line.is_locked = initial_lock_status
    mock_line.updated_at = datetime.now(timezone.utc) 
    
    # Mock DB session and query
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_line
    # Assign a MagicMock to session.refresh
    mock_session.refresh = MagicMock() 
    
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    # Call the API endpoint
    response = test_client.patch(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/toggle-lock'
    )
    
    # Assertions
    assert response.status_code == 200
    assert mock_line.is_locked == (not initial_lock_status)
    mock_session.commit.assert_called_once()
    # Check refresh was called with the mock line object
    mock_session.refresh.assert_called_once_with(mock_line)
    
    # Check response data (updated_at should be a string now)
    json_data = response.get_json()
    assert 'data' in json_data
    assert json_data['data']['id'] == line_id
    assert json_data['data']['is_locked'] == (not initial_lock_status)
    assert isinstance(json_data['data']['updated_at'], str)
    
    # Test toggling back
    initial_lock_status = mock_line.is_locked 
    mock_session.reset_mock() 
    response_back = test_client.patch(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/toggle-lock'
    )
    assert response_back.status_code == 200
    assert mock_line.is_locked == (not initial_lock_status)
    assert response_back.get_json()['data']['is_locked'] == (not initial_lock_status)
    mock_session.commit.assert_called_once()

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_toggle_lock_line_not_found(mock_get_db, test_client):
    """Test toggling lock for a non-existent line."""
    script_id = 1
    line_id = 999
    
    # Mock DB session and query (line not found)
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    response = test_client.patch(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/toggle-lock'
    )
    
    assert response.status_code == 404
    assert "Line not found" in response.get_json()['error']
    mock_session.commit.assert_not_called() 

# --- Tests for Manual Text Update Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_update_line_text_success(mock_get_db, test_client):
    """Test successfully updating line text manually."""
    script_id = 1
    line_id = 101
    new_text = "Manually updated text."
    
    mock_line = MagicMock(spec=models.VoScriptLine)
    mock_line.id = line_id
    mock_line.vo_script_id = script_id
    mock_line.template_line_id = 202 # Example
    mock_line.category_id = 303 # Example
    mock_line.generated_text = "Old text"
    mock_line.status = "generated"
    mock_line.latest_feedback = "Old feedback"
    mock_line.generation_history = []
    mock_line.line_key = "OLD_KEY"
    mock_line.order_index = 1
    mock_line.prompt_hint = "Old hint"
    mock_line.is_locked = False
    mock_line.created_at = datetime.now(timezone.utc)
    mock_line.updated_at = datetime.now(timezone.utc)
    
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_line
    def mock_refresh(obj):
        obj.updated_at = datetime.now(timezone.utc)
    mock_session.refresh = MagicMock() # Use MagicMock
    
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    response = test_client.patch(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/update-text',
        json={'generated_text': new_text}
    )
    
    assert response.status_code == 200
    assert mock_line.generated_text == new_text
    assert mock_line.status == 'manual' # Check status update
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_line)
    
    json_data = response.get_json()
    assert json_data['data']['generated_text'] == new_text
    assert json_data['data']['status'] == 'manual'

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_update_line_text_not_found(mock_get_db, test_client):
    """Test updating text for a non-existent line."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    response = test_client.patch(
        f'/api/vo-scripts/1/lines/999/update-text',
        json={'generated_text': 'test'}
    )
    assert response.status_code == 404

def test_update_line_text_missing_body(test_client):
    """Test update text with missing generated_text in body."""
    response = test_client.patch('/api/vo-scripts/1/lines/101/update-text', json={})
    assert response.status_code == 400

# --- Tests for Delete Line Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_delete_line_success(mock_get_db, test_client):
    """Test successfully deleting a line."""
    script_id = 1
    line_id = 101
    mock_line = MagicMock(spec=models.VoScriptLine, id=line_id, vo_script_id=script_id)
    
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = mock_line
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    response = test_client.delete(f'/api/vo-scripts/{script_id}/lines/{line_id}')
    
    assert response.status_code == 200
    assert "Line deleted successfully" in response.get_json()['message']
    mock_session.delete.assert_called_once_with(mock_line)
    mock_session.commit.assert_called_once()

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_delete_line_not_found(mock_get_db, test_client):
    """Test deleting a non-existent line."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    response = test_client.delete('/api/vo-scripts/1/lines/999')
    assert response.status_code == 404

# ... rest of tests ... 