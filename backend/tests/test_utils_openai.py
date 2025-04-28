# backend/tests/test_utils_openai.py
import unittest
from unittest.mock import patch, MagicMock
import openai

# Import the function to test (assuming it will be in backend/utils_openai.py)
from backend import utils_openai

class TestUtilsOpenAI(unittest.TestCase):

    @patch('backend.utils_openai.client') # Patch the OpenAI client instance in the utils module
    def test_call_openai_responses_api_success(self, mock_openai_client):
        """Test successful call to OpenAI Responses API."""
        # Configure the mock client and its nested methods/attributes
        mock_response = MagicMock()
        mock_response.output_text = "This is the refined text."
        
        mock_create_method = MagicMock(return_value=mock_response)
        mock_responses_api = MagicMock()
        mock_responses_api.create = mock_create_method
        mock_openai_client.responses = mock_responses_api
        
        test_prompt = "Refine this text: Original text."
        model = "gpt-4o"
        max_tokens = 100
        # Get the default temperature from the module to ensure consistency
        expected_temperature = utils_openai.DEFAULT_TEMPERATURE 
        
        result = utils_openai.call_openai_responses_api(
            prompt=test_prompt, 
            model=model, 
            max_tokens=max_tokens
            # Testing with default temperature
        )
        
        self.assertEqual(result, "This is the refined text.")
        
        # Verify the create method was called correctly, including default temperature
        mock_create_method.assert_called_once_with(
            model=model,
            input=test_prompt,
            max_output_tokens=max_tokens,
            temperature=expected_temperature # Check against the expected default
        )

    @patch('backend.utils_openai.client')
    def test_call_openai_responses_api_empty_response(self, mock_openai_client):
        """Test call where OpenAI returns an empty response."""
        mock_response = MagicMock()
        mock_response.output_text = ""
        mock_create_method = MagicMock(return_value=mock_response)
        mock_responses_api = MagicMock()
        mock_responses_api.create = mock_create_method
        mock_openai_client.responses = mock_responses_api
        
        result = utils_openai.call_openai_responses_api(prompt="Test prompt")
        
        self.assertIsNone(result, "Should return None for empty output_text")
        mock_create_method.assert_called_once()

    @patch('backend.utils_openai.client')
    @patch('backend.utils_openai.logging') # Patch logging
    def test_call_openai_responses_api_openai_error(self, mock_logging, mock_openai_client):
        """Test call where OpenAI API raises an error."""
        test_error = openai.APIError("Test API Error", request=None, body=None)
        mock_create_method = MagicMock(side_effect=test_error)
        mock_responses_api = MagicMock()
        mock_responses_api.create = mock_create_method
        mock_openai_client.responses = mock_responses_api
        
        result = utils_openai.call_openai_responses_api(prompt="Test prompt")
        
        self.assertIsNone(result)
        mock_create_method.assert_called_once()
        # Verify that an error was logged
        mock_logging.exception.assert_called_once()
        self.assertIn("OpenAI API error", mock_logging.exception.call_args[0][0])

    @patch('backend.utils_openai.client')
    @patch('backend.utils_openai.logging') # Patch logging
    def test_call_openai_responses_api_unexpected_error(self, mock_logging, mock_openai_client):
        """Test call where an unexpected error occurs."""
        test_error = Exception("Unexpected failure")
        mock_create_method = MagicMock(side_effect=test_error)
        mock_responses_api = MagicMock()
        mock_responses_api.create = mock_create_method
        mock_openai_client.responses = mock_responses_api
        
        result = utils_openai.call_openai_responses_api(prompt="Test prompt")
        
        self.assertIsNone(result)
        mock_create_method.assert_called_once()
        mock_logging.exception.assert_called_once()
        self.assertIn("Unexpected error", mock_logging.exception.call_args[0][0])

    # Add more tests? (e.g., different parameters, model selection)

if __name__ == '__main__':
    unittest.main() 