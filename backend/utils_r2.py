import os
import boto3
import botocore # Import botocore for Config
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

# Configuration - Loaded from environment variables
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME") # Assuming one bucket for now, adjust if needed

def get_r2_client():
    """Creates and returns a boto3 S3 client configured for Cloudflare R2."""
    if not all([R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        logger.error("R2 client config missing.")
        return None

    try:
        session = boto3.session.Session()
        s3_client = session.client(
            service_name='s3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name='auto',  # Explicitly set region for R2
            config=botocore.client.Config(signature_version='s3v4') # Explicitly set signature version
        )
        # Optional: Test connection by listing buckets (requires ListBuckets permission)
        # s3_client.list_buckets()
        logger.info("Successfully created R2 S3 client with region='auto' and signature_version='s3v4'.")
        return s3_client
    except ClientError as e:
        logger.error(f"Failed to create R2 S3 client: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred creating R2 S3 client: {e}")
        return None

# --- Placeholder functions to be implemented ---

def upload_blob(blob_name: str, data: bytes, content_type: str = 'application/octet-stream') -> bool:
    """Uploads data (bytes) to a blob in the configured R2 bucket.

    Args:
        blob_name: The full path (key) for the object in the bucket.
        data: The data to upload as bytes.
        content_type: The MIME type of the content.

    Returns:
        True if upload was successful, False otherwise.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot upload blob: R2 client or bucket name not configured.")
        return False

    try:
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=blob_name,
            Body=data,
            ContentType=content_type
            # Consider adding other parameters like CacheControl if needed
            # CacheControl="public, max-age=31536000" # Example for static assets
        )
        logger.info(f"Successfully uploaded {blob_name} to R2 bucket {R2_BUCKET_NAME}.")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload {blob_name} to R2 bucket {R2_BUCKET_NAME}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during upload of {blob_name}: {e}")
        return False

def download_blob_to_memory(blob_name: str) -> bytes | None:
    """Downloads a blob's content from the R2 bucket into memory.

    Args:
        blob_name: The full path (key) for the object in the bucket.

    Returns:
        The blob content as bytes if successful, None otherwise.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot download blob: R2 client or bucket name not configured.")
        return None

    try:
        response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=blob_name)
        # The body is a streaming body, read it fully into memory
        data = response['Body'].read()
        logger.info(f"Successfully downloaded {blob_name} from R2 bucket {R2_BUCKET_NAME}.")
        return data
    except ClientError as e:
        # Handle specific errors like NoSuchKey (file not found)
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.warning(f"Blob not found in R2 bucket {R2_BUCKET_NAME}: {blob_name}")
        else:
            logger.error(f"Failed to download {blob_name} from R2 bucket {R2_BUCKET_NAME}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during download of {blob_name}: {e}")
        return None

def list_blobs_in_prefix(prefix: str) -> list[dict]:
    """Lists blobs in the R2 bucket matching the given prefix.

    Handles pagination to retrieve all matching objects.

    Args:
        prefix: The prefix (simulated directory path) to filter by.
                Ensure it ends with '/' if listing directory contents.

    Returns:
        A list of dictionaries, where each dictionary represents a blob
        and contains keys like 'Key', 'Size', 'LastModified'. 
        Returns an empty list if no objects match or on error.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot list blobs: R2 client or bucket name not configured.")
        return []

    blobs = []
    paginator = s3_client.get_paginator('list_objects_v2')
    try:
        page_iterator = paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix)
        
        # Iterate through all pages returned by the paginator
        for page in page_iterator:
            # The 'Contents' key is only present if objects are found in that page
            if "Contents" in page:
                for obj in page["Contents"]:
                    blobs.append({
                        'Key': obj['Key'],
                        'Size': obj['Size'],
                        'LastModified': obj['LastModified']
                    })
            # No need to explicitly check for NoSuchKey here, 
            # the paginator handles empty results gracefully.
            
        logger.info(f"Listed {len(blobs)} blobs with prefix '{prefix}' in R2 bucket {R2_BUCKET_NAME}.")
        return blobs
        
    except ClientError as e:
        # Log specific S3/R2 client errors
        error_code = e.response.get('Error', {}).get('Code')
        logger.error(f"Failed to list blobs with prefix '{prefix}' in R2 bucket {R2_BUCKET_NAME}. Error code: {error_code}, Message: {e}")
        return [] # Return empty list on client error
    except Exception as e:
        # Log unexpected errors
        logger.exception(f"An unexpected error occurred listing blobs with prefix '{prefix}': {e}")
        return [] # Return empty list on unexpected error

def blob_exists(blob_name: str) -> bool:
    """Checks if a blob exists in the R2 bucket using head_object.

    Args:
        blob_name: The full path (key) for the object in the bucket.

    Returns:
        True if the blob exists, False otherwise.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot check blob existence: R2 client or bucket name not configured.")
        return False

    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=blob_name)
        # If head_object succeeds without error, the object exists
        logger.debug(f"Blob exists: {blob_name} in R2 bucket {R2_BUCKET_NAME}.")
        return True
    except ClientError as e:
        # If the error code is 404 (Not Found) or NoSuchKey, the blob doesn't exist.
        # R2 might return 404, standard S3 often uses NoSuchKey.
        error_code = e.response.get('Error', {}).get('Code')
        response_status = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        if error_code == 'NoSuchKey' or response_status == 404:
            logger.debug(f"Blob does not exist: {blob_name} in R2 bucket {R2_BUCKET_NAME}.")
            return False
        else:
            # Log other client errors
            logger.error(f"Error checking existence for {blob_name} in R2 bucket {R2_BUCKET_NAME}: {e}")
            return False # Treat other errors as indication of non-existence or access issue
    except Exception as e:
        logger.error(f"An unexpected error occurred checking existence for {blob_name}: {e}")
        return False

def delete_blob(blob_name: str) -> bool:
    """Deletes a blob from the R2 bucket.

    Args:
        blob_name: The full path (key) for the object in the bucket.

    Returns:
        True if deletion was successful or the object didn't exist,
        False otherwise.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot delete blob: R2 client or bucket name not configured.")
        return False

    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=blob_name)
        # delete_object doesn't typically raise an error if the object doesn't exist,
        # so success means the object is gone (either deleted or never existed).
        logger.info(f"Successfully deleted (or confirmed non-existent) {blob_name} from R2 bucket {R2_BUCKET_NAME}.")
        return True
    except ClientError as e:
        logger.error(f"Failed to delete {blob_name} from R2 bucket {R2_BUCKET_NAME}: {e}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during deletion of {blob_name}: {e}")
        return False

def generate_presigned_url(blob_name: str, expiration: int = 3600) -> str | None:
    """Generates a presigned URL for temporary GET access to a blob.

    Args:
        blob_name: The full path (key) for the object in the bucket.
        expiration: Time in seconds for the presigned URL to remain valid (default 1 hour).

    Returns:
        The presigned URL string if successful, None otherwise.
    """
    s3_client = get_r2_client()
    if not s3_client or not R2_BUCKET_NAME:
        logger.error("Cannot generate presigned URL: R2 client or bucket name not configured.")
        return None

    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': blob_name},
            ExpiresIn=expiration
            # HttpMethod='GET' # GET is the default
        )
        logger.info(f"Generated presigned URL for {blob_name} (expires in {expiration}s)." )
        return url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {blob_name}: {e}")
        # Could check if the object exists first if needed, but often not required
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred generating presigned URL for {blob_name}: {e}")
        return None 