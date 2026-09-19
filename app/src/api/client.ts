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
 *
 * ## Two deployments, one code path
 *
 * `VITE_API_URL` decides where a request goes, and it takes two shapes:
 *
 * | Value | Where a request goes | Used by |
 * |---|---|---|
 * | unset | `http://127.0.0.1:8900` | local development, `uv run mva-viz-api` on the same machine |
 * | `/` or `` | this page's own origin | the hosted dashboard, where Vercel's proxy forwards `/api/*` |
 *
 * The hosted build is the reason the second shape exists: an absolute URL in the bundle
 * would tell every visitor the backend's hostname and port. Same-origin paths mean the
 * only address the browser ever holds is the one it is already on — `app/api/proxy.ts`
 * on Vercel is what knows the real one, and it runs on the server.
 */

import { fixtureFor } from '../fixtures';
import type { Envelope, Health } from './types';

/**
 * The prefix put in front of every API path. Empty means "this origin".
 *
 * A trailing slash is stripped so `VITE_API_URL=/` (an empty string is awkward to set in
 * a Vercel project, `/` is not) and `VITE_API_URL=https://host/` both behave.
 */
function apiBase(configured: string | undefined): string {
  if (configured === undefined) return 'http://127.0.0.1:8900';
  return configured.replace(/\/+$/, '');
}

export const API_URL: string = apiBase(import.meta.env.VITE_API_URL);

/**
 * The same thing, in words, for a message or a tooltip. `API_URL` is empty in the hosted
 * build, and "No API answered at " reads as a bug rather than as same-origin.
 */
export const API_LABEL: string =
  API_URL || `${globalThis.location?.origin ?? 'this origin'} (proxied)`;

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

// --- session-wide flags, observable so the header can show a badge -----------

/**
 * A one-way latch the header can subscribe to: false until something trips it, then true
 * for the rest of the session. Shaped for `useSyncExternalStore`, which needs a stable
 * `subscribe` and a `get` that returns the same value until it actually changes.
 */
function flagStore() {
  let raised = false;
  const listeners = new Set<() => void>();
  return {
    raise(): void {
      if (raised) return;
      raised = true;
      listeners.forEach((fn) => fn());
    },
    subscribe(fn: () => void): () => void {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    get: (): boolean => raised,
  };
}

/** At least one exhibit on this session was served from a committed fixture. */
export const fixtureModeStore = flagStore();

/**
 * The API answered, and refused for want of a token.
 *
 * Worth its own signal because `/health` is deliberately unauthenticated, so the status dot
 * says "up" — correctly, the service is alive — while every panel is empty. Seen for real:
 * a dev build pointed straight at the deployed API. Liveness and usability are not the same
 * question, and the header has to be able to say which one failed.
 */
export const unauthorizedStore = flagStore();

// --- the request ------------------------------------------------------------

export type Params = Record<string, string | number | boolean | undefined>;

function buildUrl(path: string, params?: Params): string {
  // Base + path, resolved against this page. `API_URL` absolute wins over the origin;
  // `API_URL` empty leaves a same-origin path. One expression covers both deployments.
  const url = new URL(`${API_URL}${path}`, globalThis.location?.origin ?? 'http://localhost');
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
  if (err instanceof TypeError) return true;
  // The hosted deployment never gets a TypeError for a dead backend: the browser reaches
  // Vercel fine, and Vercel's proxy reports the failure as a status. 502 is "no server
  // there", 504 "it did not answer in time" — both mean the same thing here, and both are
  // codes only that proxy emits (`app/server/upstream.ts`). 503 is deliberately excluded:
  // the reads-API job routes use it for "the upstream read store is down", which the
  // Probes page shows on purpose rather than papering over with fixtures.
  return err instanceof ApiError && (err.status === 502 || err.status === 504);
}

/**
 * True when this build of the app knows a path this server does not.
 *
 * A long-running API process predates the app that talks to it: a newly added endpoint
 * gets a 404 from the old process, and treating that as "the API answered no" left every
 * new page showing "Request failed / Not Found" until someone restarted the server. That
 * happened to /api/health/dependencies against an API started the day before.
 *
 * The distinction is narrow on purpose. FastAPI answers an unrouted path with exactly
 * `{"detail": "Not Found"}`; an endpoint that looked and found nothing answers with its
 * own sentence ("no such gene", "shard 9 out of range"). Only the framework's default
 * text — and only when a fixture exists for the path — counts as "route missing". A real
 * 404 from a real endpoint still reaches the user, which is what /api/search and
 * /api/callset/region rely on.
 */
export function isRouteMissing(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 501) return true;
  return err.status === 404 && err.message.trim() === 'Not Found';
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
    if (res.status === 401 || res.status === 403) unauthorizedStore.raise();
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
    // Only "no server there" or "this server has no such route" falls back. A 404 the
    // endpoint itself raised (unknown gene, unknown shard) or a 422 (bad lane) is the live
    // API answering correctly and must reach the user as an error, not be papered over
    // with fixture rows.
    if (!FIXTURES_ENABLED || !(isUnreachable(err) || isRouteMissing(err))) throw err;
    const fixture = await fixtureFor(path, params);
    if (!fixture) throw err;
    fixtureModeStore.raise();
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
  if (res.status === 401 || res.status === 403) unauthorizedStore.raise();
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
