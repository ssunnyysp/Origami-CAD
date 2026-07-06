import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin /api calls are forwarded to the Python geometry service,
    // so the frontend needs no backend URL configuration and no CORS.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
