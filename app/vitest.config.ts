import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

// Kept separate from vite.config.ts rather than merged: `vitest/config`'s `defineConfig`
// pulls in Vitest's own nested copy of `vite` (a different Plugin type than the app's
// root `vite` dependency), so passing `react()`/`tailwindcss()` plugins through it fails
// to type-check. Tests don't need those plugins — Vite/esbuild transforms TSX by default
// — so this file only carries the resolve alias and the test runner settings.
export default defineConfig({
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    // Individual tests already opt into a 30s-60s timeout for the heaviest mounts
    // (axe scans, multi-exhibit pages); the default 10s hook timeout still applies
    // to shared `afterEach(cleanup)` hooks, so a slow machine under full-suite load
    // can time out unmounting right after one of those renders. Match the ceiling.
    hookTimeout: 60000,
    // Vitest's default runs test *files* in parallel worker threads. On a modest laptop
    // (see `docs/notes` on local machine limits) this suite's jsdom + mount-and-poll tests
    // (`testHarness.ts`) contend hard enough for CPU that otherwise-fine `waitFor` timeouts
    // start missing — measured: the parallel default took 122-160s and flaked on a
    // different file each run; running files one at a time took 67.8s, clean. Serial is
    // both faster and deterministic here, so it is the default.
    fileParallelism: false,
  },
});
