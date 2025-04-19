# backend/celery_app.py
from celery import Celery
import os
import ssl

# Use the REDIS_TLS_URL with SSL disabled for Heroku Redis
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Default connection options (empty)
broker_connection_options = {}
redis_backend_connection_options = {}

# Check if the URLs provided by Heroku start with 'redis://' (non-SSL)
# Heroku Redis addon might provide rediss:// directly, or redis:// with instructions to use SSL
# If redis:// is used, we need to explicitly enable SSL via options.
if broker_url.startswith('redis://'):
    broker_connection_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }
if result_backend.startswith('redis://'):
    redis_backend_connection_options = {
        'ssl_cert_reqs': ssl.CERT_NONE
    }

# Use 'rediss://' if SSL options are applied to 'redis://' URLs
# Celery requires the scheme to match the SSL usage
if broker_url.startswith('redis://') and broker_connection_options:
    print("Broker URL is redis://, but SSL options are set. Changing scheme to rediss://")
    broker_url = broker_url.replace('redis://', 'rediss://', 1)

if result_backend.startswith('redis://') and redis_backend_connection_options:
    print("Result Backend URL is redis://, but SSL options are set. Changing scheme to rediss://")
    result_backend = result_backend.replace('redis://', 'rediss://', 1)


celery = Celery(
    # Using the filename as the main name is common
    'backend.tasks', # Corresponds to backend/tasks.py
    broker=broker_url,
    backend=result_backend,
    # include tasks explicitly here now that it's simpler
    include=['backend.tasks']
    # broker_use_ssl=broker_connection_options, # Let rediss:// scheme handle SSL
    # redis_backend_use_ssl=redis_backend_connection_options # Let rediss:// scheme handle SSL
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
# print(f"Celery App: Broker SSL options={broker_connection_options}") # Removed args, log less relevant
# print(f"Celery App: Backend SSL options={redis_backend_connection_options}") # Removed args, log less relevant 