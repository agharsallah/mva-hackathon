import type { Step8Composition } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * What the sequence explains, and what is left over.
 *
 * A dosage is a count, and short-read counts depend on GC: library preparation and
 * amplification favour some compositions by a few per cent across a whole chromosome. That
 * is the same size as the low-fraction mosaic gain this step is looking for, and the
 * bootstrap interval cannot separate them — resampling probes measures counting noise and
 * is blind to a bias every probe on the chromosome shares.
 *
 * So the ratio is regressed on each chromosome's GC and the residual is what a copy-number
 * claim may be made from. **The residual spread, not the bootstrap width, is the precision
 * floor.** Both regressors are shown because the choice between them changes the answer.
 */
export function Composition({
  composition,
  source,
  cachedAt,
  origin,
}: {
  composition: Step8Composition;
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const fit = composition.reported;
  const other = composition.alternative;
  const rows = composition.rows ?? [];
  if (!fit || rows.length === 0) return null;

  const tested = composition.autosomes_tested ?? rows.length;
  const worst = [...rows].sort((a, b) => Math.abs(b.z) - Math.abs(a.z))[0];
  const floor = fit.residual_spread * 200;
  const line = [Math.min(...rows.map((row) => row.gc)), Math.max(...rows.map((row) => row.gc))];

  return (
    <div className="space-y-4">
      <Exhibit
        title="Dosage against composition, and the line that explains most of it"
        reading={
          `GC explains ${(fit.correlation ** 2 * 100).toFixed(0)}% of the spread between chromosomes. ` +
          `Removing it takes the autosomal spread from ${(fit.spread * 100).toFixed(2)}% to ` +
          `${(fit.residual_spread * 100).toFixed(2)}% — so the smallest cell fraction this route could ` +
          `argue is about ${floor.toFixed(1)}%, not the ±1% a bootstrap interval suggests.`
        }
        legend={
          <>
            Each dot is one autosome: its GC fraction against its measured dosage.{' '}
            <span className="text-machinery-400">Blue line</span> — the fitted trend, which is
            instrument, not biology. Vertical distance from the line is what is left to explain. The
            regressor is the <strong>chromosome&rsquo;s</strong> GC from the reference and not its
            probes&rsquo;: GC bias acts on fragments of a few hundred bases, so a 31-mer&rsquo;s own
            GC is the wrong scale, and a probe set is what the uniqueness filter left rather than a
            fair sample of the sequence it was cut from.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={rows}
      >
        <Plot
          height={360}
          data={[
            {
              x: rows.map((row) => row.gc),
              y: rows.map((row) => row.relative),
              text: rows.map((row) => `chr${row.chrom}`),
              type: 'scatter',
              mode: 'markers+text',
              textposition: 'top center',
              textfont: { size: 9 },
              marker: { size: 9, color: C.good },
              name: 'measured',
              hovertemplate: '%{text}<br>GC %{x:.4f}<br>dosage %{y:.4f}<extra></extra>',
            },
            {
              x: line,
              y: line.map((value) => fit.slope * value + fit.intercept),
              type: 'scatter',
              mode: 'lines',
              line: { color: C.machinery, width: 2 },
              name: 'fitted composition trend',
              hoverinfo: 'skip',
            },
          ]}
          layout={{
            xaxis: { title: { text: 'chromosome GC fraction' } },
            yaxis: { title: { text: 'dosage against the autosomal median' } },
            legend: { orientation: 'h', y: 1.14 },
          }}
        />
      </Exhibit>

      <Exhibit
        title="What is left after composition, in units of the residual spread"
        reading={
          `The largest residual is chr${worst.chrom} at ${worst.z.toFixed(2)} sigma, an implied ` +
          `${(worst.implied_fraction * 100).toFixed(1)}% of cells. With ${tested} autosomes tested at ` +
          `once, that is not a finding: roughly one chromosome clears two sigma on a genome with ` +
          `nothing wrong with it.`
        }
        legend={
          <>
            Each autosome&rsquo;s dosage after the GC trend is removed, in units of the spread of
            those residuals. <span className="text-decision-400">Yellow dotted lines</span> — ±2
            sigma, which is where a single pre-specified chromosome would start to be interesting
            and where a set of {tested} is still noise.{' '}
            <span className="text-machinery-400">Blue</span> — one copy per copy expected. Hovering
            a bar reads the same number as a cell fraction: a gain in a share <em>f</em> of cells
            raises a chromosome&rsquo;s sequence by <em>f</em>/2, so the fraction is twice the
            deviation, signed rather than folded so a loss reads negative.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={rows}
      >
        <Plot
          height={340}
          data={[
            {
              x: rows.map((row) => row.chrom),
              y: rows.map((row) => row.z),
              type: 'bar',
              marker: {
                color: rows.map((row) => (Math.abs(row.z) > 2 ? C.decision : C.good)),
              },
              name: 'residual',
              hovertemplate:
                'chr%{x}<br>%{y:.2f} sigma<br>implied %{customdata:.2f}% of cells<extra></extra>',
              customdata: rows.map((row) => row.implied_fraction * 100),
            },
          ]}
          layout={{
            xaxis: { title: { text: 'chromosome' }, type: 'category' },
            yaxis: { title: { text: 'residual ÷ residual spread (sigma)' } },
            showlegend: false,
            shapes: [2, 0, -2].map((y) => ({
              type: 'line' as const,
              xref: 'paper' as const,
              x0: 0,
              x1: 1,
              y0: y,
              y1: y,
              line: {
                color: y === 0 ? C.machinery : C.decision,
                width: 1,
                dash: y === 0 ? ('solid' as const) : ('dot' as const),
              },
            })),
          }}
        />
      </Exhibit>

      {other && (
        <Exhibit
          title="The regressor that was not used, and what it would have said"
          reading={
            `Regressed on probe GC instead, the fit is weaker — Pearson ${other.correlation.toFixed(3)} ` +
            `against ${fit.correlation.toFixed(3)}, residual spread ${(other.residual_spread * 100).toFixed(2)}% ` +
            `against ${(fit.residual_spread * 100).toFixed(2)}% — and it moves chromosomes whose probes ` +
            `misrepresent their sequence.`
          }
          legend={
            <>
              Both fits, side by side. The choice was made on mechanism and on fit quality, not on
              which produced the quieter answer, and it is shown here so that can be checked: a
              chromosome whose probes <em>understate</em> its GC is under-predicted by a probe-GC
              fit and handed a positive residual it did not earn.{' '}
              <span className="text-good-400">Green</span> — the reported fit, on the
              chromosome&rsquo;s GC. <span className="text-chrome-400">Grey</span> — the
              alternative, on probe GC.
            </>
          }
          source={source}
          cachedAt={cachedAt}
          origin={origin}
          data={[fit, other]}
        >
          <DataTable
            rows={[fit, other]}
            rowKey={(row) => row.source}
            columns={[
              { key: 'source', header: 'regressor', render: (row) => row.source },
              {
                key: 'correlation',
                header: 'Pearson r',
                align: 'right',
                render: (row) => row.correlation.toFixed(4),
              },
              {
                key: 'r2',
                header: 'variance explained',
                align: 'right',
                render: (row) => `${(row.correlation ** 2 * 100).toFixed(1)}%`,
              },
              {
                key: 'spread',
                header: 'spread before',
                align: 'right',
                render: (row) => `${(row.spread * 100).toFixed(3)}%`,
              },
              {
                key: 'residual_spread',
                header: 'spread after',
                align: 'right',
                render: (row) => `${(row.residual_spread * 100).toFixed(3)}%`,
              },
              {
                key: 'slope',
                header: 'slope per unit GC',
                align: 'right',
                render: (row) => row.slope.toFixed(4),
              },
            ]}
          />
        </Exhibit>
      )}
    </div>
  );
}
