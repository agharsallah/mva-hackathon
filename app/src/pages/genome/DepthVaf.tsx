import { useAlleleBalance } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Depth against balance. Two independent axes have to agree for a chromosome to be
 * normal: it must be read as deeply as the rest of the genome (a lost copy reads
 * shallower) and its heterozygous sites must split evenly. The crosshair is the
 * "everything normal" point; distance from it is the anomaly.
 */
export function DepthVaf() {
  const q = useAlleleBalance();
  return (
    <Exhibit
      title="Depth against balance — two axes that must both agree"
      legend={
        <>
          One point per contig. x = mean read depth over heterozygous sites, y = mean VAF. Crosshair
          = (autosomal mean depth, 0.50), the &quot;two intact copies, evenly covered&quot; point.{' '}
          <Chip color={C.good}>balanced</Chip> · <Chip color={C.broken}>flagged</Chip>. Labels name
          the contig.
        </>
      }
      reading={
        <>
          A whole-chromosome gain would sit up and right, a loss down and left. The autosomes form
          one tight cluster on the crosshair; X and Y sit low-left because a male sample has a
          single copy of each.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={400}>
        {(rows) => {
          const autosomes = rows.filter(
            (r) => !['X', 'Y', 'MT'].includes(r.chrom.replace(/^chr/, '')),
          );
          const meanDp =
            autosomes.reduce((a, r) => a + r.mean_dp, 0) / Math.max(1, autosomes.length);
          const groups: [string, typeof rows, string][] = [
            ['balanced', rows.filter((r) => r.balance_call === 'balanced'), C.good],
            ['flagged', rows.filter((r) => r.balance_call !== 'balanced'), C.broken],
          ];
          return (
            <>
              <Plot
                height={380}
                data={groups
                  .filter(([, g]) => g.length > 0)
                  .map(([name, g, color]) => ({
                    type: 'scatter',
                    mode: 'markers+text',
                    name,
                    x: g.map((r) => r.mean_dp),
                    y: g.map((r) => r.mean_vaf),
                    text: g.map((r) => r.chrom),
                    textposition: 'top center',
                    textfont: { color: C.inkDim, size: 9 },
                    marker: { size: 11, color, line: { color: C.paper, width: 1 }, opacity: 0.9 },
                    customdata: g.map((r) => [r.n_het, r.dp_vs_autosomal]),
                    hovertemplate:
                      'chr%{text}<br>depth %{x:.1f}× (%{customdata[1]:.3f} of autosomal)<br>' +
                      'VAF %{y:.4f}<br>%{customdata[0]:,} het sites<extra></extra>',
                  }))}
                layout={baseLayout({
                  margin: { l: 62, r: 20, t: 10, b: 46 },
                  xaxis: {
                    title: {
                      text: 'mean read depth at heterozygous sites (×)',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: 'mean VAF', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: 0.5,
                      y1: 0.5,
                      line: { color: C.inkDim, width: 1.2, dash: 'dash' },
                    },
                    {
                      type: 'line',
                      yref: 'paper',
                      y0: 0,
                      y1: 1,
                      x0: meanDp,
                      x1: meanDp,
                      line: { color: C.inkDim, width: 1.2, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      x: meanDp,
                      y: 0.5,
                      text: `crosshair: ${dec(meanDp, 1)}× / 0.50`,
                      showarrow: true,
                      arrowcolor: C.inkDim,
                      arrowhead: 0,
                      ax: 40,
                      ay: 34,
                      font: { color: C.inkDim, size: 10 },
                    },
                  ],
                  legend: { orientation: 'h', y: 1.08, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <p className="mt-2 text-[11px] text-chrome-500">
                autosomal mean depth{' '}
                <span className="font-mono text-chrome-300">{dec(meanDp, 1)}×</span> over{' '}
                {autosomes.length} contigs
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
