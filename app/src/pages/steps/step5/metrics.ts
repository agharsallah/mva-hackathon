import type { Step5Citation, Step5Domain, Step5Group, Step5Residue } from '../../../api/types';

/** The two groups the decoy null is measured between; everything else is background. */
export const MEASURED_GROUPS = ['target', 'decoy'];

/** Matched terms a paper needs before it counts as a case-report anchor (pre-registered). */
export const ANCHOR_TERMS = 5;

export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString();
}

export function share(part: number | undefined, whole: number | undefined): string {
  if (!part || !whole) return '—';
  return `${((part / whole) * 100).toFixed(1)}%`;
}

/** A correlation or an AUC: three decimals, because the second one is where 0.5 lives. */
export function stat(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(3);
}

/**
 * A publication count on a log axis, floored at 1.
 *
 * Citation volume spans five orders of magnitude across 815 genes — a gene nobody has
 * written about sits at 0, and HLA-DRB1 at tens of thousands — so a linear axis shows one
 * bar and 814 slivers.
 */
export function logCount(value: number | null | undefined): number {
  return Math.log10(Math.max((value ?? 0) + 1, 1));
}

/**
 * How the knowledge ordering moved a gene against its citation rank.
 *
 * Positive means the literature *promoted* it — it sits higher in the knowledge ordering
 * than its publication count alone would put it — which is the only direction that says
 * the route added anything.
 */
export function movement(rows: Step5Citation[]): {
  promoted: number;
  demoted: number;
  still: number;
} {
  return rows.reduce(
    (acc, row) => {
      if (row.moved > 0) acc.promoted += 1;
      else if (row.moved < 0) acc.demoted += 1;
      else acc.still += 1;
      return acc;
    },
    { promoted: 0, demoted: 0, still: 0 },
  );
}

/** The target and decoy rows of the group table, in that order, for a side-by-side read. */
export function measured(groups: Step5Group[]): Step5Group[] {
  return MEASURED_GROUPS.map((name) => groups.find((row) => row.grouping === name)).filter(
    (row): row is Step5Group => row !== undefined,
  );
}

/**
 * Which of the claim's three conditions a residue actually met.
 *
 * Returned as three independent flags rather than one verdict because the claim was filed
 * that way: "outside every annotated domain" and "the model has no confident opinion
 * there" are different refutations and the page has to be able to name which one happened.
 */
export function conditions(row: Step5Residue | null | undefined) {
  return [
    { label: 'inside an InterPro domain', met: Boolean(row?.in_domain) },
    { label: `structure confident (pLDDT ≥ 70)`, met: Boolean(row?.confident) },
    { label: 'AlphaMissense calls it damaging', met: Boolean(row?.am_agrees) },
  ];
}

/** The InterPro rows of one protein, longest first so a short domain draws on top. */
export function tracksFor(domains: Step5Domain[], gene: string): Step5Domain[] {
  return domains
    .filter((row) => row.gene === gene)
    .sort((a, b) => b.end_fraction - b.start_fraction - (a.end_fraction - a.start_fraction));
}
