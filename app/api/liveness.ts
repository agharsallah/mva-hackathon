/**
 * `GET /health` — the backend's liveness probe, behind the same proxy as everything else.
 *
 * The header's status dot calls `/health`, and on `mva-viz-api` that path sits *outside*
 * `/api` (it is the one route with no token guard, so an uptime probe carries no secret).
 * The catch-all proxy only matches `/api/*`, so `vercel.json` rewrites `/health` here and
 * this file maps it back to the upstream `/health`.
 *
 * It answers `{ok: false}` rather than a proxy error when the backend is down: the dot is
 * a status indicator, and "the API is not answering" is a status, not a failed request.
 */

import { hasSession } from '../server/session';
import { forward, NO_STORE, problem } from '../server/upstream';

export const config = { runtime: 'edge' };

export default async function handler(request: Request): Promise<Response> {
  const env = process.env as Record<string, string | undefined>;
  if (!(await hasSession(request, env))) return problem(401, 'authentication required');

  const reply = await forward(request, env, '/health');
  if (reply.ok) return reply;
  return new Response(JSON.stringify({ ok: false, service: 'mva-viz-api' }), {
    status: 200,
    headers: { 'content-type': 'application/json', ...NO_STORE },
  });
}
