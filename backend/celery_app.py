# backend/celery_app.py
from celery import Celery
import os
import ssl

# Note: For Docker, ensure these env vars point to the 'redis' service name
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Configure SSL options for Heroku Redis
# First, make sure to set the ssl_cert_reqs parameter directly in the URL
if broker_url.startswith('rediss://'):
    # Parse the URL and add ssl cert parameter
    if '?' not in broker_url:
        broker_url += '?ssl_cert_reqs=CERT_NONE'
    else:
        broker_url += '&ssl_cert_reqs=CERT_NONE'

if result_backend.startswith('rediss://'):
    # Parse the URL and add ssl cert parameter
    if '?' not in result_backend:
        result_backend += '?ssl_cert_reqs=CERT_NONE'
    else:
        result_backend += '&ssl_cert_reqs=CERT_NONE'

# Redis backend options
redis_backend_options = {
    'ssl_cert_reqs': ssl.CERT_NONE
}

celery = Celery(
    # Using the filename as the main name is common
    'backend.tasks', # Corresponds to backend/tasks.py
    broker=broker_url,
    backend=result_backend,
    # include tasks explicitly here now that it's simpler
    include=['backend.tasks'],
    # Add Redis backend options
    redis_backend_options=redis_backend_options
)

# Optional configuration settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use json
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Set broker options directly here too
    broker_use_ssl={
        'ssl_cert_reqs': ssl.CERT_NONE
    }
)

print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}") 