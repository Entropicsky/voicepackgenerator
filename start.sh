#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Substitute PORT into the Nginx snippet and write to conf.d for default main config
export DOLLAR='$'
envsubst '$PORT $DOLLAR' < /app/frontend/nginx.conf > /etc/nginx/conf.d/default.conf
# Start nginx with default config (daemon off), explicitly specifying the config file
nginx -c /etc/nginx/conf.d/default.conf -g 'daemon off;' &

# Exec gunicorn with multiple workers and threads
exec gunicorn backend.app:app \
    --bind 0.0.0.0:5000 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - 