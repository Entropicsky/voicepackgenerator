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
# Use the absolute path to the generated config file
nginx -c /tmp/nginx.conf -g 'daemon off;' &

# Start gunicorn
# Bind to localhost as nginx is proxying internally
# Use gevent worker, increased timeout, access logging, and debug level error logging
# Ensure Gunicorn runs from the correct directory where backend.app can be found
cd /app/backend
gunicorn backend.app:app \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    -k gevent \
    --log-level debug \
    --access-logfile - \
    --error-logfile - 
    # Removed header limit for now, ProxyFix should handle it
    # --limit-request-field_size 16384 

# Wait for any process to exit
wait -n
  
# Exit with status of process that exited first
exit $? 