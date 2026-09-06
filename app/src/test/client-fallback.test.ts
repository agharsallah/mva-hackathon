/**
 * The fixture-fallback rule, pinned.
 *
 * `get()` decides between "serve the committed fixture" and "let the user see the error",
 * and both mistakes are bad in different ways: falling back too eagerly hides a real API
 * answer behind invented rows, and falling back too rarely shows "Request failed" for a
 * server that is simply older than the app talking to it.
 *
 * These tests exist because the second mistake actually happened: /api/health/dependencies
 * returned 404 from an API process started before that route was written, and the page
 * rendered an error card instead of its fixture.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { get } from '../api/client';

/** A response shaped the way the real fetch wrapper reads one. */
function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    json: async () => body,
  } as Response;
}

const FIXTURED_PATH = '/api/overview';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('fixture fallback', () => {
  it('serves the fixture when no server is there at all', async () => {
    // A network-level failure is a TypeError, which is what the browser throws.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    const result = await get(FIXTURED_PATH);
    expect(result.origin).toBe('fixture');
  });

  it('serves the fixture when the running server has no such route', async () => {
    // FastAPI's default body for an unrouted path. This is the old-API case.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Not Found' })));
    const result = await get(FIXTURED_PATH);
    expect(result.origin).toBe('fixture');
  });

  it('serves the fixture on 501 Not Implemented', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(501, { detail: 'not implemented yet' })),
    );
    const result = await get(FIXTURED_PATH);
    expect(result.origin).toBe('fixture');
  });

  it('raises the endpoint’s own 404 instead of inventing rows', async () => {
    // The route exists and answered: "there is no such gene". The user must see that.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'unknown gene BRCA9' })),
    );
    await expect(get(FIXTURED_PATH)).rejects.toThrow('unknown gene BRCA9');
  });

  it('raises a 422 rather than papering over a bad request', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(422, { detail: 'lane 9 out of range' })),
    );
    await expect(get(FIXTURED_PATH)).rejects.toThrow('lane 9 out of range');
  });

  it("serves the fixture on the hosted proxy's 502 and 504", async () => {
    // The hosted deployment never sees a TypeError for a dead backend: the browser reaches
    // Vercel fine, and `app/server/upstream.ts` reports the failure as a status instead.
    for (const status of [502, 504]) {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(jsonResponse(status, { detail: 'the viz API is unreachable' })),
      );
      const result = await get(FIXTURED_PATH);
      expect(result.origin).toBe('fixture');
      vi.unstubAllGlobals();
    }
  });

  it('raises a 503 — "the read store is down" is a state the Probes page shows', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(503, { detail: 'reads API unreachable' })),
    );
    await expect(get(FIXTURED_PATH)).rejects.toThrow('reads API unreachable');
  });

  it('raises when the path has no fixture, whatever the failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Not Found' })));
    await expect(get('/api/not-a-real-endpoint')).rejects.toThrow();
  });
});
