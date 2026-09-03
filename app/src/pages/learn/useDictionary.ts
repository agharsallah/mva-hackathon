/**
 * The dictionary, loaded once per session. Not a React Query hook: the JSON is a build
 * artifact bundled with the app, so there is nothing to refetch, cache-expire or fall back
 * to — one module-level promise is the whole cache.
 */

import { useEffect, useState } from 'react';

import { type Dictionary, loadDictionary } from '../../lib/dictionary';

let pending: Promise<Dictionary> | null = null;
let loaded: Dictionary | null = null;

function load(): Promise<Dictionary> {
  if (!pending) {
    pending = loadDictionary().then((d) => {
      loaded = d;
      return d;
    });
  }
  return pending;
}

export function useDictionary(): { dictionary: Dictionary | null; error: unknown } {
  const [dictionary, setDictionary] = useState<Dictionary | null>(loaded);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (dictionary) return;
    let live = true;
    load().then(
      (d) => live && setDictionary(d),
      (e: unknown) => live && setError(e),
    );
    return () => {
      live = false;
    };
  }, [dictionary]);
  return { dictionary, error };
}
