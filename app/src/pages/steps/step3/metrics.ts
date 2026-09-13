import type { Step3Calibration, Step3Confirmation, Step3Reach } from '../../../api/types';

/** The tiers step 1 actually nominated — everything else is a padded neighbour. */
export const TARGET_TIERS = ['core', 'mechanism-term', 'net'];

/** One fitted parameter, or undefined when the model has not been fitted yet. */
export function fitted(rows: Step3Calibration[] | undefined, metric: string): number | undefined {
  return rows?.find((row) => row.metric === metric)?.value;
}

/** A share as a percentage with one decimal, or an em dash when there is nothing to divide. */
export function share(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;
}

export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString();
}

/**
 * Confirmation totals over the target tiers only.
 *
 * The bait pads each target by up to 50 kb, so most alleles typed in this step belong to
 * neighbouring genes the symptom ranking never nominated. Folding those into "targets"
 * compares a gene list against a null it does not contain.
 */
export function targetTotals(rows: Step3Confirmation[], novel: boolean) {
  const wanted = rows.filter((row) => row.novel === novel && TARGET_TIERS.includes(row.tier));
  const probed = wanted.reduce((total, row) => total + row.fully_probed, 0);
  const confirmed = wanted.reduce((total, row) => total + row.confirmed, 0);
  return { probed, confirmed, rate: probed ? confirmed / probed : null };
}

/** How a gene came to be excluded by the stage-0 gate, in words. */
export function reachLabel(row: Step3Reach): string {
  if (row.reachable) return 'reachable';
  const reasons = [];
  if (row.sparse_bait) reasons.push('sparse bait');
  if (row.mapq_refused) reasons.push('aligner refused');
  return `excluded — ${reasons.join(' + ') || 'unknown'}`;
}
