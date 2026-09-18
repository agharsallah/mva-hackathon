/**
 * The small, testable decisions the Submissions exhibits share.
 *
 * Kept out of the components so the colour rule for a decode row and the rendering of a
 * selector clause are one function each, readable next to the sentence that explains them
 * on the page — and so no component file exports anything but components.
 */

import type {
  DecodeTable,
  IterationState,
  Selectors,
  SelectorSpec,
  SubmissionIteration,
} from '../../api/types';
import { REPO_BLOB } from '../../lib/dictionary';
import type { Tone } from '../../lib/palette';

/** A repo-relative path as a GitHub blob URL, so a methodology link opens where it lives. */
export const blobUrl = (path: string): string => `${REPO_BLOB}${path}`;

/**
 * Where an iteration stands, as a colour.
 *
 * `frozen` is green because a frozen folder is the goal state — it was uploaded and can
 * never be edited again. `ready` is yellow: it is a decision point, the gate before a
 * non-renewable probe is spent. `draft` is plain machinery, still being written.
 */
export const STATE_TONE: Record<IterationState, Tone> = {
  draft: 'machinery',
  ready: 'decision',
  frozen: 'good',
};

export const STATE_MEANING: Record<IterationState, string> = {
  draft: 'still being written — not rehearsed',
  ready: 'built and rehearsed, not uploaded',
  frozen: 'uploaded — this folder can never be edited again',
};

/** Newest first: the reader's default question is about the latest iteration. */
export function newestFirst(iterations: SubmissionIteration[]): SubmissionIteration[] {
  return [...iterations].sort((a, b) => b.number - a.number || a.track.localeCompare(b.track));
}

/**
 * Whether this track is judged by a panel rather than by the organisers' scorer.
 *
 * Track 1 uploads a predictions file and gets a number back, so its folder carries a CSV, a
 * decode table and the coordinate-free selectors behind every row. **Track 2 has no scorer
 * at all**: it is read by people, from the report, the filled methods form, the repository
 * and a three-minute video. Those sections are therefore absent by rule, not missing by
 * accident, and the dossier says so instead of drawing empty frames.
 */
export const isPanelJudged = (it: { track: string }): boolean => it.track === 'track2';

/** What a panel-judged track hands over in place of a scored predictions file. */
export const PANEL_DELIVERABLES = [
  'the report (PDF)',
  'the filled methods form (xlsx)',
  'the repository',
  'a 3-minute video',
] as const;

/** `track1` + `1` → `track1 · iteration 1`, the label used in the selector and the header. */
export const iterationKey = (it: { track: string; number: number }): string =>
  `${it.track}/iteration-${it.number}`;

// ── the decode table ────────────────────────────────────────────────────────────────────

/**
 * What one row of the decode table means, as a tone.
 *
 * The table lists every reply the scorer can give. Exactly one of them is the answer we
 * want (green), one says the pair is not in the callset at all (red), one cannot tell two
 * hypotheses apart (yellow — the ambiguity that caps the information gain), and the rest
 * are informative-but-wrong replies (blue).
 */
export type DecodeTone = Extract<Tone, 'good' | 'broken' | 'decision' | 'machinery'>;

export interface DecodeRow {
  cells: string[];
  tone: DecodeTone;
  /** One clause saying why this row carries that colour, shown as the row's title. */
  why: string;
}

const MISSING = new Set(['—', '-', '', 'none']);

/** The index of a column whose header contains `needle`, or -1. */
function columnOf(columns: string[], needle: string): number {
  return columns.findIndex((c) => c.toLowerCase().includes(needle));
}

export function decodeRows(table: DecodeTable): DecodeRow[] {
  const fullIdx = columnOf(table.columns, 'full match');
  const survivorIdx = columnOf(table.columns, 'survivor');
  const fmaxIdx = columnOf(table.columns, 'max');

  return table.rows.map((cells) => {
    const full = (cells[fullIdx] ?? '').trim();
    const survivors = (cells[survivorIdx] ?? '').trim();
    const fmax = Number((cells[fmaxIdx] ?? '').trim());
    const ambiguous = survivors.includes(',');

    if (full === '1') {
      return {
        cells,
        tone: 'good',
        why: 'the rank-1 pair is right — full marks, nothing left to ask',
      };
    }
    if (ambiguous) {
      return {
        cells,
        tone: 'decision',
        why: 'this reply cannot separate two hypotheses — the ambiguity that caps the information gain',
      };
    }
    if (MISSING.has(full.toLowerCase()) && (fmax === 0 || Number.isNaN(fmax))) {
      return { cells, tone: 'broken', why: 'no match at all — neither allele is causal' };
    }
    return {
      cells,
      tone: 'machinery',
      why: 'an informative wrong answer: it names which alternative pairing is real',
    };
  });
}

// ── selectors ───────────────────────────────────────────────────────────────────────────

/** `null` → `NULL`, `true` → `TRUE`, everything else → its own text. */
function literal(value: unknown): string {
  if (value === null) return 'NULL';
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  return String(value);
}

/**
 * One allele's selector as the SQL it stands for:
 * `gene = BUB1B AND consequence LIKE %stop_gained%`.
 *
 * No coordinate appears, by construction — the clause names what the allele *is*, and the
 * resolver turns it into a position on a machine that has database access.
 */
export function whereClause(spec: SelectorSpec): string {
  return spec.where
    .map(([column, op, value]) => `${column} ${op.toUpperCase()} ${literal(value)}`)
    .join(' AND ');
}

/** `fbc9e750…` — enough to recognise the file, never the whole 64 characters inline. */
export const shortSha = (sha: string | null): string => (sha ? `${sha.slice(0, 12)}…` : '—');

// ── numbers, and the small facts the beginner-facing exhibits read off a payload ─────────

/** A decode-table cell as a number, or `null` for the em dash the markdown writes for "none". */
export function cellNumber(cell: string | undefined): number | null {
  const text = (cell ?? '').trim();
  if (MISSING.has(text.toLowerCase())) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

/** The index of the column whose header contains `needle`, or -1. Exported for the exhibits. */
export const decodeColumn = (table: DecodeTable, needle: string): number =>
  columnOf(table.columns, needle);

/**
 * The scorer's rank-point tiers: being right is worth less the further down the file it sits.
 * Ranks beyond the last tier earn nothing, which is why the tail of a submission is free.
 */
export const RANK_TIERS: { from: number; to: number; points: number }[] = [
  { from: 1, to: 1, points: 100 },
  { from: 2, to: 3, points: 50 },
  { from: 4, to: 5, points: 25 },
  { from: 6, to: 10, points: 10 },
];

/** What rank `rank` would be worth, in rank points. */
export function rankPoints(rank: number): number {
  return RANK_TIERS.find((t) => rank >= t.from && rank <= t.to)?.points ?? 0;
}

/**
 * The gene the primary rows are about, read off the selectors rather than hard-coded: the
 * value of the first `gene =` clause among the alleles. `null` when no clause names one.
 */
export function primaryGene(selectors: Selectors): string | null {
  for (const spec of Object.values(selectors.alleles)) {
    for (const [column, , value] of spec.where) {
      if (column.toLowerCase() === 'gene' && typeof value === 'string') return value;
    }
  }
  return null;
}

/**
 * An epcr for the eye: two decimals when it carries them, significant digits when the
 * value is a small derived share (0.0004758 must not read as 0.00).
 */
export function fmtEpcr(value: number): string {
  return value >= 0.01 ? value.toFixed(value >= 0.1 ? 2 : 3) : value.toPrecision(3);
}
