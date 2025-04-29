# backend/tests/test_api_voscript.py
import pytest
import json
# from unittest import mock, MagicMock # Import MagicMock
from unittest import mock
from unittest.mock import MagicMock # Correct import
from flask import Flask
from datetime import datetime, timezone # Ensure datetime is imported
from sqlalchemy.orm import Session # Import Session
from backend.models import SessionLocal # ADDED for test_db fixture

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

# --- ADD test_db fixture definition --- 
@pytest.fixture(scope='function')
def test_db():
    """Fixture to set up and tear down a test database session for each test."""
    db = SessionLocal()
    try:
        # Seed necessary data for API tests
        template = models.VoScriptTemplate(id=99, name="API Test Template")
        db.add(template)
        db.flush()
        # Use a different ID to avoid collision with potentially real script ID 1
        script = models.VoScript(id=999, name="API Test VO Script", template_id=template.id, character_description="Test Desc") 
        db.add(script)
        db.commit()
        
        yield db # Provide the session to tests
    finally:
        # Clean up test data
        db.query(models.VoScriptLine).filter(models.VoScriptLine.vo_script_id == 999).delete() # Delete lines first
        db.query(models.VoScript).filter(models.VoScript.id == 999).delete()
        db.query(models.VoScriptTemplate).filter(models.VoScriptTemplate.id == 99).delete()
        db.commit()
        db.close()
# --- END test_db fixture definition --- 

