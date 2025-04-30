# backend/utils_openai.py
# This file will contain reusable logic for interacting with the OpenAI API,
# specifically using the Responses API for synchronous refinements.

import os
import logging
import openai
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load the OpenAI API key from environment variables
# Note: Ensure OPENAI_API_KEY is set in your .env file or environment
client = openai.OpenAI()

# Use OPENAI_AGENT_MODEL from environment variables with fallback to gpt-4o
DEFAULT_REFINEMENT_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-4o")
DEFAULT_MAX_TOKENS = 4096 # Updated based on GPT-4o max output limit
DEFAULT_TEMPERATURE = 0.7 # Default for creative tasks

# Define which OpenAI exceptions should trigger a retry
RETRYABLE_EXCEPTIONS = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    # Retry on 5xx errors as well, might be temporary server issues
    lambda e: isinstance(e, openai.APIStatusError) and e.status_code >= 500 
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10), # Wait 2s, 4s, ... up to 10s between retries
    retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS)
)
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
        # FIX: Explicitly check for None and apply default INSIDE the function
        actual_model_to_use = model if model is not None else DEFAULT_REFINEMENT_MODEL
        # Ensure we didn't somehow still end up with None or empty string
        if not actual_model_to_use:
             actual_model_to_use = "gpt-4o" # Final fallback
             logging.warning(f"Model was None or empty even after default logic, falling back to gpt-4o")
             
        logging.info(f"Calling OpenAI Responses API with model: {actual_model_to_use}, max_tokens: {max_tokens}, temp: {temperature}")
        # Use the client initialized at the module level
        response = client.responses.create(
            model=actual_model_to_use,
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

    except openai.APIStatusError as e:
        # Log specific non-retried API errors (like 4xx)
        logging.error(f"OpenAI APIStatusError: Status={e.status_code}, Message={e.message}")
        return None
    except Exception as e:
        # Catch other unexpected errors during the API call 
        logging.exception(f"Unexpected error calling OpenAI API: {e}")
        # Ensure non-retried exceptions are re-raised if retry decorator doesn't handle them
        # or return None if we want to treat all other errors as failures
        return None 