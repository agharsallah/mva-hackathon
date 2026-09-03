/**
 * Shared mount harness for gate 2 (`modules.test.tsx`) and gate 3 (`a11y.test.tsx`) — both
 * need the same thing: one module, mounted inside the real `QueryClientProvider` and a
 * `MemoryRouter` parked on that module's route, with every request forced onto the fixture
 * path. See `modules.test.tsx`'s file header for why a rejected `TypeError` is exactly what
 * `api/client.ts` treats as "no server there," not an approximation of it.
 *
 * `vi.mock('plotly.js-dist-min', ...)` is NOT here: Vitest hoists `vi.mock` calls to the
 * top of the file that calls them, so it has to be declared in every test file that
 * (transitively) renders a chart, not centralized in a helper.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import { Component, lazy, type ReactNode, Suspense } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, vi } from 'vitest';

import type { FeatureModule } from '../app/modules/types';

/** Call from `beforeEach`: routes every request in the test onto its committed fixture. */
export function stubUnreachableFetch(): void {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
}

/**
 * Stands in for `ModuleBoundary`'s error boundary, scoped to the test: a page that throws
 * while rendering reports through `onError` instead of aborting the whole test run.
 */
class Catch extends Component<
  { onError: (e: unknown) => void; children: ReactNode },
  { crashed: boolean }
> {
  state = { crashed: false };

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(error: unknown) {
    this.props.onError(error);
  }

  render() {
    return this.state.crashed ? null : this.props.children;
  }
}

export interface Mounted {
  /** Whatever the page threw while rendering, or null if it didn't. */
  caught: unknown;
  /** The rendered root, for a caller (e.g. axe) that needs the live DOM node. */
  container: HTMLElement;
}

/**
 * Mount one module at its own route and wait for it to settle. "Settled" is two things,
 * checked in order:
 *
 *   1. At least one heading painted — `Section` and `Exhibit` both render an `<h2>`/`<h3>`
 *      unconditionally, before their data arrives, so this is really "the lazy chunk
 *      resolved and the page got past its Suspense boundary," not a data-readiness check.
 *   2. The query client has nothing in flight — a page's exhibits don't all start their
 *      fetch in the same tick (a chip like `NormChip` fires its own query once its parent's
 *      data has arrived), so this is checked, settles briefly, then checked again to catch
 *      that kind of one-step waterfall rather than returning on a momentary lull.
 *
 * Skipping step 2 and only waiting on the heading looks fine most of the time (the heading
 * appears from the page's own `Section`/`Exhibit` shell, before any exhibit's late query
 * resolves) but leaves a real race: a component's data can arrive, and React can update it,
 * *after* this function has already returned control to the test — outside of Testing
 * Library's `act()` tracking, which is exactly the "not wrapped in act()" warning React
 * prints when it happens. Step 2 closes that gap so a caller's post-mount assertions (gate
 * 2's console.error check, gate 3's axe pass) run against a page that is actually finished.
 */
export async function mountModule(mod: FeatureModule): Promise<Mounted> {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Page = lazy(mod.load);
  let caught: unknown = null;

  const { container } = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[mod.path]}>
        <Catch onError={(e) => (caught = e)}>
          <Suspense fallback={<div>loading…</div>}>
            <Routes>
              <Route path={mod.path} element={<Page />} />
            </Routes>
          </Suspense>
        </Catch>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await waitFor(
    () => {
      if (caught) return; // already crashed — stop waiting, let the caller's assertion report it
      expect(screen.queryAllByRole('heading').length).toBeGreaterThan(0);
    },
    { timeout: 8000 },
  );

  const noneInFlight = () => expect(queryClient.isFetching()).toBe(0);
  if (!caught) {
    // Settle-then-recheck, in a loop rather than once. A one-step waterfall (a chip firing
    // its own query when its parent's data lands) needed one recheck; `/panel` now has a
    // two-step one — `/api/panel/structure-genes` arrives, and only then does the cross-gene
    // metrics table fan out one `useQueries` pair per gene — so a single recheck returned
    // control while those were still resolving, and React updated the tree outside `act()`.
    // The loop exits on the first pass that finds the client idle *and still idle* after a
    // gap, which is the general form of the same check.
    for (let round = 0; round < 10; round++) {
      await waitFor(noneInFlight, { timeout: 8000 });
      // The gap is spent **inside `act`**, which is the part a bare `setTimeout` got wrong:
      // react-query commits through its own notify batch, so the render caused by the last
      // query to settle lands a tick *after* `isFetching()` reaches 0 — outside the window
      // `waitFor` covers, which is exactly the "not wrapped in act(...)" warning. Spending
      // the gap in `act` makes those commits part of the harness's own flush.
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 60));
      });
      if (queryClient.isFetching() === 0) break;
    }
    await waitFor(noneInFlight, { timeout: 8000 });
  }

  return { caught, container };
}
