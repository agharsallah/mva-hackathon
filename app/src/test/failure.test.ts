/**
 * The two pure decisions behind every failure the app shows: which of seven failures this
 * error *is* (`classifyError`), and whether it is worth asking again (`shouldRetry`).
 *
 * Both are tested without a DOM because both are the reason the DOM says what it says: the
 * kind picks the sentence and the remedy in `ErrorCard`, and the retry predicate decides
 * whether the reader ever sees that card at all. Order matters in `classifyError` — 503 is
 * checked before "any 5xx", and a cancelled request before a network `TypeError` — so the
 * cases below pin the overlaps, not just one representative per branch.
 */

import { describe, expect, it } from 'vitest';

import { API_LABEL, ApiError } from '../api/client';
import { classifyError } from '../components/failure';
import { shouldRetry } from '../lib/queryClient';

/** An error carrying a name rather than a type — how `fetch` reports a cancelled request. */
function abortError(): Error {
  const e = new Error('The operation was aborted.');
  e.name = 'AbortError';
  return e;
}

describe('classifyError', () => {
  it('reads a 503 as the upstream reads service being down, not as a server fault', () => {
    const f = classifyError(new ApiError('reads API unreachable', 503, '/api/reads/job'));
    expect(f.kind).toBe('upstream-down');
    expect(f.title).toMatch(/reads service/i);
  });

  it('reads a 404 as an endpoint the running API does not have', () => {
    const f = classifyError(new ApiError('Not Found', 404, '/api/health/dependencies'));
    expect(f.kind).toBe('route-missing');
    expect(f.command).toBe('uv run mva-viz-api');
  });

  it('reads a 501 the same way — not implemented is also a route this build knows and that one does not', () => {
    expect(classifyError(new ApiError('Not Implemented', 501, '/api/x')).kind).toBe(
      'route-missing',
    );
  });

  it("reads FastAPI's bare 'Not Found' body as route-missing whatever status carried it", () => {
    // The message test sits beside the status test, so an ApiError whose body is exactly
    // the framework's default sentence classifies as route-missing even off 404/501.
    expect(classifyError(new ApiError('Not Found', 400, '/api/x')).kind).toBe('route-missing');
  });

  it("does NOT read a plain Error('Not Found') as route-missing — only an ApiError can be one", () => {
    // Deliberate: the whole branch is guarded on `error instanceof ApiError`, matching
    // `api/client.ts`'s `isRouteMissing`. A bare Error carrying that text did not come
    // from a server answer and must not claim a server diagnosis.
    expect(classifyError(new Error('Not Found')).kind).toBe('unknown');
  });

  it('reads a 422 as the API rejecting this query', () => {
    const f = classifyError(new ApiError('lane must be one of …', 422, '/api/callset/region'));
    expect(f.kind).toBe('bad-request');
    expect(f.remedy).toMatch(/selection/i);
  });

  it('reads a 500 as the API failing while answering', () => {
    expect(classifyError(new ApiError('internal error', 500, '/api/panel')).kind).toBe(
      'server-fault',
    );
  });

  it("reads a fetch TypeError as 'no API answered', and names the URL it tried", () => {
    const f = classifyError(new TypeError('Failed to fetch'));
    expect(f.kind).toBe('unreachable');
    expect(f.title).toContain(API_LABEL);
    expect(f.command).toBe('uv run mva-viz-api');
  });

  it('reads an AbortError as a cancelled request, not as a dead API', () => {
    expect(classifyError(abortError()).kind).toBe('aborted');
  });

  it('falls back to unknown rather than guessing', () => {
    const f = classifyError(new Error('something nobody anticipated'));
    expect(f.kind).toBe('unknown');
    expect(f.title).toBe('Request failed');
  });

  it('always produces a title and an explanation, whatever the kind', () => {
    const errors: Error[] = [
      new ApiError('x', 503, '/a'),
      new ApiError('Not Found', 404, '/a'),
      new ApiError('x', 422, '/a'),
      new ApiError('x', 500, '/a'),
      new TypeError('Failed to fetch'),
      abortError(),
      new Error('x'),
    ];
    const kinds = errors.map((e) => classifyError(e).kind);
    expect(new Set(kinds).size).toBe(7); // all seven kinds are reachable
    for (const e of errors) {
      const f = classifyError(e);
      expect(f.title.length).toBeGreaterThan(0);
      expect(f.explain.length).toBeGreaterThan(0);
    }
  });
});

describe('shouldRetry', () => {
  it('gives up after two attempts, whatever the error', () => {
    expect(shouldRetry(2, new TypeError('Failed to fetch'))).toBe(false);
    expect(shouldRetry(2, new ApiError('x', 500, '/a'))).toBe(false);
  });

  it('never retries a 4xx — the API said no to this exact request', () => {
    expect(shouldRetry(0, new ApiError('Not Found', 404, '/a'))).toBe(false);
    expect(shouldRetry(0, new ApiError('bad lane', 422, '/a'))).toBe(false);
    expect(shouldRetry(1, new ApiError('bad lane', 400, '/a'))).toBe(false);
  });

  it('retries a 5xx — the API may be restarting', () => {
    expect(shouldRetry(0, new ApiError('internal error', 500, '/a'))).toBe(true);
    expect(shouldRetry(1, new ApiError('reads down', 503, '/a'))).toBe(true);
  });

  it('retries a network failure on both attempts it is allowed', () => {
    expect(shouldRetry(0, new TypeError('Failed to fetch'))).toBe(true);
    expect(shouldRetry(1, new TypeError('Failed to fetch'))).toBe(true);
  });
});

describe('classifyError — the API answered but refused', () => {
  it('reads a 401 as authorisation, not as a bad parameter', () => {
    const f = classifyError(new ApiError('missing or wrong X-API-Key', 401, '/api/overview'));
    expect(f.kind).toBe('unauthorized');
    // The old classifier fell through to the generic 4xx and told the reader to change a
    // selection that was never the problem. Observed on a dev build pointed at the
    // deployed API: 401 on every panel, "Usually a selection in the URL no longer matches".
    expect(f.explain).not.toMatch(/parameters were refused/);
    expect(f.remedy).toMatch(/VITE_/);
  });

  it('reads a 403 the same way', () => {
    expect(classifyError(new ApiError('Forbidden', 403, '/api/overview')).kind).toBe(
      'unauthorized',
    );
  });

  it('still reads a 422 as a bad request', () => {
    expect(classifyError(new ApiError('lane must be one of …', 422, '/api/x')).kind).toBe(
      'bad-request',
    );
  });
});
