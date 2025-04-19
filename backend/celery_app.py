# backend/celery_app.py
# Option B: Smart Redis TLS URL selection
from celery import Celery
import os
import ssl

# Determine raw Redis URL (prefer TLS, fallback to plain, then CELERY_BROKER_URL, then default)
raw_url = os.environ.get('REDIS_TLS_URL') or os.environ.get('REDIS_URL') or os.getenv('CELERY_BROKER_URL') or 'redis://redis:6379/0'

# Upgrade scheme and configure SSL options
if raw_url.startswith('redis://'):
    broker_url = raw_url.replace('redis://', 'rediss://', 1)
    ssl_opts = {'ssl_cert_reqs': ssl.CERT_NONE}
elif raw_url.startswith('rediss://'):
    broker_url = raw_url
    ssl_opts = {'ssl_cert_reqs': ssl.CERT_REQUIRED}
else:
    broker_url = raw_url
    ssl_opts = {}

result_backend = broker_url

# Instantiate Celery with direct broker/backend URLs and SSL options
celery = Celery(
    'backend.tasks',
    broker=broker_url,
    backend=result_backend,
    include=['backend.tasks'],
    broker_use_ssl=ssl_opts or None,
    result_backend_use_ssl=ssl_opts or None,
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
print(f"Celery App: Broker transport options={ssl_opts}")
print(f"Celery App: Result backend transport options={ssl_opts}") 