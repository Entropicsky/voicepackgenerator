# backend/tests/test_utils_elevenlabs.py
import pytest
import os
import requests
from unittest import mock
from .. import utils_elevenlabs

# --- Mocks ---

# Mock successful requests.get for voices
@mock.patch('requests.get')
def test_get_available_voices_success(mock_get):
    """Test successful fetching of voices."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'voices': [
            {'voice_id': 'id1', 'name': 'Voice One'},
            {'voice_id': 'id2', 'name': 'Voice Two'}
        ]
    }
    mock_get.return_value = mock_response

    # Mock os.getenv to return a dummy API key
    with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake_key'}):
        voices = utils_elevenlabs.get_available_voices()

    assert len(voices) == 2
    assert voices[0]['name'] == 'Voice One'
    mock_get.assert_called_once_with(
        f"{utils_elevenlabs.ELEVENLABS_API_URL}/voices",
        headers={'xi-api-key': 'fake_key', 'Content-Type': 'application/json'}
    )

# Mock requests.get raising an exception
@mock.patch('requests.get')
def test_get_available_voices_request_error(mock_get):
    """Test error during voice fetching."""
    mock_get.side_effect = requests.exceptions.RequestException("Connection error")

    with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake_key'}):
        with pytest.raises(utils_elevenlabs.ElevenLabsError, match="Error fetching voices"):
            utils_elevenlabs.get_available_voices()

# Test case where API key is missing
def test_get_available_voices_no_api_key():
    """Test missing API key raises error."""
    # Ensure API key is not in env for this test
    with mock.patch.dict(os.environ, {}, clear=True):
         with pytest.raises(utils_elevenlabs.ElevenLabsError, match="ELEVENLABS_API_KEY environment variable not set"):
            utils_elevenlabs.get_available_voices()

# Mock successful requests.post for TTS generation
@mock.patch('requests.post')
@mock.patch('builtins.open', new_callable=mock.mock_open)
@mock.patch('os.makedirs')
def test_generate_tts_audio_success(mock_makedirs, mock_open_file, mock_post):
    """Test successful TTS audio generation and saving."""
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.content = b'fake_audio_data'
    mock_post.return_value = mock_response

    output_file = "/fake/output/test.mp3"

    with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake_key'}):
        utils_elevenlabs.generate_tts_audio(
            text="Hello world",
            voice_id="voice1",
            output_path=output_file,
            stability=0.5,
            similarity_boost=0.75
        )

    # Check requests.post call arguments
    expected_url = f"{utils_elevenlabs.ELEVENLABS_API_URL}/text-to-speech/voice1"
    expected_params = {'output_format': 'mp3_44100_128'}
    expected_payload = {
        'text': 'Hello world',
        'model_id': utils_elevenlabs.DEFAULT_MODEL,
        'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75}
    }
    mock_post.assert_called_once_with(
        expected_url,
        headers={'xi-api-key': 'fake_key', 'Content-Type': 'application/json'},
        params=expected_params,
        json=expected_payload
    )

    # Check os.makedirs call
    mock_makedirs.assert_called_once_with(os.path.dirname(output_file), exist_ok=True)

    # Check file write call
    mock_open_file.assert_called_once_with(output_file, 'wb')
    mock_open_file().write.assert_called_once_with(b'fake_audio_data')


# Mock requests.post raising an exception
@mock.patch('requests.post')
def test_generate_tts_audio_failure(mock_post):
    """Test failure during TTS generation after retries."""
    mock_post.side_effect = requests.exceptions.RequestException("API Error")

    with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake_key'}):
        with pytest.raises(utils_elevenlabs.ElevenLabsError, match="Failed to generate TTS after 3 attempts"):
            utils_elevenlabs.generate_tts_audio(
                text="Test fail",
                voice_id="voice_fail",
                output_path="/fake/fail.mp3",
                retries=3 # Explicitly set retries for clarity
            )
    assert mock_post.call_count == 3 # Check retries happened

# Test rate limiting retry
@mock.patch('requests.post')
@mock.patch('time.sleep') # Mock time.sleep to avoid actual delay
@mock.patch('builtins.open', new_callable=mock.mock_open)
@mock.patch('os.makedirs')
def test_generate_tts_audio_rate_limit_retry(mock_makedirs, mock_open_file, mock_sleep, mock_post):
    """Test that rate limiting (429) triggers a retry."""
    mock_rate_limit_response = mock.Mock()
    mock_rate_limit_response.status_code = 429

    mock_success_response = mock.Mock()
    mock_success_response.status_code = 200
    mock_success_response.content = b'audio_after_retry'

    # Simulate 429 on first call, 200 on second
    mock_post.side_effect = [mock_rate_limit_response, mock_success_response]

    output_file = "/fake/retry.mp3"
    with mock.patch.dict(os.environ, {'ELEVENLABS_API_KEY': 'fake_key'}):
        utils_elevenlabs.generate_tts_audio(
            text="Retry test",
            voice_id="voice_retry",
            output_path=output_file,
            retries=3,
            delay=5
        )

    assert mock_post.call_count == 2 # Called twice (initial fail, successful retry)
    mock_sleep.assert_called_once_with(5) # Check sleep was called with correct delay
    mock_open_file.assert_called_once_with(output_file, 'wb')
    mock_open_file().write.assert_called_once_with(b'audio_after_retry') 