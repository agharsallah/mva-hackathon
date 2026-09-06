/**
 * `GET|POST /api/logout` — drop the session cookie and land back on the password page.
 *
 * Expiring the cookie is the whole logout: there is no server-side session to delete,
 * because the cookie *is* the session (`server/session.ts`). GET is allowed so the app
 * can offer a plain link; the cookie is `SameSite=Lax`, so a cross-site request cannot
 * carry it and the worst a forged GET can do is sign someone out.
 */

import { cookieHeader } from '../server/session';

export const config = { runtime: 'edge' };

export default function handler(): Response {
  return new Response(null, {
    status: 303,
    headers: {
      location: '/',
      // Max-Age=0 with the same Path and flags is what actually removes it; a cookie
      // that differs in Path is a *second* cookie, and the old one keeps working.
      'set-cookie': cookieHeader('', 0),
      'cache-control': 'no-store, private',
    },
  });
}
