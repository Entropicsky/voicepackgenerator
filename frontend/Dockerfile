# Target File: frontend/Dockerfile
# Instructions: Use a multi-stage build. Stage 1 builds React app, Stage 2 uses Nginx to serve static files and proxy API calls.

# Stage 1: Build the React application
FROM node:20-slim as builder
WORKDIR /app
COPY package*.json ./
# Force clean install inside Docker
RUN rm -rf node_modules && npm install
COPY . .
# Ensure dist dir is removed before build
RUN rm -rf dist
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:alpine as final

# Copy built static files from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy the Nginx config *template*
COPY nginx.template.conf /etc/nginx/nginx.template.conf

# Add a script to process the template and start Nginx
COPY entrypoint.sh /docker-entrypoint-custom.sh
RUN chmod +x /docker-entrypoint-custom.sh

# Expose standard Nginx port (will be mapped by docker-compose)
EXPOSE 80

# Use custom entrypoint
CMD ["/docker-entrypoint-custom.sh"] 