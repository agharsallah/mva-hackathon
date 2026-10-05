/**
 * One fetch wrapper for the whole app.
 *
 * Every backend endpoint answers with the same envelope `{data, cached_at, source}`,
 * so there is exactly one request function and every hook is a thin call on it.
 *
 * ## Two deployments, one code path
 *
 * `VITE_API_URL` decides where a request goes, and it takes two shapes:
 *
 * | Value | Where a request goes | Used by |
 * |---|---|---|
 * | unset | `http://127.0.0.1:8900` | local development, the API running on the same machine |
 * | `/` or `` | this page's own origin | the hosted dashboard, where Vercel's proxy forwards `/api/*` |
 *
 * The hosted build is the reason the second shape exists: an absolute URL in the bundle
 * would tell every visitor the backend's hostname and port. Same-origin paths mean the
 * only address the browser ever holds is the one it is already on — `app/api/proxy.ts`
 * on Vercel is what knows the real one, and it runs on the server.
 */

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

export interface Result<T> {
  data: T;
  cachedAt: string | null;
  /** The API's own provenance string: the table, object or file behind these rows. */
  source: string;
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

  /** 503 from the proxy means the upstream service is down — a state worth showing. */
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
 * True when this build of the app knows a path this server does not.
 *
 * A long-running API process predates the app that talks to it: a newly added endpoint
 * gets a 404 from the old process, and treating that as "the API answered no" leaves every
 * new page showing "Request failed / Not Found" until someone restarts the server.
 *
 * The distinction is narrow on purpose. FastAPI answers an unrouted path with exactly
 * `{"detail": "Not Found"}`; an endpoint that looked and found nothing answers with its
 * own sentence. Only the framework's default text counts as "route missing", so a real
 * 404 from a real endpoint still reaches the user as the answer it is.
 */
export function isRouteMissing(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 501) return true;
  return err.status === 404 && err.message.trim() === 'Not Found';
}

export async function get<T>(
  path: string,
  params?: Params,
  signal?: AbortSignal,
): Promise<Result<T>> {
  const res = await fetch(buildUrl(path, params), {
    signal,
    headers: { accept: 'application/json' },
  });
  await assertOk(res, path);
  const body = (await res.json()) as Envelope<T>;
  return { data: body.data, cachedAt: body.cached_at, source: body.source };
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
 * POST to the API. The routes carry the same `{data, cached_at, source}` envelope as
 * everything else, so the payload is unwrapped here and callers only ever see it.
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

/** GET on a route whose payload is the whole answer: enveloped, unwrapped here. */
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
