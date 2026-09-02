/**
 * Gate 3 — accessibility.
 *
 * Reuses gate 2's mount harness (`testHarness.tsx`): every module, offline, fixture data
 * forced on, settled on a heading — then runs `axe-core` over the rendered DOM instead of
 * asserting on it directly.
 *
 * THIS FILE DOES NOT FIX PAGES. Another wave owns the page components; this gate's job is
 * to produce the worklist, not clear it. Per the mission brief: real violations are
 * reported with their exact axe output and the test is marked `.todo`, not weakened or
 * skipped silently — a green run here must mean "no violations," never "we stopped
 * checking."
 *
 * axe-core cannot evaluate every WCAG rule against a jsdom DOM (no real layout engine, no
 * computed color contrast in most jsdom setups), so `color-contrast` is disabled globally
 * below — that is a capability limit of the test environment, not a ruleset the app is
 * being let off. Every other rule in axe-core's default ("best practice" + WCAG 2.x) set
 * runs unmodified.
 */

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { modules } from '../app/modules';
import { mountModule, stubUnreachableFetch } from './testHarness';

// `vitest-axe`'s `toHaveNoViolations` matcher augments the ambient `Vi.Assertion`
// namespace, a type-extension shape `vitest@3` no longer uses (it uses `declare module
// 'vitest'` instead) — `tsc -b` correctly can't see the matcher through it, so this
// asserts on the plain `AxeResults` object instead: the same information, no matcher/type
// coupling, and a failure message that already reads as a violation list.
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

const AXE_OPTIONS = {
  rules: {
    // jsdom has no real rendering/layout engine, so a contrast check here would either
    // false-pass everything (no computed styles) or throw — this is a test-environment
    // limit, not a decision to stop checking contrast in the real app.
    'color-contrast': { enabled: false },
  },
};

describe('accessibility — every module, axe-core, offline fixtures', () => {
  for (const mod of modules) {
    it(`${mod.id} has no axe violations`, async () => {
      const { caught, container } = await mountModule(mod);
      expect(caught, `module "${mod.id}" threw while rendering`).toBeNull();

      const results = await axe(container, AXE_OPTIONS);
      const summary = results.violations
        .map((v) => `  [${v.impact}] ${v.id} (${v.nodes.length} node(s)) — ${v.help}`)
        .join('\n');
      if (results.violations.length > 0) console.log(`axe violations on "${mod.id}":\n${summary}`);

      expect(results.violations, `axe violations on "${mod.id}":\n${summary}`).toEqual([]);
    });
  }
});

/**
 * KNOWN VIOLATIONS — recorded here as the worklist for the wave that owns page components.
 * Populate/update this block from the `console.log` output above whenever the suite above
 * is turned back to `.todo` for a specific module; each entry names the module, the axe
 * rule id, the node count, and the human-readable `help` string, so a fix can be scoped
 * without re-running the suite first.
 *
 * (Empty at the time this gate was written — see the run's reported counts. If a future
 * run finds real violations, move the affected module's `it(...)` above to `it.todo(...)`
 * and record the violation list here instead of weakening AXE_OPTIONS.)
 */
