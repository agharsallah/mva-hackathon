/**
 * Shared mount harness for the two in-page-navigation gates — `section-nav.test.tsx` (the
 * "On this page" rail and the "Jump to section" select) and `command-palette.test.tsx` (the
 * ⌘K palette). Both need the same three things: a routed tree carrying a journey context, a
 * fixed set of mounted `Section`s, and jsdom's two missing layout APIs stubbed. Whatever is
 * passed to `mount` lands inside the router, so a test that needs to observe a navigation
 * renders its own `useLocation` probe alongside the components under test.
 *
 * The tree is assembled here rather than mounted through `AppShell`: the assertions are about
 * three components and one store, and a real shell would drag in every page chunk, the plotly
 * mock and a 15 s settle. `navigation.test.tsx` covers the rail on a real routed page.
 *
 * **The two jsdom gaps**, both because jsdom has no layout engine:
 *
 *   - `IntersectionObserver` is not implemented at all. `OnThisPage`'s scroll-spy guards on
 *     `typeof IntersectionObserver === 'undefined'` and would simply never run, so the stub is
 *     what makes the observer path (`observe` per section, `disconnect` on unmount) execute
 *     during these tests. Its callback is never invoked — jsdom has no scrolling to report —
 *     so *which* entry is marked current is not asserted anywhere.
 *   - `Element.prototype.scrollIntoView` is not implemented either, so "jumping" is asserted
 *     as "`scrollIntoView` was called, on this element", which is the whole of what the
 *     components do.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { expect, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { Section } from '../components/Controls';
import { JourneyProvider } from '../components/journey';
import type { JourneyGroup } from '../components/journeyContext';

/** Two pages, one group — enough for the palette's "Pages" list to be assertable. */
export const GROUPS: JourneyGroup[] = [
  {
    id: 'data',
    label: 'Data',
    question: 'Is the measurement trustworthy?',
    pages: [
      { to: '/callset', label: 'Callset', title: 'The callset', description: 'What survived.' },
      { to: '/reads', label: 'Reads', title: 'The reads', description: 'The raw measurement.' },
    ],
  },
];

export function mount(ui: ReactNode, at = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[at]}>
        <JourneyProvider groups={GROUPS}>
          {/* A landmark, so axe's "all content sits in a landmark" rule is answered by the
              page shape the real app has rather than by this file's scaffolding. */}
          <main>{ui}</main>
        </JourneyProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * Three sections: two taking the auto id from their title, one overriding it — the case a
 * doc's `#anchor` depends on. No title contains the word "the", which is what lets the
 * palette's filter tests use "the" to select pages only.
 */
export const sections = (
  <>
    <Section title="Coverage by chromosome">a</Section>
    <Section title="Zygosity split">b</Section>
    <Section title="Header fields" id="declared-fields">
      c
    </Section>
  </>
);

class FakeIntersectionObserver {
  readonly root = null;
  readonly rootMargin = '';
  readonly thresholds: number[] = [];
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

/** Call from `beforeEach`. Returns the `scrollIntoView` spy; see the file header. */
export function stubLayoutApis(): ReturnType<typeof vi.fn> {
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver);
  const scrollIntoView = vi.fn();
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    value: scrollIntoView,
    writable: true,
    configurable: true,
  });
  return scrollIntoView;
}

/** Call from `afterEach`, so a later file gets jsdom back exactly as it found it. */
export function restoreLayoutApis(): void {
  Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView');
  vi.unstubAllGlobals();
}

/** The element a `stubLayoutApis()` spy was called on. */
export function jumpedTo(spy: ReturnType<typeof vi.fn>): HTMLElement {
  return spy.mock.contexts[0] as HTMLElement;
}

/**
 * Runs axe over `container` and asserts zero violations. `color-contrast` is disabled: jsdom
 * has no layout engine, so there are no computed colours to measure — the same environment
 * limit `a11y.test.tsx` documents, not a rule being waived. The `act` wrapper is that file's
 * pattern too: axe takes ~600 ms, long enough for a React timer to fire outside act.
 */
export async function expectNoAxeViolations(container: HTMLElement, what: string): Promise<void> {
  let results!: Awaited<ReturnType<typeof axe>>;
  await act(async () => {
    results = await axe(container, { rules: { 'color-contrast': { enabled: false } } });
  });
  const summary = results.violations
    .map((v) => `  [${v.impact}] ${v.id} (${v.nodes.length} node(s)) — ${v.help}`)
    .join('\n');
  expect(results.violations, `axe violations on ${what}:\n${summary}`).toEqual([]);
}

/** Opens the palette with the hotkey and returns its dialog, once the lazy chunk lands. */
export async function openPalette(): Promise<HTMLElement> {
  fireEvent.keyDown(window, { key: 'k', metaKey: true });
  return screen.findByRole('dialog', { name: 'Jump to' });
}
