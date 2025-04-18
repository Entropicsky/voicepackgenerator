# backend/utils_elevenlabs.py
import os
import requests
import time
import json
from typing import List, Dict, Any, Optional, Tuple

# Use V2 endpoint base FOR /voices, but keep V1 for TTS
ELEVENLABS_API_V2_URL = "https://api.elevenlabs.io/v2"
ELEVENLABS_API_V1_URL = "https://api.elevenlabs.io/v1" # Define V1 URL
DEFAULT_MODEL = "eleven_multilingual_v2" # Or use a specific model if needed

class ElevenLabsError(Exception):
    """Custom exception for ElevenLabs API errors."""
    pass

def get_api_key() -> str:
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        raise ElevenLabsError("ELEVENLABS_API_KEY environment variable not set.")
    return api_key

def get_headers() -> Dict[str, str]:
    return {
        'xi-api-key': get_api_key(),
        'Content-Type': 'application/json'
    }

def get_available_voices(
    search: Optional[str] = None,
    category: Optional[str] = None, # premade, cloned, generated, professional
    voice_type: Optional[str] = None, # personal, community, default, workspace
    sort: Optional[str] = None, # created_at_unix, name
    sort_direction: Optional[str] = None, # asc, desc
    # Remove page_size parameter from function signature (will use API default)
    # page_size: int = 100, 
    next_page_token: Optional[str] = None
) -> List[Dict[str, Any]]: # Might return more info with V2
    """Fetches voices from the V2 API with filtering and sorting."""
    url = f"{ELEVENLABS_API_V2_URL}/voices"
    # Start with an empty params dict
    params: Dict[str, Any] = {}
    # Conditionally add parameters if they are provided
    # if page_size:
    #     params['page_size'] = page_size # Don't send page_size
    if search:
        params['search'] = search
    if category:
        params['category'] = category
    if voice_type:
        params['voice_type'] = voice_type
    if sort:
        params['sort'] = sort
    if sort_direction:
        params['sort_direction'] = sort_direction
    if next_page_token:
        params['next_page_token'] = next_page_token

    try:
        # Only include params in the request if the dictionary is not empty
        request_args = {"headers": get_headers()}
        if params:
            request_args["params"] = params
            
        print(f"Fetching voices with request_args: {request_args}") # Debugging
        response = requests.get(url, **request_args)
        response.raise_for_status()
        voices_data = response.json()
        # V2 response structure might be different, check API docs if needed
        # Assuming it still has a 'voices' key
        return voices_data.get('voices', [])
    except requests.exceptions.RequestException as e:
        raise ElevenLabsError(f"Error fetching V2 voices from ElevenLabs API: {e}") from e
    except Exception as e:
        raise ElevenLabsError(f"An unexpected error occurred while fetching V2 voices: {e}") from e

def get_available_models(require_sts: bool = False) -> List[Dict[str, Any]]:
    """Fetches available models, optionally filtering for STS capability."""
    url = f"{ELEVENLABS_API_V1_URL}/models"
    print(f"Fetching models from {url}. Require STS: {require_sts}")
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        all_models = response.json()
        print(f"Received {len(all_models)} models from API.")
        
        filtered_models = []
        for model in all_models:
            model_id = model.get('model_id')
            model_name = model.get('name')
            can_tts = model.get('can_do_text_to_speech', False)
            can_sts = model.get('can_do_voice_conversion', False) 
            requires_alpha = model.get('requires_alpha_access', False)
            
            # Log details for each model
            print(f"  - Model: {model_name} ({model_id}) | TTS: {can_tts} | STS: {can_sts} | Alpha: {requires_alpha}")
            
            if not model_id or not model_name or requires_alpha:
                continue
            
            if require_sts:
                if can_sts:
                    print(f"    -> Including STS model: {model_name}")
                    filtered_models.append(model)
                # else: 
                #     print(f"    -> Excluding non-STS model: {model_name}")
            else: # require TTS
                if can_tts:
                    print(f"    -> Including TTS model: {model_name}")
                    filtered_models.append(model)
                # else:
                #     print(f"    -> Excluding non-TTS model: {model_name}")
                    
        print(f"Returning {len(filtered_models)} filtered models.")
        return filtered_models
    except requests.exceptions.RequestException as e:
        raise ElevenLabsError(f"Error fetching models from ElevenLabs API: {e}") from e
    except Exception as e:
        raise ElevenLabsError(f"An unexpected error occurred while fetching models: {e}") from e

