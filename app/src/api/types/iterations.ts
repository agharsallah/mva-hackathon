/**
 * The iterations overview: `GET /api/iterations`, and the per-iteration data catalogue.
 *
 * Two axes the rest of the app keeps apart. A **research iteration** (`docs/iteration<n>/`) is
 * one route through the case — its steps, its claims, its methodology entries. A
 * **submission iteration** (`submissions/<track>/iteration-<n>/`) is one folder the
 * organisers would receive. Their numbers do not line up (Track 2's iteration-4 folder is
 * built from research iteration 4; Track 1 has no iteration-4 folder), so this payload lists
 * both and says which research iterations each folder cites.
 *
 * The **catalogue** is derived, never typed: every dataset a set of methodology entries
 * names (a warehouse table, a committed data file, a gitignored build file), joined to the
 * lineage ledger (`warehouse.data_lineage`) and to the provenance manifest beside a file.
 * `role: 'produced'` needs attribution evidence — a ledger edge or manifest that cites one of
 * the entries; everything else is `cited`: the entries name it, which says nothing about
 * whether they read or wrote it. No genomic position passes through here.
 */

import type { IterationState } from './submissions';

export type DatasetKind = 'table' | 'file' | 'raw' | 'clinical' | 'reference';

/** `produced` = a ledger edge or manifest attributes it to one of the entries; `cited` = only named. */
export type DatasetRole = 'produced' | 'cited';

/** `edge` = a `warehouse.data_lineage` row · `manifest` = a `*.provenance.json` beside it · `none`. */
export type LineageStatus = 'edge' | 'manifest' | 'none';

/** One upstream input of a dataset, from its newest lineage edge or its manifest. */
export interface CatalogInput {
  ref: string;
  /** '' when the edge or manifest records no digest. */
  sha256: string;
}

export interface CatalogDataset {
  /** `track2.shortlist`, `ressources/track2/shortlist.tsv`, `build/it4/tables/x.parquet`, `s3://…`. */
  ref: string;
  kind: DatasetKind;
  role: DatasetRole;
  /** Methodology entry numbers that name or produced it, sorted: `['084', '154']`. */
  entries: string[];
  /** Research step folders those entries sit in: `['iteration2/step-3']`. */
  steps: string[];
  rows: number | null;
  /** '' when unknown. */
  sha256: string;
  version: string;
  /** The edge's `tool` or the manifest's `built_by`; '' when unknown. */
  built_by: string;
  /** ISO-8601; '' when unknown. */
  built_at: string;
  lineage: LineageStatus;
  /** `warehouse.data_lineage`, the manifest's repo path, or ''. */
  provenance: string;
  inputs: CatalogInput[];
  /** True for tracked files; false for gitignored `build/` paths and for warehouse tables. */
  committed: boolean;
  /** File present on this checkout, or table present in the ledger. */
  exists: boolean;
}

export interface CatalogCoverage {
  datasets: number;
  produced: number;
  /** Datasets whose `lineage` is not `none`. */
  with_lineage: number;
  tables: number;
  files: number;
}

export interface IterationCatalog {
  /** False when the ledger was unreachable: tables then carry `lineage: 'none'` for that reason. */
  available: boolean;
  note: string;
  /** Repo paths of the methodology entries scanned. */
  entries: string[];
  datasets: CatalogDataset[];
  coverage: CatalogCoverage;
}

/** Register claims by their latest status: `{ supported: 10, refuted: 3, testing: 1 }`. */
export type ClaimCounts = Record<string, number>;

export interface ResearchIterationOverview {
  /** `iteration1` … */
  iteration: string;
  /** The iteration's own one-line docstring from its step map. */
  summary: string;
  /** False for a folder with a plan and no step map (iteration 3). */
  declared: boolean;
  current: boolean;
  steps: number;
  done: number;
  open: number;
  /** Declared research steps per track they feed. */
  tracks: { track1: number; track2: number; both: number };
  claims: ClaimCounts;
  entries: { count: number; first: string; last: string };
  /** Submission folder keys (`track1/iteration-2`) whose README cites one of this iteration's entries. */
  submissions: string[];
  /** The app route of this iteration under each track, or null when it has no step for that track. */
  routes: { track1: string | null; track2: string | null };
  docs: string;
  catalog: IterationCatalog;
}

export interface SubmissionOverview {
  /** `track1/iteration-2` — also the `/submissions?it=` value. */
  key: string;
  track: string;
  number: number;
  folder: string;
  state: IterationState;
  standing: string;
  uploaded: boolean;
  /** Track 1 is scored by the oracle; Track 2 by the judging panel. */
  judged_by: 'oracle' | 'panel';
  /** Research iterations whose entries the folder's README cites, sorted. */
  research: string[];
  /** Methodology entries the contributions table links. */
  entries: number;
  hypotheses: number;
  figures: number;
  /** Rows of the README's contributions table. */
  steps: number;
  /** The oracle's reply when uploaded, else null. */
  reply: string | null;
  lineage: { available: boolean; edges: number; sources: number };
  catalog: CatalogCoverage;
}

/** GET /api/iterations */
export interface IterationsOverview {
  research: ResearchIterationOverview[];
  submissions: SubmissionOverview[];
  /** The whole ledger: how many edges name the methodology entry that produced them. */
  ledger: { available: boolean; edges: number; attributed: number; note: string };
}
