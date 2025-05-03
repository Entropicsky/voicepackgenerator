# backend/tasks/__init__.py
"""
Task organization module for Celery tasks.
This module imports and registers all tasks from the specialized task modules.
"""

# Import Celery app from root
from backend.celery_app import celery

# Import specialized task modules 
from .generation_tasks import *
from .regeneration_tasks import *
from .audio_tasks import *
from .script_tasks import *

# Define what should be imported when "from backend.tasks import *" is used
__all__ = [
    # Import all task functions here to ensure they're available from the tasks package
    'run_generation',
    'regenerate_line_takes',
    'run_speech_to_speech_line',
    'crop_audio_take',
    'run_script_creation_agent',
    'generate_category_lines',
]

print("Celery Worker: Loading tasks package...") 