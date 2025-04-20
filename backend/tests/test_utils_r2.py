import pytest
from unittest.mock import patch, MagicMock
import botocore

# Import the module to test
from backend import utils_r2

# Define standard args for mocking
BUCKET_NAME = "test-bucket"
ENDPOINT_URL = "https://fake-account-id.r2.cloudflarestorage.com"
ACCESS_KEY = "test-access-key"
SECRET_KEY = "test-secret-key"

# Fixture to automatically mock environment variables and the boto3 client for each test
@pytest.fixture(autouse=True)
def mock_env_and_boto(mocker):
    # Mock environment variables
    mocker.patch.dict(utils_r2.os.environ, {
        "R2_BUCKET_NAME": BUCKET_NAME,
        "R2_ENDPOINT_URL": ENDPOINT_URL,
        "R2_ACCESS_KEY_ID": ACCESS_KEY,
        "R2_SECRET_ACCESS_KEY": SECRET_KEY
    })

    # Mock the boto3 session and client
    mock_s3_client = MagicMock()
    mock_session = MagicMock()
    mock_session.client.return_value = mock_s3_client
    mocker.patch('backend.utils_r2.boto3.session.Session', return_value=mock_session)

    # Make the mock client accessible to tests if needed, though often we check calls via the fixture's patch
    # You could also return mock_s3_client here if preferred
    utils_r2.s3_client_instance = mock_s3_client # Add instance for direct access in tests if needed

    return mock_s3_client # Return the client mock for direct use in tests

def test_get_r2_client_success(mock_env_and_boto, mocker):
    """Test successful creation of the R2 client."""
    # Reload module to re-evaluate globals with mocked env vars
    # Not strictly necessary here as get_r2_client reads env vars dynamically
    # but good practice if globals were set at import time.
    # import importlib
    # importlib.reload(utils_r2)

    client = utils_r2.get_r2_client()
    assert client is not None
    # Check if boto3.session.Session().client was called correctly
    utils_r2.boto3.session.Session().client.assert_called_once_with(
        service_name='s3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )

def test_get_r2_client_missing_env_var(mocker):
    """Test client creation failure when an environment variable is missing."""
    # Unset one of the required env vars
    mocker.patch.dict(utils_r2.os.environ, {
        "R2_BUCKET_NAME": BUCKET_NAME,
        "R2_ENDPOINT_URL": ENDPOINT_URL,
        "R2_ACCESS_KEY_ID": ACCESS_KEY,
        # R2_SECRET_ACCESS_KEY is missing
    })
    # Reload module to pick up changed env vars if needed (depends on implementation)
    # import importlib
    # importlib.reload(utils_r2)

    client = utils_r2.get_r2_client()
    assert client is None

# === Tests for upload_blob ===

def test_upload_blob_success(mock_env_and_boto):
    """Test successful blob upload."""
    mock_s3_client = mock_env_and_boto # Get the mock client from the fixture
    blob_name = "test/path/file.mp3"
    data = b"audio data"
    content_type = "audio/mpeg"

    result = utils_r2.upload_blob(blob_name, data, content_type)

    assert result is True
    mock_s3_client.put_object.assert_called_once_with(
        Bucket=BUCKET_NAME,
        Key=blob_name,
        Body=data,
        ContentType=content_type
    )

def test_upload_blob_client_error(mock_env_and_boto):
    """Test blob upload failure due to ClientError."""
    mock_s3_client = mock_env_and_boto
    blob_name = "test/path/file.mp3"
    data = b"audio data"
    content_type = "audio/mpeg"

    # Configure the mock put_object to raise ClientError
    mock_s3_client.put_object.side_effect = botocore.exceptions.ClientError(
        error_response={'Error': {'Code': 'SomeError', 'Message': 'Details'}},
        operation_name='PutObject'
    )

    result = utils_r2.upload_blob(blob_name, data, content_type)

    assert result is False
    mock_s3_client.put_object.assert_called_once()

def test_upload_blob_no_client(mocker):
    """Test upload failure if client cannot be created."""
    # Mock get_r2_client to return None
    mocker.patch('backend.utils_r2.get_r2_client', return_value=None)
    result = utils_r2.upload_blob("test.txt", b"data")
    assert result is False


# --- Add tests for other functions (download_blob_to_memory, etc.) below --- 