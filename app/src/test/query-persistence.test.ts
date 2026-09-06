/**
 * What the dashboard is allowed to leave on a visitor's disk, pinned.
 *
 * The cache is persisted so a reload costs no API request. That makes the allowlist in
 * `src/lib/queryPersistence.ts` a data-perimeter control, not a performance knob: a path
 * that reaches it writes its payload to `localStorage`, where it outlives the tab, the
 * session cookie and the password. These tests fail if a coordinate-bearing endpoint ever
 * appears there, and if a liveness endpoint is ever cached across reloads — a stale "up"
 * is worse than no dot at all.
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { QueryClient } from '@tanstack/react-query';
import {
  type Persister,
  persistQueryClientRestore,
  persistQueryClientSave,
} from '@tanstack/react-query-persist-client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { STALE_TIME } from '../lib/queryClient';
import type { PersistableQuery } from '../lib/queryPersistence';
import {
  createPersister,
  PERSIST_KEY,
  PERSISTED_PATHS,
  persistOptions,
  shouldPersistQuery,
} from '../lib/queryPersistence';

/** Endpoints that carry a real patient position, or whose answer is about *now*. */
const NEVER_PERSISTED = [
  '/api/panel/locus',
  '/api/panel/het-pairs',
  '/api/panel/clinvar-presence',
  '/api/callset/region',
  '/api/search',
  '/api/health/dependencies',
  '/api/jobs',
  'health',
];

/** A query object with only the two fields the predicate reads. */
function query(queryKey: unknown[], status: 'success' | 'error' | 'pending' = 'success') {
  return { queryKey, state: { status } } satisfies PersistableQuery;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('the persisted-cache allowlist', () => {
  it.each(NEVER_PERSISTED)('never persists %s', (path) => {
    expect(PERSISTED_PATHS.has(path)).toBe(false);
    expect(shouldPersistQuery(query([path, null]))).toBe(false);
  });

  it('persists an aggregate endpoint', () => {
    expect(shouldPersistQuery(query(['/api/overview', null]))).toBe(true);
  });

  it('persists a parameterised entry under its own key', () => {
    expect(shouldPersistQuery(query(['/api/panel/gene-structure', { gene: 'BUB1B' }]))).toBe(true);
  });

  it('never persists a failed query — a restored error would outlive the outage', () => {
    expect(shouldPersistQuery(query(['/api/overview', null], 'error'))).toBe(false);
    expect(shouldPersistQuery(query(['/api/overview', null], 'pending'))).toBe(false);
  });

  it('never persists a key that is not a path', () => {
    expect(shouldPersistQuery(query([{ some: 'key' }]))).toBe(false);
  });

  it('names only endpoints the app actually calls', () => {
    const hooks = readFileSync(path.resolve(__dirname, '../api/hooks.ts'), 'utf-8');
    for (const path of PERSISTED_PATHS) {
      expect(hooks, `${path} is in the allowlist but no hook requests it`).toContain(`'${path}'`);
    }
  });
});

describe('the persister', () => {
  it('is null when storage refuses, so a private window still boots', () => {
    vi.stubGlobal('localStorage', {
      setItem: () => {
        throw new Error('SecurityError: the operation is insecure');
      },
      removeItem: () => undefined,
      getItem: () => null,
    });
    expect(createPersister()).toBeNull();
  });

  it('is null when there is no storage at all', () => {
    vi.stubGlobal('localStorage', undefined);
    expect(createPersister()).toBeNull();
  });

  it('leaves no probe key behind when storage works', () => {
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      setItem: (k: string, v: string) => store.set(k, v),
      removeItem: (k: string) => store.delete(k),
      getItem: (k: string) => store.get(k) ?? null,
    });
    expect(createPersister()).not.toBeNull();
    expect(store.size).toBe(0);
    expect(PERSIST_KEY).toMatch(/^mva-/);
  });

  it('fences a restored cache by build and by age', () => {
    expect(persistOptions.buster).toBeTruthy();
    expect(persistOptions.maxAge).toBe(24 * 60 * 60 * 1000);
  });
});

/**
 * The point of the whole mechanism, measured rather than asserted: a second session
 * against the same storage refetches only what the allowlist refused to persist.
 */
describe('what a reload costs', () => {
  /** A `Storage` that lives in this test, so the measurement is not jsdom's to keep. */
  function memoryStorage(): Storage {
    const map = new Map<string, string>();
    return {
      get length() {
        return map.size;
      },
      clear: () => map.clear(),
      getItem: (k) => map.get(k) ?? null,
      key: (i) => [...map.keys()][i] ?? null,
      removeItem: (k) => void map.delete(k),
      setItem: (k, v) => void map.set(k, v),
    } as Storage;
  }

  /**
   * Write the cache out and wait for it to land. The sync persister throttles its write
   * through a timer even at `throttleTime: 0`, so the store is empty for one tick after
   * `persistQueryClientSave` resolves.
   */
  async function save(
    client: QueryClient,
    persister: Persister,
    storage: Storage,
    buster = persistOptions.buster,
  ): Promise<void> {
    await persistQueryClientSave({ queryClient: client, persister, ...persistOptions, buster });
    await vi.waitFor(() => expect(storage.getItem(PERSIST_KEY)).not.toBeNull());
  }

  const PERSISTED = '/api/overview';
  const EXCLUDED = '/api/panel/locus';

  /** One session: fetch both paths through a fresh client, returning the fetch count. */
  async function session(
    persister: Persister,
    restore: boolean,
  ): Promise<{ client: QueryClient; fetches: number }> {
    let fetches = 0;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    if (restore)
      await persistQueryClientRestore({ queryClient: client, persister, ...persistOptions });
    for (const path of [PERSISTED, EXCLUDED]) {
      await client.fetchQuery({
        queryKey: [path, null],
        queryFn: () => {
          fetches += 1;
          return Promise.resolve({ data: [], cachedAt: null, source: 'test', origin: 'api' });
        },
        staleTime: STALE_TIME,
      });
    }
    return { client, fetches };
  }

  it('refetches only the endpoints it may not persist', async () => {
    const storage = memoryStorage();
    const persister = createSyncStoragePersister({ storage, key: PERSIST_KEY, throttleTime: 0 });

    const first = await session(persister, false);
    expect(first.fetches).toBe(2); // cold: both paths cost a request

    await save(first.client, persister, storage);
    expect(storage.getItem(PERSIST_KEY)).toContain(PERSISTED);
    expect(storage.getItem(PERSIST_KEY)).not.toContain(EXCLUDED);

    const second = await session(persister, true);
    expect(second.fetches).toBe(1); // reload: only the excluded path is asked again
  });

  it('ignores a cache written by another build', async () => {
    const storage = memoryStorage();
    const persister = createSyncStoragePersister({ storage, key: PERSIST_KEY, throttleTime: 0 });
    const first = await session(persister, false);
    await save(first.client, persister, storage, 'a-previous-deployment');

    const second = await session(persister, true);
    expect(second.fetches).toBe(2); // busted: the reload is as cold as a first visit
  });
});
