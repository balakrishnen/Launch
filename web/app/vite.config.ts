import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: { outDir: '../../sethread/web/dist', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8765', '/p': 'http://127.0.0.1:8765', '/oslc': 'http://127.0.0.1:8765' } },
})
