/**
 * One fetch wrapper for the whole app.
 *
 * Every viz-API endpoint answers with the same envelope `{data, cached_at, source}`,
 * so there is exactly one request function and every hook is a thin call on it.
 *
 * Fixture fallback: the API is built concurrently and may not be running. When a request
 * cannot reach the server at all (or the endpoint is not implemented yet), and fixtures
 * are enabled, we serve the committed fixture for that path and mark the app as running
 * on fixture data. Endpoints with no fixture (the reads-API job proxy) still raise.
 */

import { fixtureFor } from '../fixtures';
import type { Envelope, Health } from './types';

export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8900';
export const FIXTURES_ENABLED: boolean = import.meta.env.VITE_USE_FIXTURES !== 'false';

/** Where a given payload actually came from — surfaced next to every exhibit. */
export type Origin = 'api' | 'fixture';

export interface Result<T> {
  data: T;
  cachedAt: string | null;
  /** The API's own provenance string: the table, object or file behind these rows. */
  source: string;
  origin: Origin;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** 503 from the proxy means the upstream reads API is down — a state worth showing. */
  get isUpstreamDown(): boolean {
    return this.status === 503;
  }
}

// --- fixture-mode flag, observable so the header can show a badge ------------

let fixtureMode = false;
const listeners = new Set<() => void>();

function markFixtureMode(): void {
  if (fixtureMode) return;
  fixtureMode = true;
  listeners.forEach((fn) => fn());
}

export const fixtureModeStore = {
  subscribe(fn: () => void): () => void {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
  get: (): boolean => fixtureMode,
};

// --- the request ------------------------------------------------------------

export type Params = Record<string, string | number | boolean | undefined>;

function buildUrl(path: string, params?: Params): string {
  const url = new URL(path, API_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

/**
 * True when the failure means "no server there", as opposed to "server said no".
 *
 * A cancelled fetch (AbortError) is deliberately NOT unreachable: react-query aborts the
 * first request of every StrictMode double-mount, and treating that as a dead API would
 * flip the whole app into fixture mode on a perfectly healthy server.
 */
function isUnreachable(err: unknown): boolean {
  return err instanceof TypeError;
}

async function raw<T>(path: string, params?: Params, signal?: AbortSignal): Promise<Result<T>> {
  const res = await fetch(buildUrl(path, params), {
    signal,
    headers: { accept: 'application/json' },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(detail, res.status, path);
  }
  const body = (await res.json()) as Envelope<T>;
  return { data: body.data, cachedAt: body.cached_at, source: body.source, origin: 'api' };
}

export async function get<T>(
  path: string,
  params?: Params,
  signal?: AbortSignal,
): Promise<Result<T>> {
  try {
    return await raw<T>(path, params, signal);
  } catch (err) {
    // Only "no server there" falls back. A 404 (unknown gene, unknown shard) or a 422
    // (bad lane) is the live API answering correctly and must reach the user as an error,
    // not be papered over with fixture rows.
    const notImplemented = err instanceof ApiError && err.status === 501;
    if (!FIXTURES_ENABLED || !(isUnreachable(err) || notImplemented)) throw err;
    const fixture = await fixtureFor(path, params);
    if (!fixture) throw err;
    markFixtureMode();
    return {
      data: fixture.data as T,
      cachedAt: fixture.cached_at,
      source: fixture.source,
      origin: 'fixture',
    };
  }
}

/**
 * Throw an ApiError carrying the server's own `{detail}` when a response is not ok.
 * Error bodies are never enveloped, so this is shared by every request shape.
 */
async function assertOk(res: Response, path: string): Promise<void> {
  if (res.ok) return;
  let detail = `${res.status} ${res.statusText}`;
  try {
    const parsed = (await res.json()) as { detail?: string };
    if (parsed?.detail) detail = parsed.detail;
  } catch {
    /* non-JSON error body — keep the status line */
  }
  throw new ApiError(detail, res.status, path);
}

/**
 * POST to the reads-API proxy. No fixture fallback: submitting a job needs a real server.
 * The proxy routes carry the same `{data, cached_at, source}` envelope as everything else,
 * so the upstream JobOut is unwrapped here and callers only ever see the job itself.
 */
export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  await assertOk(res, path);
  return ((await res.json()) as Envelope<T>).data;
}

/** GET on a proxy route: enveloped like the rest, unwrapped to the upstream payload. */
export async function getBare<T>(path: string, params?: Params): Promise<T> {
  const res = await fetch(buildUrl(path, params), { headers: { accept: 'application/json' } });
  await assertOk(res, path);
  return ((await res.json()) as Envelope<T>).data;
}

/** GET /health — no envelope. Used by the header's status dot. */
export async function health(): Promise<Health> {
  const res = await fetch(buildUrl('/health'));
  if (!res.ok) throw new ApiError(`${res.status}`, res.status, '/health');
  return (await res.json()) as Health;
}
