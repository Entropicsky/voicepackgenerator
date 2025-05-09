# backend/utils_openai.py
# This file will contain reusable logic for interacting with the OpenAI API,
# specifically using the Responses API for synchronous refinements.

import os
import logging
import openai
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import base64
import httpx # For potential direct image URL fetching if ever needed

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

# NEW function for image description
def get_image_description(image_base64_data: str, model_name: str) -> Optional[str]:
    """
    Sends an image (as base64 data URL) to the specified OpenAI model and returns its description.
    Example base64_data_url: "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD//gA7..."
    """
    logger.info(f"Attempting to get image description using model: {model_name}")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not set for image description.")
        return None

    try:
        client = openai.OpenAI(api_key=api_key)
        
        # The vision model expects image content in a specific format.
        # For base64 data URLs, we need to extract the actual base64 part.
        # Example format for API: 
        # {
        #   "type": "image_url",
        #   "image_url": {
        #     "url": "data:image/jpeg;base64,{base64_image}"
        #   }
        # }
        
        # Ensure the input is a valid data URL before attempting to send
        if not image_base64_data.startswith("data:image/") or ";base64," not in image_base64_data:
            logger.error(f"Invalid base64 data URL format: {image_base64_data[:100]}...")
            return "Error: Invalid image data format provided."

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in detail. Focus on elements that would be relevant for a character description in a video game script, such as appearance, attire, expression, and any notable items or environment details that might inform persona."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_base64_data,
                        },
                    },
                ],
            }
        ]

        logger.debug(f"Sending image to OpenAI model {model_name} for description.")
        
        # Using the chat completions endpoint as it supports vision for gpt-4o
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=500 # Limit response length for descriptions
        )
        
        if response.choices and response.choices[0].message and response.choices[0].message.content:
            description = response.choices[0].message.content.strip()
            logger.info(f"Successfully received image description (len: {len(description)}). Start: {description[:100]}...")
            return description
        else:
            logger.error(f"No content in OpenAI response for image description. Response: {response}")
            return "No description generated by the AI."

    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API request failed to connect during image description: {e}")
        return "Error: Failed to connect to image analysis service."
    except openai.RateLimitError as e:
        logger.error(f"OpenAI API request hit rate limit during image description: {e}")
        return "Error: Image analysis service rate limit exceeded."
    except openai.APIStatusError as e:
        logger.error(f"OpenAI API returned an error status during image description: {e.status_code} - {e.response}")
        return f"Error from image analysis service: {e.message}"
    except Exception as e:
        logger.exception(f"Unexpected error calling OpenAI for image description: {e}")
        return "Error: An unexpected error occurred during image analysis." 