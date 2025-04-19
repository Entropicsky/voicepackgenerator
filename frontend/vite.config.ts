import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import pluginReactSWC from '@vitejs/plugin-react-swc'
// import basicSsl from '@vitejs/plugin-basic-ssl' // Removed unused SSL plugin

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    pluginReactSWC(),
    // basicSsl(), // Enable if HTTPS is needed locally, ensure certs are trusted
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '0.0.0.0', // Allow access from network
    port: 5174, // Use a different port than the static build Nginx
    strictPort: true, // Don't automatically pick another port
    // Add polling for file watching reliability
    watch: {
      usePolling: true,
      interval: 100, // Optional: Check frequency in ms
    },
    // Proxy API requests to the backend container running on localhost:5001
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api/, ''), // Only if backend doesn't expect /api prefix
      },
      '/audio': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      }
    }
  }
})
