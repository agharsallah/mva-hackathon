/**
 * Loading and failure, once, for the whole app.
 *
 * `Skeleton` is shaped like the thing it stands in for (an exhibit, a table, a row of tiles)
 * so the page keeps its layout while data is in flight, and it waits 150 ms before painting
 * so a fast answer never flashes grey. After six seconds it says so, and where to look.
 *
 * `ErrorCard` names *which* failure happened — no API answering, an endpoint the running API
 * does not have, the upstream reads service down, a rejected query, a server fault — because
 * each one has a different fix. It always offers Retry, Status and the raw details.
 *
 * `Loaded` is the render-prop gate over a react-query result that keeps pages free of
 * `isLoading ? … : error ? … : …` ladders. When a refetch fails but the last answer is still
 * in the cache, it keeps showing that answer and says so, instead of replacing a chart with
 * an error.
 */

import type { UseQueryResult } from '@tanstack/react-query';
import { type ReactNode, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError, type Result } from '../api/client';
import { CONTROL, cx, RULE, TINT, WELL } from '../lib/ui';
import { classifyError } from './failure';

// ── Skeleton ────────────────────────────────────────────────────────────────────────────

export type SkeletonVariant = 'exhibit' | 'table' | 'tiles' | 'block';

/** True once `ms` have passed since mount. */
function useElapsed(ms: number): boolean {
  const [done, setDone] = useState(false);
  useEffect(() => {
    const t = window.setTimeout(() => setDone(true), ms);
    return () => window.clearTimeout(t);
  }, [ms]);
  return done;
}

const BONE = 'rounded-pill bg-chrome-800/70';

function ExhibitBones() {
  return (
    <div className="flex h-full flex-col p-4">
      <div className="flex items-center justify-between">
        <div className={cx(BONE, 'h-3 w-1/3')} />
        <div className={cx(BONE, 'h-5 w-16')} />
      </div>
      <div className="relative mt-4 flex-1">
        {[0, 25, 50, 75, 100].map((pct) => (
          <div
            key={pct}
            className="absolute inset-x-0 border-t border-line-soft"
            style={{ top: `${pct}%` }}
          />
        ))}
        <div className="absolute inset-x-8 bottom-0 flex items-end gap-3">
          {[40, 70, 55, 85, 30, 65, 50].map((h, i) => (
            <div key={i} className={cx(BONE, 'flex-1')} style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
      <div className="mt-4 space-y-2 border-t border-line pt-3">
        <div className={cx(BONE, 'h-2.5 w-3/4')} />
        <div className={cx(BONE, 'h-2.5 w-1/2')} />
      </div>
    </div>
  );
}

function TableBones({ rows }: { rows: number }) {
  return (
    <div className="p-4">
      <div className="grid grid-cols-4 gap-4 border-b border-line pb-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={cx(BONE, 'h-2.5 w-2/3')} />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="grid grid-cols-4 gap-4 border-b border-line-soft py-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={cx(BONE, 'h-2.5', i === 0 ? 'w-1/2' : 'w-3/4')} />
          ))}
        </div>
      ))}
    </div>
  );
}

function TileBones() {
  return (
    <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="border-l-2 border-line py-0.5 pl-3">
          <div className={cx(BONE, 'h-2.5 w-1/2')} />
          <div className={cx(BONE, 'mt-3 h-6 w-2/3')} />
          <div className={cx(BONE, 'mt-3 h-2 w-3/4')} />
        </div>
      ))}
    </div>
  );
}

export function Skeleton({
  height = 360,
  variant = 'exhibit',
  rows = 6,
  label = 'Loading',
  framed = false,
}: {
  height?: number;
  variant?: SkeletonVariant;
  /** Table variant only: how many body rows to sketch. */
  rows?: number;
  /** What is loading, for screen readers. */
  label?: string;
  /**
   * Draw the card border and panel tint. Off by default because most skeletons stand in for
   * an exhibit's body *inside* an `Exhibit` card, which already draws the frame; on for a
   * skeleton that stands alone on the page (a whole page, a tile row).
   */
  framed?: boolean;
}) {
  const show = useElapsed(150);
  const slow = useElapsed(6000);
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={cx(
        'overflow-hidden rounded-card transition-opacity duration-300',
        framed && 'border border-line bg-panel',
        show ? 'animate-pulse opacity-100' : 'opacity-0',
      )}
      style={{ minHeight: height }}
    >
      <span className="sr-only">{label}…</span>
      {variant === 'exhibit' && (
        <div style={{ height }}>
          <ExhibitBones />
        </div>
      )}
      {variant === 'table' && <TableBones rows={rows} />}
      {variant === 'tiles' && <TileBones />}
      {slow && (
        <p className="border-t border-line px-4 py-2 text-xs text-chrome-400" aria-live="polite">
          Still loading. The API may be waking up or the query is heavy.{' '}
          <Link to="/status" className="underline decoration-chrome-600 underline-offset-2">
            Check the dependency status
          </Link>
          .
        </p>
      )}
    </div>
  );
}

