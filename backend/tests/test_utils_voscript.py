# backend/tests/test_utils_voscript.py
import unittest
from unittest.mock import patch, MagicMock, call
from sqlalchemy.orm import Session
from datetime import datetime, timezone

# Import modules to test/mock
from backend import utils_voscript
from backend import models

class TestUtilsVoScript(unittest.TestCase):

    def test_get_line_context_found(self):
        """Test fetching context for an existing line."""
        mock_session = MagicMock(spec=Session)
        mock_line = MagicMock(spec=models.VoScriptLine)
        mock_template_line = MagicMock(spec=models.VoScriptTemplateLine)
        mock_category = MagicMock(spec=models.VoScriptTemplateCategory)
        mock_script = MagicMock(spec=models.VoScript)
        mock_template = MagicMock(spec=models.VoScriptTemplate)

        # Setup mock object attributes
        mock_line.id = 101
        mock_line.vo_script_id = 1
        mock_line.template_line_id = 202
        mock_line.generated_text = "Original generated text."
        mock_line.status = "generated"
        mock_line.latest_feedback = "Needs more energy."
        mock_line.template_line = mock_template_line
        mock_line.vo_script = mock_script

        mock_template_line.id = 202
        mock_template_line.line_key = "GREETING_1"
        mock_template_line.prompt_hint = "A friendly welcome."
        mock_template_line.order_index = 0
        mock_template_line.category = mock_category
        mock_template_line.template = mock_template # Link template line to template
        
        mock_category.id = 303
        mock_category.name = "Greetings"
        mock_category.prompt_instructions = "Keep it warm and inviting."

        mock_script.id = 1
        mock_script.name = "Test Script"
        mock_script.character_description = "A friendly robot."
        mock_script.template = mock_template # Link script to template
        
        mock_template.id = 404
        mock_template.name = "Friendly Bot Template"
        mock_template.prompt_hint = "General tone: Cheerful."

        # Configure the mock session query chain
        mock_query = mock_session.query.return_value
        mock_options = mock_query.options.return_value
        mock_filter = mock_options.filter.return_value
        mock_filter.first.return_value = mock_line
        
        line_id_to_fetch = 101
        context = utils_voscript.get_line_context(mock_session, line_id_to_fetch)

        # Assertions
        mock_session.query.assert_called_once_with(models.VoScriptLine)
        # TODO: Add assertion for options (joinedload etc.) if implemented that way
        mock_options.filter.assert_called_once()
        # Check the filter condition (difficult to assert precisely with MagicMock args)
        mock_filter.first.assert_called_once()
        
        self.assertIsNotNone(context)
        self.assertEqual(context['line_id'], line_id_to_fetch)
        self.assertEqual(context['current_text'], "Original generated text.")
        self.assertEqual(context['status'], "generated")
        self.assertEqual(context['latest_feedback'], "Needs more energy.")
        self.assertEqual(context['line_key'], "GREETING_1")
        self.assertEqual(context['line_template_hint'], "A friendly welcome.")
        self.assertEqual(context['category_name'], "Greetings")
        self.assertEqual(context['category_instructions'], "Keep it warm and inviting.")
        self.assertEqual(context['script_name'], "Test Script")
        self.assertEqual(context['character_description'], "A friendly robot.")
        self.assertEqual(context['template_name'], "Friendly Bot Template")
        self.assertEqual(context['template_hint'], "General tone: Cheerful.")

    def test_get_line_context_not_found(self):
        """Test fetching context for a non-existent line."""
        mock_session = MagicMock(spec=Session)
        mock_query = mock_session.query.return_value
        mock_options = mock_query.options.return_value
        mock_filter = mock_options.filter.return_value
        mock_filter.first.return_value = None # Simulate line not found
        
        context = utils_voscript.get_line_context(mock_session, 999)
        
        self.assertIsNone(context)
        mock_filter.first.assert_called_once()

    def test_get_line_context_missing_relations(self):
        """Test fetching context when related objects (template, category) are missing."""
        mock_session = MagicMock(spec=Session)
        mock_line = MagicMock(spec=models.VoScriptLine)
        mock_script = MagicMock(spec=models.VoScript)

        # Setup mock object attributes - line exists, but no template_line or script
        mock_line.id = 101
        mock_line.vo_script_id = 1
        mock_line.template_line_id = None # Missing link
        mock_line.generated_text = "Orphan text."
        mock_line.status = "pending"
        mock_line.latest_feedback = None
        mock_line.template_line = None # Explicitly None
        mock_line.vo_script = None # Explicitly None
        
        mock_query = mock_session.query.return_value
        mock_options = mock_query.options.return_value
        mock_filter = mock_options.filter.return_value
        mock_filter.first.return_value = mock_line
        
        context = utils_voscript.get_line_context(mock_session, 101)

        # Assertions - Should still return basic info
        self.assertIsNotNone(context)
        self.assertEqual(context['line_id'], 101)
        self.assertEqual(context['current_text'], "Orphan text.")
        self.assertEqual(context['status'], "pending")
        self.assertIsNone(context['latest_feedback'])
        # Check that missing fields are None or have defaults
        self.assertIsNone(context.get('line_key'))
        self.assertIsNone(context.get('line_template_hint'))
        self.assertIsNone(context.get('category_name'))
        self.assertIsNone(context.get('category_instructions'))
        self.assertIsNone(context.get('script_name'))
        self.assertIsNone(context.get('character_description'))
        self.assertIsNone(context.get('template_name'))
        self.assertIsNone(context.get('template_hint'))

    def test_get_category_lines_context_found(self):
        """Test fetching context for lines within a specific category."""
        mock_session = MagicMock(spec=Session)
        
        # --- Mocks Setup --- #
        # Mock Script (with refinement prompt)
        mock_template_obj = MagicMock(spec=models.VoScriptTemplate, prompt_hint="Template hint")
        mock_template_obj.name = "TmplName"
        mock_parent_script = MagicMock(spec=models.VoScript, 
                                     id=1, 
                                     name="Parent Script", 
                                     refinement_prompt="Global script prompt here.", 
                                     character_description="Char desc",
                                     template=mock_template_obj)
                                     
        # Mock lines, template lines, category (Fix category name mock)
        mock_line1 = MagicMock(spec=models.VoScriptLine, id=101, generated_text="Line 1 text", status="generated", latest_feedback=None)
        mock_tl1 = MagicMock(spec=models.VoScriptTemplateLine, line_key="CAT1_A", prompt_hint="Hint A", order_index=1)
        mock_cat1 = MagicMock(spec=models.VoScriptTemplateCategory, prompt_instructions="Category instructions")
        mock_cat1.name = "TargetCategory" # Explicitly set name
        mock_line1.template_line = mock_tl1
        mock_tl1.category = mock_cat1

        mock_line2 = MagicMock(spec=models.VoScriptLine, id=102, generated_text="Line 2 text", status="review", latest_feedback="Needs review")
        mock_tl2 = MagicMock(spec=models.VoScriptTemplateLine, line_key="CAT1_B", prompt_hint="Hint B", order_index=0)
        mock_cat2 = MagicMock(spec=models.VoScriptTemplateCategory, prompt_instructions="Category instructions")
        mock_cat2.name = "TargetCategory" # Explicitly set name
        mock_line2.template_line = mock_tl2
        mock_tl2.category = mock_cat2
        
        # Mock Session Calls (Corrected for multiple queries)
        mock_script_query = MagicMock()
        mock_script_query.options.return_value.get.return_value = mock_parent_script

        mock_lines_query = MagicMock()
        mock_options = mock_lines_query.options.return_value
        mock_filter_script = mock_options.filter.return_value
        mock_join1 = mock_filter_script.join.return_value
        mock_join2 = mock_join1.join.return_value
        mock_filter_category = mock_join2.filter.return_value
        mock_order_by = mock_filter_category.order_by.return_value
        mock_order_by.all.return_value = [mock_line2, mock_line1]
        
        def query_side_effect(model_class):
            if model_class == models.VoScript:
                return mock_script_query
            elif model_class == models.VoScriptLine:
                return mock_lines_query
            return MagicMock()
        mock_session.query.side_effect = query_side_effect
        
        # --- Execute --- #
        script_id = 1
        category_name = "TargetCategory"
        contexts = utils_voscript.get_category_lines_context(mock_session, script_id, category_name)

        # --- Assertions --- #
        # Check parent script fetch call
        mock_session.query.assert_any_call(models.VoScript)
        mock_script_query.options.assert_called_once() 
        mock_script_query.options.return_value.get.assert_called_once_with(script_id)
        
        # Check lines fetch call chain
        mock_session.query.assert_any_call(models.VoScriptLine)
        mock_lines_query.options.assert_called_once() 
        mock_options.filter.assert_called_once() 
        mock_filter_script.join.assert_called_once() 
        mock_join1.join.assert_called_once() 
        mock_join2.filter.assert_called_once() 
        mock_filter_category.order_by.assert_called_once() 
        mock_order_by.all.assert_called_once()
        
        self.assertIsNotNone(contexts)
        self.assertEqual(len(contexts), 2)
        
        # Check context content, including script prompt
        self.assertEqual(contexts[0]['line_id'], 102)
        self.assertEqual(contexts[0]['script_refinement_prompt'], "Global script prompt here.")
        self.assertEqual(contexts[0]['template_name'], "TmplName")
        
        self.assertEqual(contexts[1]['line_id'], 101)
        self.assertEqual(contexts[1]['script_refinement_prompt'], "Global script prompt here.")
        self.assertEqual(contexts[1]['category_name'], "TargetCategory")
        self.assertEqual(contexts[1]['template_hint'], "Template hint")

    def test_get_category_lines_context_parent_script_not_found(self):
        """Test when the parent script ID does not exist."""
        mock_session = MagicMock(spec=Session)
        # Simulate parent script not found
        mock_session.query.return_value.options.return_value.get.return_value = None
        
        script_id = 999
        category_name = "AnyCategory"
        contexts = utils_voscript.get_category_lines_context(mock_session, script_id, category_name)
        
        self.assertEqual(contexts, []) # Expect empty list
        mock_session.query.assert_called_once_with(models.VoScript) # Check it tried to get script
        mock_session.query.return_value.options.return_value.get.assert_called_once_with(script_id)

    def test_get_category_lines_context_not_found(self):
        """Test fetching context when no lines match the category."""
        mock_session = MagicMock(spec=Session)
        
        # Mock parent script found
        mock_parent_script = MagicMock(spec=models.VoScript, id=1, refinement_prompt=None)
        mock_script_query = MagicMock()
        mock_script_query.options.return_value.get.return_value = mock_parent_script
        
        # Mock lines query returns empty
        mock_lines_query = MagicMock()
        mock_lines_query.options.return_value.filter.return_value.join.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        # Make session.query return the correct mock based on the model being queried
        def query_side_effect(model_class):
            if model_class == models.VoScript:
                return mock_script_query
            elif model_class == models.VoScriptLine:
                return mock_lines_query
            return MagicMock() # Default mock if other models queried
        mock_session.query.side_effect = query_side_effect
        
        contexts = utils_voscript.get_category_lines_context(mock_session, 1, "NonExistentCategory")
        
        self.assertIsNotNone(contexts)
        self.assertEqual(len(contexts), 0)
        # Check all() was called on the lines query
        mock_lines_query.options.return_value.filter.return_value.join.return_value.join.return_value.filter.return_value.order_by.return_value.all.assert_called_once()

    # --- Tests for get_script_lines_context --- 
    def test_get_script_lines_context_found(self):
        """Test fetching context for all lines within a specific script."""
        mock_session = MagicMock(spec=Session)
        
        # --- Mocks Setup --- #
        # Mock Category Prompts
        mock_cat1_obj = MagicMock(spec=models.VoScriptTemplateCategory, id=303, prompt_instructions="Instr 1", refinement_prompt="Cat 1 prompt.")
        mock_cat1_obj.name = "Category1" # Set name
        mock_cat2_obj = MagicMock(spec=models.VoScriptTemplateCategory, id=304, prompt_instructions="Instr 2", refinement_prompt="Cat 2 prompt.")
        mock_cat2_obj.name = "Category2" # Set name
        # Mock Template
        mock_template_obj = MagicMock(spec=models.VoScriptTemplate, name="TmplName", prompt_hint="Template hint")
        mock_template_obj.categories = [mock_cat1_obj, mock_cat2_obj] # Add categories to template
        # Mock Script
        mock_parent_script = MagicMock(spec=models.VoScript, id=1, name="Script", refinement_prompt="Global prompt.", character_description="Char desc", template=mock_template_obj)

        # Mock Lines (referencing categories)
        mock_line1 = MagicMock(spec=models.VoScriptLine, id=101, generated_text="Line 1 text", status="generated", latest_feedback=None)
        mock_tl1 = MagicMock(spec=models.VoScriptTemplateLine, line_key="CAT1_A", prompt_hint="Hint A", order_index=1, category_id=303)
        mock_line1.template_line = mock_tl1
        
        mock_line2 = MagicMock(spec=models.VoScriptLine, id=102, generated_text="Line 2 text", status="review", latest_feedback="Needs review")
        mock_tl2 = MagicMock(spec=models.VoScriptTemplateLine, line_key="CAT2_B", prompt_hint="Hint B", order_index=0, category_id=304)
        mock_line2.template_line = mock_tl2
        
        # Mock Session Calls (Corrected for multiple queries)
        mock_script_query = MagicMock()
        mock_script_query.options.return_value.get.return_value = mock_parent_script # For fetching script + template + categories

        mock_lines_query = MagicMock()
        mock_options = mock_lines_query.options.return_value
        mock_filter_script = mock_options.filter.return_value
        mock_join = mock_filter_script.join.return_value
        mock_order_by = mock_join.order_by.return_value
        mock_order_by.all.return_value = [mock_line2, mock_line1] # Return in DB order

        def query_side_effect(model_class):
            if model_class == models.VoScript:
                return mock_script_query
            elif model_class == models.VoScriptLine:
                return mock_lines_query
            return MagicMock()
        mock_session.query.side_effect = query_side_effect
        
        # --- Execute --- #
        script_id = 1
        contexts = utils_voscript.get_script_lines_context(mock_session, script_id)

        # --- Assertions --- #
        # Check parent script fetch call
        mock_session.query.assert_any_call(models.VoScript)
        mock_script_query.options.assert_called_once()
        mock_script_query.options.return_value.get.assert_called_once_with(script_id)
        
        # Check lines fetch call chain
        mock_session.query.assert_any_call(models.VoScriptLine)
        mock_lines_query.options.assert_called_once() 
        mock_options.filter.assert_called_once()
        mock_filter_script.join.assert_called_once()
        mock_join.order_by.assert_called_once()
        mock_order_by.all.assert_called_once()
        
        self.assertIsNotNone(contexts)
        self.assertEqual(len(contexts), 2)
        
        # Check context content, including category prompts
        self.assertEqual(contexts[0]['line_id'], 102)
        self.assertEqual(contexts[0]['category_name'], "Category2")
        self.assertEqual(contexts[0]['category_refinement_prompt'], "Cat 2 prompt.")
        self.assertEqual(contexts[0]['script_refinement_prompt'], "Global prompt.")
        
        self.assertEqual(contexts[1]['line_id'], 101)
        self.assertEqual(contexts[1]['category_name'], "Category1")
        self.assertEqual(contexts[1]['category_refinement_prompt'], "Cat 1 prompt.")
        self.assertEqual(contexts[1]['script_refinement_prompt'], "Global prompt.")

    def test_get_script_lines_context_not_found(self):
        """Test fetching context when no lines exist for the script."""
        mock_session = MagicMock(spec=Session)
        
        # Mock parent script found
        mock_parent_script = MagicMock(spec=models.VoScript, id=99, refinement_prompt=None, template=None)
        mock_script_query = MagicMock()
        mock_script_query.options.return_value.get.return_value = mock_parent_script
        
        # Mock lines query returns empty
        mock_lines_query = MagicMock()
        mock_options = mock_lines_query.options.return_value
        mock_filter = mock_options.filter.return_value
        mock_join = mock_filter.join.return_value 
        mock_order_by = mock_join.order_by.return_value
        mock_order_by.all.return_value = [] 

        def query_side_effect(model_class):
            if model_class == models.VoScript:
                return mock_script_query
            elif model_class == models.VoScriptLine:
                return mock_lines_query
            return MagicMock()
        mock_session.query.side_effect = query_side_effect
        
        contexts = utils_voscript.get_script_lines_context(mock_session, 99)
        
        self.assertIsNotNone(contexts)
        self.assertEqual(len(contexts), 0)
        mock_order_by.all.assert_called_once()

    # --- Tests for update_line_in_db --- 
    @patch('backend.utils_voscript.datetime') 
    def test_update_line_in_db_success(self, mock_datetime):
        """Test successfully updating a line."""
        mock_session = MagicMock(spec=Session)
        mock_line = MagicMock(spec=models.VoScriptLine)
        mock_line.id = 101
        mock_line.generation_history = [] # Start with empty history
        
        # Configure mock datetime
        fake_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Mock the datetime object returned by datetime.now()
        mock_now_instance = MagicMock()
        mock_now_instance.isoformat.return_value = fake_now.isoformat()
        # Make the mocked datetime.now() return our instance
        mock_datetime.now.return_value = mock_now_instance 
        
        # Mock the DB query
        mock_session.query.return_value.get.return_value = mock_line
        
        line_id = 101
        new_text = "Updated text by test."
        new_status = "review"
        model_name = "test-model"
        
        updated_line_obj = utils_voscript.update_line_in_db(
            mock_session, line_id, new_text, new_status, model_name
        )

        # Assertions
        mock_session.query.assert_called_once_with(models.VoScriptLine)
        mock_session.query.return_value.get.assert_called_once_with(line_id)
        self.assertEqual(updated_line_obj, mock_line) # Should return the updated object
        
        # Check updated attributes
        self.assertEqual(mock_line.generated_text, new_text)
        self.assertEqual(mock_line.status, new_status)
        
        # Check history append
        self.assertIsInstance(mock_line.generation_history, list)
        self.assertEqual(len(mock_line.generation_history), 1)
        history_entry = mock_line.generation_history[0]
        # Check datetime.now was called with timezone.utc
        mock_datetime.now.assert_called_once_with(timezone.utc)
        self.assertEqual(history_entry['timestamp'], fake_now.isoformat())
        self.assertEqual(history_entry['type'], "generation") # Default type for now
        self.assertEqual(history_entry['text'], new_text)
        self.assertEqual(history_entry['model'], model_name)
        
        # Check commit was called
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch('backend.utils_voscript.datetime')
    def test_update_line_in_db_append_history(self, mock_datetime):
        """Test appending to existing history."""
        mock_session = MagicMock(spec=Session)
        mock_line = MagicMock(spec=models.VoScriptLine)
        mock_line.id = 102
        existing_history = [{'timestamp': '2023-12-31T10:00:00', 'type': 'initial', 'text': 'First draft'}]
        mock_line.generation_history = existing_history.copy() # Use copy
        
        fake_now = datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        mock_now_instance = MagicMock()
        mock_now_instance.isoformat.return_value = fake_now.isoformat()
        mock_datetime.now.return_value = mock_now_instance
        
        mock_session.query.return_value.get.return_value = mock_line
        
        new_text = "Second draft update."
        updated_line_obj = utils_voscript.update_line_in_db(mock_session, 102, new_text, "review", "gpt-4o")

        self.assertEqual(mock_line.generated_text, new_text)
        self.assertEqual(len(mock_line.generation_history), 2) # Should have appended
        self.assertEqual(mock_line.generation_history[0]['text'], 'First draft')
        self.assertEqual(mock_line.generation_history[1]['text'], new_text)
        mock_datetime.now.assert_called_once_with(timezone.utc)
        mock_session.commit.assert_called_once()

if __name__ == '__main__':
    unittest.main() 