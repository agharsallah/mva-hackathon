/**
 * The three primitives every page's loading and failure path goes through.
 *
 * Tested through the DOM because their whole value *is* the DOM: a skeleton that paints
 * before 150 ms would flash grey on a fast answer, an error card that does not name the
 * failure is a spinner with extra steps, and `Loaded` dropping a chart on a failed refetch
 * is the exact regression the stale strip exists to prevent.
 *
 * Everything renders inside a `MemoryRouter` — `ErrorCard`, `Skeleton`'s slow note and the
 * stale strip all link to `/status` with react-router's `<Link>`, which throws outside a
 * router. No `QueryClientProvider`: `Loaded` reads a `UseQueryResult` it is handed, so the
 * four states are built as plain objects instead of being provoked out of a real client —
 * which is the only way to get "data AND error" (a failed refetch over a warm cache)
 * deterministically.
 */

import type { UseQueryResult } from '@tanstack/react-query';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';

import { ApiError, type Result } from '../api/client';
import { ErrorCard, Loaded, Skeleton } from '../components/QueryState';

// jsdom has no layout engine, so axe's contrast check would have no computed colours to
// measure — the same environment limit `a11y.test.tsx` documents, not a rule being waived.
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } };

function mount(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ── Skeleton ────────────────────────────────────────────────────────────────────────────

describe('Skeleton', () => {
  it('announces itself as a busy region with a screen-reader label', () => {
    mount(<Skeleton label="Loading the panel" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveTextContent('Loading the panel…');
  });

  it('stays invisible for 150 ms, then paints and pulses', () => {
    vi.useFakeTimers();
    mount(<Skeleton />);
    const status = screen.getByRole('status');

    expect(status.className).toContain('opacity-0');
    expect(status.className).not.toContain('animate-pulse');

    act(() => void vi.advanceTimersByTime(149));
    expect(status.className).toContain('opacity-0');

    act(() => void vi.advanceTimersByTime(1));
    expect(status.className).toContain('animate-pulse');
    expect(status.className).toContain('opacity-100');
    expect(status.className).not.toContain('opacity-0');
  });

  it('says so after six seconds, and points at the status page', () => {
    vi.useFakeTimers();
    mount(<Skeleton />);

    act(() => void vi.advanceTimersByTime(5999));
    expect(screen.queryByText(/still loading/i)).toBeNull();

    act(() => void vi.advanceTimersByTime(1));
    expect(screen.getByText(/still loading/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /dependency status/i })).toHaveAttribute(
      'href',
      '/status',
    );
  });

  it('sketches exactly the number of table rows it is asked for', () => {
    vi.useFakeTimers();
    const { container } = mount(<Skeleton variant="table" rows={3} height={160} />);
    // Structural, not a test id: the body rows are the four-column grids with the row
    // padding; the header grid above them has none. Adding a hook to the component for
    // the test's benefit would be the test changing the thing it measures.
    expect(container.querySelectorAll('div.grid-cols-4.py-3')).toHaveLength(3);
    expect(container.querySelectorAll('div.grid-cols-4')).toHaveLength(4); // + the header
  });

  it('has no axe violations', async () => {
    const { container } = mount(<Skeleton variant="tiles" height={160} />);
    const results = await axe(container, AXE_OPTIONS);
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});

// ── ErrorCard ───────────────────────────────────────────────────────────────────────────

describe('ErrorCard', () => {
  const apiError = new ApiError('reads API unreachable', 503, '/api/reads/job');

  it('is an alert that names the classified failure', () => {
    mount(<ErrorCard error={apiError} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(/reads service is not answering/i);
  });

  it('lets a caller override the heading without changing the diagnosis', () => {
    mount(<ErrorCard error={apiError} title="The Reads module failed to load" />);
    expect(screen.getByRole('alert')).toHaveTextContent('The Reads module failed to load');
    // The explanation still comes from the classifier.
    expect(screen.getByRole('alert')).toHaveTextContent(/raw sequencing data/i);
  });

  it('offers Retry, and calls back exactly once per click', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    mount(<ErrorCard error={apiError} onRetry={onRetry} />);
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('omits Retry where nothing can be retried', () => {
    mount(<ErrorCard error={apiError} />);
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
  });

  it('always offers the status page', () => {
    mount(<ErrorCard error={apiError} />);
    expect(screen.getByRole('link', { name: 'Open Status' })).toHaveAttribute('href', '/status');
  });

  it('renders extra guidance passed as children', () => {
    mount(
      <ErrorCard error={apiError}>
        <p>Try the panel page instead.</p>
      </ErrorCard>,
    );
    expect(screen.getByText('Try the panel page instead.')).toBeInTheDocument();
  });

  it('details an API failure with the endpoint and status it came back with', () => {
    const { container } = mount(<ErrorCard error={apiError} />);
    const dl = container.querySelector('details dl');
    expect(dl?.textContent).toContain('endpoint');
    expect(dl?.textContent).toContain('/api/reads/job');
    expect(dl?.textContent).toContain('status');
    expect(dl?.textContent).toContain('503');
    expect(dl?.textContent).toContain('message');
    expect(dl?.textContent).toContain('at');
  });

  it('details a non-API failure with only what it actually knows', () => {
    const { container } = mount(<ErrorCard error={new Error('boom')} />);
    const dl = container.querySelector('details dl');
    expect(dl?.textContent).not.toContain('endpoint');
    expect(dl?.textContent).not.toContain('status');
    expect(dl?.textContent).toContain('message');
    expect(dl?.textContent).toContain('boom');
    expect(dl?.textContent).toContain('at');
  });

  it('has no axe violations', async () => {
    const { container } = mount(<ErrorCard error={apiError} onRetry={vi.fn()} />);
    const results = await axe(container, AXE_OPTIONS);
    expect(results.violations.map((v) => v.id)).toEqual([]);
  });
});

// ── Loaded ──────────────────────────────────────────────────────────────────────────────

interface Row {
  gene: string;
}

function envelope(gene: string): Result<Row> {
  return { data: { gene }, cachedAt: null, source: 'test', origin: 'fixture' };
}

/**
 * A `UseQueryResult` is a 30-field discriminated union; `Loaded` reads four of those
 * fields. Building the four states as plain objects and casting through `unknown` keeps
 * each case one readable line, and is what lets "data AND error" — a refetch that failed
 * over a warm cache — be tested at all.
 */
function fakeQuery(fields: {
  isPending?: boolean;
  data?: Result<Row>;
  error?: Error | null;
  refetch?: () => void;
}): UseQueryResult<Result<Row>, Error> {
  return {
    isPending: false,
    data: undefined,
    error: null,
    refetch: vi.fn(),
    ...fields,
  } as unknown as UseQueryResult<Result<Row>, Error>;
}

const child = (data: Row) => <p>gene {data.gene}</p>;

describe('Loaded', () => {
  it('shows the skeleton while the query is pending', () => {
    mount(<Loaded query={fakeQuery({ isPending: true })}>{child}</Loaded>);
    expect(screen.getByRole('status')).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('shows the error card when it failed with nothing cached, and retries through refetch', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mount(
      <Loaded query={fakeQuery({ error: new ApiError('boom', 500, '/api/panel'), refetch })}>
        {child}
      </Loaded>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(/failed while answering/i);
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it('renders the children, and nothing else, on a clean success', () => {
    mount(<Loaded query={fakeQuery({ data: envelope('BUB1B') })}>{child}</Loaded>);
    expect(screen.getByText('gene BUB1B')).toBeInTheDocument();
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('keeps the last answer on screen when a refetch fails, and says it is doing so', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    mount(
      <Loaded
        query={fakeQuery({
          data: envelope('CEP57'),
          error: new TypeError('Failed to fetch'),
          refetch,
        })}
      >
        {child}
      </Loaded>,
    );

    expect(screen.getByText('gene CEP57')).toBeInTheDocument(); // the chart is NOT replaced
    expect(screen.queryByRole('alert')).toBeNull();

    const strip = screen.getByRole('status');
    expect(strip).toHaveTextContent('Showing the last answer.');
    expect(strip).toHaveTextContent(/the refresh failed/i);

    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
