import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, host: '127.0.0.1' },
  build: {
    // Plotly is a ~4 MB bundle; keep it in its own lazily-loaded chunk.
    chunkSizeWarningLimit: 5000,
  },
});
