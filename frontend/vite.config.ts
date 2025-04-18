import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Make server accessible externally (within Docker network and via port mapping)
    host: '0.0.0.0',
    port: 5173,
    // Explicitly configure watcher to ignore the config file itself
    // and node_modules, and use polling as it's often needed in Docker.
    watch: {
      ignored: ['**/vite.config.ts', '**/node_modules/**'],
      usePolling: true,
      interval: 1000 // Optional: adjust polling interval if needed
    },
    // Add proxy settings here
    proxy: {
      // Point back to backend service name for container-to-container communication
      '/api': {
        target: 'http://backend:5000',
        changeOrigin: true,
        secure: false,
      },
      '/audio': {
        target: 'http://backend:5000',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
