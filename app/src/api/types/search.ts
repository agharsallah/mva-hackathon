/**
 * The universal search: one typed query → a window, then that window's records.
 *
 * Two endpoints, deliberately not one. Resolution is cheap and shareable; the region read
 * is the only user-steerable path in the service that touches the five-million-row raw
 * callset layer. Keeping them apart lets the page say *what the query resolved to, and by
 * which resolver* before, and independently of, paying for the scan.
 */

/** Which of the three forms the server decided the query was — by shape, before any lookup. */
export type SearchKind = 'region' | 'gene' | 'rsid';

/**
 * GET /api/search?q=… — where a query points, and which resolver said so.
 *
 * `chrom` is **bare**, the way the callset spells it (`"15"`, not `"chr15"`).
 * `source` names the resolver that answered — the query string itself, the candidate
 * panel, the callset's own `id` column, or Ensembl — and is also the envelope's `source`.
 * `note` is a caveat the UI must render (an unpadded Ensembl span, an rsID resolved from
 * dbSNP rather than from the callset) and is **null** when there is none.
 *
 * Failures are statuses, not fields, and they are different facts:
 * - **422** the query is not one of the three forms, or the window exceeds the span cap
 * - **404** valid shape, but no authority knows the name
 * - **502** Ensembl was unreachable — never a guessed coordinate
 * - **200** resolved. The table may still be empty, and *that is a finding*: for an rsID
 *   resolved from dbSNP it means the site was never called in this callset.
 */
export interface SearchResolution {
  kind: SearchKind;
  chrom: string;
  start: number;
  end: number;
  /** Human handle for the window, e.g. `"BUB1B — 15:40,140,983-40,241,137"`. */
  label: string;
  source: string;
  note: string | null;
}

/**
 * One callset record inside a searched window.
 *
 * Same shape as `LocusVariant` plus `id`, the record's dbSNP name, which is **null**
 * where the VCF wrote `.`. `ad_alt` and `vaf` are **null** at a `1/2` multiallelic site —
 * the same convention `/api/panel/locus` uses, because a blank is a question and a halved
 * VAF is a wrong answer. `alt` stays comma-packed at those sites, exactly as delivered.
 *
 * These are real patient coordinates at runtime. Never persist them into this repository;
 * the fixture uses an obviously synthetic ladder.
 */
export interface RegionVariant {
  pos: number;
  id: string | null;
  ref: string;
  alt: string;
  qual: number | null;
  filter: string;
  gt: string | null;
  dp: number | null;
  ad_ref: number | null;
  ad_alt: number | null;
  vaf: number | null;
  gq: number | null;
}

/**
 * GET /api/callset/region?chrom=&start=&end= — every record in one window.
 *
 * The window is echoed back so a cached payload still says which window it is for.
 * Windows wider than the server's span cap are a **422** carrying the cap: the raw layer
 * has no index, so a whole chromosome answers just as fast and then weighs megabytes.
 */
export interface RegionWindow {
  /** Bare contig, as the callset spells it. */
  chrom: string;
  start: number;
  end: number;
  /** `variants.length`, carried so an empty window is still self-describing. */
  n: number;
  variants: RegionVariant[];
}
