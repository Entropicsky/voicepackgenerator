#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Ensure the target directory exists
mkdir -p /etc/nginx/conf.d/

# Substitute PORT into the Nginx snippet and write to a temporary config file
export DOLLAR='$'
envsubst '$PORT $DOLLAR' < /app/frontend/nginx.conf > /tmp/nginx.conf 
# Start nginx with the temporary config (daemon off), explicitly specifying the config file
nginx -c /tmp/nginx.conf -g 'daemon off;' &

# Exec gunicorn with multiple workers and threads
exec gunicorn backend.app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - 