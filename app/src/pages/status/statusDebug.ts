import { useSyncExternalStore } from 'react';

/**
 * Gate for the Status page's hidden advanced panel.
 *
 * Prod builds only (`import.meta.env.PROD`) — a dev server already shows everything a
 * developer needs. Unlocked by setting a localStorage key to a matching value, both named
 * by env vars (`VITE_STATUS_DEBUG_KEY` / `VITE_STATUS_DEBUG_VALUE`) rather than hardcoded,
 * so the unlock phrase is a deploy-time secret, not something grep finds in this repo.
 * Either var unset (or unmatched) keeps the panel off.
 */
const DEBUG_KEY = import.meta.env.VITE_STATUS_DEBUG_KEY;
const DEBUG_VALUE = import.meta.env.VITE_STATUS_DEBUG_VALUE;

function readUnlocked(): boolean {
  if (!import.meta.env.PROD || !DEBUG_KEY || !DEBUG_VALUE) return false;
  try {
    return window.localStorage.getItem(DEBUG_KEY) === DEBUG_VALUE;
  } catch {
    // Private-mode Safari and similar throw on access rather than returning null.
    return false;
  }
}

/** Re-checked on `storage` events so flipping the key in another tab (or devtools) takes
 * effect without a reload. */
export function useStatusDebugUnlocked(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      window.addEventListener('storage', onChange);
      return () => window.removeEventListener('storage', onChange);
    },
    readUnlocked,
    () => false,
  );
}

/**
 * Whether this page may reveal real endpoint addresses at all.
 *
 * A dev server already shows a developer their own hosts, so the toggle stays free there.
 * In a prod build the addresses are real infrastructure — masked by default is presentation
 * hygiene (`redact.ts`), but the "show" controls themselves must not be public, or masking
 * is theatre: anyone can click it. So in prod the controls are gone entirely unless the
 * same debug flag that unlocks the advanced panel is set.
 */
export function useCanRevealAddresses(): boolean {
  const debugUnlocked = useStatusDebugUnlocked();
  return !import.meta.env.PROD || debugUnlocked;
}
