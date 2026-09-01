/**
 * The fixture layer answers exactly what it answered before the rows moved to JSON.
 *
 * `fixtureHashes.json` was produced from the pre-refactor TypeScript fixtures: one
 * sha256 prefix per request in `fixtureMatrix.ts`, over `JSON.stringify(envelope)`. A
 * changed hash means an offline payload changed — which is either a bug in the loading
 * layer or a deliberate data edit that has to be re-blessed on purpose.
 */

import { createHash } from 'node:crypto';

import { describe, expect, it } from 'vitest';

import { fixtureFor, fixturePaths } from '../fixtures';
import hashes from './fixtureHashes.json';
import { key, MATRIX } from './fixtureMatrix';

const digest = (v: unknown): string =>
  createHash('sha256').update(JSON.stringify(v)).digest('hex').slice(0, 16);

describe('fixture payloads', () => {
  it.each(MATRIX)('%s %j is unchanged', async (path, params) => {
    const k = key(path, params);
    const envelope = (await fixtureFor(path, params)) ?? null;
    expect(digest(envelope)).toBe((hashes as Record<string, string>)[k]);
  });

  it('every registered path is exercised by the matrix', () => {
    const covered = new Set(MATRIX.map(([path]) => path));
    expect(fixturePaths().filter((p) => !covered.has(p))).toEqual([]);
  });

  it('serves nothing for an unknown path, so the client re-raises the real error', async () => {
    await expect(fixtureFor('/api/not-a-real-endpoint')).resolves.toBeUndefined();
  });
});
