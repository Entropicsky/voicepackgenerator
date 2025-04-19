#!/usr/bin/env sh
set -e

# Set default port for local Docker environment (ignored by Heroku which sets its own PORT)
export PORT=${PORT:-80}

# Substitute environment variables in the template
# Need DOLLAR var for envsubst to ignore nginx vars like $host
export DOLLAR='$'
envsubst '$PORT $DOLLAR' < /etc/nginx/nginx.template.conf > /etc/nginx/nginx.conf

# Execute the default Nginx entrypoint script or start Nginx directly
# Using `nginx -g 'daemon off;'` ensures it runs in the foreground
echo "Starting Nginx..."
exec nginx -g 'daemon off;' 