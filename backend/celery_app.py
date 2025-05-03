# backend/celery_app.py
# Option B: Smart Redis TLS URL selection - REVISED
from celery import Celery
import os
import ssl

# Determine raw Redis URL (prioritize TLS, then plain, then generic broker, then default)
redis_tls_url = os.environ.get('REDIS_TLS_URL')
redis_url = os.environ.get('REDIS_URL')
celery_broker_url = os.getenv('CELERY_BROKER_URL')
default_url = 'redis://redis:6379/0' # Default for local Docker

# Select the URL based on priority
broker_url = redis_tls_url or redis_url or celery_broker_url or default_url

# Configure SSL context *only* if the final determined URL uses the 'rediss://' scheme
ssl_opts = {}
if broker_url.startswith('rediss://'):
    # Reverting to dictionary approach, using CERT_NONE for now to ensure connection.
    # Security Warning: CERT_NONE is vulnerable to MITM attacks.
    ssl_opts = {'ssl_cert_reqs': ssl.CERT_NONE}
    # If connection works, consider trying CERT_REQUIRED with CA certs:
    # ssl_opts = {
    #     'ssl_cert_reqs': ssl.CERT_REQUIRED,
    #     'ssl_ca_certs': '/etc/ssl/certs/ca-certificates.crt'
    # }

# Note: No longer appending to broker_url string
result_backend = broker_url

# Instantiate Celery using broker_use_ssl / redis_backend_use_ssl
celery = Celery(
    'backend.tasks',
    broker=broker_url, # Use the base URL
    backend=result_backend, # Use the base URL
    include=['backend.tasks'],
    # Pass the SSL options dictionary if it was populated (i.e., rediss://)
    broker_use_ssl=ssl_opts or None,
    redis_backend_use_ssl=ssl_opts or None, # Use redis_backend_use_ssl for Celery >= 5.2
)

# Update other Celery configuration settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_extended=True,  # Enable extended result format for better error handling
    task_track_started=True,  # Ensure tasks are tracked when started
    result_expires=86400,  # Keep results for a day (in seconds)
    worker_prefetch_multiplier=1,  # Handle one task at a time to prevent overloading
    task_reject_on_worker_lost=True,  # Reject tasks if worker is lost
    timezone='UTC',
    enable_utc=True,
)

# Updated print statements for better debugging
print(f"Celery App: Determined broker_url = {broker_url}")
print(f"Celery App: Using SSL context via options = {ssl_opts if ssl_opts else 'No SSL'}")
# Keep the final print statements for consistency if needed elsewhere
# print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}")
# print(f"Celery App: Broker transport options={ssl_opts}")
# print(f"Celery App: Result backend transport options={ssl_opts}") 