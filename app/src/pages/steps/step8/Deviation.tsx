import type { Step8Bdev, Step8Constants, Step8Fraction, Step8ModelFit } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { byKaryogram, count, dev, fraction, HEMIZYGOUS, stat } from './metrics';

/**
 * What this sample actually shows — and it is read *after* the limits, on purpose.
 *
 * The null is per contig, built from that contig's own depth margin and the genome-wide
 * over-dispersion. A shared threshold would have flagged every shallow contig; this one
 * judges a shallow arm against a wider null instead. What it cannot do is separate a real
 * allele imbalance from a contig that is simply more dispersed than the genome — collapsed
 * repeats do that too — so the fitted over-dispersion travels in the table beside it.
 */
export function Deviation({
  bdev,
  fractions,
  models,
  constants,
  source,
  cachedAt,
  origin,
}: {
  bdev: Step8Bdev[];
  fractions: Step8Fraction[];
  models: Step8ModelFit[];
  constants: Step8Constants;
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const whole = byKaryogram(bdev.filter((row) => row.arm === ''));
  const flagged = whole.filter((row) => row.exceeds_null);
  const byChrom = new Map(fractions.map((row) => [row.chrom, row]));
  // Each contig's own over-dispersion, read off the `normal` fit: the Bdev null uses the
  // genome-wide value, so a contig several times that is dispersed by its own repeats and
  // its deviation is not evidence of a mosaic. The column is why the two sit side by side.
  const fitted = new Map(
    models.filter((row) => row.model === 'normal').map((row) => [row.chrom, row.rho]),
  );
  const chroms = whole.map((row) => row.chrom);

  return (
    <div className="space-y-4">
      <Exhibit
        title="Fold-over deviation, against each contig's own null"
        reading={
          flagged.length === 0
            ? 'No contig exceeds the null its own depths generate.'
            : `Above their null: ${flagged.map((row) => `chr${row.chrom}`).join(', ')} — read the over-dispersion column before reading that as mosaicism.`
        }
        legend={
          <>
            Bars are the observed mean <code>|BAF − centre|</code>.{' '}
            <span className="text-good-400">Green</span> — inside the null.{' '}
            <span className="text-broken-400">Red</span> — above it.{' '}
            <span className="text-chrome-400">Grey</span> — X and Y, hemizygous in this proband and
            not comparable with an autosome. The <span className="text-decision-400">yellow</span>{' '}
            tick is the null&rsquo;s 95th percentile and the{' '}
            <span className="text-machinery-400">blue</span> one its mean, both simulated from that
            contig&rsquo;s own depth margin at the genome-wide over-dispersion ρ ={' '}
            {dev(constants.rho)}, around a centre of {dev(constants.centre)} rather than 0.5.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={whole}
      >
        <Plot
          height={380}
          data={[
            {
              x: chroms,
              y: whole.map((row) => row.bdev),
              type: 'bar',
              marker: {
                color: whole.map((row) =>
                  HEMIZYGOUS.has(row.chrom) ? C.absent : row.exceeds_null ? C.broken : C.good,
                ),
              },
              name: 'observed',
              hovertemplate: 'chr%{x}<br>Bdev %{y:.5f}<extra></extra>',
            },
            {
              x: chroms,
              y: whole.map((row) => row.null_p95),
              type: 'scatter',
              mode: 'markers',
              marker: { symbol: 'line-ew-open', size: 18, line: { width: 2, color: C.decision } },
              name: 'null 95th percentile',
              hovertemplate: 'chr%{x}<br>reject above %{y:.5f}<extra></extra>',
            },
            {
              x: chroms,
              y: whole.map((row) => row.null_mean),
              type: 'scatter',
              mode: 'markers',
              marker: { symbol: 'line-ew-open', size: 18, line: { width: 1, color: C.machinery } },
              name: 'null mean',
              hovertemplate: 'chr%{x}<br>null mean %{y:.5f}<extra></extra>',
            },
          ]}
          layout={{
            xaxis: { title: { text: 'chromosome' }, type: 'category' },
            yaxis: { title: { text: 'mean |BAF − centre|' } },
            legend: { orientation: 'h', y: 1.14 },
          }}
        />
      </Exhibit>

      <Exhibit
        title="Every contig, with the fraction estimate and the bias it was corrected for"
        reading={
          'The published estimator reads far from zero on a balanced contig at this depth, so the same estimator is run on null draws and subtracted. The corrected column is the one to quote.'
        }
        legend={
          <>
            <strong>z</strong> is how many null standard deviations the deviation sits above the
            null mean; <strong>ρ fitted</strong> is that contig&rsquo;s own over-dispersion — a
            contig several times the genome-wide value is dispersed by repeats, and its deviation is
            not evidence of a mosaic. <strong>DANFIP raw</strong> is Markello 2012 as written,{' '}
            <strong>null</strong> is the same estimator on balanced draws from the same depths, and{' '}
            <strong>corrected</strong> is the difference, floored at zero.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={whole}
      >
        <DataTable
          rows={whole}
          rowKey={(row) => row.chrom}
          columns={[
            {
              key: 'chrom',
              header: 'contig',
              render: (row) => (
                <span className={HEMIZYGOUS.has(row.chrom) ? 'text-chrome-400' : ''}>
                  chr{row.chrom}
                </span>
              ),
            },
            {
              key: 'n_sites',
              header: 'het calls',
              align: 'right',
              render: (row) => count(row.n_sites),
            },
            { key: 'bdev', header: 'deviation', align: 'right', render: (row) => dev(row.bdev) },
            {
              key: 'null_p95',
              header: 'reject above',
              align: 'right',
              render: (row) => dev(row.null_p95),
            },
            {
              key: 'z',
              header: 'z',
              align: 'right',
              render: (row) => (
                <span className={row.exceeds_null ? 'text-broken-400' : 'text-good-400'}>
                  {stat(row.z)}
                </span>
              ),
            },
            {
              key: 'rho_fitted',
              header: 'ρ fitted',
              align: 'right',
              sortable: false,
              render: (row) => {
                const own = fitted.get(row.chrom);
                if (own === undefined) return '—';
                const ratio = own / row.rho;
                return (
                  <span className={ratio > 2 ? 'text-broken-400' : ''}>
                    {dev(own)} ({ratio.toFixed(1)}×)
                  </span>
                );
              },
            },
            {
              key: 'f_raw',
              header: 'DANFIP raw',
              align: 'right',
              sortable: false,
              render: (row) => fraction(byChrom.get(row.chrom)?.f_raw ?? null),
            },
            {
              key: 'f_null',
              header: 'its null',
              align: 'right',
              sortable: false,
              render: (row) => fraction(byChrom.get(row.chrom)?.f_null ?? null),
            },
            {
              key: 'f_hat',
              header: 'corrected',
              align: 'right',
              sortable: false,
              render: (row) => <strong>{fraction(byChrom.get(row.chrom)?.f_hat ?? null)}</strong>,
            },
          ]}
        />
      </Exhibit>
    </div>
  );
}
