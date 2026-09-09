/** GET /api/provenance/lineage */
export interface LineageRow {
  produced_at: string;
  target_schema: string;
  target_table: string;
  target_rows: number;
  source_kind: string;
  source_ref: string;
  source_version: string | null;
  source_sha256: string | null;
  transform: string;
  tool: string;
  notes: string | null;
}

/** GET /api/provenance/derivations */
export interface DerivationRow {
  run_at: string;
  derivation: string;
  question: string;
  n_rows: number;
}

/** GET /api/provenance/sources — the delivery, one row per object. */
export interface SourceObjectRow {
  file_name: string;
  kind: string;
  role: string;
  size_bytes: number;
  hash_verified: boolean;
  sha256_source: string | null;
  version_id: string | null;
  lane: number | null;
  read_num: number | null;
}

/** GET /api/probe/ledger — the 6-probe oracle budget, spend by spend. */
export interface ProbeLedgerRow {
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

/**
 * GET /api/provenance/reference — one row per committed reference table or offline
 * fixture directory, read off the manifest beside the bytes.
 *
 * The three rows above come from `warehouse.data_lineage`, which records *derivations*:
 * table X was computed from object Y by transform Z. Reference data has none of that. A
 * gnomAD constraint table, an HPO release, an Ensembl gene record and an AlphaFold model
 * are **fetched**, so there is no upstream table and no transform, and an edge claiming
 * one would be fabricated. What they have instead is a `*provenance.json` manifest
 * committed next to the file, written by the build tool on every run — never by hand —
 * and this row is the normalised view of one of those.
 */
export interface ReferenceProvenanceRow {
  /** What was built, e.g. `structure_genes`, `protein-structure fixtures`. */
  name: string;
  /** `reference` = a committed table under `ressources/reference`; `fixture` = an offline payload directory. */
  kind: 'reference' | 'fixture';
  /** Repository-relative path of the manifest itself. */
  path: string;
  /** ISO-8601 instant the build ran. */
  built_at: string;
  /** The tool that wrote it, e.g. `tools/build_gene_set.py`. */
  built_by: string;
  /** Short commit at build time — which precedes the commit that lands the built files. */
  code_version: string;
  /** What was fetched or read. `release` absorbs a version; both digest fields are null for a live API. */
  inputs: Array<{
    name: string;
    url: string;
    release: string | null;
    sha256: string | null;
    bytes: number | null;
  }>;
  /** What was written. `rows` is null for a payload whose size is not a row count. */
  outputs: Array<{
    path: string;
    sha256: string;
    bytes: number | null;
    rows: number | null;
  }>;
  /** One line saying what the build actually did. */
  note: string;
}
