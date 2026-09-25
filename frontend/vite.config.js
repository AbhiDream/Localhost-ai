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
    // Match the backend bind address. On Windows, `localhost` can resolve to
    // IPv6 (::1) while FastAPI is bound to IPv4, producing proxy failures and
    // an empty/white workbench even though both terminals appear to be ready.
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/outputs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
