// @vitest-environment node
/**
 * How the proxy decides which upstream path to forward.
 *
 * The path arrives in a query parameter because Vercel's catch-all route did not hold:
 * `api/[...path].ts` matched `/api/overview` but answered `x-vercel-error: NOT_FOUND` for
 * `/api/health/dependencies` on a live deployment. `vercel.json` now rewrites `/api/:path*`
 * to `/api/proxy?upstream=/api/:path*`, which makes two things this file pins:
 *
 * - the value is attacker-reachable (anyone can call `/api/proxy?upstream=…` directly), so
 *   it is validated rather than trusted — otherwise it steers the request at any path on
 *   the backend host;
 * - the routing parameter must not be forwarded, while the request's real query must be.
 */

import { describe, expect, it } from 'vitest';

import { forwardedSearch, safeUpstreamPath } from '../../api/proxy';

describe('safeUpstreamPath', () => {
  it('accepts the paths the dashboard actually calls, at any depth', () => {
    for (const path of [
      '/api/overview',
      '/api/health/dependencies',
      '/api/callset/observed-expected',
      '/api/submissions/track1/1/figure/karyogram',
      '/api/panel/locus',
    ]) {
      expect(safeUpstreamPath(path)).toBe(path);
    }
  });

  it('refuses anything that could steer the request off the API surface', () => {
    for (const hostile of [
      '/api/../admin',
      '/api/x/../../secret',
      '/api//evil.example',
      '/health',
      '/',
      'https://evil.example/api/x',
      '//evil.example/api/x',
      '',
      null,
    ]) {
      expect(safeUpstreamPath(hostile)).toBeNull();
    }
  });
});

describe('forwardedSearch', () => {
  it('drops the routing parameter and keeps the real query', () => {
    const url = new URL('https://dash.example/api/proxy?upstream=/api/panel/genes&gene=BUB1B');
    expect(forwardedSearch(url)).toBe('?gene=BUB1B');
  });

  it('is empty when the request carried no query of its own', () => {
    expect(forwardedSearch(new URL('https://dash.example/api/proxy?upstream=/api/overview'))).toBe(
      '',
    );
  });

  it('keeps every parameter, not just the first', () => {
    const url = new URL('https://dash.example/api/proxy?upstream=/api/reads/runs&lane=1&read=2');
    expect(forwardedSearch(url)).toBe('?lane=1&read=2');
  });
});
