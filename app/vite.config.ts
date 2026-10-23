import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv, type Plugin, type ProxyOptions } from 'vite';

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
  // The shareable demo build names no host at all.
  if (process.env.VITE_DEMO === 'true') return {};
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

/**
 * `pnpm dev` against the server's token-protected viz API, without Vercel.
 *
 * With `VITE_API_URL=/` the browser asks this dev server for `/api/*` and `/health`; this
 * forwards them to `MVA_VIZ_API_URL` and adds `X-API-Key: MVA_VIZ_API_TOKEN` — the job
 * `api/proxy.ts` does on Vercel. Both come from the repo-root `.env` and live only in the
 * Node process, never in `import.meta.env` or the bundle. Unset `MVA_VIZ_API_URL` and
 * there is no proxy; with `VITE_API_URL` absolute the browser never asks this server.
 */
function devApiProxy(mode: string): Record<string, ProxyOptions> | undefined {
  if (process.env.VITE_DEMO === 'true') return undefined;
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '');
  const target = env.MVA_VIZ_API_URL?.replace(/\/+$/, '');
  if (!target) return undefined;
  const options: ProxyOptions = {
    target,
    changeOrigin: true,
    headers: env.MVA_VIZ_API_TOKEN ? { 'X-API-Key': env.MVA_VIZ_API_TOKEN } : {},
  };
  return { '/api': options, '^/health$': options };
}

/**
 * In the demo build, rewrite every text that names the real case — page prose, the glossary
 * (generated from `docs/dictionary.md`) and the page title. Same mapping as
 * `tools/build_demo_fixtures.py`; `tools/check-demo-leaks.mjs` fails the build if it misses.
 */
const DEMO_RENAMES: [string, string][] = [
  ['PROBAND01', 'HG002'],
  ['HP:0000121', 'HP:0002667'],
  ['Nephrocalcinosis', 'Nephroblastoma'],
  ['HP:0001508', 'HP:0000252'],
  ['Failure to thrive', 'Microcephaly'],
  ['HP:0003202', 'HP:0001305'],
  ['Skeletal muscle atrophy', 'Dandy-Walker malformation'],
  ['HP:0001622', 'HP:0000518'],
  ['Premature birth', 'Cataract'],
  ['HP:0001518', 'HP:0001511'],
  ['Small for gestational age', 'Intrauterine growth retardation'],
  ['HP:0200067', 'HP:0003826'],
  ['Recurrent spontaneous abortion', 'Stillbirth'],
  ['recurrent-miscarriage', 'stillbirth'],
  ['recurrent miscarriage', 'stillbirth'],
  ['miscarriage', 'stillbirth'],
  // headline counts the page prose quotes, real -> demo (overview.json in fixtures/demo)
  ['1,071,835,104', '711,908,327'],
  ['1,079,858,785', '717,312,040'],
  ['136,586,642', '88,125,298'],
  ['5,012,204', '4,819,668'],
  ['271,414', '207,456'],
  ['94.58', '95.70'],
  ['66,860', '62,944'],
];
const demoRename = (text: string): string =>
  DEMO_RENAMES.reduce((t, [from, to]) => t.replaceAll(from, to), text);

function demoSanitize(): Plugin {
  return {
    name: 'demo-sanitize',
    apply: () => process.env.VITE_DEMO === 'true',
    transform: (code, id) => (/\/src\/.*\.(tsx?|json)$/.test(id) ? demoRename(code) : null),
    transformIndexHtml: (html) => demoRename(html),
    // The figure of the real submission file: emitted by the glossary's eager glob even
    // when nothing in the demo links to it.
    generateBundle(_, bundle) {
      for (const name of Object.keys(bundle))
        if (name.includes('submission-csv')) delete bundle[name];
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss(), demoSanitize()],
  define: {
    __CONFIGURED_ENDPOINTS__: JSON.stringify(configuredEndpoints(mode)),
    // The fence on the persisted query cache: a deployment never reads the cache a
    // previous one wrote, so a changed payload shape can never be restored into a build
    // that does not understand it. Constant in dev, or every restart would throw the
    // local cache away.
    __BUILD_ID__: JSON.stringify(
      mode === 'production' ? (process.env.VERCEL_GIT_COMMIT_SHA ?? String(Date.now())) : 'dev',
    ),
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  // strictPort: without it Vite silently takes 5174 when 5173 is busy (a second dev
  // server, or one left running), and the app then loads on an origin the API's CORS
  // list does not name — which reaches the user as "api down", not as a port clash.
  server: { port: 5173, host: '127.0.0.1', strictPort: true, proxy: devApiProxy(mode) },
  build: {
    // Plotly is a ~4 MB bundle; keep it in its own lazily-loaded chunk.
    chunkSizeWarningLimit: 5000,
  },
}));
