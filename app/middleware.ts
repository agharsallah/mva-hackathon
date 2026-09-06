/**
 * Vercel Routing Middleware — the password gate in front of the whole deployment.
 *
 * It runs before the CDN cache on every request, so nothing the dashboard is built from
 * leaves the edge without a valid session: not `index.html`, not the JavaScript chunks,
 * not a figure PNG. That is the difference between gating the app and gating a route
 * inside it — an SPA route would have already shipped the bundle before it could refuse.
 *
 * ```
 *   request ──▶ middleware ──┬── valid session ──▶ next()  (the SPA, the proxy, assets)
 *                            ├── /api/login    ──▶ next()  (the one open route)
 *                            ├── document      ──▶ 401 + the password page
 *                            └── anything else ──▶ 401 JSON
 * ```
 *
 * **Fail closed.** With `DASHBOARD_PASSWORD` or `DASHBOARD_SESSION_SECRET` missing, the
 * deployment is misconfigured, and a misconfigured private dashboard must be unreachable
 * rather than public — so it answers 503 and says which variable is missing. That is also
 * what a local `vercel dev` without `vercel env pull` will show.
 *
 * The gate is not the only check: `api/[...path].ts` verifies the session again before it
 * forwards anything upstream. Middleware alone is one deployment-config mistake away from
 * being skipped, and the proxy is the route that reaches patient data.
 */

import { next } from '@vercel/functions';

import { loginPage, safeNext } from './server/loginPage';
import { hasSession, sessionConfig } from './server/session';

export const config = {
  /**
   * Everything except the login route itself and Vercel's own paths. `/api/login` must
   * stay open or the password could never be submitted; `/api/logout` is harmless either
   * way and is excluded so signing out works from an expired session.
   */
  matcher: ['/((?!api/login|api/logout|_vercel/).*)'],
  runtime: 'edge',
};

/** True when the browser is navigating (wants a page), rather than fetching data. */
function wantsHtml(request: Request): boolean {
  if (request.headers.get('sec-fetch-mode') === 'navigate') return true;
  return (request.headers.get('accept') ?? '').includes('text/html');
}

function unconfigured(missing: string[]): Response {
  return new Response(
    `This dashboard is password-protected but not configured: ${missing.join(' and ')} ` +
      `${missing.length > 1 ? 'are' : 'is'} not set in the Vercel project.`,
    { status: 503, headers: { 'content-type': 'text/plain; charset=utf-8', ...NO_STORE } },
  );
}

/** Nothing behind the gate is cacheable by a shared cache — not even a 401. */
const NO_STORE = { 'cache-control': 'no-store, private' } as const;

export default async function middleware(request: Request): Promise<Response> {
  const env = process.env as Record<string, string | undefined>;
  if (!sessionConfig(env)) {
    const missing = [
      env.DASHBOARD_PASSWORD ? '' : 'DASHBOARD_PASSWORD',
      env.DASHBOARD_SESSION_SECRET ? '' : 'DASHBOARD_SESSION_SECRET',
    ].filter(Boolean);
    return unconfigured(missing);
  }

  if (await hasSession(request, env)) return next();

  const url = new URL(request.url);
  if (!wantsHtml(request)) {
    return new Response(JSON.stringify({ detail: 'authentication required' }), {
      status: 401,
      headers: { 'content-type': 'application/json', ...NO_STORE },
    });
  }
  return new Response(loginPage({ next: safeNext(url.pathname + url.search) }), {
    // 401, not 200: the page IS the refusal. It also keeps crawlers and the CDN off it.
    status: 401,
    headers: { 'content-type': 'text/html; charset=utf-8', ...NO_STORE },
  });
}
