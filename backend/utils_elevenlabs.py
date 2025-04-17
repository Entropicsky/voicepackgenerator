# backend/utils_elevenlabs.py
import os
import requests
import time
from typing import List, Dict, Any, Optional

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
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

def get_available_voices() -> List[Dict[str, Any]]:
    """Fetches the list of available voices from the ElevenLabs API."""
    url = f"{ELEVENLABS_API_URL}/voices"
    try:
        response = requests.get(url, headers=get_headers())
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        voices_data = response.json()
        return voices_data.get('voices', [])
    except requests.exceptions.RequestException as e:
        raise ElevenLabsError(f"Error fetching voices from ElevenLabs API: {e}") from e
    except Exception as e:
        raise ElevenLabsError(f"An unexpected error occurred while fetching voices: {e}") from e

def generate_tts_audio(
    text: str,
    voice_id: str,
    output_path: str,
    stability: Optional[float] = None,
    similarity_boost: Optional[float] = None,
    style: Optional[float] = None,
    speed: Optional[float] = None,
    use_speaker_boost: Optional[bool] = None,
    model_id: str = DEFAULT_MODEL,
    output_format: str = 'mp3_44100_128',
    retries: int = 3,
    delay: int = 5
) -> None:
    """Generates TTS audio using ElevenLabs API and saves it to output_path."""
    url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}"
    params = {'output_format': output_format}
    payload = {
        'text': text,
        'model_id': model_id,
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