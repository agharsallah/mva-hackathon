/**
 * The research register: `warehouse.hypotheses` and `warehouse.evidence`.
 *
 * Both endpoints answer with a {@link Register} rather than a bare list, because these two
 * tables are created on first write by `mva-science` and may not exist yet. "No claim has
 * been recorded" and "the register has never been written" are different facts, and the
 * page says which one is true.
 */

/** Where a claim stands. Mirrors `mva.science.hypothesis.Status`. */
export type HypothesisStatus = 'proposed' | 'testing' | 'supported' | 'refuted' | 'superseded';

/** Which way an observation cuts. Mirrors `mva.science.evidence.Direction`. */
export type EvidenceDirection = 'supports' | 'refutes' | 'neutral';

/**
 * One revision of one claim. The register is append-only: a changed belief is a new
 * `revision` of the same `hypothesis_id`, never an edit, so several rows share an id and
 * the highest revision is the current belief.
 */
export interface HypothesisRow {
  hypothesis_id: string;
  revision: number;
  recorded_at: string;
  /** The research step whose goal this claim serves, e.g. `step-2`. */
  step: string;
  statement: string;
  prediction: string;
  /** The observation that would kill the claim, written before the run. */
  refuted_by: string;
  /** Which line of attack the claim belongs to. Empty until a verdict names one. */
  path: string | null;
  gene: string | null;
  status: HypothesisStatus | string;
  /** A stated heuristic, not a calibrated probability. Null until a verdict is committed. */
  confidence: number | null;
  reasoning: string | null;
  author: string | null;
}

/** One sourced observation, bound to the claim it moves. */
export interface EvidenceRow {
  evidence_id: number;
  recorded_at: string;
  hypothesis_id: string;
  /** `measurement` | `annotation` | `literature` | `oracle` | `absence`. */
  kind: string;
  direction: EvidenceDirection | string;
  /** A human judgement in 0..1 of how much this observation moves the claim. */
  strength: number;
  claim: string;
  /** Methodology entry, table, PMID, ClinVar id or probe reply. Never null. */
  source_ref: string;
  /** The derivation edge behind the observation, or null when there is not one. */
  lineage_ref: string | null;
  author: string | null;
}

/**
 * The payload shape both science endpoints share.
 *
 * `table_exists: false` means the table has never been written — the endpoint is read-only
 * and deliberately does not create it. `table_exists: true` with `rows: []` would mean the
 * register exists and holds nothing.
 */
export interface Register<R> {
  table_exists: boolean;
  rows: R[];
}

/** GET /api/science/hypotheses */
export type HypothesisRegister = Register<HypothesisRow>;

/** GET /api/science/evidence */
export type EvidenceRegister = Register<EvidenceRow>;
