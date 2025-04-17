# Use an official Node runtime as a parent image
FROM node:20-alpine

# Set work directory
WORKDIR /app

# Copy package.json and package-lock.json (if available) first
COPY package*.json ./

# Install dependencies
# Use ci for potentially faster and more reliable installs in CI/CD
# RUN npm ci
RUN npm install

# Copy the rest of project code
# This allows us to use the node_modules cache from the previous layer
COPY . .

# Expose port (for Vite dev server)
EXPOSE 5173

# Command to run the Vite dev server
# Using --host makes it accessible from outside the container
CMD ["npm", "run", "dev", "--", "--host"] 