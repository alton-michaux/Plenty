import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Same-origin in dev, so no CORS and the client just calls /api/...
    proxy: { '/api': 'http://localhost:8765', '/openapi.json': 'http://localhost:8765' },
  },
})
