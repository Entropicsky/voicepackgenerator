# Use an official Python runtime as a parent image
FROM python:3.11-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# Add git for potential VCS requirements in pip packages
# Remove sqlite as it's no longer needed
# Add ca-certificates and update-ca-certificates for TLS validation
# Add ffmpeg for pydub audio processing
RUN apk update && \
    apk add --no-cache git ca-certificates ffmpeg && \
    update-ca-certificates

# Install pip dependencies
# Copy only requirements to leverage Docker cache
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY backend /app/backend
WORKDIR /app/backend
# Make port 5000 available to the world outside this container
# Note: For production, consider using a different port or reverse proxy
EXPOSE 5000

# Define environment variable for Flask app entry point
ENV FLASK_APP=app.py
# Set FLASK_ENV to development for debugging, change to production later
ENV FLASK_ENV=development 

# Ensure the output directory exists
RUN mkdir -p /app/output/audio

# Create the database file if it doesn't exist and initialize schema
# This RUN step ensures the DB exists before the CMD tries to access it
# We touch the file first, then initialize.
# RUN touch /app/jobs.db && python -c 'from models import init_db; init_db()' # Removed SQLite init

# Run app.py when the container launches
# Use gunicorn for potentially better performance/handling multiple workers
# CMD ["python", "app.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"] # Assuming 'app' is the Flask app instance in app.py 