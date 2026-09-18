import type { Step8ModelFit, Step8Verdict } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { byKaryogram, fraction, stat, verdictTone } from './metrics';

/**
 * Five models per contig, and the three reasons the winner is usually not a call.
 *
 * Kong 2018 compares five per-chromosome models by BIC and declares a margin under ten
 * low-confidence. Re-implemented here from the paper, that rule is doing more work than the
 * paper needed it to: two of the five models are *nested* — meiotic trisomy is mitotic
 * trisomy plus a balanced tract — so their margin is bounded below by one BIC penalty and a
 * trisomy can be led but never confidently called. That is a property of the model family,
 * not of this sample, and the `call` column says it rather than hiding it behind a ranking.
 */
export function Models({
  fits,
  verdicts,
  source,
  cachedAt,
  origin,
}: {
  fits: Step8ModelFit[];
  verdicts: Step8Verdict[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const rows = byKaryogram(verdicts);
  const called = rows.filter((row) => row.confident && row.measurable);
  const unmeasurable = rows.filter((row) => !row.measurable);
  const byChrom = new Map<string, Step8ModelFit[]>();
  for (const fit of fits) {
    byChrom.set(fit.chrom, [...(byChrom.get(fit.chrom) ?? []), fit]);
  }

  return (
    <Exhibit
      title="Five models per chromosome, and what the margin allows"
      reading={
        `${called.length} of ${rows.length} contigs clear Kong 2018's ΔBIC ≥ 10` +
        (unmeasurable.length
          ? `; ${unmeasurable.length} are reported not measurable, their allele balance swallowed by tails no model explains.`
          : '.')
      }
      legend={
        <>
          One row per contig. <strong>Call</strong> is the only column to read as a result:{' '}
          <span className="text-good-400">green</span> — the leading model is <code>normal</code>;{' '}
          <span className="text-decision-400">yellow</span> — a mechanism leads but the margin does
          not license it, so it reads <em>not distinguishable</em>;{' '}
          <span className="text-broken-400">red</span> — <em>not measurable</em>, the fitted noise
          share is past 10% and no band structure survives underneath it. <strong>Noise</strong> is
          the share of calls no model claims to explain — collapsed repeats, unflagged copy number,
          one allele mapping badly. <strong>Trisomy vs CN-LOH</strong> is the pairwise margin for
          the two models that share their bands and differ only in depth; near zero means depth
          could not separate them at this precision.
        </>
      }
      source={source}
      cachedAt={cachedAt}
      origin={origin}
      data={verdicts}
    >
      <DataTable
        rows={rows}
        rowKey={(row) => row.chrom}
        columns={[
          { key: 'chrom', header: 'contig', render: (row) => `chr${row.chrom}` },
          {
            key: 'call',
            header: 'call',
            render: (row) => <Badge tone={verdictTone(row)}>{row.call}</Badge>,
          },
          { key: 'best', header: 'leading model', render: (row) => row.best },
          { key: 'runner_up', header: 'runner-up', render: (row) => row.runner_up },
          {
            key: 'delta_bic',
            header: 'ΔBIC',
            align: 'right',
            render: (row) => (
              <span className={row.confident ? 'text-good-400' : 'text-decision-400'}>
                {stat(row.delta_bic)}
              </span>
            ),
          },
          {
            key: 'fraction',
            header: 'fitted fraction',
            align: 'right',
            render: (row) => (row.best === 'normal' ? '—' : fraction(row.fraction)),
          },
          {
            key: 'noise_share',
            header: 'noise',
            align: 'right',
            render: (row) => (
              <span className={row.measurable ? '' : 'text-broken-400'}>
                {(row.noise_share * 100).toFixed(1)}%
              </span>
            ),
          },
          {
            key: 'trisomy_vs_cnloh',
            header: 'trisomy vs CN-LOH',
            align: 'right',
            render: (row) => stat(row.trisomy_vs_cnloh),
          },
          {
            key: 'fitted',
            header: 'models fitted',
            align: 'right',
            sortable: false,
            render: (row) => (byChrom.get(row.chrom) ?? []).length,
          },
        ]}
      />
    </Exhibit>
  );
}
