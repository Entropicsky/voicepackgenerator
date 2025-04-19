# backend/celery_app.py
from celery import Celery
import os
import ssl

# Prefer TLS-enabled Redis URL on Heroku, falling back to standard Redis URL or Celery-specific vars
redis_url = os.environ.get('REDIS_TLS_URL') or os.environ.get('REDIS_URL')
broker_url = redis_url or os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = redis_url or os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Default connection options (empty)
broker_transport_opts = {}
result_backend_transport_opts = {}

# Only enable TLS when explicitly using REDIS_TLS_URL env var
tls_env_url = os.environ.get('REDIS_TLS_URL')
if tls_env_url:
    # Celery broker and backend both use the redis_url env var when TLS is desired
    if broker_url.startswith('redis://'):
        broker_transport_opts = {'ssl_cert_reqs': ssl.CERT_NONE}
        broker_url = broker_url.replace('redis://', 'rediss://', 1)
    elif broker_url.startswith('rediss://'):
        broker_transport_opts = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
    
    if result_backend.startswith('redis://'):
        result_backend_transport_opts = {'ssl_cert_reqs': ssl.CERT_NONE}
        result_backend = result_backend.replace('redis://', 'rediss://', 1)
    elif result_backend.startswith('rediss://'):
        result_backend_transport_opts = {'ssl_cert_reqs': ssl.CERT_REQUIRED}

# Instantiate Celery with SSL options for Redis
celery = Celery(
    'backend.tasks', # Corresponds to backend/tasks.py
    broker=broker_url,
    backend=result_backend,
    include=['backend.tasks'],
    broker_use_ssl=broker_transport_opts,
    result_backend_use_ssl=result_backend_transport_opts,
)

# Update other Celery configuration settings
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use json
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}")
print(f"Celery App: Broker transport options={broker_transport_opts}")
print(f"Celery App: Result backend transport options={result_backend_transport_opts}") 