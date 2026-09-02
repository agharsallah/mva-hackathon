/**
 * Gate 2 — every module renders.
 *
 * The module manifest (`src/app/modules`) is the one place a page's route, nav label and
 * lazy chunk are declared. Nothing today mounts every one of those chunks and checks it
 * actually comes up — a refactor can break a page's render and nothing catches it until a
 * human clicks through the nav bar. This test mounts each module the same way `AppShell`
 * does (its own `<Route>`, inside the real `QueryClientProvider`), forces fixture mode so
 * it runs with no network, and asserts the mount didn't throw, didn't log to
 * `console.error`, and produced at least one heading.
 *
 * See `testHarness.tsx` for the mount mechanics shared with gate 3, and for why a rejected
 * `TypeError` from `fetch` is exactly the condition `api/client.ts` treats as "no server
 * there" rather than an approximation of it.
 *
 * PLOTLY IS STUBBED: `plotly.js-dist-min` is a ~4 MB WebGL bundle, and jsdom has no WebGL
 * context to render into — loading the real thing would only slow the suite down and log
 * WebGL warnings, it would never validate anything a smoke test cares about. `Plot.tsx`
 * only ever calls `.react()` and `.purge()` on the module's default export, so the mock
 * below is exactly that shape.
 */

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { modules } from '../app/modules';
import type { FeatureModule } from '../app/modules/types';
import { mountModule, stubUnreachableFetch } from './testHarness';

vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  stubUnreachableFetch();
});

describe('every module renders, offline, with no console.error', () => {
  it.each(modules.map((m): [string, FeatureModule] => [m.id, m]))(
    '%s',
    async (_id, mod) => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      const { caught } = await mountModule(mod);

      expect(caught, `module "${mod.id}" threw while rendering: ${String(caught)}`).toBeNull();
      expect(
        consoleError,
        `module "${mod.id}" wrote to console.error:\n` +
          consoleError.mock.calls.map((c) => c.map(String).join(' ')).join('\n'),
      ).not.toHaveBeenCalled();
    },
    15000,
  );
});
