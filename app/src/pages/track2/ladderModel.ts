/**
 * The step-7 grading, as data — no JSX, so the arithmetic is testable and the panels stay
 * about layout.
 *
 * Three shapes are derived here and nowhere else:
 *
 *   * the **matrix** the ladder exhibit draws (one row per drug, one cell per direction),
 *   * the **cell tone** rule, which is the whole argument of the exhibit compressed into a
 *     colour: a result a person read outranks a result a program looked up, and a drug the
 *     card warns against outranks both,
 *   * the **per-drug aggregates** the paediatric panel needs, which are counts over ~11k
 *     registry rows and must never be recomputed inside a render.
 */

import type { LadderRow, MeasuredFact, PediatricTrialRow, ShortlistRow } from '../../api/types';
import type { Tone } from '../../lib/palette';

/** Rows at rung 1 are *named, never submitted* — the exhibit starts at 2. */
export const MIN_SHOWN_RUNG = 2;

/** The pre-registered non-specificity line for a decoy overlap (H049). */
export const JACCARD_LINE = 0.1;

/** Flags that make a row a warning rather than a candidate. */
const WARNING_FLAGS = new Set(['A1', 'A2', 'standard_of_care']);

export const isWarning = (row: { flags: string[] }): boolean =>
  row.flags.some((f) => WARNING_FLAGS.has(f));

/**
 * The cell's colour, in the repo's language.
 *
 * `broken` (red) — the card warns against this drug, or it is chemotherapy the child is
 * already on: a high rung here is not a candidate at all.
 * `good` (green) — a person read a paper for this drug *and* it reached rung 4 or 5.
 * `decision` (yellow) — a person read a paper, but the drug stops at rung 2 or 3: a real
 * mechanism result with no clinical evidence behind it yet.
 * `machinery` (blue) — automated tests alone. A registered trial in the tumour makes a drug
 * look graded without anyone having shown it acts on *this* mechanism: already being tried,
 * not a mechanism finding.
 */
export function cellTone(row: LadderRow): Tone {
  if (isWarning(row)) return 'broken';
  if (row.curated_rung !== null) return (row.rung ?? 0) >= 4 ? 'good' : 'decision';
  return 'machinery';
}

export interface LadderCell {
  row: LadderRow;
  tone: Tone;
}

export interface LadderMatrixRow {
  drug_name: string;
  /** Direction id → the graded row, where one exists. */
  cells: Record<string, LadderCell>;
  /** The best rung this drug reached on any direction. */
  best: number;
  /** True when at least one of its cells rests on a PMID a person read. */
  curated: boolean;
}

export interface LadderMatrix {
  /** Curated drugs first, then automated-only; each block by best rung, then by name. */
  rows: LadderMatrixRow[];
  /** The direction columns actually present at or above `MIN_SHOWN_RUNG`. */
  directions: string[];
  /** Best rung → how many drugs stop there. Keyed by number for a stat row. */
  byBestRung: Map<number, number>;
}

/** Directions sort `D1…D4` first, then anything else (`pathway`) alphabetically. */
function directionOrder(a: string, b: string): number {
  const rank = (d: string) => (/^D\d+$/.test(d) ? 0 : 1);
  return rank(a) - rank(b) || a.localeCompare(b);
}

/** The drug × direction matrix of everything graded above rung 1. */
export function ladderMatrix(ladder: LadderRow[], minRung = MIN_SHOWN_RUNG): LadderMatrix {
  const graded = ladder.filter((r) => (r.rung ?? 0) >= minRung);
  const byDrug = new Map<string, LadderMatrixRow>();
  const directions = new Set<string>();

  for (const row of graded) {
    directions.add(row.direction_id);
    const entry = byDrug.get(row.drug_name) ?? {
      drug_name: row.drug_name,
      cells: {},
      best: 0,
      curated: false,
    };
    entry.cells[row.direction_id] = { row, tone: cellTone(row) };
    entry.best = Math.max(entry.best, row.rung ?? 0);
    entry.curated = entry.curated || row.curated_rung !== null;
    byDrug.set(row.drug_name, entry);
  }

  const rows = [...byDrug.values()].sort(
    (a, b) =>
      Number(b.curated) - Number(a.curated) ||
      b.best - a.best ||
      a.drug_name.localeCompare(b.drug_name),
  );

  const byBestRung = new Map<number, number>();
  for (const r of rows) byBestRung.set(r.best, (byBestRung.get(r.best) ?? 0) + 1);

  return { rows, directions: [...directions].sort(directionOrder), byBestRung };
}

/** How many registry studies admitting children exist per drug. One pass over ~11k rows. */
export function pediatricStudiesPerDrug(trials: PediatricTrialRow[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const t of trials) out.set(t.drug_name, (out.get(t.drug_name) ?? 0) + 1);
  return out;
}

/** Drug name → does its US label carry a section 8.4, per the ladder. */
export function pediatricLabelPerDrug(ladder: LadderRow[]): Map<string, boolean> {
  const out = new Map<string, boolean>();
  for (const r of ladder)
    out.set(r.drug_name, (out.get(r.drug_name) ?? false) || !!r.pediatric_label);
  return out;
}

/** The shortlist's two halves: what the report may argue, and what only has a context trial. */
export function splitShortlist(shortlist: ShortlistRow[]): {
  argue: ShortlistRow[];
  contextOnly: ShortlistRow[];
} {
  return {
    argue: shortlist.filter((r) => r.verdict === 'argue'),
    contextOnly: shortlist.filter((r) => r.verdict !== 'argue'),
  };
}

/** The do-not table's groups, in the order a reader needs them: worst first. */
export const DO_NOT_ORDER = ['do not', 'caution', 'standard of care'] as const;

export const DO_NOT_TONE: Record<string, Tone> = {
  'do not': 'broken',
  caution: 'decision',
  'standard of care': 'machinery',
};

/** Verdict → its rows, in `DO_NOT_ORDER`. Empty groups are dropped, not rendered blank. */
export function groupDoNot(rows: ShortlistRow[]): Array<[string, ShortlistRow[]]> {
  return DO_NOT_ORDER.map(
    (verdict) => [verdict, rows.filter((r) => r.verdict === verdict)] as [string, ShortlistRow[]],
  ).filter(([, group]) => group.length > 0);
}

/** `https://pubmed.ncbi.nlm.nih.gov/<pmid>/` — the one place the URL is spelled. */
export const pubmed = (pmid: string): string => `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;

/**
 * A card fact whose value starts with UNMEASURED is a stated gap, not a result.
 *
 * The test is on the value rather than on the id, because "which fact is missing" is a
 * property of the card and must survive the card being revised again.
 */
export const isUnmeasured = (f: MeasuredFact): boolean => /^UNMEASURED\b/i.test(f.value.trim());
