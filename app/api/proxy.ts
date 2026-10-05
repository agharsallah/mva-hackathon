/**
 * The API proxy — every `/api/*` request the dashboard makes, forwarded to the backend.
 *
 * The browser must never learn where the backend is. Before this, the bundle carried
 * `VITE_API_URL` and the browser opened a connection straight to the backend, which put
 * the API's hostname, its port and (once it had one) its token in devtools for anyone who
 * got past the password. Now the only address in the bundle is this origin's own.
 *
 * The forwarding itself lives in `server/upstream.ts`, shared with `api/liveness.ts`.
 *
 * ## Why the path arrives in a query parameter
 *
 * This was `api/[...path].ts`, relying on Vercel's catch-all route to match every depth
 * under `/api/`. It does not: on a deployed Vite project the segment expands like a single
 * `[path]`, so `/api/overview` reached the function and `/api/health/dependencies` came
 * back `x-vercel-error: NOT_FOUND` — measured on a live deployment, not assumed.
 *
 * So the routing is explicit instead. `vercel.json` rewrites `/api/:path*` here with the
 * original path in `?upstream=`, and the filesystem check that runs *before* rewrites is
 * what keeps `/api/proxy`, `/api/login`, `/api/logout` and `/api/liveness` reaching their
 * own functions rather than looping through this one.
 *
 * ## It re-checks the session
 *
 * `middleware.ts` already refused an unauthenticated request, and this checks again anyway.
 * This is the one route that reaches private data; a matcher edited wrongly, or a future
 * change in how Vercel orders routing, must not be the only thing standing between the
 * public and every data route.
 */

import { hasSession } from '../server/session';
import { forward, problem } from '../server/upstream';

export const config = { runtime: 'edge' };

/** The query parameter `vercel.json` puts the original path in. */
const PATH_PARAM = 'upstream';

/**
 * A path this proxy is allowed to forward, or `null`.
 *
 * Narrow on purpose. The value arrives in a query string, so a caller can set it directly
 * rather than letting the rewrite do it; without this, `?upstream=/api/../../something`
 * would let them steer the request at any path on the backend host.
 */
export function safeUpstreamPath(raw: string | null): string | null {
  if (!raw || !raw.startsWith('/api/')) return null;
  if (raw.includes('..') || raw.includes('//')) return null;
  return /^\/api\/[A-Za-z0-9\-._~/]*$/.test(raw) ? raw : null;
}

/**
 * The request's own query, minus the routing parameter.
 *
 * `?id=42` must survive; `?upstream=` is this layer's plumbing and would be an
 * unknown parameter to FastAPI.
 */
export function forwardedSearch(url: URL): string {
  const params = new URLSearchParams(url.searchParams);
  params.delete(PATH_PARAM);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export default async function handler(request: Request): Promise<Response> {
  const env = process.env as Record<string, string | undefined>;
  if (!(await hasSession(request, env))) return problem(401, 'authentication required');

  const incoming = new URL(request.url);
  // The rewrite supplies `upstream`; the pathname is the fallback for a direct hit on
  // /api/proxy, which is only reachable by someone typing it.
  const raw = incoming.searchParams.get(PATH_PARAM) ?? incoming.pathname;
  const path = safeUpstreamPath(raw);
  if (!path) return problem(400, `not a forwardable API path: ${raw}`);

  return forward(request, env, path, forwardedSearch(incoming));
}
