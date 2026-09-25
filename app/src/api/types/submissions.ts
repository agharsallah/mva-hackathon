/**
 * The submission iterations: `GET /api/submissions`.
 *
 * One row per `submissions/<track>/iteration-<n>/` folder on disk, joined to three things
 * the folder itself does not hold: the warehouse's lineage edges, the probe ledger, and the
 * research register. A submission is the one artefact that leaves this repository, so the
 * payload is deliberately the *whole* dossier — what would be uploaded, what produced it,
 * what it would cost, and what every possible reply would mean.
 *
 * Nothing here carries a genomic position. The predictions CSV does, which is exactly why
 * it is never committed: the folder holds a **selector** (a `WHERE` clause over a warehouse
 * result table) per allele instead, and only `csv.sha256` identifies the file that was
 * built from them. See `SelectorSpec`.
 */

/** `draft` = still being written · `ready` = built and rehearsed · `frozen` = uploaded. */
export type IterationState = 'draft' | 'ready' | 'frozen';

/** One file in the folder, classified by what the organisers do with it. */
export interface Deliverable {
  name: string;
  kind:
    | 'readme'
    | 'report-md'
    | 'report-pdf'
    | 'methods-json'
    | 'methods-xlsx'
    | 'decode-table'
    | 'selectors'
    | 'other';
  bytes: number;
  /** ISO-8601 modification instant. */
  modified: string;
}

/**
 * The predictions file. `path` is outside the repository and `sha256` is the only thing
 * committed about it — a content hash names the bytes without carrying them.
 */
export interface SubmissionCsv {
  path: string | null;
  sha256: string | null;
  rows: number | null;
}

/**
 * What every reply the scorer can give would mean, parsed out of `decode-table.md`.
 *
 * `rows` are raw cells in the markdown's column order, so the table renders whatever the
 * iteration wrote rather than a shape this app fixed in advance.
 */
export interface DecodeTable {
  columns: string[];
  rows: string[][];
  /** The entropy / expected-information-gain sentence under the table. */
  summary: string;
  /** The "Rows, in rank order: …" sentence — the submitted rank order, by label. */
  row_order: string;
}

/** One allele, named by what it *is* rather than by where it sits. */
export interface SelectorSpec {
  /** The warehouse result table the clause runs against, e.g. `results.coding_candidates`. */
  table: string;
  /** `[column, operator, value]`, ANDed. Must match exactly one row. */
  where: [string, string, unknown][];
}

/** One row of the predictions CSV, by allele name instead of by coordinate. */
export interface SelectorRow {
  /** 1-based position in the submitted file. */
  rank: number;
  variant: string;
  partner: string | null;
  /** Estimated probability of causal relationship — the scorer's confidence column. */
  epcr: number;
  finding_type: 'primary' | 'secondary';
  label: string;
  notes: string;
  /** The ranker's pair (or single-allele) score the epcr was derived from; null when typed. */
  score?: number | null;
  /** The register claim this row tests, when it is the anchor row. */
  hypothesis?: string | null;
}

/** One entry in the hypothesis space the decode table was computed over. */
export interface SelectorHypothesis {
  label: string;
  alleles: string[];
  prior: number;
  /** `declared` for an unseen-allele hypothesis, `row <label>` when derived from a row. */
  prior_source?: string;
}

/** What one result table says about a selected allele — never its position. */
export interface AlleleFacts {
  name: string;
  table: string;
  gene: string | null;
  consequence: string | null;
  impact: string | null;
  zygosity: string | null;
  filter: string | null;
  dp: number | null;
  vaf: number | null;
  gnomad_af: number | null;
  clin_sig: string | null;
  rsid: string | null;
  is_clinvar_plp: boolean | null;
  /** rarity × severity, the ranker's single-allele term. */
  score: number;
}

/**
 * How every non-coordinate field was derived (`derivation.json`): the anchor hypothesis
 * and its register confidence, the facts per allele, and the arithmetic line by line.
 */
export interface Derivation {
  anchor: { row?: string; hypothesis?: string; confidence?: number };
  parameters: Record<string, number>;
  alleles: Record<string, AlleleFacts>;
  arithmetic: string[];
}

