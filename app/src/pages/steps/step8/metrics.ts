import type { Step8Limit, Step8Verdict } from '../../../api/types';

/** Karyogram order: 1 to 22, then X and Y. Never sorted by value — see `ORDER` in the charts. */
export const ORDER = [...Array.from({ length: 22 }, (_, i) => String(i + 1)), 'X', 'Y'];

/** Contigs with one copy in this male proband. Their allele balance is not an autosome's. */
export const HEMIZYGOUS = new Set(['X', 'Y']);

export function byKaryogram<T extends { chrom: string }>(rows: T[]): T[] {
  const rank = new Map(ORDER.map((name, index) => [name, index]));
  return [...rows].sort(
    (a, b) =>
      (rank.get(a.chrom) ?? 99) - (rank.get(b.chrom) ?? 99) || a.chrom.localeCompare(b.chrom),
  );
}

export function count(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString();
}

/** A deviation or an over-dispersion: five decimals, because the whole signal lives there. */
export function dev(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(5);
}

/** A cell fraction, as a percentage. `null` is a blind spot, and reads as one. */
export function fraction(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value)
    ? 'never detected'
    : `${(value * 100).toFixed(1)}%`;
}

export function stat(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? '—' : value.toFixed(2);
}

/** The simulated fractions a power curve was evaluated at, read off its own keys. */
export function grid(rows: Step8Limit[]): number[] {
  const first = rows[0];
  if (!first) return [];
  return Object.keys(first)
    .filter((key) => key.startsWith('power_'))
    .map((key) => Number(key.slice('power_'.length)))
    .filter((value) => Number.isFinite(value))
    .sort((a, b) => a - b);
}

export function power(row: Step8Limit, at: number): number | null {
  const value = row[`power_${at}`];
  return typeof value === 'number' ? value : null;
}

/**
 * How a verdict should read in one word. `call` already carries the refusals; this is the
 * tone to paint it, and the three of them are the three things that can be true.
 */
export function verdictTone(row: Step8Verdict): 'good' | 'decision' | 'broken' {
  if (row.call === 'not measurable') return 'broken';
  if (row.best === 'normal') return 'good';
  return 'decision';
}
