# backend/celery_app.py
from celery import Celery
import os
import ssl

# Note: For Docker, ensure these env vars point to the 'redis' service name
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Configure SSL options for Heroku Redis
broker_options = {}
backend_options = {}

# If using SSL (rediss:// protocol), add the required SSL settings
if broker_url.startswith('rediss://'):
    broker_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

if result_backend.startswith('rediss://'):
    backend_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

celery = Celery(
    # Using the filename as the main name is common
    'backend.tasks', # Corresponds to backend/tasks.py
    broker=broker_url,
    backend=result_backend,
    # include tasks explicitly here now that it's simpler
    include=['backend.tasks'],
    # Add the broker and backend options
    broker_transport_options=broker_options,
    redis_backend_options=backend_options
)

# Optional configuration settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use json
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}") 