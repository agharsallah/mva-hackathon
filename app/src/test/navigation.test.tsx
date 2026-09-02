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
 * The header nav's link, by its accessible name — the same thing a user clicks. Scoped to
 * the "Pages" landmark because the footer links to some of the same pages.
 */
const navLink = (label: string) =>
  within(screen.getByRole('navigation', { name: 'Pages' })).getByRole('link', { name: label });

describe('navigating with the nav bar', () => {
  beforeEach(() => {
    stubUnreachableFetch();
  });

  it('renders the page the clicked link points at, not the previous one', async () => {
    const user = userEvent.setup();
    renderApp('/');
    await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0));

    await user.click(navLink('Catalog'));

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

    await user.click(navLink('Provenance'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /the data flow/i })).toBeTruthy(),
      { timeout: 15_000 },
    );

    await user.click(navLink('Catalog'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /what were we given\?/i })).toBeTruthy(),
      { timeout: 15_000 },
    );

    await user.click(navLink('Provenance'));
    await waitFor(
      () => expect(screen.getByRole('heading', { name: /the data flow/i })).toBeTruthy(),
      { timeout: 15_000 },
    );
  }, 30_000);
});
