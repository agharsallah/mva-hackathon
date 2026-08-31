import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { useFilters } from '../../api/hooks';
import { C } from '../../lib/palette';
import { int, pct } from '../../lib/format';

/**
 * The filtering funnel. A FILTER value is the caller's veto, and it is a heuristic: it
 * says "I would not stake a publication on this record", not "this record is false". For
 * an N-of-1 case that distinction matters, because the suppressed set is a search space
 * — the causal variant could be sitting in it.
 */
export function Funnel() {
  const q = useFilters();
  return (
    <Exhibit
      title="Filtering funnel — what the caller kept and what it vetoed"
      legend={
        <>
          <Chip color={C.raw}>all records delivered</Chip> · <Chip color={C.good}>PASS (survived every
          filter)</Chip> · <Chip color={C.broken}>suppressed, broken out by which filter fired</Chip>. Bar length
          is the record count on a log axis, so the small filters stay readable next to PASS. A record can carry
          several filters, which is why values like <span className="font-mono">MQ40;QD2</span> appear.
        </>
      }
      reading="271,414 records are suppressed. That is not a discard pile — it is where a real variant hides if the caller's mapping-quality or depth heuristic misjudged its locus."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={380}>
        {(rows) => {
          const passRow = rows.find((r) => r.filter_value === 'PASS');
          const suppressed = rows.filter((r) => r.filter_value !== 'PASS');
          const total = rows.reduce((a, r) => a + r.count, 0);
          const suppressedTotal = suppressed.reduce((a, r) => a + r.count, 0);
          const stages = [
            { label: 'delivered', count: total, color: C.raw },
            { label: 'PASS', count: passRow?.count ?? 0, color: C.good },
            ...suppressed
              .slice()
              .sort((a, b) => b.count - a.count)
              .map((r) => ({ label: r.filter_value, count: r.count, color: C.broken })),
          ];
          return (
            <>
              <Plot
                height={340}
                data={[
                  {
                    type: 'bar',
                    orientation: 'h',
                    y: stages.map((s) => s.label).reverse(),
                    x: stages.map((s) => s.count).reverse(),
                    marker: { color: stages.map((s) => s.color).reverse(), line: { width: 0 } },
                    text: stages.map((s) => int(s.count)).reverse(),
                    textposition: 'outside',
                    textfont: { color: C.inkDim, size: 10 },
                    customdata: stages.map((s) => (s.count / total) * 100).reverse(),
                    hovertemplate: '%{y}<br>%{x:,} records (%{customdata:.2f}% of delivered)<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 96, r: 74, t: 8, b: 44 },
                  bargap: 0.28,
                  xaxis: {
                    type: 'log',
                    title: { text: 'records (log scale)', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: { type: 'category', gridcolor: 'rgba(0,0,0,0)', tickfont: { color: C.inkDim, size: 11 } },
                  showlegend: false,
                })}
              />
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                <div className="rounded-lg border border-purple-900/40 bg-purple-950/20 p-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-purple-400">delivered</div>
                  <div className="font-mono text-sm text-zinc-200">{int(total)}</div>
                </div>
                <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-emerald-400">PASS</div>
                  <div className="font-mono text-sm text-zinc-200">
                    {int(passRow?.count ?? 0)}{' '}
                    <span className="text-zinc-500">({pct(((passRow?.count ?? 0) / total) * 100)})</span>
                  </div>
                </div>
                <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-2.5">
                  <div className="text-[10px] uppercase tracking-wider text-red-400">suppressed</div>
                  <div className="font-mono text-sm text-zinc-200">
                    {int(suppressedTotal)}{' '}
                    <span className="text-zinc-500">({pct((suppressedTotal / total) * 100)})</span>
                  </div>
                </div>
              </div>
              <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-500">
                <li>
                  <span className="font-mono text-zinc-300">MQ40</span> — mapping quality below 40: the aligner
                  was unsure the reads belong here at all
                </li>
                <li>
                  <span className="font-mono text-zinc-300">QD2</span> — quality normalised by depth below 2:
                  the confidence is not backed by enough reads
                </li>
                <li>
                  <span className="font-mono text-zinc-300">LowQual</span> — the raw site confidence itself was
                  low
                </li>
              </ul>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
