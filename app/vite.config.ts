import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // strictPort: without it Vite silently takes 5174 when 5173 is busy (a second dev
  // server, or one left running), and the app then loads on an origin the API's CORS
  // list does not name — which reaches the user as "api down", not as a port clash.
  server: { port: 5173, host: '127.0.0.1', strictPort: true },
  build: {
    // Plotly is a ~4 MB bundle; keep it in its own lazily-loaded chunk.
    chunkSizeWarningLimit: 5000,
  },
});