# --- Tests for Line Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # NEW: Mock rules utility
def test_refine_line_success_no_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful line refinement via API (apply_best_practices=False)."""
    script_id = 1
    line_id = 101
    user_prompt = "Make it punchier."
    
    mock_get_context.return_value = {"line_id": line_id, "current_text": "Original text.", "character_description": "Char"}
    refined_text = "This is the punchier text!"
    mock_call_openai.return_value = refined_text
    mock_updated_line = models.VoScriptLine(id=line_id, generated_text=refined_text, status="review")
    mock_update_db.return_value = mock_updated_line
    mock_get_rules.return_value = "IGNORED_RULES" # Mock return, though it shouldn't be called
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator 
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/refine',
        json={'line_prompt': user_prompt, 'apply_best_practices': False} # Flag is False
    )
    
    assert response.status_code == 200
    assert response.get_json()['data']['generated_text'] == refined_text
    mock_get_rules.assert_not_called() # Ensure rules function wasn't called
    mock_call_openai.assert_called_once() 
    # Assert the prompt does NOT contain the rules structure
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" not in actual_prompt 
    assert "ElevenLabs Rules:" not in actual_prompt
    assert "User Refinement Request: \"Make it punchier.\"" in actual_prompt

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # NEW: Mock rules utility
def test_refine_line_success_with_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful line refinement via API (apply_best_practices=True)."""
    script_id = 1
    line_id = 102
    user_prompt = "Make it sadder."
    elevenlabs_rules_text = "Rule: Add <break time='0.5s'/> for pauses."
    
    mock_get_context.return_value = {"line_id": line_id, "current_text": "Happy text.", "character_description": "Char"}
    refined_text = "This is sadder text <break time='0.5s'/>."
    mock_call_openai.return_value = refined_text
    mock_updated_line = models.VoScriptLine(id=line_id, generated_text=refined_text, status="review")
    mock_update_db.return_value = mock_updated_line
    mock_get_rules.return_value = elevenlabs_rules_text # Mock rules return
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator 
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/refine',
        json={'line_prompt': user_prompt, 'apply_best_practices': True} # Flag is TRUE
    )
    
    assert response.status_code == 200
    assert response.get_json()['data']['generated_text'] == refined_text
    mock_get_rules.assert_called_once() # Ensure rules function WAS called
    mock_call_openai.assert_called_once() 
    # Assert the prompt DOES contain the rules structure
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" in actual_prompt 
    assert "User Request: \"Make it sadder.\"" in actual_prompt
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt
    assert "3. Output ONLY the final text" in actual_prompt

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_line_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') 
def test_refine_line_success_with_rules_no_prompt(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful line refinement when ONLY apply_best_practices is true."""
    script_id = 1
    line_id = 103
    elevenlabs_rules_text = "Rule: Add pauses."
    
    mock_get_context.return_value = {"line_id": line_id, "current_text": "Text needing pause.", "character_description": "Char"}
    refined_text = "Text needing pause <break time='0.5s'/>."
    mock_call_openai.return_value = refined_text
    mock_updated_line = models.VoScriptLine(id=line_id, generated_text=refined_text, status="review")
    mock_update_db.return_value = mock_updated_line
    mock_get_rules.return_value = elevenlabs_rules_text
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator 
    
    # Call API with empty/null line_prompt but apply_best_practices=True
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/refine',
        json={'line_prompt': '', 'apply_best_practices': True} 
    )
    
    assert response.status_code == 200
    assert response.get_json()['data']['generated_text'] == refined_text
    mock_get_rules.assert_called_once()
    mock_call_openai.assert_called_once() 
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "User Request: \"No specific user refinement request provided. Focus only on applying ElevenLabs best practices.\"" in actual_prompt
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt

def test_refine_line_missing_prompt_and_flag(test_client):
    """Test API response when both line_prompt and apply_best_practices are missing/false."""
    # Send empty prompt and flag=false - should fail validation
    response = test_client.post(
        '/api/vo-scripts/1/lines/101/refine',
        json={'line_prompt': '', 'apply_best_practices': False}
    )
    assert response.status_code == 400
    assert "Missing 'line_prompt' or 'apply_best_practices' must be true" in response.get_json()['error']
    
    # Send only flag=false - should fail validation
    response_flag_false = test_client.post(
        '/api/vo-scripts/1/lines/101/refine', 
        json={'apply_best_practices': False}
    ) 
    assert response_flag_false.status_code == 400
    assert "Missing 'line_prompt' or 'apply_best_practices' must be true" in response_flag_false.get_json()['error']

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

# --- Tests for Category Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # Mock rules utility
def test_refine_category_success_no_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful category refinement (apply_best_practices=False)."""
    script_id = 1
    category_name = "TestCategory"
    user_prompt = "Make this category more dramatic."
    
    mock_context1 = {"line_id": 101, "current_text": "Line A original.", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Line B original.", "is_locked": True}
    mock_get_context.return_value = [mock_context1, mock_context2]
    refined_text1 = "Line A dramatic!"
    mock_call_openai.return_value = refined_text1
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/categories/refine',
        json={'category_name': category_name, 'category_prompt': user_prompt, 'apply_best_practices': False} # Flag is False
    )
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['data']) == 1
    assert json_data['data'][0]['id'] == 101

    mock_get_rules.assert_not_called()
    mock_call_openai.assert_called_once() # Only called for line 101
    # Check prompt structure (should NOT have rules)
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" not in actual_prompt
    assert "ElevenLabs Rules:" not in actual_prompt
    assert f"Category Prompt: {user_prompt}" in actual_prompt
    
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY)

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # Mock rules utility
def test_refine_category_success_with_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful category refinement (apply_best_practices=True)."""
    script_id = 1
    category_name = "TestCategory"
    user_prompt = "Make this category more dramatic."
    elevenlabs_rules_text = "Rule: Add pauses."
    
    mock_context1 = {"line_id": 101, "current_text": "Line A original.", "is_locked": False}
    mock_get_context.return_value = [mock_context1]
    refined_text1 = "Line A dramatic! <break time='0.5s'/>"
    mock_call_openai.return_value = refined_text1
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1
    mock_get_rules.return_value = elevenlabs_rules_text
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/categories/refine',
        json={'category_name': category_name, 'category_prompt': user_prompt, 'apply_best_practices': True} # Flag is TRUE
    )
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['data']) == 1
    assert json_data['data'][0]['id'] == 101

    mock_get_rules.assert_called_once() # Rules should be fetched
    mock_call_openai.assert_called_once() 
    # Check prompt structure (should have rules)
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" in actual_prompt
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt
    assert f"Category Prompt: {user_prompt}" in actual_prompt
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt
    
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY)

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
    """Test API response when category_name or category_prompt is missing (and apply_best_practices=False)."""
    # Missing category_prompt, flag defaults to False
    response1 = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_name': "TestCategory"}
    )
    assert response1.status_code == 400
    assert "Missing 'category_prompt' or 'apply_best_practices' must be true" in response1.get_json()['error']
    
    # Missing category_name, flag defaults to False
    response2 = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_prompt': "Test Prompt"}
    )
    assert response2.status_code == 400
    assert "Missing 'category_name'" in response2.get_json()['error'] 
    
    # Missing category_prompt, flag explicitly False
    response3 = test_client.post(
        '/api/vo-scripts/1/categories/refine',
        json={'category_name': "TestCategory", 'apply_best_practices': False}
    )
    assert response3.status_code == 400
    assert "Missing 'category_prompt' or 'apply_best_practices' must be true" in response3.get_json()['error'] 

# --- Test hierarchical prompt construction for Category --- #
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
    # NEW: Assert sibling/variety instructions are present when appropriate
    # (This specific test doesn't apply rules, so check they AREN'T there)
    assert "Sibling Line Examples" not in actual_prompt 
    assert "Ensure the refined output for this specific line is varied" not in actual_prompt

# Add a new test specifically for verifying prompt with siblings+rules in category refine
@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_category_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules')
def test_refine_category_prompt_with_siblings_and_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Verify prompt construction for category refinement WITH siblings AND apply_rules=True."""
    script_id = 1
    category_name = "TestCategory"
    category_prompt = "Category instruction."
    elevenlabs_rules_text = "Rule: Use breaks."
    mock_get_rules.return_value = elevenlabs_rules_text

    # Mock context with multiple lines
    mock_context1 = {"line_id": 101, "current_text": "Line A text.", "line_key": "LINE_A", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Line B text.", "line_key": "LINE_B", "is_locked": False}
    mock_get_context.return_value = [mock_context1, mock_context2]
    
    # Mock OpenAI/DB update return values (we only care about the prompt here)
    mock_call_openai.return_value = "Some refined text"
    mock_update_db.return_value = models.VoScriptLine(id=101)

    # Mock get_db
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    # Call API with apply_best_practices = True
    test_client.post(
        f'/api/vo-scripts/{script_id}/categories/refine',
        json={'category_name': category_name, 'category_prompt': category_prompt, 'apply_best_practices': True}
    )
    
    # Assert call_openai was called twice (once per non-locked line)
    assert mock_call_openai.call_count == 2
    
    # Check prompt for the FIRST line (line 101)
    call_args_1, call_kwargs_1 = mock_call_openai.call_args_list[0]
    actual_prompt_1 = call_kwargs_1.get('prompt')
    assert "--- Sibling Line Examples ---" in actual_prompt_1
    assert "- LINE_B: \"Line B text.\"" in actual_prompt_1 # Check sibling B is present
    assert "IMPORTANT: Ensure the refined output for this specific line is varied" in actual_prompt_1
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt_1 # Check rules are included
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt_1

    # Check prompt for the SECOND line (line 102)
    call_args_2, call_kwargs_2 = mock_call_openai.call_args_list[1]
    actual_prompt_2 = call_kwargs_2.get('prompt')
    assert "--- Sibling Line Examples ---" in actual_prompt_2
    assert "- LINE_A: \"Line A text.\"" in actual_prompt_2 # Check sibling A is present
    assert "IMPORTANT: Ensure the refined output for this specific line is varied" in actual_prompt_2
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt_2 # Check rules are included
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt_2

# --- Tests for Script Refinement Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # NEW Mock
def test_refine_script_success_no_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful script refinement (apply_best_practices=False)."""
    script_id = 1
    global_prompt = "Overall: Make everything more formal."
    
    mock_context1 = {"line_id": 101, "current_text": "Hiya!", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Yo!", "is_locked": True}
    mock_get_context.return_value = [mock_context1, mock_context2]
    refined_text1 = "Greetings."
    mock_call_openai.return_value = refined_text1
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/refine',
        json={'global_prompt': global_prompt, 'apply_best_practices': False} # Flag is False
    )
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['data']) == 1
    assert json_data['data'][0]['id'] == 101

    mock_get_rules.assert_not_called()
    mock_call_openai.assert_called_once() 
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" not in actual_prompt
    assert "ElevenLabs Rules:" not in actual_prompt
    assert f"Global Script Prompt: {global_prompt}" in actual_prompt
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY)

@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules') # NEW Mock
def test_refine_script_success_with_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Test successful script refinement (apply_best_practices=True)."""
    script_id = 1
    global_prompt = "Overall: Make everything more formal."
    elevenlabs_rules_text = "Rule: Use breaks."
    
    mock_context1 = {"line_id": 101, "current_text": "Hiya!", "is_locked": False}
    mock_get_context.return_value = [mock_context1]
    refined_text1 = "Greetings. <break time='0.2s'/>"
    mock_call_openai.return_value = refined_text1
    mock_updated_line1 = models.VoScriptLine(id=101, generated_text=refined_text1, status="review")
    mock_update_db.return_value = mock_updated_line1
    mock_get_rules.return_value = elevenlabs_rules_text # Mock rules return
    
    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    response = test_client.post(
        f'/api/vo-scripts/{script_id}/refine',
        json={'global_prompt': global_prompt, 'apply_best_practices': True} # Flag is TRUE
    )
    
    assert response.status_code == 200
    json_data = response.get_json()
    assert len(json_data['data']) == 1
    assert json_data['data'][0]['id'] == 101

    mock_get_rules.assert_called_once() # Rules should be fetched
    mock_call_openai.assert_called_once() 
    call_args, call_kwargs = mock_call_openai.call_args
    actual_prompt = call_kwargs.get('prompt')
    assert "--- Stage 1: User Refinement Request ---" in actual_prompt
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt
    assert f"Global Script Prompt: {global_prompt}" in actual_prompt
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt
    
    mock_update_db.assert_called_once_with(mock_session, 101, refined_text1, "review", mock.ANY)

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
    """Test API response when global_prompt is missing (and apply_best_practices=False)."""
    # Flag defaults to false, send empty prompt
    response = test_client.post('/api/vo-scripts/1/refine', json={'global_prompt': ''})
    assert response.status_code == 400
    assert "Missing 'global_prompt' or 'apply_best_practices' must be true" in response.get_json()['error']
    
    # Flag explicitly false, send empty prompt
    response2 = test_client.post('/api/vo-scripts/1/refine', json={'global_prompt': '', 'apply_best_practices': False})
    assert response2.status_code == 400
    assert "Missing 'global_prompt' or 'apply_best_practices' must be true" in response2.get_json()['error']

# --- Test hierarchical prompt construction for Script --- #
@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
def test_refine_script_prompt_construction(
    mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Verify hierarchical prompt construction for script refinement (without rules/siblings)."""
    script_id = 1
    global_prompt = "Make the whole script sound older."
    
    # Mock context including category and line prompts/feedback
    mock_context1 = {
        "line_id": 101, 
        "current_text": "Line A original.", 
        "script_refinement_prompt": "Old Global Prompt (should be ignored)", 
        "category_refinement_prompt": "Category 1 Old Prompt.",
        "latest_feedback": "Line A specific feedback.",
        "character_description": "Test Char",
        "is_locked": False # Ensure not locked for testing
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
        json={'global_prompt': global_prompt, 'apply_best_practices': False} # Explicitly false
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
    # Check that sibling/variety/rules stuff is NOT present
    assert "Sibling Line Examples" not in actual_prompt
    assert "IMPORTANT: Ensure the refined output" in actual_prompt # Variety instruction IS included
    assert "ElevenLabs Rules:" not in actual_prompt

# Add similar test for script refine WITH siblings and rules
@mock.patch('backend.routes.vo_script_routes.get_db')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.get_script_lines_context')
@mock.patch('backend.routes.vo_script_routes.utils_openai.call_openai_responses_api')
@mock.patch('backend.routes.vo_script_routes.utils_voscript.update_line_in_db')
@mock.patch('backend.routes.vo_script_routes._get_elevenlabs_rules')
def test_refine_script_prompt_with_siblings_and_rules(
    mock_get_rules, mock_update_db, mock_call_openai, mock_get_context, mock_get_db, test_client
):
    """Verify prompt construction for script refinement WITH siblings AND apply_rules=True."""
    script_id = 1
    global_prompt = "Make it all sound like pirates."
    elevenlabs_rules_text = "Rule: Arrr matey."
    mock_get_rules.return_value = elevenlabs_rules_text

    # Mock context with multiple lines
    mock_context1 = {"line_id": 101, "current_text": "Hello.", "line_key": "GREET", "is_locked": False}
    mock_context2 = {"line_id": 102, "current_text": "Goodbye.", "line_key": "FAREWELL", "is_locked": False}
    mock_get_context.return_value = [mock_context1, mock_context2]
    
    mock_call_openai.return_value = "Ahoy!"
    mock_update_db.return_value = models.VoScriptLine(id=101)

    mock_session = MagicMock()
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    test_client.post(
        f'/api/vo-scripts/{script_id}/refine',
        json={'global_prompt': global_prompt, 'apply_best_practices': True}
    )
    
    assert mock_call_openai.call_count == 2
    
    # Check prompt for the FIRST line (line 101)
    call_args_1, call_kwargs_1 = mock_call_openai.call_args_list[0]
    actual_prompt_1 = call_kwargs_1.get('prompt')
    assert "--- Sibling Line Examples ---" in actual_prompt_1
    assert "- FAREWELL: \"Goodbye.\"" in actual_prompt_1
    assert "IMPORTANT: Ensure the refined output for this specific line is varied" in actual_prompt_1
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt_1
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt_1
    assert f"Global Script Prompt: {global_prompt}" in actual_prompt_1

    # Check prompt for the SECOND line (line 102)
    call_args_2, call_kwargs_2 = mock_call_openai.call_args_list[1]
    actual_prompt_2 = call_kwargs_2.get('prompt')
    assert "--- Sibling Line Examples ---" in actual_prompt_2
    assert "- GREET: \"Hello.\"" in actual_prompt_2
    assert "IMPORTANT: Ensure the refined output for this specific line is varied" in actual_prompt_2
    assert "--- Stage 2: Apply ElevenLabs Best Practices ---" in actual_prompt_2
    assert f"ElevenLabs Rules:\n{elevenlabs_rules_text}" in actual_prompt_2
    assert f"Global Script Prompt: {global_prompt}" in actual_prompt_2

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

# REMOVE MOCK - Use real DB via test_db fixture
# @mock.patch('backend.routes.vo_script_routes.get_db') 
def test_update_line_text_success(test_client, test_db): # Inject test_db fixture
    """Test successfully updating line text manually."""
    script_id = 999 # Use ID from test_db fixture
    
    # Create a real line object in the test DB
    line_to_update = models.VoScriptLine(
        vo_script_id=script_id,
        line_key="UPDATE_ME",
        generated_text="Old Text",
        status="generated",
        category_id=None, # Assuming category isn't strictly needed for this test
        template_line_id=None
    )
    test_db.add(line_to_update)
    test_db.commit()
    test_db.refresh(line_to_update)
    line_id = line_to_update.id # Get the actual ID
    
    new_text = "Manually updated text."
    
    # Call the API endpoint
    response = test_client.patch(
        f'/api/vo-scripts/{script_id}/lines/{line_id}/update-text',
        json={'generated_text': new_text}
    )
    
    # Assertions
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['data']['generated_text'] == new_text
    assert json_data['data']['status'] == 'manual'
    
    # Verify in DB
    test_db.refresh(line_to_update) # Refresh from DB
    assert line_to_update.generated_text == new_text
    assert line_to_update.status == 'manual'
    assert line_to_update.latest_feedback is None # Check feedback cleared
    assert isinstance(line_to_update.generation_history, list)
    assert len(line_to_update.generation_history) >= 2 # Should have pre/post entries
    assert line_to_update.generation_history[-1]['type'] == 'manual_edit'
    assert line_to_update.generation_history[-1]['text'] == new_text

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

# --- Tests for Add New Line Endpoint --- #

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_add_line_success(mock_get_db, test_client):
    """Test successfully adding a new custom line to a script."""
    script_id = 1
    payload = {
        "line_key": "CUSTOM_GREET",
        "category_name": "Greetings", # Specify category by name
        "initial_text": "A custom hello.",
        "order_index": 5,
        "prompt_hint": "Custom hint."
    }
    
    # Mock category lookup
    mock_category = MagicMock(spec=models.VoScriptTemplateCategory)
    mock_category.id = 303 # Found category ID
    
    # Mock session and query/add/commit
    mock_session = MagicMock(spec=Session)
    # Mock finding the category by name and script's template_id (assuming script is fetched first)
    mock_script = MagicMock(spec=models.VoScript, template_id=404)
    mock_session.query.return_value.get.return_value = mock_script # Mock get script
    mock_session.query.return_value.filter.return_value.first.return_value = mock_category # Mock find category
    
    # Capture the object added to the session
    added_line = None
    def capture_add(obj):
        nonlocal added_line
        if isinstance(obj, models.VoScriptLine):
            added_line = obj
    mock_session.add.side_effect = capture_add
    
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator

    # Call API
    response = test_client.post(f'/api/vo-scripts/{script_id}/lines', json=payload)
    
    # Assertions
    assert response.status_code == 201
    mock_session.add.assert_called_once() # Check add was called
    assert added_line is not None
    assert added_line.vo_script_id == script_id
    assert added_line.line_key == payload['line_key']
    assert added_line.category_id == mock_category.id
    assert added_line.generated_text == payload['initial_text']
    assert added_line.order_index == payload['order_index']
    assert added_line.prompt_hint == payload['prompt_hint']
    assert added_line.template_line_id is None # Should be null for custom line
    assert added_line.status == 'manual' # Should start as manual?
    mock_session.commit.assert_called_once()
    
    json_data = response.get_json()
    assert 'data' in json_data
    assert json_data['data']['line_key'] == payload['line_key']
    assert json_data['data']['status'] == 'manual'

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_add_line_missing_fields(mock_get_db, test_client):
    """Test adding line with missing required fields."""
    script_id = 1
    # Missing line_key
    payload1 = { "category_name": "Cat", "initial_text": "Hi", "order_index": 1 }
    response1 = test_client.post(f'/api/vo-scripts/{script_id}/lines', json=payload1)
    assert response1.status_code == 400
    assert "Missing 'line_key'" in response1.get_json()['error']
    
    # Missing category_name
    payload2 = { "line_key": "Key", "initial_text": "Hi", "order_index": 1 }
    response2 = test_client.post(f'/api/vo-scripts/{script_id}/lines', json=payload2)
    assert response2.status_code == 400
    assert "Missing 'category_name'" in response2.get_json()['error']

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_add_line_script_not_found(mock_get_db, test_client):
    """Test adding line to a non-existent script."""
    mock_session = MagicMock()
    mock_session.query.return_value.get.return_value = None # Script not found
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    payload = { "line_key": "Key", "category_name": "Cat", "order_index": 1 }
    response = test_client.post('/api/vo-scripts/999/lines', json=payload)
    assert response.status_code == 404
    assert "Script not found" in response.get_json()['error']

@mock.patch('backend.routes.vo_script_routes.get_db')
def test_add_line_category_not_found(mock_get_db, test_client):
    """Test adding line when specified category doesn't exist for the script's template."""
    mock_session = MagicMock()
    mock_script = MagicMock(spec=models.VoScript, template_id=404)
    mock_session.query.return_value.get.return_value = mock_script # Script found
    # Category not found
    mock_session.query.return_value.filter.return_value.first.return_value = None 
    
    mock_get_db_iterator = MagicMock()
    mock_get_db_iterator.__next__.return_value = mock_session
    mock_get_db.return_value = mock_get_db_iterator
    
    payload = { "line_key": "Key", "category_name": "BadCat", "order_index": 1 }
    response = test_client.post('/api/vo-scripts/1/lines', json=payload)
    assert response.status_code == 404
    assert "Category 'BadCat' not found" in response.get_json()['error']

# ... rest of tests ... 