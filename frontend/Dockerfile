# Target File: frontend/Dockerfile
# Instructions: Use a multi-stage build. Stage 1 builds React app, Stage 2 uses Nginx to serve static files and proxy API calls.

# Stage 1: Build the React application
FROM node:20-slim as builder
WORKDIR /app
COPY package*.json ./
# Clean potential stale caches/dependencies/output
RUN rm -rf node_modules && rm -rf dist && rm -rf .vite 
RUN npm install
COPY . .
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:alpine
# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy built static files from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html
# Expose Nginx default port
EXPOSE 80
# Nginx default CMD will start the server (no CMD needed here) 