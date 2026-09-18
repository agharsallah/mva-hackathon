import type { Step8Limit } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { byKaryogram, count, fraction, grid, HEMIZYGOUS, power } from './metrics';

/**
 * The two exhibits that make every other number on this page mean something.
 *
 * Entry 037 reported every autosome flat. It averaged the B-allele fraction inside each
 * megabase, and a mosaic gain splits heterozygous sites into two bands symmetric about the
 * centre — so the mean does not move and "flat" is what any gain of any size would have
 * produced. The comparison below runs both statistics on the same depth margin under the
 * same over-dispersion; the only difference is the quantity being averaged.
 *
 * The limit chart is the one a negative result has to be quoted with. It comes first in
 * reading order for that reason, before anything about what this sample shows.
 */
export function Limits({
  limits,
  source,
  cachedAt,
  origin,
}: {
  limits: Step8Limit[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const folded = byKaryogram(limits.filter((row) => row.statistic === 'bdev'));
  const mean = byKaryogram(limits.filter((row) => row.statistic === 'mean_baf'));
  const fractions = grid(folded);
  const reached = folded.filter((row) => row.f80 !== null);
  const meanReached = mean.filter((row) => row.f80 !== null);
  // Autosomes only: X and Y are hemizygous in this proband and their limit is the limit of
  // a route that cannot see them, so folding them in would have the sentence claim every
  // autosome needs 5 % when they need 2-3 %.
  const autosomal = reached.filter((row) => !HEMIZYGOUS.has(row.chrom));
  const worst = autosomal.length ? Math.max(...autosomal.map((row) => row.f80 as number)) : null;

  return (
    <div className="space-y-4">
      <Exhibit
        title="The same sites, scored two ways"
        reading={
          `Fold-over deviation reaches 80% power on ${reached.length} of ${folded.length} contigs; ` +
          `the mean B-allele fraction entry 037 used reaches it on ${meanReached.length}.`
        }
        legend={
          <>
            One line per contig, power against injected cell fraction.{' '}
            <span className="text-good-400">Green</span> — fold-over <code>|BAF − centre|</code>,
            averaged after folding. <span className="text-broken-400">Red</span> — the mean B-allele
            fraction, folded after averaging, which is what entry 037 measured. Both are evaluated
            on the same depth margin under the same over-dispersion, so the only difference is the
            quantity being averaged. <span className="text-decision-400">Yellow</span> — the 80%
            power the limit is read off. The red statistic is scored <strong>two-sided</strong>, the
            generous reading: a mosaic could move a mean either way and 037 would have reported
            either.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={limits}
      >
        <Plot
          height={420}
          data={[
            ...mean.map((row, index) => ({
              x: fractions,
              y: fractions.map((at) => power(row, at)),
              type: 'scatter' as const,
              mode: 'lines' as const,
              line: { color: C.broken, width: 1 },
              opacity: 0.6,
              name: '037 mean BAF',
              legendgroup: 'mean',
              showlegend: index === 0,
              hovertemplate: `chr${row.chrom} · mean BAF<br>f %{x}<br>power %{y:.2f}<extra></extra>`,
            })),
            ...folded.map((row, index) => ({
              x: fractions,
              y: fractions.map((at) => power(row, at)),
              type: 'scatter' as const,
              mode: 'lines' as const,
              line: { color: C.good, width: 1 },
              opacity: 0.7,
              name: 'fold-over Bdev',
              legendgroup: 'bdev',
              showlegend: index === 0,
              hovertemplate: `chr${row.chrom} · fold-over<br>f %{x}<br>power %{y:.2f}<extra></extra>`,
            })),
          ]}
          layout={{
            xaxis: { title: { text: 'injected cell fraction' }, tickformat: '.0%' },
            yaxis: { title: { text: 'power' }, range: [0, 1.02] },
            shapes: [
              {
                type: 'line',
                xref: 'paper',
                x0: 0,
                x1: 1,
                y0: 0.8,
                y1: 0.8,
                line: { color: C.decision, width: 2, dash: 'dash' },
              },
            ],
            legend: { orientation: 'h', y: 1.12 },
          }}
        />
      </Exhibit>

      <Exhibit
        title="The smallest mosaic fraction each chromosome could have shown"
        reading={
          worst === null
            ? 'No contig reaches 80% power at any simulated fraction.'
            : `Every autosome detects a mosaic present in ${fraction(worst)} of cells or more; a blank row is a blind spot, not a small limit.`
        }
        legend={
          <>
            One row per contig, with its heterozygous-call count and mean depth — the two things the
            limit is a function of. <strong>Detects at or above</strong> is the smallest injected
            fraction reaching 80% power.{' '}
            <span className="text-broken-400">&ldquo;never detected&rdquo;</span> means the
            statistic does not reach 80% at any fraction simulated, which is a blind spot rather
            than a small limit. X and Y are marked: in a male proband they carry almost no
            heterozygous calls, so allele balance cannot see them at all.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={folded}
      >
        <DataTable
          rows={folded}
          rowKey={(row) => row.chrom}
          columns={[
            {
              key: 'chrom',
              header: 'contig',
              render: (row) => (
                <span className={HEMIZYGOUS.has(row.chrom) ? 'text-chrome-400' : ''}>
                  chr{row.chrom}
                  {HEMIZYGOUS.has(row.chrom) && ' · hemizygous'}
                </span>
              ),
            },
            {
              key: 'n_sites',
              header: 'het calls',
              align: 'right',
              render: (row) => count(row.n_sites),
            },
            {
              key: 'mean_depth',
              header: 'mean depth',
              align: 'right',
              render: (row) => `${row.mean_depth.toFixed(1)}×`,
            },
            {
              key: 'f80',
              header: 'detects at or above',
              align: 'right',
              render: (row) => (
                <span className={row.f80 === null ? 'text-broken-400' : 'text-good-400'}>
                  {fraction(row.f80)}
                </span>
              ),
            },
            {
              key: 'mean_f80',
              header: "037's statistic",
              align: 'right',
              sortable: false,
              render: (row) => {
                const twin = mean.find((other) => other.chrom === row.chrom);
                return <span className="text-broken-400">{fraction(twin?.f80 ?? null)}</span>;
              },
            },
          ]}
        />
      </Exhibit>
    </div>
  );
}
