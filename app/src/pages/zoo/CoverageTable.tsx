import type { ZooModel } from '../../api/types/zoo';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';
import { useZooModels } from './hooks';

/**
 * Coverage as a matrix: every consequence class the callset contains, against every lane
 * that ran.
 *
 * This is the table that decides how much the rest of the page is worth. A ranking is only
 * over the pairs a lane could score, so a class with a low fraction here is that lane's blind
 * spot, and a pair with a half in that class silently leaves its ranking. Printing the
 * fraction per class — rather than one number per lane — is what keeps that visible.
 */

interface Row {
  consequence: string;
  total: number;
  scored: Record<string, number>;
}

function buildRows(models: ZooModel[]): Row[] {
  const scored = models.filter((m) => m.coverage);
  const classes = new Set<string>();
  for (const m of scored) Object.keys(m.coverage!.by_consequence).forEach((c) => classes.add(c));
  return [...classes]
    .map((consequence) => ({
      consequence,
      total: Math.max(...scored.map((m) => m.coverage!.by_consequence[consequence]?.total ?? 0), 0),
      scored: Object.fromEntries(
        scored.map((m) => [m.key, m.coverage!.by_consequence[consequence]?.scored ?? 0]),
      ),
    }))
    .sort((a, b) => b.total - a.total);
}

function Cell({ scored, total }: { scored: number; total: number }) {
  const fraction = total > 0 ? scored / total : 0;
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="h-1.5 w-12 rounded-pill bg-chrome-900" aria-hidden="true">
        <div
          className="h-full rounded-pill"
          style={{
            width: `${fraction * 100}%`,
            background: fraction === 0 ? C.unmeasured : C.good,
          }}
        />
      </div>
      <span className="tabular-nums w-24 text-right text-chrome-300">
        {scored === 0 ? '—' : `${int(scored)} · ${pct(fraction * 100, 0)}`}
      </span>
    </div>
  );
}

export function CoverageTable() {
  const q = useZooModels();

  return (
    <Exhibit
      title="What each lane could score, class by class"
      legend={
        <>
          One row per <strong>consequence class</strong> (what the change does to the protein), one
          column per lane that ran. <Chip color={C.good}>green</Chip> = the share of that class the
          lane scored · <Chip color={C.unmeasured}>grey</Chip> = the lane scored nothing in that
          class, its blind spot. <code>—</code> means zero scored, never &ldquo;scored zero&rdquo;:
          an unscored allele leaves the lane&rsquo;s ranking instead of entering it at the bottom.
        </>
      }
      reading={
        <>
          The three missense lanes and the splice lane cover different classes almost disjointly,
          which is the whole argument for running more than one: their agreement, where it exists,
          is agreement between different instruments rather than between two copies of one.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420} variant="table">
        {(models) => {
          const lanes = models.filter((m) => m.coverage);
          const rows = buildRows(models);
          const columns: Column<Row>[] = [
            {
              key: 'consequence',
              header: 'consequence class',
              render: (r) => <code className="text-chrome-300">{r.consequence}</code>,
            },
            {
              key: 'total',
              header: 'records',
              align: 'right',
              render: (r) => <span className="tabular-nums">{int(r.total)}</span>,
            },
            ...lanes.map((m): Column<Row> => ({
              key: m.key,
              header: m.name,
              align: 'right',
              sortValue: (r) => (r.total ? r.scored[m.key] / r.total : 0),
              render: (r) => <Cell scored={r.scored[m.key] ?? 0} total={r.total} />,
            })),
          ];
          return (
            <DataTable
              rows={rows}
              columns={columns}
              rowKey={(r) => r.consequence}
              filterable
              filterLabel="class"
              maxHeight={480}
            />
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
