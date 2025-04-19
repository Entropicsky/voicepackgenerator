# backend/__init__.py
# This file makes Python treat the directory as a package. 
from .celery_app import celery  # noqa: Expose celery app for autodiscovery
from . import tasks               # Import tasks so they register 