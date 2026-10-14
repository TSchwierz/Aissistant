import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev UI on :8742; API stays on Pi :8741 (CORS enabled for this origin).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 8742,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 8742,
    strictPort: true,
  },
})
