/**
 * Exhibit selections live in the URL, not in component state.
 *
 * Every control on this app is a *view* selection — which contig, which metric, 2D or 3D.
 * Held in `useState` those selections die on reload and cannot be linked to, which makes a
 * figure in the report unciteable: "open Genome, pick chr7, switch to 3D" is not a
 * reference. Held in the query string they survive reload, back/forward and copy-paste, and
 * one URL is a complete citation of one figure.
 *
 * The contract, in four rules:
 *
 * 1. **The default is absence.** A control sitting on its default writes no parameter, so a
 *    freshly opened page has a clean URL and a shared URL names only what was deliberately
 *    changed.
 * 2. **Updates replace, they do not push.** Flipping a toggle five times leaves one history
 *    entry, so the browser Back button still means "the previous page".
 * 3. **Exhibits coexist.** Each write merges into the parameters already there, and keys are
 *    namespaced per exhibit (`bins.chrom` vs `baf.chrom`), so two exhibits on one page never
 *    overwrite each other.
 * 4. **Junk falls back silently.** A value outside the allowed set reads as the default. A
 *    hand-edited or stale URL degrades to the default view; it never renders a broken one.
 *
 * The API is string-typed at the core because a query string is strings; the typed wrappers
 * (`useUrlEnum`, `useUrlNumber`, `useUrlToggle`, `useUrlText`) are thin adapters over it.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

type Setter<T> = (next: T) => void;

/** The one read rule: absent or not allowed ⇒ the default. */
function readParam(
  params: URLSearchParams,
  key: string,
  fallback: string,
  allowed?: readonly string[],
): string {
  const raw = params.get(key);
  if (raw === null) return fallback;
  if (allowed && !allowed.includes(raw)) return fallback;
  return raw;
}

/**
 * One string selection, stored in the query string.
 *
 * @param key      the parameter name — short, stable, and namespaced per exhibit, because it
 *                 becomes part of every shared URL and of the report's figure references.
 * @param fallback the default value; while the selection equals it, the parameter is absent.
 * @param allowed  optional vocabulary; anything else in the URL reads as `fallback`.
 */
export function useUrlState(
  key: string,
  fallback: string,
  allowed?: readonly string[],
): [string, Setter<string>] {
  const [params, setParams] = useSearchParams();

  // `allowed` is usually an inline literal, so its identity changes every render. Reading it
  // through a ref keeps the setter stable without asking every call site to memoise.
  const vocab = useRef(allowed);
  vocab.current = allowed;

  const value = readParam(params, key, fallback, allowed);

  const set = useCallback<Setter<string>>(
    (next) => {
      setParams(
        (prev) => {
          // Merge, never replace: another exhibit's parameters are already in the URL.
          //
          // The base is the *live* address bar, not the `prev` React Router hands us. `prev`
          // is the value captured when this component last rendered, so two writes in one
          // tick both see the same stale snapshot and the second silently drops the first.
          // `navigate` updates `window.location` synchronously, so reading it here makes
          // same-tick writes compose. `prev` remains the fallback outside a browser.
          const out = new URLSearchParams(
            typeof window === 'undefined' ? prev : window.location.search,
          );
          const ok = !vocab.current || vocab.current.includes(next);
          if (!ok || next === fallback) out.delete(key);
          else out.set(key, next);
          return out;
        },
        { replace: true },
      );
    },
    [key, fallback, setParams],
  );

  return [value, set];
}

/** A string-union selection (a `Select` over a fixed option list). */
export function useUrlEnum<T extends string>(
  key: string,
  fallback: T,
  allowed: readonly T[],
): [T, Setter<T>] {
  const [value, set] = useUrlState(key, fallback, allowed);
  return [value as T, set as Setter<T>];
}

/** A numeric selection. Non-numeric or out-of-vocabulary values fall back. */
export function useUrlNumber(
  key: string,
  fallback: number,
  allowed?: readonly number[],
): [number, Setter<number>] {
  const vocab = allowed?.map(String);
  const [raw, set] = useUrlState(key, String(fallback), vocab);
  const parsed = Number(raw);
  const value = Number.isFinite(parsed) ? parsed : fallback;
  return [value, useCallback((next: number) => set(String(next)), [set])];
}

/** A boolean toggle, written as `1` / `0`. The default state writes nothing. */
export function useUrlToggle(key: string, fallback = false): [boolean, Setter<boolean>] {
  const [raw, set] = useUrlState(key, fallback ? '1' : '0', ['0', '1']);
  return [raw === '1', useCallback((next: boolean) => set(next ? '1' : '0'), [set])];
}

/**
 * A free-text filter. The box stays instant; the URL is written `delayMs` after the last
 * keystroke, so typing a nine-letter table name costs one URL update instead of nine.
 */
export function useUrlText(key: string, fallback = '', delayMs = 300): [string, Setter<string>] {
  const [committed, setCommitted] = useUrlState(key, fallback);
  const [draft, setDraft] = useState(committed);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mirrored = useRef(committed);

  // The URL can also change from outside this box — a reload, Back, or a pasted link. Only
  // then does the draft get overwritten; a debounced write of our own is already mirrored.
  useEffect(() => {
    if (committed !== mirrored.current) {
      mirrored.current = committed;
      setDraft(committed);
    }
  }, [committed]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const set = useCallback<Setter<string>>(
    (next) => {
      setDraft(next);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        mirrored.current = next;
        setCommitted(next);
      }, delayMs);
    },
    [setCommitted, delayMs],
  );

  return [draft, set];
}

/**
 * Fall back when a parameter names something the *loaded* options do not contain.
 *
 * Some vocabularies are not known until the API answers (the panel gene list). Until they
 * arrive the parameter is taken at face value; once they do, an unknown value reads as the
 * default rather than driving a query for a gene that does not exist.
 */
export function known<T extends string>(value: T, options: readonly T[], fallback: T): T {
  return options.length === 0 || options.includes(value) ? value : fallback;
}
