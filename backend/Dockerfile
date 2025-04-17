# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Copy only necessary files for dependency installation first
COPY backend/requirements.txt .
# If celery_app or tasks were needed at install time, copy them too
# COPY celery_app.py .
# COPY tasks.py .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
# No need for explicit pytest-mock install here if it's in requirements.txt

# Copy the rest of the application code
# Copy backend specific code
COPY ./backend /app/backend
# Copy root files needed by worker/app
COPY celery_app.py .
COPY tasks.py .

# Install the backend package itself in editable mode (still useful for discovery)
# Needs setup.py at the context root (which is now project root)
# Let's try WITHOUT installing for now, rely on PYTHONPATH
# RUN pip install -e .

# Expose port (for Flask)
EXPOSE 5000

# The default command will be specified in docker-compose.yml
# For running Flask: flask --app app:app run --host=0.0.0.0 --port=5000
# For running Celery: celery -A celery_app:celery_app worker --loglevel=INFO 