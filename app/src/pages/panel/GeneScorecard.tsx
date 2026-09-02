import { usePanelGenes } from '../../api/hooks';
import type { PanelGeneRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int, pct } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Gene scorecard. Two numbers per candidate gene: how many records the caller kept, and
 * how many it suppressed. A gene with a low PASS share is not a clean gene — it is a gene
 * whose evidence is partly hidden behind a heuristic, and therefore a gene that needs
 * looking at by hand.
 */
export function GeneScorecard() {
  const q = usePanelGenes();

  const columns: Column<PanelGeneRow>[] = [
    {
      key: 'gene',
      header: 'gene',
      render: (r) => <span className="font-mono text-zinc-100">{r.gene}</span>,
    },
    { key: 'chrom', header: 'contig', render: (r) => <span className="font-mono">{r.chrom}</span> },
    { key: 'n_all', header: 'records', align: 'right', render: (r) => int(r.n_all) },
    {
      key: 'n_pass',
      header: 'PASS',
      align: 'right',
      render: (r) => <span className="text-emerald-400">{int(r.n_pass)}</span>,
    },
    {
      key: 'n_filtered',
      header: 'suppressed',
      align: 'right',
      render: (r) => (
        <span className={r.n_filtered > 0 ? 'text-red-400' : 'text-zinc-600'}>
          {int(r.n_filtered)}
        </span>
      ),
    },
    {
      key: 'pct_pass',
      header: 'PASS %',
      align: 'right',
      render: (r) => (
        <span className={r.pct_pass < 96 ? 'text-red-400' : 'text-zinc-300'}>
          {pct(r.pct_pass, 1)}
        </span>
      ),
    },
    { key: 'per_mb', header: 'var/Mb', align: 'right', render: (r) => dec(r.variants_per_mb, 1) },
    {
      key: 'note',
      header: 'why it is on the panel',
      render: (r) => <span className="text-zinc-400">{r.note}</span>,
    },
  ];

  return (
    <Exhibit
      title="MVA candidate panel — kept against suppressed, per gene"
      legend={
        <>
          Stacked bars, one per candidate gene. <Chip color={C.good}>PASS records</Chip> ·{' '}
          <Chip color={C.broken}>suppressed records (a non-PASS FILTER fired)</Chip>. The{' '}
          <span style={{ color: C.decision }}>yellow markers</span> read against the right axis and
          give the PASS share; the dashed line at 96 % is the level below which a gene's evidence is
          materially hidden.
        </>
      }
      reading="Of the well-covered genes, BUB1B has the worst PASS share at 95.0 %. But the real outlier is TRIP13: 6 of its 12 records are suppressed — half its evidence sits behind a filter, in an established MVA gene."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(rows) => {
          const ordered = [...rows].sort((a, b) => b.n_all - a.n_all);
          const worst = [...rows].sort((a, b) => a.pct_pass - b.pct_pass)[0];
          return (
            <>
              <Plot
                height={340}
                data={[
                  {
                    type: 'bar',
                    name: 'PASS',
                    x: ordered.map((r) => r.gene),
                    y: ordered.map((r) => r.n_pass),
                    marker: { color: C.good, line: { width: 0 } },
                    hovertemplate: '%{x}<br>%{y:,} PASS records<extra></extra>',
                  },
                  {
                    type: 'bar',
                    name: 'suppressed',
                    x: ordered.map((r) => r.gene),
                    y: ordered.map((r) => r.n_filtered),
                    marker: { color: C.broken, line: { width: 0 } },
                    hovertemplate: '%{x}<br>%{y:,} suppressed records<extra></extra>',
                  },
                  {
                    type: 'scatter',
                    name: 'PASS %',
                    mode: 'markers',
                    yaxis: 'y2',
                    x: ordered.map((r) => r.gene),
                    y: ordered.map((r) => r.pct_pass),
                    marker: {
                      color: C.decision,
                      size: 10,
                      symbol: 'diamond',
                      line: { color: C.paper, width: 1 },
                    },
                    hovertemplate: '%{x}<br>%{y:.1f}% PASS<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 60, r: 58, t: 8, b: 46 },
                  barmode: 'stack',
                  bargap: 0.34,
                  xaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: 'records in the gene', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis2: {
                    title: { text: 'PASS %', font: { color: C.decision, size: 12 } },
                    overlaying: 'y',
                    side: 'right',
                    range: [40, 102],
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.decision, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      xref: 'paper',
                      yref: 'y2',
                      x0: 0,
                      x1: 1,
                      y0: 96,
                      y1: 96,
                      line: { color: C.decision, width: 1, dash: 'dot' },
                    },
                  ],
                  legend: { orientation: 'h', y: 1.12, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              {worst && (
                <p className="mb-3 text-[11px] text-zinc-500">
                  lowest PASS share: <span className="font-mono text-red-400">{worst.gene}</span> at{' '}
                  {pct(worst.pct_pass, 1)} ({int(worst.n_filtered)} of {int(worst.n_all)} records
                  suppressed)
                </p>
              )}
              <DataTable rows={ordered} columns={columns} rowKey={(r) => r.gene} />
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
