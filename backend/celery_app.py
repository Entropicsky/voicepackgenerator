# backend/celery_app.py
from celery import Celery
import os
import ssl

# Use the REDIS_TLS_URL with SSL disabled for Heroku Redis
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

# Default connection options (empty)
broker_transport_opts = {}
result_backend_transport_opts = {}

# If the scheme is redis:// (not rediss://), Heroku Redis might still require SSL.
# In this case, we need to provide the SSL options explicitly.
if broker_url.startswith('redis://'):
    broker_transport_opts = {
        'ssl_cert_reqs': ssl.CERT_NONE,
        # Add other potential SSL options here if needed later
    }
if result_backend.startswith('redis://'):
    result_backend_transport_opts = {
        'ssl_cert_reqs': ssl.CERT_NONE,
    }

# # Use 'rediss://' if SSL options are applied to 'redis://' URLs
# # Celery requires the scheme to match the SSL usage
# # REVERTED THIS: Let transport_options handle SSL
# if broker_url.startswith('redis://') and broker_transport_opts:
#     print("Broker URL is redis://, but SSL options are set. Changing scheme to rediss://")
#     broker_url = broker_url.replace('redis://', 'rediss://', 1)

# if result_backend.startswith('redis://') and result_backend_transport_opts:
#     print("Result Backend URL is redis://, but SSL options are set. Changing scheme to rediss://")
#     result_backend = result_backend.replace('redis://', 'rediss://', 1)

celery = Celery(
    # Using the filename as the main name is common
    'backend.tasks', # Corresponds to backend/tasks.py
    broker=broker_url,
    backend=result_backend,
    # include tasks explicitly here now that it's simpler
    include=['backend.tasks']
)

# Optional configuration settings
# Apply SSL settings via transport options if needed
celery.conf.update(
    broker_transport_options=broker_transport_opts,
    result_backend_transport_options=result_backend_transport_opts,
    task_serializer='json',
    accept_content=['json'],  # Ensure tasks use json
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

print(f"Celery App: Configured with broker={broker_url}, backend={result_backend}")
print(f"Celery App: Broker transport options={broker_transport_opts}")
print(f"Celery App: Result backend transport options={result_backend_transport_opts}") 