export interface Selectors {
  alleles: Record<string, SelectorSpec>;
  rows: SelectorRow[];
  hypotheses: SelectorHypothesis[];
  /** Null for an iteration whose rows were typed by hand. */
  derivation?: Derivation | null;
}

/** One answer in the organisers' methods form; `row` is the template's row number. */
export interface MethodsFormAnswer {
  row: string;
  answer: string;
}

/** A roadmap step that contributed, with the methodology entries that prove it. */
export interface StepContribution {
  step: string;
  contribution: string;
  methodology: { label: string; path: string }[];
}

/** A rendered figure. `url` is the API route that serves the PNG. */
export interface SubmissionFigure {
  slug: string;
  path: string;
  url: string;
}

export interface SubmissionReport {
  path: string;
  markdown: string;
}

/**
 * A root or input this iteration rests on.
 *
 * `raw` is the delivered VCF object, `clinical` the phenotype document — the two data
 * sources every conclusion must be cross-referenced against. `reference` is public
 * annotation, `table` a warehouse result table, `file` a committed spec or a downloaded
 * release. A walk through a panel-judged iteration's tables also meets the kinds its
 * recorders wrote (`api`, `card`, `derived`), kept under the edge's own word.
 */
export interface LineageSource {
  kind: 'raw' | 'clinical' | 'reference' | 'table' | 'file' | (string & {});
  ref: string;
  version: string;
  sha256: string;
  note: string;
}

/** One recorded derivation edge — the same row shape as `/api/provenance/lineage`. */
export interface SubmissionLineageEdge {
  produced_at: string;
  target_schema: string;
  target_table: string;
  target_rows: number;
  source_kind: string;
  source_ref: string;
  source_version: string;
  source_sha256: string;
  transform: string;
  tool: string;
  notes: string;
  is_current: boolean;
}

/**
 * `available: false` means the database was unreachable, so `edges` is empty for a reason
 * the page must state rather than render as "no lineage". `sources` is still populated:
 * the roots that can be read off disk survive a dead warehouse.
 */
export interface SubmissionLineage {
  available: boolean;
  note: string;
  sources: LineageSource[];
  edges: SubmissionLineageEdge[];
}

/** One revision of one register claim — append-only, oldest first. */
export interface RegisterRevision {
  hypothesis_id: string;
  revision: number;
  status: string;
  /** A stated heuristic, never a calibrated probability. Null before a verdict. */
  confidence: number | null;
  reasoning: string;
  recorded_at: string;
  step: string;
  statement: string;
}

/** The rows `/api/probe/ledger` returns, narrowed to this iteration. */
export interface SubmissionProbe {
  probe_id: string;
  logged_at: string;
  track: string;
  probe_type: string;
  submitted_by?: string | null;
  submission_ref?: string | null;
  /** sha256 of the submitted CSV. The CSV itself holds coordinates and never leaves the warehouse. */
  payload_sha256: string;
  n_rows: number | null;
  response: string | null;
  score: number | null;
  rationale: string | null;
}

export interface SubmissionAudit {
  probes: SubmissionProbe[];
  register: RegisterRevision[];
}

/** One `submissions/<track>/iteration-<n>/` folder, with everything joined to it. */
export interface SubmissionIteration {
  track: string;
  number: number;
  folder: string;
  state: IterationState;
  /** The folder README's `**Standing:**` (or `**Frozen:**`) line, markdown stripped. */
  standing: string;
  uploaded: boolean;
  csv: SubmissionCsv;
  deliverables: Deliverable[];
  decode_table: DecodeTable;
  selectors: Selectors;
  methods_form: MethodsFormAnswer[];
  contributions: StepContribution[];
  /** `H\d{3}` ids named anywhere in the folder, unique and sorted. */
  hypotheses: string[];
  figures: SubmissionFigure[];
  report: SubmissionReport;
  lineage: SubmissionLineage;
  audit: SubmissionAudit;
}

/** GET /api/submissions */
export interface Submissions {
  iterations: SubmissionIteration[];
}
