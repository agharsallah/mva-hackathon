/**
 * Clicking a nav link must actually change the page.
 *
 * It did not. Every route's element is the same component type — `ModuleBoundary` — at the
 * same position in the tree, so React reconciles a navigation as a props update on the
 * existing instance rather than a fresh mount. `ModuleBoundary` memoised its `lazy(load)`
 * on `[attempt]` alone, so the memo handed back the PREVIOUS module's component and the
 * old page stayed on screen. A hard reload mounted the tree from scratch and looked fine,
 * which is exactly why this survived the module-render gate: that gate mounts each module
 * at its own route, and never navigates between two.
 *
 * These tests navigate.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from '../app/AppShell';
import { stubUnreachableFetch } from './testHarness';

// A 4 MB WebGL bundle is not what these tests are about; every page that draws imports it.
vi.mock('plotly.js-dist-min', () => ({
  default: { react: vi.fn().mockResolvedValue(undefined), purge: vi.fn() },
}));

function renderApp(at = '/') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[at]}>
        <AppShell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/**
 * The header's links, by accessible name — the same thing a user clicks. The nav is
 * two-tier: a "Sections" landmark (row 1) whose tabs land on a section's first page, and a
 * "Pages" landmark (row 2) listing the pages inside the active section. Both are scoped to
 * their landmark because the footer links to some of the same pages.
 */
const sectionLink = (label: string) =>
  within(screen.getByRole('navigation', { name: 'Sections' })).getByRole('link', {
    name: label,
  });
const pageLink = (label: string) =>
  within(screen.getByRole('navigation', { name: 'Pages' })).getByRole('link', { name: label });

describe('navigating with the nav bar', () => {
  beforeEach(() => {
    stubUnreachableFetch();
  });

  it('renders the page the clicked link points at, not the previous one', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0));

    // The Platform tab lands on its first page, Catalog.
    await user.click(sectionLink('Platform'));

    // A Catalog heading, which Overview never renders.
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /what were we given\?/i })).toBeTruthy(),
      { timeout: 15_000 },
    );
  }, 20_000);

  it('keeps working across three hops, so the second navigation is not a fluke', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0));

    await user.click(sectionLink('Platform'));
    await user.click(pageLink('Provenance'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /the data flow/i })).toBeTruthy(),
      { timeout: 15_000 },
    );

    await user.click(pageLink('Catalog'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /what were we given\?/i })).toBeTruthy(),
      { timeout: 15_000 },
    );

    await user.click(pageLink('Provenance'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /the data flow/i })).toBeTruthy(),
      { timeout: 15_000 },
    );
  }, 30_000);

  it('shows the page h1 and the section question from the manifest', async () => {
    renderApp('/callset');
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: 'The callset' })).toBeTruthy(),
    );
    // Row 2 lists the Data section's pages, Callset marked current.
    expect(pageLink('Callset').getAttribute('aria-current')).toBe('page');
    expect(pageLink('Reads')).toBeTruthy();
    expect(pageLink('Genome')).toBeTruthy();
    // The journey hand-off points at the neighbours in manifest order.
    const journey = screen.getByRole('navigation', { name: 'Journey' });
    expect(within(journey).getByRole('link', { name: /Reads/ }).getAttribute('href')).toBe(
      '/reads',
    );
    expect(
      within(journey)
        .getByRole('link', { name: /Genome/ })
        .getAttribute('href'),
    ).toBe('/genome');
  });

  /**
   * The rail is drawn by `PageFrame` from the section registry, which only fills once the
   * page's lazy chunk has mounted and its `Section` effects have run — so this is the one
   * assertion that the whole chain (module chunk → `Section` → registry → rail) closes on a
   * real route. The per-component behaviour lives in `section-nav.test.tsx`.
   */
  it('builds the "On this page" rail from the sections the routed page mounted', async () => {
    renderApp('/callset');
    const rail = await screen.findByRole(
      'navigation',
      { name: 'On this page' },
      { timeout: 15_000 },
    );
    expect(
      within(rail).getByRole('link', { name: "What survived the caller's filters" }),
    ).toBeTruthy();
  }, 20_000);

  /**
   * A step page three levels down must say where it is in every row, not only in the last:
   * the screenshot that prompted this showed "Step 2" lit and "Iteration 4" and "Track 1"
   * dark, so a reader could not tell which iteration the step belonged to.
   */
  it('marks the whole path to a step, and the step itself as the page', async () => {
    renderApp('/track1/iteration4/step-2');
    const row = (name: string) => screen.getByRole('navigation', { name });
    const current = (nav: string, label: string) =>
      within(row(nav)).getByRole('link', { name: label }).getAttribute('aria-current');
    await waitFor(() => expect(current('Pages', 'Track 1')).toBe('true'));
    expect(current('Track 1 pages', 'Iteration 4')).toBe('true');
    expect(current('Track 1 pages', 'Iteration 2')).toBeNull();
    expect(current('Iteration 4 pages', 'Step 2')).toBe('page');
    expect(current('Iteration 4 pages', 'overview')).toBeNull();
    // The zoo is one of iteration 4's pages, not a peer of Track 1.
    expect(within(row('Iteration 4 pages')).getByRole('link', { name: 'Zoo' })).toBeTruthy();
    expect(within(row('Pages')).queryByRole('link', { name: 'Zoo' })).toBeNull();
  });

  it('sends the old /zoo address to iteration 4, query intact', async () => {
    renderApp('/zoo?model=esm1b');
    await waitFor(() =>
      expect(
        within(screen.getByRole('navigation', { name: 'Iteration 4 pages' }))
          .getByRole('link', { name: 'Zoo' })
          .getAttribute('aria-current'),
      ).toBe('page'),
    );
  });

  it("lists an iteration's non-step pages on its overview", async () => {
    renderApp('/track1/iteration4');
    const block = await screen.findByRole('region', { name: 'Pages of this iteration' });
    expect(
      within(block)
        .getByRole('link', { name: /model zoo/i })
        .getAttribute('href'),
    ).toBe('/track1/iteration4/zoo');
  });
});
