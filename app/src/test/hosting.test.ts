// @vitest-environment node
/**
 * The hosting layer: the signed session cookie, and the redirect guard on the login page.
 *
 * Node environment, not jsdom — `server/session.ts` signs with WebCrypto (`crypto.subtle`),
 * which is what the Vercel Edge runtime gives it and what Node exposes natively.
 *
 * These are the two places where a mistake is silent rather than loud: a cookie that
 * verifies when it should not lets a stranger into the dashboard, and a `next` parameter
 * that is not checked turns the login page into an open redirect.
 */

import { describe, expect, it } from 'vitest';

import { loginPage, safeNext } from '../../server/loginPage';
import {
  cookieHeader,
  hasSession,
  issue,
  isValid,
  passwordMatches,
  SESSION_TTL_SECONDS,
  sessionConfig,
  timingSafeEqual,
} from '../../server/session';

const CONFIG = { password: 'correct horse battery staple', secret: 'a-signing-secret' };

function requestWithCookie(value: string): Request {
  return new Request('https://dash.example/api/overview', {
    headers: { cookie: `mva_dash=${value}` },
  });
}

describe('sessionConfig', () => {
  it('is null when either variable is missing, so the caller fails closed', () => {
    expect(sessionConfig({})).toBeNull();
    expect(sessionConfig({ DASHBOARD_PASSWORD: 'p' })).toBeNull();
    expect(sessionConfig({ DASHBOARD_SESSION_SECRET: 's' })).toBeNull();
  });

  it('reads both variables when both are set', () => {
    expect(sessionConfig({ DASHBOARD_PASSWORD: 'p', DASHBOARD_SESSION_SECRET: 's' })).toEqual({
      password: 'p',
      secret: 's',
    });
  });
});

describe('timingSafeEqual', () => {
  it('is a correct equality test, whatever its timing', () => {
    expect(timingSafeEqual('abc', 'abc')).toBe(true);
    expect(timingSafeEqual('abc', 'abd')).toBe(false);
    expect(timingSafeEqual('abc', 'abcd')).toBe(false);
    expect(timingSafeEqual('', '')).toBe(true);
  });
});

describe('the session cookie', () => {
  it('verifies a cookie it just issued', async () => {
    expect(await isValid(CONFIG, await issue(CONFIG))).toBe(true);
  });

  it('rejects a tampered signature', async () => {
    const [expiry] = (await issue(CONFIG)).split('.');
    expect(await isValid(CONFIG, `${expiry}.forged`)).toBe(false);
  });

  it('rejects a cookie whose expiry was pushed forward', async () => {
    const [expiry, signature] = (await issue(CONFIG)).split('.');
    expect(await isValid(CONFIG, `${Number(expiry) + 86_400}.${signature}`)).toBe(false);
  });

  it('rejects an expired cookie', async () => {
    const cookie = await issue(CONFIG);
    const later = Date.now() + (SESSION_TTL_SECONDS + 60) * 1000;
    expect(await isValid(CONFIG, cookie, later)).toBe(false);
  });

  it('rejects malformed values instead of throwing', async () => {
    for (const value of ['', '.', 'nodot', '.sig', 'abc.sig', `${'9'.repeat(30)}.sig`]) {
      expect(await isValid(CONFIG, value)).toBe(false);
    }
    expect(await isValid(CONFIG, undefined)).toBe(false);
  });

  it('stops verifying once the password changes — a rotation logs everyone out', async () => {
    const cookie = await issue(CONFIG);
    expect(await isValid({ ...CONFIG, password: 'a new password' }, cookie)).toBe(false);
  });

  it('stops verifying once the signing secret changes', async () => {
    const cookie = await issue(CONFIG);
    expect(await isValid({ ...CONFIG, secret: 'rotated' }, cookie)).toBe(false);
  });
});

describe('passwordMatches', () => {
  it('accepts only the exact password', () => {
    expect(passwordMatches(CONFIG, CONFIG.password)).toBe(true);
    expect(passwordMatches(CONFIG, CONFIG.password.toUpperCase())).toBe(false);
    expect(passwordMatches(CONFIG, '')).toBe(false);
  });
});

describe('cookieHeader', () => {
  it('carries the three flags that keep it out of scripts, plain HTTP and cross-site posts', () => {
    const header = cookieHeader('value', SESSION_TTL_SECONDS);
    expect(header).toContain('HttpOnly');
    expect(header).toContain('Secure');
    expect(header).toContain('SameSite=Lax');
    expect(header).toContain('Path=/');
  });

  it('expires the cookie at Max-Age=0, on the same path, so logout really removes it', () => {
    expect(cookieHeader('', 0)).toContain('Max-Age=0');
    expect(cookieHeader('', 0)).toContain('Path=/');
  });
});

describe('hasSession', () => {
  it('is false when the gate is not configured, however good the cookie looks', async () => {
    const cookie = await issue(CONFIG);
    expect(await hasSession(requestWithCookie(cookie), {})).toBe(false);
  });

  it('reads the cookie out of the header when the gate is configured', async () => {
    const env = {
      DASHBOARD_PASSWORD: CONFIG.password,
      DASHBOARD_SESSION_SECRET: CONFIG.secret,
    };
    expect(await hasSession(requestWithCookie(await issue(CONFIG)), env)).toBe(true);
    expect(await hasSession(requestWithCookie('nonsense'), env)).toBe(false);
    expect(await hasSession(new Request('https://dash.example/'), env)).toBe(false);
  });
});

describe('safeNext', () => {
  it('keeps a same-origin path', () => {
    expect(safeNext('/track2?tab=drugs')).toBe('/track2?tab=drugs');
  });

  it('refuses anything that could leave this origin', () => {
    for (const hostile of [
      '//evil.example',
      '/\\evil.example',
      'https://evil.example',
      'javascript:alert(1)',
      '',
      null,
      undefined,
    ]) {
      expect(safeNext(hostile)).toBe('/');
    }
  });
});

describe('loginPage', () => {
  it('escapes what it reflects back, so `next` cannot inject markup', () => {
    const html = loginPage({ next: '/a"><script>alert(1)</script>', error: '<b>no</b>' });
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;b&gt;no&lt;/b&gt;');
  });

  it('tells crawlers to stay out', () => {
    expect(loginPage({ next: '/' })).toContain('noindex');
  });
});
