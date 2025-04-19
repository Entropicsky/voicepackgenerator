# Consolidated Dockerfile for running Nginx + Gunicorn/Flask in one dyno

# --- Base Python Image ---
FROM python:3.11-alpine as python-base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies
# Add build-base etc. for gevent C extensions
RUN apk update && apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    # Add git for potential VCS requirements in pip packages
    git \
    # Add sqlite for Flask-Migrate/Alembic support with SQLite
    sqlite \
    # Add Nginx and envsubst (from gettext package)
    nginx \
    gettext

# Install pip dependencies (Copy requirements FIRST for caching)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# --- Node Builder Stage (for Frontend) ---
FROM node:20-slim as node-builder
# Set working directory INSIDE /app to match final structure assumption
WORKDIR /app/frontend 
COPY frontend/package*.json .
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Final Stage --- 
FROM python-base as final

WORKDIR /app

# Copy Python backend code
COPY backend/ /app/backend/

# Copy built frontend static files from node-builder stage
COPY --from=node-builder /app/frontend/dist /app/frontend/dist/

# Copy Nginx config template (will be processed by start.sh)
# The start.sh script expects it at /app/frontend/nginx.conf
COPY frontend/nginx.conf /app/frontend/nginx.conf

# Copy startup script and make executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Ensure output directory exists (although volume mount is better locally)
RUN mkdir -p /app/backend/output/audio

# Database initialization (relative to WORKDIR /app)
RUN touch /app/backend/jobs.db && cd /app/backend && python -c 'from models import init_db; init_db()'

# Expose the port Nginx will listen on (set by $PORT)
# Heroku uses $PORT, so this is mainly informational for Docker
EXPOSE 8080 

# Run the startup script (ensure it uses correct paths relative to /app)
CMD ["/app/start.sh"] 