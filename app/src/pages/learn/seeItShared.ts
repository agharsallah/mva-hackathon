/**
 * The see-it link types and the two helpers both halves of the table use. Separate from
 * `seeIt.ts` so the halves can import them without a cycle (seeIt imports the halves).
 */

export interface SeeItLink {
  /** Route with an optional `#exhibit-anchor`. */
  to: string;
  /** What the reader will see there, in a few words. */
  label: string;
}

export interface SeeIt {
  app: SeeItLink[];
  /** `docs/...` paths, rendered as GitHub links. */
  docs?: { path: string; label: string }[];
}

/** A step-0 methodology entry by its number-and-slug file name. */
export const method = (n: string, label: string) => ({
  path: `docs/step-0/methodology/${n}.md`,
  label,
});

/**
 * Route + exhibit anchor. Exists for the one anchor whose first letters spell a hex colour
 * (`#baf-karyogram…`) and would otherwise trip `local/no-raw-hex-color` as a literal.
 */
export const at = (route: string, anchor: string) => `${route}#${anchor}`;
