import type { Step6Leader, Step6MatrixCell, Step6Route } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { alleles, cellLabel, matrixPairs, matrixRoutes, rowLabel, score, triple } from './metrics';

/**
 * The step's headline: routes × leading pairs, and where each instrument actually put each one.
 *
 * The cell that matters is the one that says **not listed**. Reciprocal rank fusion gives a
 * pair a route never mentioned the same rank everywhere, and a heatmap that coloured that
 * like any other rank would read silence as agreement. Here those cells are flat grey and
 * labelled, so a column of grey is legible as "this instrument never saw any of this".
 */
export function AgreementMatrix({
  cells,
  routes,
  leaders,
  source,
  cachedAt,
  origin,
}: {
  cells: Step6MatrixCell[];
  routes: Step6Route[];
  leaders: Step6Leader[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const pairs = matrixPairs(cells);
  const columns = matrixRoutes(routes);
  const byKey = new Map(cells.map((cell) => [`${cell.pair_id}|${cell.route}`, cell]));

  // Plotly draws a heatmap bottom-up, so the best fused rank has to be the last row for it
  // to appear at the top of the figure.
  const rows = [...pairs].reverse();
  const z = rows.map((pair) =>
    columns.map((route) => {
      const cell = byKey.get(`${pair.pair_id}|${route.route}`);
      return !cell || cell.defaulted ? null : cell.route_rank;
    }),
  );
  const text = rows.map((pair) =>
    columns.map((route) => cellLabel(byKey.get(`${pair.pair_id}|${route.route}`))),
  );

  return (
    <div className="space-y-4">
      <Exhibit
        title="Agreement matrix — routes against the leading pairs"
        reading="A column of grey is an instrument that never listed any of the leaders; a single green cell is the only route that put a pair first."
        legend={
          <>
            One cell per (route, pair): the rank <em>that route</em> gave that pair.{' '}
            <span style={{ color: C.good }}>■</span> rank 1 ·{' '}
            <span style={{ color: C.decision }}>■</span> inside the route&rsquo;s top 50, darker is
            better · <span style={{ color: C.absent }}>■</span> <strong>not listed</strong> — the
            route never mentioned this pair, which is weaker than ranking it last and is never
            agreement. A <strong>*</strong> on a number means the rank was inherited from the
            pair&rsquo;s gene, so every pair of that gene carries it. Rows run best fused rank
            first.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={cells}
      >
        <Plot
          height={Math.max(320, rows.length * 26 + 120)}
          data={[
            {
              type: 'heatmap',
              z,
              x: columns.map((route) => `${route.route}${route.admitted ? '' : ' (w 0)'}`),
              y: rows.map(rowLabel),
              text,
              texttemplate: '%{text}',
              textfont: { size: 10 },
              hovertemplate: '%{y}<br>%{x}: %{text}<extra></extra>',
              colorscale: [
                [0, C.good],
                [0.04, C.decision],
                [1, C.machineryDim],
              ],
              zmin: 1,
              zmax: 50,
              showscale: false,
              xgap: 2,
              ygap: 2,
            },
          ]}
          layout={{
            margin: { l: 330, r: 16, t: 10, b: 48 },
            plot_bgcolor: C.absent,
            yaxis: { automargin: true, tickfont: { size: 10 } },
          }}
        />
      </Exhibit>

      <Exhibit
        title="The fused ranking, with what stands behind each pair"
        reading="One row says the whole case for a pair: where each route put it, how many disjoint sources speak for it, and whether the raw reads confirm it."
        legend={
          <>
            <strong>Evidence</strong> counts the disjoint raw sources speaking for the pair after
            routes sharing one are collapsed — <strong>1</strong> means several routes and a single
            witness. <strong>Confirmation</strong> is the read route&rsquo;s three booleans:{' '}
            <span className="text-good-400">green</span> when all three hold,{' '}
            <span className="text-decision-400">yellow</span> when some do,{' '}
            <span className="text-chrome-400">grey</span> when the gene was never measured.{' '}
            <strong>w-rank</strong> is the same pair under measured-error-rate weights.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={leaders}
      >
        <DataTable
          rows={leaders}
          rowKey={(row) => row.pair_id}
          columns={[
            { key: 'fused_rank', header: '#', align: 'right', render: (row) => row.fused_rank },
            { key: 'gene', header: 'Gene', render: (row) => row.gene },
            {
              key: 'pair_id',
              header: 'Alleles',
              render: (row) => <span className="text-chrome-400">{alleles(row.pair_id)}</span>,
            },
            { key: 'shape', header: 'Shape', render: (row) => row.shape ?? '—' },
            {
              key: 'set',
              header: 'Set',
              render: (row) =>
                row.is_target ? (
                  <Badge tone="good">target · {row.tier ?? '—'}</Badge>
                ) : row.is_decoy ? (
                  <Badge tone="broken">decoy</Badge>
                ) : (
                  <Badge>neither</Badge>
                ),
              sortValue: (row) => (row.is_target ? 2 : row.is_decoy ? 0 : 1),
            },
            {
              key: 'rrf_score',
              header: 'RRF',
              align: 'right',
              render: (row) => score(row.rrf_score),
            },
            {
              key: 'rank_sensitivity',
              header: 'w-rank',
              align: 'right',
              render: (row) => row.rank_sensitivity ?? '—',
            },
            {
              key: 'independent_evidence',
              header: 'Evidence',
              align: 'right',
              render: (row) => (
                <Badge tone={row.independent_evidence >= 2 ? 'good' : 'decision'}>
                  {row.independent_evidence} of 4
                </Badge>
              ),
              sortValue: (row) => row.independent_evidence,
            },
            {
              key: 'confirmation',
              header: 'Confirmation',
              render: (row) => {
                const met = triple(row).filter((flag) => flag.met);
                if (met.length === 0) return <Badge>not measured</Badge>;
                return (
                  <Badge tone={met.length === 3 ? 'good' : 'decision'}>
                    {met.map((flag) => flag.label).join(' · ')}
                  </Badge>
                );
              },
              sortValue: (row) => triple(row).filter((flag) => flag.met).length,
            },
          ]}
        />
      </Exhibit>
    </div>
  );
}
