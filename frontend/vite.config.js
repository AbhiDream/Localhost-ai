import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  // Keep generated Vite files in the user's Temp directory. Some Windows
  // environments lock generated files under node_modules during startup.
  cacheDir: path.join(process.env.TEMP || process.cwd(), 'localhost-ai-vite-cache'),
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/outputs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
