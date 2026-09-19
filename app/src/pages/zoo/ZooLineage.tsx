import type { ZooLineageRow } from '../../api/types/zoo';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int, iso } from '../../lib/format';
import { C } from '../../lib/palette';
import { cx } from '../../lib/ui';
import { useZooLineage } from './hooks';

/**
 * Lineage: which table was produced from what, by which transformation, when.
 *
 * The repo's standing rule is that nothing is produced without its source and its generation
 * process recorded, and `warehouse.data_lineage` is where that record lives — append-only, so
 * a table rebuilt twice has two edges and neither is overwritten. Drawn here as one column
 * per zoo table, with each edge as `source → transform → target (rows)`.
 */

function Edge({ row }: { row: ZooLineageRow }) {
  return (
    <li className="rounded-control border border-line-soft bg-well p-2 text-micro">
      <div className="flex flex-wrap items-baseline gap-2">
        <span
          className="rounded-pill px-1.5 py-px text-chrome-950"
          style={{ background: C.raw }}
          title={`source kind: ${row.source_kind}`}
        >
          {row.source_kind}
        </span>
        <span className="font-mono break-all text-chrome-300">{row.source_ref}</span>
      </div>
      <div className="mt-1 flex items-start gap-2">
        <span aria-hidden="true" style={{ color: C.machinery }}>
          →
        </span>
        <span className="font-mono break-all text-chrome-400">{row.transform}</span>
      </div>
      <div className="mt-1 flex flex-wrap items-baseline gap-2 text-chrome-500">
        <span aria-hidden="true" style={{ color: C.good }}>
          ⇒
        </span>
        <span className="text-chrome-200">
          {row.target_schema}.{row.target_table}
        </span>
        <span className="tabular-nums">{int(row.target_rows)} rows</span>
        <span>{iso(row.produced_at)}</span>
        <span>
          by <code>{row.tool}</code>
        </span>
        {row.notes && <span className="italic">{row.notes}</span>}
      </div>
      {row.source_version && (
        <p className="mt-1 text-chrome-600">
          source version <code>{row.source_version}</code>
          {row.source_sha256 ? ` · sha256 ${row.source_sha256.slice(0, 12)}…` : ''}
        </p>
      )}
    </li>
  );
}

export function ZooLineage() {
  const q = useZooLineage();

  return (
    <Exhibit
      title="How each zoo table was made"
      legend={
        <>
          One entry per <strong>lineage edge</strong>, grouped by the table it produced.{' '}
          <Chip color={C.raw}>purple</Chip> = the source it was read from ·{' '}
          <Chip color={C.machinery}>blue</Chip> (→) = the transformation that ran ·{' '}
          <Chip color={C.good}>green</Chip> (⇒) = the table it wrote, with its row count and the
          instant it was written. The list is append-only: a table rebuilt twice shows two edges,
          newest first, and neither replaces the other.
        </>
      }
      reading={
        <>
          Every number on this page can be walked back from the table it was read out of to the
          command and the source that produced it — which is the difference between a result and a
          claim.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
      data={q.data?.data}
    >
      <Loaded query={q} height={400}>
        {(lineage) => {
          const rows = lineage.rows;
          // Every zoo table the route knows about, not only the ones with an edge: a table
          // with no lineage row is a statement worth making, and an omitted column hides it.
          const targets = [
            ...new Set([
              ...rows.map((r) => `${r.target_schema}.${r.target_table}`),
              ...lineage.tables.filter((name) => !rows.some((r) => r.target_table === name)),
            ]),
          ];
          return (
            <div className={cx('grid gap-4', targets.length > 1 && 'lg:grid-cols-2')}>
              {targets.map((target) => {
                const edges = rows.filter((r) => `${r.target_schema}.${r.target_table}` === target);
                return (
                  <section key={target} className="space-y-2">
                    <h4 className="text-xs font-semibold text-chrome-200">
                      {target}{' '}
                      <span className="font-normal text-chrome-500">
                        · {edges.length} edge{edges.length === 1 ? '' : 's'}
                      </span>
                    </h4>
                    {edges.length === 0 ? (
                      <p className="text-micro text-chrome-500">
                        No lineage edge is recorded for this table — it exists, and nothing has
                        written how it was made.
                      </p>
                    ) : (
                      <ul className="space-y-2">
                        {edges.map((row, i) => (
                          <Edge key={`${target}-${row.produced_at}-${i}`} row={row} />
                        ))}
                      </ul>
                    )}
                  </section>
                );
              })}
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
