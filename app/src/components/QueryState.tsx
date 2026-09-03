/**
 * Loaded — render-prop gate over a react-query result.
 *
 * Keeps every page free of `isLoading ? … : error ? … : …` ladders, and gives the
 * whole app one loading skeleton and one error card.
 */

import type { UseQueryResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import type { Result } from '../api/client';
import { ApiError } from '../api/client';

export function Skeleton({ height = 360 }: { height?: number }) {
  return (
    <div
      className="animate-pulse rounded-card border border-line bg-chrome-900/60"
      style={{ height }}
    />
  );
}

/**
 * Three failures, three different fixes — so the card names which one happened.
 *
 * "Start the viz API" is actively misleading when the API is running: an endpoint added
 * after that process started answers 404, and the fix is to restart it, not to start it.
 * `get()` normally serves the fixture in that case; this branch is what a reader sees when
 * fixtures are switched off.
 */
export function ErrorCard({ error }: { error: Error }) {
  const api = error instanceof ApiError ? error : null;
  const upstream = api?.isUpstreamDown ?? false;
  const routeMissing = api !== null && (api.status === 501 || error.message.trim() === 'Not Found');

  const title = upstream
    ? 'Upstream reads API unreachable'
    : routeMissing
      ? 'This endpoint is missing from the running API'
      : 'Request failed';

  return (
    <div className="rounded-card border border-broken-900/60 bg-broken-950/25 p-4 text-sm">
      <div className="font-semibold text-broken-300">{title}</div>
      <p className="mt-1 font-mono text-xs text-broken-400/80">{error.message}</p>
      {routeMissing && (
        <p className="mt-2 text-xs text-chrome-400">
          The API process is older than this app. Restart it:{' '}
          <code className="text-chrome-300">uv run mva-viz-api</code>
        </p>
      )}
      {!upstream && !routeMissing && (
        <p className="mt-2 text-xs text-chrome-400">
          Start the viz API, or leave <code className="text-chrome-300">VITE_USE_FIXTURES</code>{' '}
          unset to browse committed fixtures.
        </p>
      )}
    </div>
  );
}

export function Loaded<T>({
  query,
  height = 360,
  children,
}: {
  query: UseQueryResult<Result<T>, Error>;
  height?: number;
  children: (data: T, meta: Result<T>) => ReactNode;
}) {
  if (query.isPending) return <Skeleton height={height} />;
  if (query.error) return <ErrorCard error={query.error} />;
  if (!query.data) return <Skeleton height={height} />;
  return <>{children(query.data.data, query.data)}</>;
}
