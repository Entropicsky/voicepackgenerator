#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Run envsubst on the nginx template to insert the correct port
# Note: Using /tmp/ for the substituted config avoids potential permission issues
# in /etc/nginx/conf.d/ and ensures the original template isn't overwritten.
export DOLLAR='$'
# Use /tmp/nginx.conf as the destination for the substituted config
envsubst < /app/frontend/nginx.conf > /tmp/nginx.conf

# Start nginx using the generated config file, running in the background
nginx -c /tmp/nginx.conf &

# Exec gunicorn with multiple workers and threads
exec gunicorn backend.app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - 