import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// SAARTHI_API lets you point the dev server at a backend on another port.
const api = process.env.SAARTHI_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': api,
      '/partner': api,
    },
  },
})
