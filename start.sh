#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Note: mkdir command is likely unnecessary as nginx base image should have it,
# but keep it just in case.
# Ensure the target directory exists (though likely unnecessary now)
mkdir -p /etc/nginx/conf.d/

# Define Upstream Host for Heroku (Nginx & Gunicorn in same dyno)
export PROXY_UPSTREAM=http://127.0.0.1:5000

# Substitute PORT and PROXY_UPSTREAM into the Nginx TEMPLATE and write to the MAIN Nginx config file
export DOLLAR='$'
# Input path adjusted as start.sh runs from /app in the consolidated Heroku image
envsubst '$PORT $PROXY_UPSTREAM $DOLLAR' < /app/frontend/nginx.template.conf > /etc/nginx/nginx.conf

# Start nginx using the default main config path (daemon off) - Nginx will load /etc/nginx/nginx.conf
nginx -g 'daemon off;' &

# Exec gunicorn with multiple workers and threads
# Gunicorn binds to 5000 internally, Nginx proxies to it
exec gunicorn backend.app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - 