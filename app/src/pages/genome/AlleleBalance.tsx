import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { useAlleleBalance } from '../../api/hooks';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';
import { chromOrder } from './order';

/**
 * THE headline figure.
 *
 * A heterozygous site on a normal pair of chromosomes should read about half variant
 * reads (VAF 0.5). An extra or missing copy shifts that ratio genome-wide on the affected
 * chromosome — which is exactly the fingerprint MVA would leave. The plot puts all 25
 * contigs against the 0.5 line so a shifted chromosome would be impossible to miss.
 */
export function AlleleBalance() {
  const q = useAlleleBalance();
  return (
    <Exhibit
      title="Allele balance per chromosome — the aneuploidy screen"
      legend={
        <>
          One dot per contig. y = mean VAF of heterozygous sites; the dashed line at{' '}
          <span className="font-mono">0.50</span> is what two intact copies produce. Dot area ∝ number of
          heterozygous sites. <Chip color={C.good}>balanced</Chip> · <Chip color={C.broken}>flagged (deviation
          beyond threshold)</Chip>. The grey band marks ±0.03 around 0.5.
        </>
      }
      reading={
        <>
          Every autosome sits inside the band. Only Y is flagged, and Y is expected to look like this in a male
          sample: one copy, so &quot;heterozygous&quot; calls there are mapping noise, not biology.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={400}>
        {(rows) => {
          const ordered = [...rows].sort((a, b) => chromOrder(a.chrom) - chromOrder(b.chrom));
          const maxHet = Math.max(...ordered.map((r) => r.n_het));
          const flagged = ordered.filter((r) => r.balance_call !== 'balanced');
          return (
            <>
              <Plot
                height={380}
                data={[
                  {
                    type: 'scatter',
                    mode: 'markers',
                    x: ordered.map((r) => r.chrom),
                    y: ordered.map((r) => r.mean_vaf),
                    marker: {
                      size: ordered.map((r) => 10 + 34 * Math.sqrt(r.n_het / maxHet)),
                      color: ordered.map((r) => (r.balance_call === 'balanced' ? C.good : C.broken)),
                      line: { color: C.paper, width: 1.5 },
                      opacity: 0.88,
                    },
                    customdata: ordered.map((r) => [r.n_het, r.mean_dp, r.vaf_deviation, r.balance_call]),
                    hovertemplate:
                      'chr%{x}<br>mean VAF %{y:.4f}<br>%{customdata[0]:,} het sites<br>' +
                      'mean depth %{customdata[1]:.1f}×<br>deviation %{customdata[2]:+.4f}<br>' +
                      '%{customdata[3]}<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 62, r: 20, t: 10, b: 40 },
                  xaxis: {
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                    type: 'category',
                    categoryorder: 'array',
                    categoryarray: ordered.map((r) => r.chrom),
                  },
                  yaxis: {
                    title: { text: 'mean VAF at heterozygous sites', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                    range: [0.28, 0.58],
                  },
                  shapes: [
                    {
                      type: 'rect',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: 0.47,
                      y1: 0.53,
                      fillcolor: 'rgba(255,255,255,0.045)',
                      line: { width: 0 },
                      layer: 'below',
                    },
                    {
                      type: 'line',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: 0.5,
                      y1: 0.5,
                      line: { color: C.inkDim, width: 1.4, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      xref: 'paper',
                      x: 0.005,
                      y: 0.5,
                      text: '0.50 — two intact copies',
                      showarrow: false,
                      xanchor: 'left',
                      yanchor: 'bottom',
                      font: { color: C.inkDim, size: 10 },
                    },
                  ],
                  showlegend: false,
                })}
              />
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-zinc-500">
                <span>
                  contigs balanced:{' '}
                  <span className="font-mono text-emerald-400">{ordered.length - flagged.length}</span> /{' '}
                  {ordered.length}
                </span>
                {flagged.map((f) => (
                  <span key={f.chrom}>
                    flagged <span className="font-mono text-red-400">chr{f.chrom}</span> — VAF{' '}
                    {dec(f.mean_vaf, 4)} ({dec(f.vaf_deviation, 4)}), {int(f.n_het)} het sites, depth{' '}
                    {dec(f.dp_vs_autosomal, 3)}× the autosomal mean
                  </span>
                ))}
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
