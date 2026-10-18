import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Forward /api requests to the FastAPI backend — eliminates CORS issues
      '/api': {
        // 127.0.0.1, not localhost: Node resolves localhost to IPv6 (::1) first,
        // the backend listens on IPv4 only, and the failed IPv6 attempt added
        // ~13 s to every proxied API call.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
