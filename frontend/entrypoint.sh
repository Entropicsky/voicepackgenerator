#!/usr/bin/env sh
set -e

# Set default port for local Docker environment (ignored by Heroku which sets its own PORT)
export PORT=${PORT:-80}
# Set default backend host for local Docker environment
export BACKEND_HOST=${BACKEND_HOST:-backend}
export PROXY_UPSTREAM=http://$BACKEND_HOST:5000

# Substitute environment variables in the template
# Need DOLLAR var for envsubst to ignore nginx vars like $host
export DOLLAR='$'
envsubst '$PORT $PROXY_UPSTREAM $DOLLAR' < /etc/nginx/nginx.template.conf > /etc/nginx/nginx.conf

# Execute the default Nginx entrypoint script or start Nginx directly
# Using `nginx -g 'daemon off;'` ensures it runs in the foreground
echo "Starting Nginx... Proxying to $PROXY_UPSTREAM"
exec nginx -g 'daemon off;' 