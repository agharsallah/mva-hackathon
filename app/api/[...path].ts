/**
 * The API proxy — every `/api/*` request the dashboard makes, forwarded to `mva-viz-api`.
 *
 * The browser must never learn where the backend is. Before this, the bundle carried
 * `VITE_API_URL` and the browser opened a connection straight to `mva-viz-api`, which put
 * the API's hostname, its port and (once it had one) its token in devtools for anyone who
 * got past the password. Now the only address in the bundle is this origin's own.
 *
 * The forwarding itself lives in `server/upstream.ts`, shared with `api/liveness.ts`.
 *
 * **It re-checks the session.** `middleware.ts` already refused an unauthenticated
 * request, and this checks again anyway. This is the one route that reaches patient data;
 * a matcher edited wrongly, or a future change in how Vercel orders routing, must not be
 * the only thing standing between the public and `/api/panel/locus`.
 */

import { hasSession } from '../server/session';
import { forward, problem } from '../server/upstream';

export const config = { runtime: 'edge' };

export default async function handler(request: Request): Promise<Response> {
  const env = process.env as Record<string, string | undefined>;
  if (!(await hasSession(request, env))) return problem(401, 'authentication required');

  const incoming = new URL(request.url);
  return forward(request, env, incoming.pathname, incoming.search);
}
