/**
 * The model zoo's payloads — `/api/zoo/*`, one type per route.
 *
 * These mirror the pinned wave-3 contract (`build/it4/agents/BRIEF-wave3.md`) field for
 * field. The zoo is deliberately **case-agnostic**: nothing here names a gene, a disease or
 * an iteration as a type. The case (which gene is "confirmed", which iteration's docs folder
 * the reports come from) is a *value* the API reads from `src/mva/zoo/zoo.example.toml` and
 * hands back on `/api/zoo/case` (and inside `/api/zoo/ranks`), so running the zoo on another
 * illness changes the configuration, not this file.
 *
 * Optional fields are optional because the contract pins a minimum, not a maximum: a route
 * may carry more (a citation, the stage list, the fused score) and every page degrades to a
 * stated absence rather than a blank when it does not.
 */

/** One lane's card: what the model is, what it may be used for, and what it could score. */
export interface ZooModel {
  key: string;
  name: string;
  version: string;
  /** 1 = precomputed lookup · 2 = local CPU process · 3 = remote GPU. */
  tier: number;
  /** `missense` | `splice` | `any` | `structure` | `disease-node`. */
  input_class?: string;
  /** Where the number comes from: `warehouse-column`, `table`, `vep-rest`, … */
  source: string;
  /** The module under `mva.zoo.adapters` that speaks to that source. */
  adapter: string;
  licence: string;
  licence_url?: string;
  non_commercial: boolean;
  /** Trained on a variant catalogue (ClinVar/HGMD) — the merge is printed with and without. */
  catalogue_adjacent: boolean;
  enabled: boolean;
  /** `mvp` | `opt-a` | `opt-b`. */
  scope: string;
  /** Verified PMID, or an empty string where none has been checked. */
  pmid: string;
  notes?: string;
  /** What the adapter needs to speak to this source: a table, a column, an endpoint. */
  params?: Record<string, unknown>;
  /** What a run of this lane would have to fetch first, in words. */
  ships?: string;
  /** Null for a lane that has not run: no coverage was measured, which is not zero coverage. */
  coverage: ZooCoverage | null;
}

export interface ZooCoverage {
  model?: string;
  scored: number;
  total: number;
  /** `scored / total`, as the API computed it — never recomputed on the page. */
  fraction: number;
  /** Consequence class → what this lane could and could not score inside it. */
  by_consequence: Record<string, { scored: number; total: number }>;
}

/**
 * The case the run was configured for — `/api/zoo/case`, and repeated inside `/api/zoo/ranks`.
 *
 * Values, never constants: `gene_source` names the exact configuration key the gene came from,
 * so a page can show *where* the case was read rather than asserting it.
 */
export interface ZooCase {
  gene: string;
  /** The configuration key the gene was read from. */
  gene_source?: string;
  case?: {
    label?: string;
    iteration?: string;
    table_prefix?: string;
    confirmed_gene?: string;
    /** How a candidate pair for this case is defined, e.g. `lof+missense`. */
    confirmed_pair_rule?: string;
    phenotype_term_set?: string;
    hpo_table?: string;
  };
  config_path?: string;
  config_digest?: string;
  run_id?: string;
  /** `catalogue-free` (catalogue fields nulled) or `aware`. */
  mode?: string;
  merge_method?: string;
  rrf_k?: number;
  llm_mode?: string;
  models?: string[];
}

/** One ranked pair in a lane's own ordering. */
export interface ZooPairRank {
  gene: string;
  rank: number | null;
  percentile: number | null;
  min_score: number | null;
  max_score: number | null;
  phase?: string | null;
  left_allele_id?: string | null;
  right_allele_id?: string | null;
  is_confirmed?: boolean;
}

/** Where the confirmed pair landed in one lane's ranking. Nulls mean "no opinion". */
export interface ZooConfirmed extends ZooPairRank {
  left_percentile: number | null;
  right_percentile: number | null;
}

export interface ZooLaneRank {
  model: string;
  version?: string;
  catalogue_adjacent: boolean;
  n_ranked: number;
  unscored_pairs: number;
  confirmed: ZooConfirmed | null;
  /** The head of this lane's own ranking, as far as the run recorded it. */
  top?: ZooPairRank[];
}

export interface ZooRanks {
  run_id: string;
  /** The configured case, as received. Absent means the API did not name one. */
  case?: ZooCase;
  per_model: ZooLaneRank[];
  pairs_total: number;
  skipped_genes: string[];
  /**
   * False when the run never recorded which genes it skipped. An empty `skipped_genes` then
   * means "not recorded", **not** "none skipped", and every page must say the difference.
   */
  skipped_genes_recorded?: boolean;
}

