/**
 * One forwarder to the backend API, shared by the two routes that talk to it.
 *
 * `api/[...path].ts` forwards `/api/*` unchanged; `api/liveness.ts` forwards the single
 * path `/health`, which sits outside `/api` on the backend. Both go through {@link forward}
 * so the token, the timeout, the header allowlist and the no-store rule are decided once.
 *
 * ```
 *   browser ──▶ /api/records                (same origin — all it ever sees)
 *                 │  Vercel edge
 *                 │  + X-API-Key: API_UPSTREAM_TOKEN
 *                 ▼
 *              https://api.example.org/api/records         (never in the bundle)
 *                 │  TLS reverse proxy on the VPS
 *                 ▼
 *              127.0.0.1:8900  the API
 * ```
 *
 * `API_UPSTREAM_URL` and `API_UPSTREAM_TOKEN` are plain (not `VITE_`-prefixed) Vercel
 * environment variables, so Vite cannot inline them even by accident: `import.meta.env`
 * exposes only `VITE_*`.
 *
 * **Nothing it returns is cacheable.** The routes it forwards can serve private data,
 * so every reply carries `no-store, private` regardless of what upstream said. A CDN that
 * cached one would serve it to the next visitor — including one who arrives after the
 * password has changed.
 */

/** Long enough for a heavy query over the WAN; most routes return at once. */
export const UPSTREAM_TIMEOUT_MS = 30_000;

export const NO_STORE = { 'cache-control': 'no-store, private' } as const;

/**
 * Response headers copied from upstream.
 *
 * An allowlist, not a blocklist: the upstream's `set-cookie`, its CORS headers and its own
 * caching directives are all wrong for this origin, and a blocklist would forward whatever
 * gets added to it next.
 */
const PASSED_THROUGH = ['content-type', 'content-disposition', 'content-length', 'etag'];

/**
 * An error the dashboard can read.
 *
 * `{detail}` is FastAPI's error shape, which `src/api/client.ts` already unwraps — so a
 * proxy failure reaches the UI as a sentence, not as a bare status line.
 */
export function problem(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'content-type': 'application/json', ...NO_STORE },
  });
}

/** `https://host` + `/api/records` + `?id=42`, with no doubled slash. */
export function upstreamUrl(base: string, path: string, search = ''): string {
  return `${base.replace(/\/+$/, '')}${path}${search}`;
}

/**
 * True when `base` names a bare IP address rather than a hostname.
 *
 * The Edge runtime refuses to fetch one, and it does not do so as a catchable error: the
 * platform answers the request itself with
 * `403 Direct IP access is not allowed in Vercel's Edge environment`, in plain text, past
 * the try/catch below. That reaches the dashboard as an unexplained 403 on every panel.
 *
 * Checked up front so the reply says what to change instead. A server reachable only by
 * IP still works — give it any name that resolves to it (a hosting provider's default
 * reverse-DNS name is enough) and put that in `API_UPSTREAM_URL`.
 */
export function isBareIpHost(base: string): boolean {
  let host: string;
  try {
    host = new URL(base).hostname;
  } catch {
    return false; // not a URL at all — `forward` reports that through the fetch failure
  }
  // IPv6 arrives bracketed, so it is the one shape that cannot be a hostname either.
  if (host.startsWith('[')) return true;
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
}

/**
 * Forward one request upstream and return the reply, or a `{detail}` problem.
 *
 * Distinguishes the two failures that look identical from the browser: 502 "there is no
 * server there" and 504 "it took too long". `src/api/client.ts` treats both as unreachable
 * and falls back to the committed fixtures, so a backend that is down degrades the hosted
 * dashboard to offline data instead of breaking every page.
 */
export async function forward(
  request: Request,
  env: Record<string, string | undefined>,
  path: string,
  search = '',
): Promise<Response> {
  const base = env.API_UPSTREAM_URL ?? '';
  if (!base) {
    return problem(503, 'API_UPSTREAM_URL is not set in this Vercel project — see app/README.md');
  }
  if (isBareIpHost(base)) {
    return problem(
      503,
      'API_UPSTREAM_URL is a bare IP address, which the Edge runtime refuses to fetch. ' +
        'Use a hostname that resolves to the server instead.',
    );
  }

  const headers: Record<string, string> = {
    accept: request.headers.get('accept') ?? 'application/json',
  };
  const token = env.API_UPSTREAM_TOKEN;
  if (token) headers['X-API-Key'] = token;

  let body: string | undefined;
  if (request.method === 'POST') {
    headers['content-type'] = request.headers.get('content-type') ?? 'application/json';
    // Buffered rather than streamed: a streaming request body needs `duplex: 'half'`, and
    // every POST here is a small JSON job submission, never an upload.
    body = await request.text();
  }

  let upstream: Response;
  try {
    upstream = await fetch(upstreamUrl(base, path, search), {
      method: request.method,
      headers,
      body,
      redirect: 'manual',
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut = error instanceof Error && error.name === 'TimeoutError';
    return timedOut
      ? problem(504, `the viz API did not answer within ${UPSTREAM_TIMEOUT_MS / 1000}s`)
      : problem(502, 'the viz API is unreachable from this deployment');
  }

  if (upstream.status === 401) {
    return problem(502, 'the API rejected this deployment: API_UPSTREAM_TOKEN is wrong');
  }

  const out = new Headers(NO_STORE);
  for (const name of PASSED_THROUGH) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  // Streamed, so a figure PNG is not buffered in the function's memory.
  return new Response(upstream.body, { status: upstream.status, headers: out });
}