def run_speech_to_speech_conversion(
    audio_data: bytes, 
    target_voice_id: str, 
    model_id: Optional[str], 
    voice_settings: Optional[dict],
    retries: int = 2, # Fewer retries for STS?
    delay: int = 5
) -> bytes:
    """Performs Speech-to-Speech using the V1 API."""
    # Default STS model if not provided
    sts_model_id = model_id or "eleven_multilingual_sts_v2" 
    
    url = f"{ELEVENLABS_API_V1_URL}/speech-to-speech/{target_voice_id}"
    headers = {'xi-api-key': get_api_key()} # No Content-Type needed for multipart
    
    files = {'audio': ('source_audio.wav', audio_data, 'audio/wav')} # Assuming WAV, adjust if needed
    data: Dict[str, Any] = {'model_id': sts_model_id}
    if voice_settings:
        # STS settings need to be JSON string according to docs
        data['voice_settings'] = json.dumps(voice_settings)

    attempt = 0
    while attempt < retries:
        try:
            print(f"Attempt {attempt + 1}/{retries}: Running STS for target voice {target_voice_id}...")
            response = requests.post(url, headers=headers, data=data, files=files)

            if response.status_code == 200:
                print(f"Successfully ran STS for target voice {target_voice_id}")
                return response.content # Return audio bytes
            elif response.status_code == 429:
                print(f"Rate limit hit during STS. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                response.raise_for_status() # Raise for other errors

        except requests.exceptions.RequestException as e:
            print(f"Error during STS (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                 raise ElevenLabsError(f"Failed STS after {retries} attempts: {e}") from e
        except Exception as e:
             raise ElevenLabsError(f"An unexpected error occurred during STS: {e}") from e

        attempt += 1

    raise ElevenLabsError(f"Failed STS for target voice {target_voice_id} after {retries} attempts.")

def generate_tts_audio(
    text: str,
    voice_id: str,
    output_path: str,
    stability: Optional[float] = None,
    similarity_boost: Optional[float] = None,
    style: Optional[float] = None,
    speed: Optional[float] = None,
    use_speaker_boost: Optional[bool] = None,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = 'mp3_44100_128',
    retries: int = 3,
    delay: int = 5
) -> None:
    """Generates TTS audio using V1 API and saves it to output_path."""
    # Explicitly use V1 URL
    url = f"{ELEVENLABS_API_V1_URL}/text-to-speech/{voice_id}" 
    params = {'output_format': output_format}
    payload = {
        'text': text,
        'model_id': model_id, # Ensure compatible model for V1
        'voice_settings': {}
    }

    # Add settings only if they are provided (not None)
    if stability is not None:
        payload['voice_settings']['stability'] = stability
    if similarity_boost is not None:
        payload['voice_settings']['similarity_boost'] = similarity_boost
    if style is not None:
        payload['voice_settings']['style'] = style
    if speed is not None:
        payload['voice_settings']['speed'] = speed
    if use_speaker_boost is not None:
        payload['voice_settings']['use_speaker_boost'] = use_speaker_boost

    # Remove voice_settings if empty
    if not payload['voice_settings']:
        del payload['voice_settings']

    attempt = 0
    while attempt < retries:
        try:
            print(f"Attempt {attempt + 1}/{retries}: Generating TTS for voice {voice_id}...")
            response = requests.post(url, headers=get_headers(), params=params, json=payload)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as audio_f:
                    audio_f.write(response.content)
                print(f"Successfully saved audio to {output_path}")
                return # Success, exit function
            elif response.status_code == 429: # Rate limit
                print(f"Rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                # Raise error for other client/server errors
                response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Error generating TTS (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                 raise ElevenLabsError(f"Failed to generate TTS after {retries} attempts: {e}") from e
        except Exception as e:
             raise ElevenLabsError(f"An unexpected error occurred during TTS generation: {e}") from e

        attempt += 1
        # Optional: Increase delay for subsequent retries?
        # delay *= 2

    # If loop finishes without returning, all retries failed
    raise ElevenLabsError(f"Failed to generate TTS for voice {voice_id} after {retries} attempts.")

# --- NEW: Voice Design Functions (V1 API) --- #

def create_voice_previews(
    voice_description: str,
    text: Optional[str] = None,
    auto_generate_text: bool = False,
    loudness: Optional[float] = None,
    quality: Optional[float] = None,
    seed: Optional[int] = None,
    guidance_scale: Optional[float] = None,
    output_format: str = 'mp3_44100_128',
    retries: int = 2,
    delay: int = 5
) -> Tuple[List[Dict[str, Any]], str]:
    """Generates voice previews using the V1 Voice Design endpoint.

    Args:
        voice_description: Text description of the desired voice.
        text: Optional text to generate audio previews (100-1000 chars).
        auto_generate_text: If True, ignores 'text' and generates sample text.
        loudness: Volume control (-1 to 1).
        quality: Quality vs variety (-1 to 1).
        seed: Randomization seed.
        guidance_scale: How closely to follow the prompt (0-100).
        output_format: Desired audio output format.
        retries: Number of retry attempts for transient errors.
        delay: Delay between retries in seconds.

    Returns:
        A tuple containing: 
          - List of preview objects (each with 'audio_base_64', 'generated_voice_id', etc.).
          - The text used for generation (either provided or auto-generated).
        
    Raises:
        ElevenLabsError: If the API call fails after retries.
    """
    url = f"{ELEVENLABS_API_V1_URL}/text-to-voice/create-previews"
    params = {'output_format': output_format}
    payload: Dict[str, Any] = {
        'voice_description': voice_description,
        'auto_generate_text': auto_generate_text
    }
    if not auto_generate_text and text:
        payload['text'] = text
    if loudness is not None:
        payload['loudness'] = loudness
    if quality is not None:
        payload['quality'] = quality
    if seed is not None:
        payload['seed'] = seed
    if guidance_scale is not None:
        payload['guidance_scale'] = guidance_scale
        
    # Basic validation (could be more thorough)
    if auto_generate_text and text:
        print("Warning: 'text' provided but 'auto_generate_text' is True. Text will be ignored.")
    if not auto_generate_text and not text:
        raise ValueError("Either 'text' must be provided or 'auto_generate_text' must be True.")
    if text and not (100 <= len(text) <= 1000):
        raise ValueError("Preview text must be between 100 and 1000 characters.")
    if not (20 <= len(voice_description) <= 1000):
         raise ValueError("Voice description must be between 20 and 1000 characters.")

    attempt = 0
    while attempt < retries:
        try:
            print(f"Attempt {attempt + 1}/{retries}: Creating voice previews...")
            response = requests.post(url, headers=get_headers(), params=params, json=payload)

            if response.status_code == 200:
                print("Successfully created voice previews.")
                result = response.json()
                previews = result.get('previews', [])
                generated_text = result.get('text', 'Error: Text not returned')
                return previews, generated_text
            elif response.status_code == 429: # Rate limit
                print(f"Rate limit hit during preview creation. Retrying in {delay} seconds...")
                time.sleep(delay)
            elif response.status_code == 422: # Validation error
                 print(f"Validation Error (422) creating previews: {response.text}")
                 raise ElevenLabsError(f"Validation failed: {response.json().get('detail', response.text)}")
            else:
                response.raise_for_status() # Raise for other client/server errors

        except requests.exceptions.RequestException as e:
            print(f"Error creating previews (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                 raise ElevenLabsError(f"Failed to create previews after {retries} attempts: {e}") from e
        except Exception as e:
            # Catch other exceptions like potential JSON decode errors or ValueErrors
            print(f"Unexpected error creating previews (attempt {attempt+1}): {e}")
            if attempt == retries -1:
                raise ElevenLabsError(f"Failed to create previews after {retries} attempts due to unexpected error: {e}") from e

        attempt += 1

    raise ElevenLabsError(f"Failed to create voice previews after {retries} attempts.")

def save_generated_voice(
    generated_voice_id: str,
    voice_name: str,
    voice_description: str,
    labels: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Saves a generated voice preview to the user's voice library.

    Args:
        generated_voice_id: The ID of the preview to save (from create_voice_previews).
        voice_name: The desired name for the new voice.
        voice_description: The description associated with the voice (should match preview).
        labels: Optional dictionary of labels for the voice.

    Returns:
        A dictionary containing the details of the newly saved voice (e.g., final voice_id).

    Raises:
        ElevenLabsError: If the API call fails.
    """
    url = f"{ELEVENLABS_API_V1_URL}/text-to-voice/create-voice-from-preview"
    payload: Dict[str, Any] = {
        'generated_voice_id': generated_voice_id,
        'voice_name': voice_name,
        'voice_description': voice_description
    }
    if labels:
        payload['labels'] = labels
        
    # Basic validation
    if not (20 <= len(voice_description) <= 1000):
         raise ValueError("Voice description must be between 20 and 1000 characters.")

    try:
        print(f"Saving generated voice preview ID: {generated_voice_id} as '{voice_name}'...")
        response = requests.post(url, headers=get_headers(), json=payload)

        if response.status_code == 200:
            print(f"Successfully saved voice '{voice_name}'.")
            return response.json()
        elif response.status_code == 422:
            print(f"Validation Error (422) saving voice: {response.text}")
            raise ElevenLabsError(f"Validation failed saving voice: {response.json().get('detail', response.text)}")
        else:
            response.raise_for_status()
            
    except requests.exceptions.RequestException as e:
        print(f"Error saving generated voice: {e}")
        raise ElevenLabsError(f"Failed to save generated voice: {e}") from e
    except Exception as e:
        print(f"Unexpected error saving generated voice: {e}")
        raise ElevenLabsError(f"An unexpected error occurred while saving the voice: {e}") from e
        
    # Should not be reached if raise_for_status works correctly, but needed for type checking
    raise ElevenLabsError("Failed to save generated voice for an unknown reason.") 