import pytest
import uuid
from backend import utils_r2
import os
import time # Import time for potential delays if needed

# Check if R2 credentials are actually set, otherwise skip
# (Prevents accidental runs without config)
R2_CONFIGURED = all([
    os.getenv("R2_ENDPOINT_URL"),
    os.getenv("R2_ACCESS_KEY_ID"),
    os.getenv("R2_SECRET_ACCESS_KEY"),
    os.getenv("R2_BUCKET_NAME")
])

# Skip all tests in this module if R2 is not configured
# Also apply the 'integration' marker
pytestmark = [
    pytest.mark.skipif(not R2_CONFIGURED, reason="Real R2 credentials not configured in environment"),
    pytest.mark.integration  # Apply the integration marker
]


@pytest.mark.integration # Explicitly mark the test function as well
def test_r2_upload_download_delete_cycle():
    """
    Tests a full upload, download, verify, and delete cycle against the actual R2 bucket.
    Requires real R2 credentials in the environment.
    """
    # Reload utils_r2 to ensure it picks up real env vars if pytest has caching issues or mocks were used elsewhere
    # Using a fixture might be cleaner long term, but reload works for now.
    import importlib
    try:
        importlib.reload(utils_r2)
    except Exception as e:
        pytest.fail(f"Failed to reload utils_r2 module: {e}")


    test_blob_key = f"integration_test_{uuid.uuid4()}.txt"
    test_data = f"Test data for integration {uuid.uuid4()}".encode('utf-8')
    content_type = "text/plain"

    # --- Ensure client can be created ---
    client = utils_r2.get_r2_client()
    assert client is not None, "Failed to create R2 client with real credentials"
    print(f"R2 Client created successfully for bucket: {utils_r2.R2_BUCKET_NAME}") # Add print for clarity

    # --- Test Upload ---
    print(f"Attempting to upload {test_blob_key}...")
    upload_success = utils_r2.upload_blob(test_blob_key, test_data, content_type)
    assert upload_success, f"Failed to upload test blob {test_blob_key}"
    print(f"Upload successful.")
    # Optional: Brief pause for potential R2 eventual consistency, though usually fast
    # time.sleep(1)

    # --- Test Download ---
    print(f"Attempting to download {test_blob_key}...")
    downloaded_data = utils_r2.download_blob_to_memory(test_blob_key)
    assert downloaded_data is not None, f"Failed to download test blob {test_blob_key}"
    assert downloaded_data == test_data, "Downloaded data does not match uploaded data"
    print(f"Download successful and data verified.")

    # --- Test Delete ---
    print(f"Attempting to delete {test_blob_key}...")
    delete_success = utils_r2.delete_blob(test_blob_key)
    assert delete_success, f"Failed to delete test blob {test_blob_key}"
    print(f"Delete successful.")
    # Optional: Brief pause
    # time.sleep(1)

    # --- Verify Deletion ---
    print(f"Verifying deletion of {test_blob_key}...")
    # Reload again before checking existence to ensure fresh client/config if needed
    # importlib.reload(utils_r2)
    exists_after_delete = utils_r2.blob_exists(test_blob_key)
    assert not exists_after_delete, f"Test blob {test_blob_key} still exists after deletion"
    print(f"Deletion verified.")

# Add more integration tests as needed, e.g., for list_blobs_in_prefix, generate_presigned_url 