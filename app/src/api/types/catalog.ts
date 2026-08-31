/**
 * The data catalogue: what every piece of data is, what it contains, when it arrived,
 * where it lives. Two endpoints — the immutable raw delivery, and everything derived
 * from it.
 */

/** GET /api/catalog/objects — one row per object in the store. */
export interface CatalogObjectRow {
  file_name: string;
  /** Key inside the bucket, without the scheme or bucket name. */
  object_key: string;
  /** Fully-qualified location, e.g. `s3://mva/source/WGS_….vcf.gz`. */
  location: string;
  kind: string;
  role: string;
  /** What the file contains, in words. */
  description: string;
  size_bytes: number;
  content_type: string | null;
  sha256: string | null;
  /** Who the hash came from — live values: `publisher`, `upload` (own upload), or `""`. */
  sha256_source: string | null;
  hash_verified: boolean;
  version_id: string | null;
  last_modified: string | null;
  /** ISO instant, or null for objects that predate the ingest ledger. */
  first_uploaded_at: string | null;
  sample: string | null;
  flowcell: string | null;
  /** Null except on FASTQ objects. */
  lane: number | null;
  /** Null except on FASTQ objects. */
  read_num: number | null;
}

/** GET /api/catalog/tables — one row per warehouse or results table. */
export interface CatalogTableRow {
  schema: string;
  table: string;
  /** Null when no catalogue entry, derivation question or fallback describes the table. */
  description: string | null;
  /** The catalogue's count for the table, as of its last refresh. */
  rows: number | null;
  /** Null together with `source_*` and `tool` when no lineage edge exists. */
  produced_at: string | null;
  source_kind: string | null;
  source_ref: string | null;
  tool: string | null;
  /**
   * The verb that writes the table, and whether it replaces it or appends to it —
   * e.g. `mva-warehouse stage + pg-ingest`, `append-only ledger — written by …`.
   * Null when the server's semantics registry does not know the table.
   */
  created_by: string | null;
  /** One sentence: the reason the table exists. Null for the same reason. */
  why: string | null;
}

/** GET /api/catalog/columns — one row per column of every warehouse/results table. */
export interface CatalogColumnRow {
  schema: string;
  table: string;
  column: string;
  /** The SQL type as `information_schema` spells it, e.g. `character varying`. */
  data_type: string;
  /** 1-based position of the column in the table. */
  ordinal: number;
  /** What the column means. Null = nothing describes it; render the gap, never blank. */
  meaning: string | null;
}
