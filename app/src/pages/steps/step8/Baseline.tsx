import type { Step8Baseline, Step8Density, Step8Multi } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { HEMIZYGOUS, ORDER, stat } from './metrics';

/**
 * The denominator, and the failure mode this disease is named after.
 *
 * Allele balance, depth and k-mer dosage are all relative measurements: a contig is judged
 * against the rest of the genome. Kong 2018's discussion says the model degrades when
 * several chromosomes are abnormal at once, and *variegated* aneuploidy is exactly that —
 * so all three routes share one failure mode, and it is the one this disease would produce.
 *
 * Two exhibits, one for each half of the answer. The first asks whether any single contig
 * can move the baseline on the real sample. The second injects two and three at once and
 * reports both what was recovered **and** what was invented, because a bound that flags
 * untouched chromosomes when its neighbours move is not a bound.
 */
export function Baseline({
  baseline,
  multi,
  density,
  source,
  cachedAt,
  origin,
}: {
  baseline: Step8Baseline;
  multi: Step8Multi[];
  density: Step8Density[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const ratios = baseline.depth_ratio ?? {};
  const sex = baseline.sex_chromosome_ratio ?? {};
  const spread = baseline.depth_spread ?? 0.02;
  const shifted = baseline.shifted ?? [];
  const chroms = ORDER.filter((name) => name in ratios || name in sex);
  const values = chroms.map((name) => ratios[name] ?? sex[name] ?? null);
  const acrocentric = density.filter((row) => row.acrocentric && row.arm === 'p');

  return (
    <div className="space-y-4">
      <Exhibit
        title="Each contig's depth against a baseline it was left out of"
        reading={
          shifted.length === 0
            ? `No contig's exclusion moves the baseline beyond its bootstrap interval; the spread across autosomes is ±${(spread * 100).toFixed(1)}%.`
            : `Moved by: ${shifted.map((name) => `chr${name}`).join(', ')} — the genome-wide assumption is under strain on this sample.`
        }
        legend={
          <>
            Each contig&rsquo;s mean depth divided by the median of the per-contig medians with that
            contig held out, so no single one can prop up its own denominator.{' '}
            <span className="text-decision-400">Yellow dots</span> — the measured spread of the
            ratio across autosomes, which is the precision floor below which a depth shift is not
            evidence of anything. <span className="text-machinery-400">Blue</span> — the baseline
            itself. <span className="text-chrome-400">Grey</span> — X and Y, where the
            proband&rsquo;s single X is the expected result rather than a finding.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={[baseline]}
      >
        <Plot
          height={340}
          data={[
            {
              x: chroms,
              y: values,
              type: 'scatter',
              mode: 'markers',
              marker: {
                size: 11,
                color: chroms.map((name) => (HEMIZYGOUS.has(name) ? C.absent : C.good)),
              },
              name: 'depth ÷ baseline',
              hovertemplate: 'chr%{x}<br>%{y:.3f}× baseline<extra></extra>',
            },
          ]}
          layout={{
            xaxis: { title: { text: 'chromosome' }, type: 'category' },
            yaxis: { title: { text: 'mean depth ÷ leave-one-out baseline' } },
            showlegend: false,
            shapes: [1 + spread, 1, 1 - spread].map((y, index) => ({
              type: 'line' as const,
              xref: 'paper' as const,
              x0: 0,
              x1: 1,
              y0: y,
              y1: y,
              line: {
                color: index === 1 ? C.machinery : C.decision,
                width: 1,
                dash: index === 1 ? ('solid' as const) : ('dot' as const),
              },
            })),
          }}
        />
      </Exhibit>

      {multi.length > 0 && (
        <Exhibit
          title="When several chromosomes are abnormal at once"
          reading={
            'Recovery alone would pass with a test that flags everything, so the second bar is the one that decides whether a genome-wide bound survives on a variegated genome.'
          }
          legend={
            <>
              Each design injects the same cell fraction into two or three contigs and rescores{' '}
              <em>every</em> contig on the same replicate.{' '}
              <span className="text-good-400">Green</span> — injected contigs recovered.{' '}
              <span className="text-broken-400">Red</span> — untouched contigs flagged, measured
              rather than assumed at the nominal rate. Each arm&rsquo;s null uses its own depths, so
              the only way an injected contig can flag an untouched one is through the two constants
              fitted across the genome — which every replicate refits, exactly as a real run would.
            </>
          }
          source={source}
          cachedAt={cachedAt}
          origin={origin}
          data={multi}
        >
          <Plot
            height={340}
            data={[
              {
                x: multi.map((row) => `${row.n_affected}× at ${(row.fraction * 100).toFixed(0)}%`),
                y: multi.map((row) => row.recall),
                type: 'bar',
                marker: { color: C.good },
                name: 'injected recovered',
                hovertemplate: '%{x}<br>recall %{y:.2f}<extra></extra>',
              },
              {
                x: multi.map((row) => `${row.n_affected}× at ${(row.fraction * 100).toFixed(0)}%`),
                y: multi.map((row) => row.false_positive_rate),
                type: 'bar',
                marker: { color: C.broken },
                name: 'untouched flagged',
                hovertemplate: '%{x}<br>false positive rate %{y:.3f}<extra></extra>',
              },
            ]}
            layout={{
              barmode: 'group',
              xaxis: { title: { text: 'design' }, type: 'category' },
              yaxis: { title: { text: 'share' } },
              legend: { orientation: 'h', y: 1.14 },
            }}
          />
        </Exhibit>
      )}

      <Exhibit
        title="Heterozygous calls per PASS call, by arm"
        reading={`The statistic a monosomy moves and allele balance cannot see. The acrocentric short arms (${acrocentric
          .map((row) => `chr${row.chrom}`)
          .join(', ')}) are reference sequence with no unique content, and their counts say so.`}
        legend={
          <>
            Heterozygous calls divided by PASS calls, per arm. Those events <strong>remove</strong>{' '}
            heterozygous sites rather than shifting them, so the count is a discriminating statistic
            — but it is reported here and deliberately kept out of the likelihood: in a bulk sample
            the diploid cells still make a site heterozygous, so what actually removes the call is
            the caller&rsquo;s threshold, and that is not a model anyone can write down honestly.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={density}
      >
        <DataTable
          rows={density.filter((row) => row.arm === 'p' || row.arm === 'q')}
          rowKey={(row) => `${row.chrom}${row.arm}`}
          columns={[
            { key: 'chrom', header: 'contig', render: (row) => `chr${row.chrom}${row.arm}` },
            {
              key: 'het_sites',
              header: 'het calls',
              align: 'right',
              render: (row) => row.het_sites.toLocaleString(),
            },
            {
              key: 'pass_sites',
              header: 'PASS calls',
              align: 'right',
              render: (row) => row.pass_sites.toLocaleString(),
            },
            {
              key: 'het_share',
              header: 'het ÷ PASS',
              align: 'right',
              render: (row) => stat(row.het_share),
            },
            {
              key: 'het_per_mb',
              header: 'het per Mb',
              align: 'right',
              render: (row) => stat(row.het_per_mb),
            },
            {
              key: 'acrocentric',
              header: 'short arm',
              render: (row) => (row.acrocentric ? 'ribosomal stalk' : '—'),
            },
          ]}
        />
      </Exhibit>
    </div>
  );
}
