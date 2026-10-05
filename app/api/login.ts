/**
 * `POST /api/login` — exchange the shared password for a signed session cookie.
 *
 * The one route `middleware.ts` lets through unauthenticated, so it is the only place an
 * attacker can guess. Three things narrow that:
 *
 * - the comparison is constant-time (`timingSafeEqual` in `server/session.ts`), so the
 *   response time says nothing about how much of a guess was right;
 * - a wrong password costs a fixed ~400 ms before it answers, which turns an online
 *   guessing run into hours per thousand attempts;
 * - the reply is the same 401 for every wrong value — it never says "no such user".
 *
 * What it is *not*: rate limiting. Vercel Functions are stateless and a per-instance
 * counter is defeated by concurrency, so the delay above is the whole defence. A password
 * with real entropy is doing the work here — generate one, do not choose one.
 * `vercel firewall` rate-limiting rules are the upgrade path if this is ever more than a
 * private dashboard.
 *
 * Accepts JSON (the login page's `fetch`) or a form post (its no-JavaScript fallback) and
 * answers in kind: JSON gets `{next}`, a form gets a 303 to the same place.
 */

import { safeNext } from '../server/loginPage';
import {
  cookieHeader,
  issue,
  passwordMatches,
  SESSION_TTL_SECONDS,
  sessionConfig,
} from '../server/session';

export const config = { runtime: 'edge' };

/** Fixed cost of a rejected attempt. Long enough to matter, short enough not to time out. */
const WRONG_PASSWORD_DELAY_MS = 400;

const NO_STORE = { 'cache-control': 'no-store, private' } as const;

interface Attempt {
  password: string;
  next: string;
  wantsJson: boolean;
}

async function readAttempt(request: Request): Promise<Attempt> {
  const type = request.headers.get('content-type') ?? '';
  if (type.includes('application/json')) {
    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
    return {
      password: typeof body.password === 'string' ? body.password : '',
      next: safeNext(typeof body.next === 'string' ? body.next : '/'),
      wantsJson: true,
    };
  }
  const form = await request.formData().catch(() => new FormData());
  return {
    password: String(form.get('password') ?? ''),
    next: safeNext(String(form.get('next') ?? '/')),
    wantsJson: false,
  };
}

export default async function handler(request: Request): Promise<Response> {
  if (request.method !== 'POST') {
    return new Response(JSON.stringify({ detail: 'POST only' }), {
      status: 405,
      headers: { 'content-type': 'application/json', allow: 'POST', ...NO_STORE },
    });
  }

  const settings = sessionConfig(process.env as Record<string, string | undefined>);
  if (!settings) {
    return new Response(JSON.stringify({ detail: 'the password gate is not configured' }), {
      status: 503,
      headers: { 'content-type': 'application/json', ...NO_STORE },
    });
  }

  const attempt = await readAttempt(request);
  if (!passwordMatches(settings, attempt.password)) {
    await new Promise((resolve) => setTimeout(resolve, WRONG_PASSWORD_DELAY_MS));
    return new Response(JSON.stringify({ detail: 'Wrong password.' }), {
      status: 401,
      headers: { 'content-type': 'application/json', ...NO_STORE },
    });
  }

  const cookie = cookieHeader(await issue(settings), SESSION_TTL_SECONDS);
  if (attempt.wantsJson) {
    return new Response(JSON.stringify({ next: attempt.next }), {
      status: 200,
      headers: { 'content-type': 'application/json', 'set-cookie': cookie, ...NO_STORE },
    });
  }
  // 303 so the browser follows with GET — a 302 would repeat the POST at the target.
  return new Response(null, {
    status: 303,
    headers: { location: attempt.next, 'set-cookie': cookie, ...NO_STORE },
  });
}
