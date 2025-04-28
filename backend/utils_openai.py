# backend/utils_openai.py
# This file will contain reusable logic for interacting with the OpenAI API,
# specifically using the Responses API for synchronous refinements.

import os
import logging
import openai
from typing import Optional

# Load the OpenAI API key from environment variables
# Note: Ensure OPENAI_API_KEY is set in your .env file or environment
client = openai.OpenAI()

DEFAULT_REFINEMENT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = 4096 # Updated based on GPT-4o max output limit
DEFAULT_TEMPERATURE = 0.7 # Default for creative tasks

# TODO: Implement call_openai_responses_api function and unit tests
def call_openai_responses_api(
    prompt: str,
    model: str = DEFAULT_REFINEMENT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    **kwargs # Allow passing other parameters like top_p etc.
) -> Optional[str]:
    """Calls the OpenAI Responses API with the given prompt and parameters.

    Args:
        prompt: The input prompt string for the model.
        model: The OpenAI model to use (e.g., 'gpt-4o').
        max_tokens: The maximum number of tokens to generate.
        temperature: The sampling temperature.
        **kwargs: Additional parameters for the OpenAI API create call.

    Returns:
        The generated text content (output_text) if successful and non-empty,
        otherwise None.
    """
    try:
        logging.info(f"Calling OpenAI Responses API with model: {model}, max_tokens: {max_tokens}, temp: {temperature}")
        # Use the client initialized at the module level
        response = client.responses.create(
            model=model,
            input=prompt, # Direct string input
            max_output_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
        
        output_text = response.output_text
        if output_text:
            logging.info(f"OpenAI API call successful. Output length: {len(output_text)}")
            return output_text.strip()
        else:
            logging.warning("OpenAI API call returned empty output_text.")
            return None

    except openai.APIError as e:
        logging.exception(f"OpenAI API error occurred: {e}")
        return None
    except Exception as e:
        logging.exception(f"Unexpected error during OpenAI API call: {e}")
        return None 