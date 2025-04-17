import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Make server accessible externally (within Docker network and via port mapping)
    host: '0.0.0.0',
    port: 5173,
    // Add proxy settings here
    proxy: {
      // Target remains backend:5000 as communication is container-to-container
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
