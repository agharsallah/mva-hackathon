/**
 * The theme switch: one bit of state, held outside React so both halves of the palette can
 * read it.
 *
 * The app ships one palette in two directions. `src/theme.generated.css` carries the dark
 * values under `@theme` and the light ones under `:root[data-theme="light"]`, so the DOM half
 * (`bg-chrome-950`, `text-good-300`) follows an attribute on `<html>` with no JavaScript at
 * all. The canvas half (Plotly, SVG, three.js) cannot: it is handed concrete hex strings, so
 * `lib/palette` has to *ask* which theme is current. That is what this store is for.
 *
 * It is deliberately not React state. `lib/palette`'s `C` is a module-level object read by
 * ~40 files at render time, and it has to resolve against the live theme without any of them
 * taking a hook. So the truth lives here, the store notifies, and `AppShell` re-keys the page
 * frame on the value so every mounted exhibit rebuilds its layout with the new numbers.
 *
 * Initial value, in order: the reader's stored choice, else the OS `prefers-color-scheme`,
 * else dark. Storage is wrapped because `localStorage` throws outright in a
 * blocked-third-party-cookie iframe and in Safari's private mode — a theme preference is not
 * worth a blank page.
 */

import { useSyncExternalStore } from 'react';

export type Theme = 'dark' | 'light';

/** localStorage key. Namespaced: this app is not the only thing on localhost. */
const STORAGE_KEY = 'mva.theme';

const listeners = new Set<() => void>();

function isTheme(value: unknown): value is Theme {
  return value === 'dark' || value === 'light';
}

/** The reader's explicit choice, if they have made one and storage is readable. */
function stored(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return isTheme(value) ? value : null;
  } catch {
    return null;
  }
}

/** Stored choice > OS preference > dark. The app was dark-only, so dark stays the default. */
function initial(): Theme {
  const choice = stored();
  if (choice) return choice;
  try {
    if (window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
  } catch {
    // matchMedia is missing in some non-browser test environments; fall through to dark.
  }
  return 'dark';
}

let current: Theme = initial();

/**
 * Put the theme on `<html>`.
 *
 * `dataset.theme` is what the generated CSS selector matches. `style.colorScheme` is the
 * separate, browser-owned switch for form controls, scrollbars and the canvas the page is
 * painted on; it is set inline because `src/index.css` hard-codes `color-scheme: dark` and a
 * light page with dark native widgets looks broken.
 */
function apply(theme: Theme): void {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
}

/**
 * Apply the current theme to the document. Called once at module load (so the palette is
 * right for any module that reads it during import) and again from `src/main.tsx` before
 * `createRoot().render()`, so the first paint is already in the right theme rather than
 * flashing dark and correcting itself.
 */
export function initTheme(): void {
  apply(current);
}

/**
 * The store. Shaped for `useSyncExternalStore` (a stable `subscribe`, a `get` that returns
 * the same value until something changes) and usable from plain modules that have no hooks.
 */
export const themeStore = {
  get: (): Theme => current,
  set(theme: Theme): void {
    if (theme === current) return;
    current = theme;
    apply(theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Preference is not persistable here; the session still switches.
    }
    for (const listener of listeners) listener();
  },
  toggle(): void {
    themeStore.set(current === 'dark' ? 'light' : 'dark');
  },
  subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },
};

initTheme();

/** The current theme, as React state. */
export function useTheme(): Theme {
  return useSyncExternalStore(themeStore.subscribe, themeStore.get, themeStore.get);
}
