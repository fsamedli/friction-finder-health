import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev: the API runs on :8000 (uvicorn api.main:app). Demo: FastAPI serves web/dist, one process.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
