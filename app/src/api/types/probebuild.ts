/**
 * POST /api/probe/build — the submission-payload builder.
 *
 * Transcribed from `mva.viz.probebuild`. Two directions of contig spelling meet here and
 * the types deliberately do not hide it: `VariantRef.chrom` goes **out** of the browser
 * bare, the way `/api/panel/annotations` serves it ("15"), and comes back inside `csv`
 * `chr`-prefixed, the way the challenge template spells it ("chr15"). The server owns
 * that conversion — nothing in the app should ever build a chromosome string itself.
 *
 * This module is imported by path rather than through `api/types/index.ts` so the exhibit
 * does not depend on an edit to a barrel several agents are writing to at once.
 */

/** One allele, in the callset's own spelling: bare contig, 1-based position. */
export interface VariantRef {
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
}

export type FindingType = 'primary' | 'secondary';

/** One hypothesis. A pair goes in ONE row — two rows score partial credit only. */
export interface ProbeBuildRow {
  variant_1: VariantRef;
  variant_2?: VariantRef | null;
  epcr: number;
  finding_type: FindingType;
  notes?: string;
}

export interface ProbeBuildRequest {
  rows: ProbeBuildRow[];
}

/** `error` blocks the file; `warning` means the scorer reads the payload differently. */
export interface BuildProblem {
  severity: 'error' | 'warning';
  message: string;
}

/**
 * The emitted CSV scored against a synthetic truth equal to row 1's own alleles. It says
 * nothing about whether the candidates are right — only that the bytes parse the way the
 * scorer parses them. `passed` is `rank_points === 100 && f_max === 1`.
 */
export interface ProbeBuildSelfTest {
  rank_points: number;
  f_max: number;
  full_match_rank: number | null;
  passed: boolean;
}

/** `csv` is empty and `self_test` is null whenever `valid` is false. */
export interface ProbeBuildResult {
  csv: string;
  valid: boolean;
  problems: BuildProblem[];
  self_test: ProbeBuildSelfTest | null;
}
