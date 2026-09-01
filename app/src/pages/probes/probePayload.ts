/**
 * The payload under construction: the draft rows, and the pure functions over them.
 *
 * Kept out of the component so the parts that are easy to get wrong — epcr ordering, pair
 * assembly, free-text parsing — are plain data transforms. Nothing here validates against
 * the challenge rules: the server does that through `mva.pipeline.submission`, which is
 * the single owner of them. A second copy of those rules living in the browser is exactly
 * the drift this project cannot afford.
 */

import type { FindingType, ProbeBuildRequest, VariantRef } from '../../api/types/probebuild';

export interface DraftRow {
  /** Stable across reorders, so React keys and inputs survive a move. */
  id: string;
  variant1: VariantRef;
  variant2: VariantRef | null;
  epcr: number;
  findingType: FindingType;
  notes: string;
  /** What the row came from — shown as a hint, never sent. */
  label: string;
}

/** The probe protocol's ladder (intel §9.1): 0.99, 0.98, … one step per rank. */
export const TOP_EPCR = 0.99;
export const EPCR_STEP = 0.01;
export const MAX_ROWS = 10;

let counter = 0;
const nextId = (): string => `row-${++counter}`;

/** Round to the two decimals the ladder uses, so 0.99 - 0.01 stays 0.98. */
const round2 = (n: number): number => Math.round(n * 100) / 100;

export const epcrAt = (index: number): number => round2(TOP_EPCR - EPCR_STEP * index);

/** Re-lay the ladder over the current order. Called after every add, move and remove. */
export function renumber(rows: DraftRow[]): DraftRow[] {
  return rows.map((row, i) => ({ ...row, epcr: epcrAt(i) }));
}

export function addRow(
  rows: DraftRow[],
  variant1: VariantRef,
  variant2: VariantRef | null,
  label: string,
): DraftRow[] {
  if (rows.length >= MAX_ROWS) return rows;
  const row: DraftRow = { id: nextId(), variant1, variant2, epcr: 0, findingType: 'primary', notes: '', label };
  return renumber([...rows, row]);
}

export function removeRow(rows: DraftRow[], id: string): DraftRow[] {
  return renumber(rows.filter((r) => r.id !== id));
}

/** Move one row by `delta` places. Out-of-range moves are no-ops, not wraps. */
export function moveRow(rows: DraftRow[], id: string, delta: number): DraftRow[] {
  const from = rows.findIndex((r) => r.id === id);
  const to = from + delta;
  if (from < 0 || to < 0 || to >= rows.length) return rows;
  const next = [...rows];
  const [row] = next.splice(from, 1);
  next.splice(to, 0, row);
  return renumber(next);
}

export function patchRow(rows: DraftRow[], id: string, patch: Partial<DraftRow>): DraftRow[] {
  return rows.map((r) => (r.id === id ? { ...r, ...patch } : r));
}

/** Drop the client-only fields. `variant_2` is omitted entirely for a single. */
export function toRequest(rows: DraftRow[]): ProbeBuildRequest {
  return {
    rows: rows.map((r) => ({
      variant_1: r.variant1,
      ...(r.variant2 ? { variant_2: r.variant2 } : {}),
      epcr: r.epcr,
      finding_type: r.findingType,
      notes: r.notes,
    })),
  };
}

/** `15:12345 C>T` — how a variant is written everywhere in this app and in papers. */
export const variantLabel = (v: VariantRef): string => `${v.chrom}:${v.pos} ${v.ref}>${v.alt}`;

export const sameVariant = (a: VariantRef, b: VariantRef): boolean =>
  a.chrom === b.chrom && a.pos === b.pos && a.ref === b.ref && a.alt === b.alt;

// --- free entry --------------------------------------------------------------

export interface ParsedLine {
  line: number;
  variant1?: VariantRef;
  variant2?: VariantRef | null;
  problem?: string;
}

/** `15:12345 C>T`, `chr15 12345 C T`, `15-12345-C-T` — anything a copy-paste produces. */
function parseVariant(text: string): VariantRef | string {
  const parts = text.trim().split(/[\s:>\-/,]+/).filter(Boolean);
  if (parts.length !== 4) return `expected chrom, pos, ref, alt — got ${parts.length} fields`;
  const [chrom, pos, ref, alt] = parts;
  const position = Number(pos);
  if (!Number.isInteger(position) || position < 1) return `position must be a whole number ≥ 1, got "${pos}"`;
  if (!/^[ACGTN]+$/i.test(ref) || !/^[ACGTN]+$/i.test(alt)) return 'ref and alt must be DNA letters';
  return { chrom, pos: position, ref: ref.toUpperCase(), alt: alt.toUpperCase() };
}

/**
 * One line per row. ` + ` joins the two alleles of a compound-het pair into one row —
 * which is the whole point: split across two rows, a true pair scores partial credit only.
 * Blank lines and `#` comments are ignored.
 */
export function parseLines(text: string): ParsedLine[] {
  const out: ParsedLine[] = [];
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const halves = line.split('+');
    if (halves.length > 2) {
      out.push({ line: i + 1, problem: 'a row holds at most two alleles' });
      return;
    }
    const parsed = halves.map(parseVariant);
    const bad = parsed.find((p): p is string => typeof p === 'string');
    if (bad) {
      out.push({ line: i + 1, problem: bad });
      return;
    }
    const [first, second] = parsed as VariantRef[];
    out.push({ line: i + 1, variant1: first, variant2: second ?? null });
  });
  return out;
}
