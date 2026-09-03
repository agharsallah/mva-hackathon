/**
 * Hide the hosts and ports in a health check's text, until someone asks to see them.
 *
 * The Status page is the one page whose whole content is infrastructure addresses: the
 * warehouse's `user@host:5432/db`, MinIO's `http://host:9012/bucket`, a remedy that spells
 * out an SSH tunnel. That is exactly right for a developer at their own terminal, and
 * exactly wrong on a shared screen or in a screenshot in a report — this is a hackathon
 * project whose deliverable includes screenshots of this app.
 *
 * So addresses render masked by default and a control reveals them per card (or for the
 * whole board). What is masked is only *where* a dependency lives — never its status,
 * latency, detail verb or remedy structure, because the page has to stay readable and
 * actionable while masked.
 *
 * This is presentation hygiene, not a security boundary. The API already guarantees no
 * credential reaches these strings (`mva.viz.health_results.redact`), and the values are
 * in the response either way — a reader with the devtools open sees them. It stops an
 * address being *shown* by accident; it does not stop it being fetched.
 */

/** Fixed-width so a masked line keeps the shape of the address it replaces. */
export const MASK = '••••';

/**
 * The address shapes these strings actually contain, narrowest first.
 *
 * Order matters: the port-forward triple (`9012:localhost:9012` inside an `ssh -L` line)
 * has to go before the bare `host:port` rule, or the first rule to run leaves the local
 * port readable next to a masked host — which would publish the very number the mask is
 * there to hide.
 */
/** Keep the shape a match had: only mask a port if the match actually carried one. */
const shaped = (prefix: string) => (match: string) =>
  `${prefix}${MASK}${match.includes(':') ? `:${MASK}` : ''}`;

const RULES: { pattern: RegExp; replace: (match: string) => string }[] = [
  // ssh -N -L 9012:localhost:9012 — local port, host, remote port
  { pattern: /\b\d{2,5}:[\w.-]+:\d{2,5}\b/g, replace: () => `${MASK}:${MASK}:${MASK}` },
  // scheme://[user@]host[:port] — the authority of any URL, userinfo included
  { pattern: /(?<=:\/\/)(?:[^/\s@]+@)?[^/\s:?#]+(?::\d+)?/g, replace: shaped('') },
  // user@host[:port] with no scheme — Postgres' own describe() shape
  { pattern: /\b[\w.-]+@[\w.-]+(?::\d+)?/g, replace: shaped(`${MASK}@`) },
  // a bare host:port left anywhere in a detail or remedy line
  { pattern: /\b[\w.-]+:\d{2,5}\b/g, replace: () => `${MASK}:${MASK}` },
];

/**
 * Mask every host and port in `text`. Idempotent: running it on already-masked text
 * changes nothing, because the mask character is not in any pattern's character class.
 */
export function maskAddresses(text: string): string {
  return RULES.reduce((out, rule) => out.replace(rule.pattern, rule.replace), text);
}

/** `null`-tolerant `maskAddresses`, for the fields the contract allows to be absent. */
export function maskOptional(text: string | null, masked: boolean): string | null {
  if (text === null) return null;
  return masked ? maskAddresses(text) : text;
}
