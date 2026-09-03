/**
 * Every link the Learn page writes lands somewhere.
 *
 * Three tables point out of the dictionary: `tracks.ts` (term slugs), `seeIt.ts` (routes with
 * exhibit anchors, and methodology paths) and the Explainer's `dict` slugs on other pages.
 * A slug is checked against the generated dictionary; a route against the module manifest;
 * an exhibit anchor by mounting that page offline, the way gate 2 does, and asking the DOM
 * for the id — so a retitled exhibit fails here, not in a reader's browser.
 */

import { existsSync } from 'node:fs';
import path from 'node:path';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { modules } from '../app/modules';
import { entriesOf, loadDictionary } from '../lib/dictionary';
import { SEE_IT } from '../pages/learn/seeIt';
import { TRACKS } from '../pages/learn/tracks';
import { mountModule, stubUnreachableFetch } from './testHarness';

vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

const dictionary = await loadDictionary();
const slugs = new Set(entriesOf(dictionary).map((e) => e.slug));
const routes = new Set(modules.map((m) => m.path));
const REPO_ROOT = path.resolve(__dirname, '../../..');

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  stubUnreachableFetch();
});

describe('tracks', () => {
  it('name only terms the dictionary defines, each once', () => {
    for (const t of TRACKS) {
      expect(
        t.slugs.filter((s) => !slugs.has(s)),
        `track "${t.id}"`,
      ).toEqual([]);
      expect(new Set(t.slugs).size, `track "${t.id}" repeats a term`).toBe(t.slugs.length);
    }
  });
});

describe('see-it links', () => {
  it('hang off terms the dictionary defines', () => {
    expect(Object.keys(SEE_IT).filter((s) => !slugs.has(s))).toEqual([]);
  });

  it('point at routes the manifest declares', () => {
    const bad = Object.values(SEE_IT)
      .flatMap((s) => s.app.map((l) => l.to.split('#')[0]))
      .filter((route) => !routes.has(route));
    expect(bad).toEqual([]);
  });

  it('cite methodology entries that exist in docs/', () => {
    const missing = Object.values(SEE_IT)
      .flatMap((s) => s.docs ?? [])
      .map((d) => d.path)
      .filter((p) => !existsSync(path.join(REPO_ROOT, p)));
    expect(missing).toEqual([]);
  });

  // One mount per page that is linked with an anchor, then every anchor on that page.
  const anchorsByRoute = new Map<string, string[]>();
  for (const s of Object.values(SEE_IT)) {
    for (const l of s.app) {
      const [route, anchor] = l.to.split('#');
      if (!anchor) continue;
      anchorsByRoute.set(route, [...(anchorsByRoute.get(route) ?? []), anchor]);
    }
  }

  it.each([...anchorsByRoute.entries()])(
    'find their exhibit anchors on %s',
    async (route, anchors) => {
      const mod = modules.find((m) => m.path === route);
      expect(mod, `no module at ${route}`).toBeDefined();
      const { container, caught } = await mountModule(mod!);
      expect(caught).toBeNull();
      const missing = [...new Set(anchors)].filter((a) => !container.querySelector(`#${a}`));
      expect(missing, `anchors missing on ${route}`).toEqual([]);
    },
    20_000,
  );
});