// ── ErrorCard ───────────────────────────────────────────────────────────────────────────

export function ErrorCard({
  error,
  onRetry,
  title,
  children,
}: {
  error: Error;
  /** Re-runs whatever failed. Omit only where nothing can be retried. */
  onRetry?: () => void;
  /** Override the classified title — a module boundary names the module instead. */
  title?: string;
  /** Extra guidance under the explanation. */
  children?: ReactNode;
}) {
  const f = classifyError(error);
  const api = error instanceof ApiError ? error : null;
  return (
    <div
      role="alert"
      className={cx('rounded-r-card border-l-2 px-4 py-3', RULE.broken, TINT.broken)}
    >
      <div className="text-sm font-semibold text-broken-300">{title ?? f.title}</div>
      <p className="mt-1 max-w-[70ch] text-sm leading-relaxed text-chrome-200">{f.explain}</p>
      {f.remedy && <p className="mt-1 max-w-[70ch] text-xs text-chrome-400">{f.remedy}</p>}
      {f.command && (
        <pre className={cx(WELL, 'mt-2 w-fit font-mono text-xs text-chrome-200')}>{f.command}</pre>
      )}
      {children}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {onRetry && (
          <button type="button" onClick={onRetry} className={cx(CONTROL, 'text-chrome-200')}>
            Retry
          </button>
        )}
        <Link to="/status" className={cx(CONTROL, 'text-chrome-400')}>
          Open Status
        </Link>
        <details className="group text-micro text-chrome-500">
          <summary className="cursor-pointer select-none px-1 hover:text-chrome-300">
            Details
          </summary>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 font-mono">
            {api && (
              <>
                <dt>endpoint</dt>
                <dd className="break-all">{api.path}</dd>
                <dt>status</dt>
                <dd>{api.status}</dd>
              </>
            )}
            <dt>message</dt>
            <dd className="break-words">{error.message || error.name}</dd>
            <dt>at</dt>
            <dd>{new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC</dd>
          </dl>
        </details>
      </div>
    </div>
  );
}

// ── Loaded ──────────────────────────────────────────────────────────────────────────────

/** The strip shown above data that is still on screen after a refetch failed. */
function StaleStrip({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const f = classifyError(error);
  return (
    <div
      role="status"
      className={cx(
        'flex flex-wrap items-center gap-x-3 gap-y-1 rounded-r-card border-l-2 px-3 py-2 text-xs',
        RULE.decision,
        TINT.decision,
      )}
    >
      <span className="font-medium text-decision-300">Showing the last answer.</span>
      <span className="text-chrome-300">The refresh failed: {f.title.toLowerCase()}.</span>
      <button type="button" onClick={onRetry} className={cx(CONTROL, 'ml-auto text-chrome-200')}>
        Retry
      </button>
    </div>
  );
}

export function Loaded<T>({
  query,
  height = 360,
  variant,
  rows,
  label,
  children,
}: {
  query: UseQueryResult<Result<T>, Error>;
  height?: number;
  variant?: SkeletonVariant;
  rows?: number;
  label?: string;
  children: (data: T, meta: Result<T>) => ReactNode;
}) {
  const retry = () => void query.refetch();
  if (query.isPending)
    return <Skeleton height={height} variant={variant} rows={rows} label={label} />;
  if (query.error && !query.data) return <ErrorCard error={query.error} onRetry={retry} />;
  if (!query.data) return <Skeleton height={height} variant={variant} rows={rows} label={label} />;
  if (query.error) {
    return (
      <div className="space-y-2">
        <StaleStrip error={query.error} onRetry={retry} />
        {children(query.data.data, query.data)}
      </div>
    );
  }
  return <>{children(query.data.data, query.data)}</>;
}
