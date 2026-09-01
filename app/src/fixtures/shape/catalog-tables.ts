import type { CatalogTableRow } from '../../api/types';
import { rows } from '../loader';
import { creationMap } from './catalog-semantics';

/**
 * FIXTURE — the warehouse and results table catalogue, one row per table.
 *
 * Row counts and descriptions fill a shape; the live API reads `information_schema`, the
 * warehouse catalogue and the lineage log. The rows exercise every gap in the contract:
 * two carry **no lineage edge** (`warehouse.gnomad_af_panel`, `results.kmer_counts`), one
 * carries **no description** (`warehouse.vep_staging`), one carries **no `created_by` and
 * no `why`** (`results.kmer_counts`, absent from `CREATION`), and `warehouse.variants_raw`
 * states in its description that its count is approximate rather than exact.
 *
 * `created_by` and `why` come from `shape/catalog-semantics.ts`, keyed by bare table
 * name exactly as the server's registry is. The seed rows live in
 * `data/catalog-tables.json`, split `warehouse` / `results`.
 */

interface TableSeed {
  table: string;
  /** Null exercises the "undescribed" gap the API can emit when nothing describes a table. */
  description: string | null;
  rows: number | null;
  produced_at?: string;
  source_kind?: string;
  source_ref?: string;
  tool?: string;
}

interface TablesData {
  warehouse: TableSeed[];
  results: TableSeed[];
}

export async function catalogTablesFixture(): Promise<CatalogTableRow[]> {
  const [creation, data] = await Promise.all([creationMap(), rows<TablesData>('catalog-tables')]);

  const table = (schema: string, s: TableSeed): CatalogTableRow => {
    const [created_by, why] = creation[s.table] ?? [null, null];
    return {
      schema,
      table: s.table,
      created_by,
      why,
      description: s.description,
      rows: s.rows,
      produced_at: s.produced_at ?? null,
      source_kind: s.source_kind ?? null,
      source_ref: s.source_ref ?? null,
      tool: s.tool ?? null,
    };
  };

  return [...data.warehouse.map((s) => table('warehouse', s)), ...data.results.map((s) => table('results', s))];
}
