import type { CatalogColumnRow } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — the semantics half of the catalogue: how each table is created, why it
 * exists, and what every column of it means.
 *
 * The live API resolves both from registries in `mva.viz.catalog_semantics` and
 * `mva.viz.catalog_columns`, keyed the same way this file is: a shared map for the
 * columns that recur across tables (`chrom`, `pos`, `ref`, `alt`, `sha256`…) and a
 * table-specific map that beats it. The fixture reproduces that resolution order rather
 * than flattening it, so the "one entry covers every table carrying this column"
 * behaviour is visible with no API running.
 *
 * Three gaps are deliberate and match what the contract can emit:
 * - `results.kmer_counts` has **no** `created_by` / `why` — a table written outside the
 *   warehouse build, which the registry does not know.
 * - `warehouse.vep_staging.raw_json` and `results.kmer_counts.hits` have **no** meaning.
 * - every other column resolves, most of them through the shared map.
 *
 * Sentences are shortened from the live registry; no genomic position appears here,
 * because a column meaning describes semantics, never a value.
 *
 * `CREATION`, `SHARED`, `SPECIFIC` and `LAYOUT` live in `data/catalog-semantics.json`;
 * this module only re-applies the resolution order and the `LAYOUT` flatMap.
 */

interface SemanticsData {
  /** `table → [created_by, why]`, applied by `fixtures/shape/catalog-tables.ts`. */
  creation: Record<string, [string, string]>;
  /** Columns that recur across tables with one meaning — written once, as on the server. */
  shared: Record<string, string>;
  /** Meanings that belong to one table. Beats `shared` on the same column name. */
  specific: Record<string, string>;
  /** `schema.table → [column, sql type][]`, in the order the table declares them. */
  layout: [string, string, [string, string][]][];
}

let cached: Promise<SemanticsData> | undefined;

function semantics(): Promise<SemanticsData> {
  return (cached ??= rows<SemanticsData>('catalog-semantics'));
}

/** Exposed for `shape/catalog-tables.ts`, which beats it in the same way the server does. */
export async function creationMap(): Promise<Record<string, [string, string]>> {
  return (await semantics()).creation;
}

export async function catalogColumnsFixture(): Promise<CatalogColumnRow[]> {
  const { shared, specific, layout } = await semantics();
  return layout.flatMap(([schema, table, columns]) =>
    columns.map(([column, data_type], index) => ({
      schema,
      table,
      column,
      data_type,
      ordinal: index + 1,
      meaning: specific[`${table}.${column}`] ?? shared[column] ?? null,
    })),
  );
}
