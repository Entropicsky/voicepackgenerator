# Consolidated Dockerfile for running Nginx + Gunicorn/Flask in one dyno

# --- Base Python Image ---
FROM python:3.11-alpine as python-base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies first
RUN apk update && apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    git \
    sqlite \
    nginx \
    gettext

# Copy full project into image so requirements file is available
COPY . /app
# Install pip dependencies using backend requirements file
RUN pip install --no-cache-dir -r backend/requirements.txt

# --- Node Builder Stage (for Frontend) ---
FROM node:20-slim as node-builder
WORKDIR /app/frontend 
# Source paths relative to build context
# Destination must end with / when using wildcard source
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# --- Final Stage --- 
# Start from the python-base stage which already has code and python deps
FROM python-base as final

WORKDIR /app

# Copy backend code (needed at runtime by Gunicorn)
COPY backend /app/backend/

# Copy frontend build artifacts
COPY --from=node-builder /app/frontend/dist /app/frontend/dist/

# Copy Nginx config template (needed by start.sh)
COPY frontend/nginx.conf /app/frontend/nginx.conf

# Copy startup script and make executable (needed for CMD)
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Ensure output directory exists 
RUN mkdir -p /app/backend/output/audio

# Database initialization (cd into backend first)
# Make sure the DB file path matches what's expected by models.py
RUN touch /app/backend/jobs.db && cd /app/backend && python -c 'from models import init_db; init_db()'

# Expose the port Nginx will listen on (set by $PORT)
EXPOSE 8080 

# Run the startup script
CMD ["/app/start.sh"] 