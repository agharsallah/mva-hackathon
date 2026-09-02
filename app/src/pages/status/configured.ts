/**
 * The endpoint a check is *configured* against, for the offline case.
 *
 * When the viz API answers, the payload's own `endpoint` is authoritative — it was read
 * from the running service's configuration. Offline the fixture cannot know a developer's
 * hosts, so `vite.config.ts` inlines the addresses from the repo-root `.env` at build time
 * and this module hands them to the board.
 *
 * Addresses only. No password, access key or token is exposed here or in the build define.
 */

declare const __CONFIGURED_ENDPOINTS__: Record<string, string> | undefined;

/** Build-time map of check id → configured address; empty in a test or a bare build. */
const CONFIGURED: Record<string, string> =
  typeof __CONFIGURED_ENDPOINTS__ === 'undefined' ? {} : __CONFIGURED_ENDPOINTS__;

/**
 * What to show for a check's endpoint, and whether it came from the API or from `.env`.
 *
 * `origin` is the payload's origin, not the check's: a fixture row's endpoint string is a
 * placeholder from the committed file, so the configured value is the truthful one to show
 * and it is labelled as such.
 */
export function endpointFor(
  id: string,
  payloadEndpoint: string | null,
  origin: 'api' | 'fixture',
): { value: string; fromEnv: boolean } | null {
  const configured = CONFIGURED[id]?.trim();
  if (origin === 'fixture' && configured) return { value: configured, fromEnv: true };
  if (payloadEndpoint) return { value: payloadEndpoint, fromEnv: false };
  if (configured) return { value: configured, fromEnv: true };
  return null;
}