/** Spearman ρ between every pair of lanes, with the overlap `n` each ρ was computed on. */
export interface ZooMatrix {
  models: string[];
  rho: (number | null)[][];
  n: number[][];
}

export interface ZooConsensus {
  rank: number;
  /** How many pairs the fusion ranked. */
  n: number;
  percentile?: number;
  /** The reciprocal-rank-fusion score itself. */
  fused?: number;
  lanes?: string[];
  excluded_lanes?: string[];
  /** The fusion's damping constant, as this consensus was computed with it. */
  k?: number;
}

export interface ZooDisagreement {
  allele_id: string;
  gene: string | null;
  top_model: string;
  top_pct: number;
  top_score?: number;
  bottom_model: string;
  bottom_pct: number;
  bottom_score?: number;
}

export interface ZooMerge {
  run_id?: string;
  matrix: ZooMatrix;
  consensus: { catalogue_free: ZooConsensus; all_lanes: ZooConsensus };
  disagreements: ZooDisagreement[];
  /** Present when the route returned a head of a longer list. */
  disagreements_total?: number;
  /** Per-lane summary the merge was built from, when the route carries it. */
  lanes?: unknown[];
  /** The merge's own lineage stamp: sources and the tool that wrote it. */
  lineage?: { run_id?: string; tool?: string; sources?: string[] };
  /** `fusion` | `fusion+synthesis` | `judge`. */
  method: string;
  rrf_k?: number;
  citation?: string;
  generated_at?: string;
}

/** One stage of the workflow, as the run manifest recorded it. */
export interface ZooStage {
  stage: string;
  seconds: number;
  rows: number;
  skipped: boolean;
  note: string;
}

export interface ZooRun {
  run_id: string;
  started: string;
  finished?: string;
  wall_clock_s: number;
  dollars: number;
  /** model key → the exact artefact version that ran. */
  models: Record<string, string>;
  /** model key → where it ran: `laptop`, `vep-rest`, `modal`, … */
  venues: Record<string, string>;
  config_digest: string;
  config_path?: string;
  mode?: string;
  merge_method?: string;
  outputs?: string[];
  stages?: ZooStage[];
}

/**
 * One rendered report. `figures` are the paths the Markdown references, relative to the
 * report file — the route names them, it does not serve their bytes, so a page shows the
 * figure's path rather than a broken image.
 */
export interface ZooReport {
  key: string;
  title?: string;
  path?: string;
  modified?: string;
  markdown: string;
  figures: string[];
}

/** `key` → report. `merged` is the cross-lane report; every other key is a lane. */
export type ZooReports = Record<string, ZooReport>;

/** `/api/zoo/lineage` — the edges, plus the table vocabulary the route filters on. */
export interface ZooLineage {
  /** Every zoo table the route knows about, whether or not it has an edge. */
  tables: string[];
  /** The table asked for, or null for all of them. */
  table: string | null;
  rows: ZooLineageRow[];
}

/** One `warehouse.data_lineage` row: what produced a zoo table, from what. */
export interface ZooLineageRow {
  produced_at: string;
  tool: string;
  notes: string | null;
  target_schema: string;
  target_table: string;
  target_rows: number;
  source_kind: string;
  source_ref: string;
  source_version: string | null;
  source_sha256: string | null;
  transform: string;
}

/** One allele's row from a single lane. `aux` is the adapter's own JSON, kept verbatim. */
export interface ZooScoreRow {
  model: string;
  version: string;
  score: number | null;
  /** The adapter's own extra fields, as the cache stored them. */
  aux: Record<string, unknown> | null;
  digest?: string;
  venue: string;
  licence: string;
  run_id: string;
  ts: string;
}

/**
 * One allele record with every lane's row on it.
 *
 * The HGVS spellings are served by the live API and are **null in the committed fixture**: an
 * HGVS string is this patient's allele spelling, and no patient spelling enters a tracked
 * file. The fixture records that redaction in its own `_redacted` field.
 */
export interface ZooAllele {
  allele_id: string;
  gene: string;
  transcript?: string | null;
  consequence: string;
  hgvs_c: string | null;
  hgvs_p: string | null;
  uniprot?: string | null;
  is_read_only: boolean;
  af_gnomad?: number | null;
  clin_sig?: string | null;
  /** How the record itself was built — the VEP release and assembly. */
  source?: string;
  rows: ZooScoreRow[];
}

/** `/api/zoo/scores/gene/{symbol}` — every allele of one gene, with every lane's opinion. */
export interface ZooGeneScores {
  gene: string;
  models: string[];
  records: ZooAllele[];
  /** How many of the records carry at least one lane's score. */
  scored_records?: number;
}
