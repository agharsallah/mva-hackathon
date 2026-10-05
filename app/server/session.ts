/**
 * The signed session cookie behind the hosted dashboard's password gate.
 *
 * This module runs ONLY on Vercel — in `middleware.ts` and in `api/*.ts`, never in the
 * browser bundle. Vite bundles `src/` and nothing else, so nothing here reaches a client.
 *
 * ## The shape
 *
 * The cookie is `<expiry>.<signature>`: an expiry in unix seconds, and an HMAC-SHA256 of
 * that expiry under a key the server holds. There is no session store — the cookie is the
 * whole session, and it is trustworthy because forging one means forging the HMAC.
 *
 * ```
 *   cookie   dash_session=1757260800.k7Qf...T4
 *                     └─ expiry ─┘ └ signature ┘
 *   key      DASHBOARD_SESSION_SECRET + ":" + DASHBOARD_PASSWORD
 *   message  "v1:1757260800"
 * ```
 *
 * The password is folded into the key on purpose: **changing `DASHBOARD_PASSWORD` in the
 * Vercel project invalidates every cookie already issued.** With the secret alone, a
 * password rotation would leave anyone who logged in before it still inside.
 *
 * ## What it is not
 *
 * One shared password, so a session identifies "someone who knew the password", never a
 * person — there is no user, no role and no audit trail of who looked at what. That is the
 * right level for a small private dashboard and wrong for anything else.
 *
 * Two comparisons here are constant-time ({@link timingSafeEqual}). A plain `===` returns
 * as soon as two characters differ, so its duration leaks how much of a guess was correct.
 */

/** How long a login lasts. Short enough that a borrowed laptop stops working by morning. */
export const SESSION_TTL_SECONDS = 12 * 60 * 60;

export const COOKIE_NAME = 'dash_session';

/** The signed-message version, so the format can change without accepting old cookies. */
const VERSION = 'v1';

const encoder = new TextEncoder();

export interface SessionConfig {
  password: string;
  secret: string;
}

/**
 * The gate's configuration, or `null` when it is not configured.
 *
 * A missing password is never treated as "no password needed": {@link isConfigured} is
 * false and the caller must fail closed. An unconfigured deployment that served the
 * dashboard to everyone would be exactly the accident this file exists to prevent.
 */
export function sessionConfig(env: Record<string, string | undefined>): SessionConfig | null {
  const password = env.DASHBOARD_PASSWORD ?? '';
  const secret = env.DASHBOARD_SESSION_SECRET ?? '';
  if (!password || !secret) return null;
  return { password, secret };
}

function key(config: SessionConfig): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    encoder.encode(`${config.secret}:${config.password}`),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}

/** URL-safe base64 of the raw HMAC — `+/=` would need escaping in a cookie value. */
async function sign(config: SessionConfig, message: string): Promise<string> {
  const mac = await crypto.subtle.sign('HMAC', await key(config), encoder.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(mac)))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '');
}

/** Compare two strings in time that does not depend on where they first differ. */
export function timingSafeEqual(a: string, b: string): boolean {
  // Length is not secret — a wrong-length guess is rejected either way — but the loop
  // below must still run over a fixed span, so it walks the longer of the two.
  const span = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let i = 0; i < span; i += 1) diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return diff === 0;
}

/** True when `attempt` is the configured password. */
export function passwordMatches(config: SessionConfig, attempt: string): boolean {
  return timingSafeEqual(attempt, config.password);
}

/** Mint a cookie value that expires `SESSION_TTL_SECONDS` from now. */
export async function issue(config: SessionConfig, now = Date.now()): Promise<string> {
  const expiry = Math.floor(now / 1000) + SESSION_TTL_SECONDS;
  return `${expiry}.${await sign(config, `${VERSION}:${expiry}`)}`;
}

/** True when `value` is a cookie this server signed and it has not expired. */
export async function isValid(
  config: SessionConfig,
  value: string | undefined,
  now = Date.now(),
): Promise<boolean> {
  if (!value) return false;
  const separator = value.indexOf('.');
  if (separator < 1) return false;
  const expiry = value.slice(0, separator);
  const signature = value.slice(separator + 1);
  if (!/^\d{1,15}$/.test(expiry)) return false;
  if (Number(expiry) * 1000 <= now) return false;
  return timingSafeEqual(signature, await sign(config, `${VERSION}:${expiry}`));
}

/** Read one cookie out of a request's `Cookie` header. */
export function readCookie(request: Request, name: string): string | undefined {
  const header = request.headers.get('cookie');
  if (!header) return undefined;
  for (const part of header.split(';')) {
    const eq = part.indexOf('=');
    if (eq < 0) continue;
    if (part.slice(0, eq).trim() === name) return decodeURIComponent(part.slice(eq + 1).trim());
  }
  return undefined;
}

/**
 * The `Set-Cookie` value for a session.
 *
 * `HttpOnly` keeps it out of `document.cookie`, so a cross-site script cannot read it.
 * `Secure` keeps it off plain HTTP. `SameSite=Lax` means another site's form post does
 * not carry it, which is the whole CSRF surface here — there is no state-changing route
 * beyond login and logout.
 */
export function cookieHeader(value: string, maxAge: number): string {
  return [
    `${COOKIE_NAME}=${value}`,
    'Path=/',
    `Max-Age=${maxAge}`,
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
  ].join('; ');
}

/** True when this request already carries a valid session. */
export async function hasSession(
  request: Request,
  env: Record<string, string | undefined>,
): Promise<boolean> {
  const config = sessionConfig(env);
  if (!config) return false;
  return isValid(config, readCookie(request, COOKIE_NAME));
}
