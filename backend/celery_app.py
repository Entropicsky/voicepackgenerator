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
    # Using CERT_NONE based on previous attempt, but Heroku might require CERT_REQUIRED.
    # This needs verification during Heroku testing.
    # ssl_opts = {'ssl_cert_reqs': ssl.CERT_NONE} 
    # Example if CERT_REQUIRED is needed:
    # ssl_opts = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
    # -- NEW APPROACH: Append SSL option to URL --
    if '?' not in broker_url:
        broker_url += "?ssl_cert_reqs=none"
    else:
        broker_url += "&ssl_cert_reqs=none"
    # Also specify the CA certs location for verification - KEEPING this in case 'none' still needs it implicitly
    broker_url += "&ssl_ca_certs=/etc/ssl/certs/ca-certificates.crt"
    # Clear ssl_opts as it's now in the URL
    ssl_opts = {}

result_backend = broker_url

# Instantiate Celery with direct broker/backend URLs and conditional SSL options
celery = Celery(
    'backend.tasks',
    broker=broker_url,
    backend=result_backend,
    include=['backend.tasks'],
    # Pass SSL options only if they exist (i.e., if broker_url started with rediss://)
    # -- REMOVED: SSL options handled by URL parameters now --
    # broker_use_ssl=ssl_opts or None,
    # result_backend_use_ssl=ssl_opts or None,
)

# Update other Celery configuration settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use json
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Updated print statements for better debugging
print(f"Celery App: Determined broker_url = {broker_url}")
# print(f"Celery App: Using SSL context = {ssl_opts if ssl_opts else 'No SSL'}") # No longer relevant
# Keep the final print statements for consistency if needed elsewhere
# print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}")
# print(f"Celery App: Broker transport options={ssl_opts}")
# print(f"Celery App: Result backend transport options={ssl_opts}") 