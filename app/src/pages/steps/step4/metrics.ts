import type { Step4Leader, Step4NullBucket, Step4PhenotypeBin } from '../../../api/types';

/** The tiers step 1 actually nominated — everything else is a padded neighbour or nothing. */
export const TARGET_TIERS = ['core', 'mechanism-term', 'net'];

/**
 * A likelihood ratio, written the way a reader can hold it.
 *
 * The ordering spans seven orders of magnitude, so a fixed number of decimals is unreadable
 * at one end and misleading at the other: 341019 wants no decimals, 0.0098 wants four.
 */
export function ratio(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (value >= 1) return value.toFixed(2);
  return value.toPrecision(2);
}

export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString();
}

export function share(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`;
}

/** log₁₀, floored, so a ratio of zero cannot take an axis to minus infinity. */
export function log10(value: number | null | undefined): number {
  return Math.log10(Math.max(value ?? 1e-6, 1e-6));
}

/** The lanes of one hypothesis, decoded from the `name=ratio;…` string the row carries. */
export function terms(row: Step4Leader | undefined): { name: string; value: number }[] {
  if (!row?.terms) return [];
  return row.terms
    .split(';')
    .map((pair) => pair.split('='))
    .filter((parts) => parts.length === 2)
    .map(([name, value]) => ({ name, value: Number(value) }));
}

/**
 * The lanes that were consulted and contributed nothing.
 *
 * A ratio of exactly 1 means one of two things — the lane had no evidence, or it lost its
 * correlation group to a stronger lane — and both are worth seeing, because a reader who
 * cannot tell which lanes were even asked cannot judge the ones that answered.
 */
export function silentTerms(row: Step4Leader | undefined): string[] {
  return terms(row)
    .filter((term) => term.value === 1)
    .map((term) => term.name);
}

/** How far the runner-up gene sits behind the leader, or undefined when there is no second. */
export function margin(leaders: Step4Leader[]): number | undefined {
  return leaders.length > 1 ? (leaders[1].behind_leader ?? undefined) : undefined;
}

/** The centre of a null bucket, for plotting a histogram whose bars carry a range. */
export function bucketCentre(bucket: Step4NullBucket): number {
  return (Number(bucket.low) + Number(bucket.high)) / 2;
}

/** A rank band's label — `1–10`, `301–1000` — from the half-open bin the fit produced. */
export function binLabel(bin: Step4PhenotypeBin): string {
  return `${Number(bin.low) + 1}–${Number(bin.high)}`;
}
