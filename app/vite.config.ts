import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

/**
 * The dependency endpoints the Status page shows while it is serving fixture rows.
 *
 * When the viz API answers, every `endpoint` string on that page comes from the API, which
 * reads the real configuration. Offline there is no API to ask, and a committed fixture
 * cannot carry a developer's hosts — so the loopback defaults in it were wrong for anyone
 * whose services are on a server.
 *
 * These four values are read from the repo-root `.env` at dev/build time and inlined, so
 * the offline page names the hosts THIS checkout is configured against. Only addresses are
 * exposed — never PGPASSWORD, S3_ACCESS_KEY, S3_SECRET_KEY or MVA_API_TOKEN — and the
 * bundle is served to loopback only. `import.meta.env` is the mechanism; `envDir` cannot
 * be used because these keys are not VITE_-prefixed and must not all be exposed wholesale.
 */
function configuredEndpoints(mode: string): Record<string, string> {
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '');
  const port = env.PGPORT || '5432';
  const scheme = (env.S3_USE_SSL || 'true') === 'false' ? 'http' : 'https';
  return {
    warehouse: env.PGHOST
      ? `${env.PGUSER || 'mva'}@${env.PGHOST}:${port}/${env.PGDATABASE || 'mva'}`
      : '',
    'object-store': env.S3_ENDPOINT
      ? `${scheme}://${env.S3_ENDPOINT}/${env.S3_BUCKET || 'mva'}`
      : '',
    parquet: env.S3_BUCKET ? `s3://${env.S3_BUCKET}/reads/runs.parquet` : '',
    'reads-api': env.MVA_READS_API_URL ? `${env.MVA_READS_API_URL.replace(/\/$/, '')}/health` : '',
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  define: {
    __CONFIGURED_ENDPOINTS__: JSON.stringify(configuredEndpoints(mode)),
  },
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
}));
