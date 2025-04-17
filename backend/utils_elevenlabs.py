# backend/utils_elevenlabs.py
import os
import requests
import time
from typing import List, Dict, Any, Optional

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
    page_size: int = 100, # Get more voices by default
    next_page_token: Optional[str] = None
) -> List[Dict[str, Any]]: # Might return more info with V2
    """Fetches voices from the V2 API with filtering and sorting."""
    url = f"{ELEVENLABS_API_V2_URL}/voices"
    params: Dict[str, Any] = {
        'page_size': page_size,
        'include_total_count': False # Don't need total count for now
    }
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
        print(f"Fetching voices with params: {params}") # Debugging
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        voices_data = response.json()
        # V2 response structure might be different, check API docs if needed
        # Assuming it still has a 'voices' key
        return voices_data.get('voices', [])
    except requests.exceptions.RequestException as e:
        raise ElevenLabsError(f"Error fetching V2 voices from ElevenLabs API: {e}") from e
    except Exception as e:
        raise ElevenLabsError(f"An unexpected error occurred while fetching V2 voices: {e}") from e

def generate_tts_audio(
    text: str,
    voice_id: str,
    output_path: str,
    stability: Optional[float] = None,
    similarity_boost: Optional[float] = None,
    style: Optional[float] = None,
    speed: Optional[float] = None,
    use_speaker_boost: Optional[bool] = None,
    model_id: str = "eleven_monolingual_v1", # Use V1 default model
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