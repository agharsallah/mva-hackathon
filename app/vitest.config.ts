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
  },
});
