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

/** GET /api/probe/ledger — the 18-probe oracle budget, spend by spend. */
export interface ProbeLedgerRow {
  probe_id: string;
  logged_at: string;
  track: string;
  probe_type: string;
  payload: string;
  n_rows: number | null;
  response: string | null;
  score: number | null;
  rationale: string | null;
}
