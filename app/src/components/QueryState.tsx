/**
 * Loaded — render-prop gate over a react-query result.
 *
 * Keeps every page free of `isLoading ? … : error ? … : …` ladders, and gives the
 * whole app one loading skeleton and one error card.
 */

import type { ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { Result } from '../api/client';
import { ApiError } from '../api/client';

export function Skeleton({ height = 360 }: { height?: number }) {
  return (
    <div
      className="animate-pulse rounded-lg border border-zinc-800 bg-zinc-900/60"
      style={{ height }}
    />
  );
}

export function ErrorCard({ error }: { error: Error }) {
  const upstream = error instanceof ApiError && error.isUpstreamDown;
  return (
    <div className="rounded-lg border border-red-900/60 bg-red-950/25 p-4 text-sm">
      <div className="font-semibold text-red-300">
        {upstream ? 'Upstream reads API unreachable' : 'Request failed'}
      </div>
      <p className="mt-1 font-mono text-xs text-red-400/80">{error.message}</p>
      {!upstream && (
        <p className="mt-2 text-xs text-zinc-400">
          Start the viz API, or leave <code className="text-zinc-300">VITE_USE_FIXTURES</code> unset to
          browse committed fixtures.
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
