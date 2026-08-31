/**
 * Shared reading rules for the Compare page.
 *
 * Two facts about the data drive everything here and are easy to get wrong:
 *
 * 1. `gnomad_af === null` means **absent from gnomAD** (a novel variant), which is the
 *    rarest thing a variant can be. It is not frequency zero and it must never be sorted,
 *    plotted or formatted as zero.
 * 2. `vaf === null` happens on `1/2` multiallelic records, where "the" alternate allele
 *    fraction is not defined. Those rows are still real records and are not dropped.
 */

import type { PanelAnnotationRow, VariantImpact } from '../../api/types';

/** Most-damaging first. Used for candidate ordering, so it is a single source of truth. */
export const IMPACT_ORDER: VariantImpact[] = ['HIGH', 'MODERATE', 'LOW', 'MODIFIER'];

export const impactRank = (impact: string): number => {
  const i = IMPACT_ORDER.indexOf(impact as VariantImpact);
  return i === -1 ? IMPACT_ORDER.length : i;
};

/**
 * Does ClinVar assert pathogenicity for this variant?
 *
 * `Conflicting_interpretations_of_pathogenicity` contains the substring "pathogenic" but
 * asserts nothing, and `Benign` combinations must not match either — so both are excluded
 * before the positive test.
 */
export function isPathogenic(clinSig: string | null): boolean {
  if (!clinSig) return false;
  const s = clinSig.toLowerCase();
  if (s.includes('conflicting')) return false;
  return /(^|[^a-z])(likely_)?pathogenic/.test(s);
}

/** Allele frequency for display. null is "novel", never "0". */
export function af(value: number | null): string {
  if (value === null) return 'novel';
  if (value === 0) return '0';
  if (value < 1e-4) return value.toExponential(1);
  return value.toPrecision(3);
}

/**
 * The filter value standing for `gene === null` rows (intergenic — the BED's ±20 kb
 * padding catches records outside any gene). A real bucket, not a dropped row.
 */
export const NO_GENE = 'NO_GENE';

/** Does a row belong under the current gene filter value? */
export function matchesGene(row: PanelAnnotationRow, value: string): boolean {
  if (value === 'ALL') return true;
  if (value === NO_GENE) return row.gene === null;
  return row.gene === value;
}

/** The gene option list for the filter, derived from the rows rather than hardcoded. */
export function geneOptions(rows: PanelAnnotationRow[]): { value: string; label: string }[] {
  const counts = new Map<string, number>();
  let unassigned = 0;
  for (const r of rows) {
    if (r.gene === null) unassigned += 1;
    else counts.set(r.gene, (counts.get(r.gene) ?? 0) + 1);
  }
  return [
    { value: 'ALL', label: `All genes (${rows.length})` },
    ...[...counts.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([gene, n]) => ({ value: gene, label: `${gene} (${n})` })),
    ...(unassigned > 0 ? [{ value: NO_GENE, label: `no gene — intergenic (${unassigned})` }] : []),
  ];
}

/**
 * The distilled candidate set: rare in the healthy population **and** capable of changing
 * the protein. Sorted most-damaging first, and within an impact by rarity — novels first,
 * because absent-from-gnomAD is rarer than any measured frequency.
 */
export function candidates(rows: PanelAnnotationRow[]): PanelAnnotationRow[] {
  return rows
    .filter((r) => r.is_protein_altering && r.is_rare_recessive)
    .sort((a, b) => {
      const d = impactRank(a.impact) - impactRank(b.impact);
      if (d !== 0) return d;
      if (a.gnomad_af === null && b.gnomad_af === null) return 0;
      if (a.gnomad_af === null) return -1;
      if (b.gnomad_af === null) return 1;
      return a.gnomad_af - b.gnomad_af;
    });
}
