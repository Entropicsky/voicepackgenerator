#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Ensure the target directory exists (though likely unnecessary now)
mkdir -p /etc/nginx/conf.d/

# Substitute PORT into the Nginx template and write to the main Nginx config file
export DOLLAR='$'
envsubst '$PORT $DOLLAR' < /app/frontend/nginx.conf > /etc/nginx/nginx.conf 
# Start nginx using the main config file (daemon off)
nginx -g 'daemon off;' &

# Exec gunicorn with multiple workers and threads
exec gunicorn backend.app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - 