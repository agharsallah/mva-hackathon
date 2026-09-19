import type { Step8Dosage, Step8Fraction } from '../../../api/types';
import { DataTable } from '../../../components/DataTable';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { byKaryogram, HEMIZYGOUS, stat } from './metrics';

/**
 * The second instrument: how much sequence each chromosome actually contributed.
 *
 * The rest of this page asks the *called* variants a question about shape — where the
 * allele balance sits at heterozygous sites. This asks the *raw reads* a question about
 * quantity, and shares no step, no file and no failure mode with the first past the FASTQ.
 * Reference-unique 31-mers are assigned one chromosome each and counted across the read
 * store; a chromosome present in more copies contributed more sequence, so its probes are
 * hit more often, in proportion.
 *
 * Its blind spots are the mirror image of the allele route's, which is the point of running
 * both. Dosage sees X and Y, where a male proband has almost no heterozygous sites for the
 * allele route to read. It cannot see copy-neutral loss of heterozygosity, which swaps whose
 * copy is present without changing how much sequence there is. **Where both can see, they
 * must agree** — and that is the claim the third exhibit tests.
 */
export function Dosage({
  dosage,
  fractions,
  source,
  cachedAt,
  origin,
}: {
  dosage: Step8Dosage[];
  fractions: Step8Fraction[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  if (dosage.length === 0) return null;

  const rows = byKaryogram(dosage);
  const chroms = rows.map((row) => row.chrom);
  const thinning = rows[0]?.thinning;
  const swept = rows[0]?.shards_swept;
  const worst = [...rows].sort((a, b) => Math.abs(b.disagreement) - Math.abs(a.disagreement))[0];

  // A trisomy in a share f of cells raises a chromosome's sequence by f/2, so an observed
  // ratio r reads back as f = 2(r − 1). The inverse is only defined for a gain: a loss comes
  // out negative and is left that way rather than folded, because the sign is the finding.
  const implied = (value: number) => 2 * (value - 1);

  // Whole-chromosome rows only. The allele route reports arms as well, and an arm's estimate
  // is not comparable with a dosage measured across the whole contig.
  const allele = new Map(fractions.filter((row) => !row.arm).map((row) => [row.chrom, row]));
  const shared = rows.filter((row) => !HEMIZYGOUS.has(row.chrom) && allele.has(row.chrom));

  return (
    <div className="space-y-4">
      <Exhibit
        title="Sequence contributed per chromosome, against two denominators"
        reading={
          `Every contig sits within its interval of a single copy-number ratio. The two denominators ` +
          `part company most on chr${worst?.chrom ?? '—'} (${stat((worst?.disagreement ?? 0) * 100)}%), ` +
          `which is the number that says whether the median denominator moved.`
        }
        legend={
          <>
            <span className="text-good-400">Green</span> — the ratio against the{' '}
            <strong>autosomal median</strong>, with its bootstrap interval. Readable, and it assumes
            most autosomes are normal. <span className="text-machinery-400">Blue</span> — the ratio
            against the <strong>genome-wide calibration set</strong>, which no single chromosome can
            move; it assumes nothing, which is what <em>variegated</em> requires.{' '}
            <span className="text-chrome-400">Grey band</span> — one copy, where a normal contig
            belongs. X and Y are drawn: a single X in a male proband reads at ~0.5 and is the
            expected result, not a finding.
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
              x: chroms,
              y: rows.map((row) => row.relative),
              type: 'scatter',
              mode: 'markers',
              marker: { size: 10, color: C.good },
              error_y: {
                type: 'data',
                symmetric: false,
                array: rows.map((row) => row.high - row.relative),
                arrayminus: rows.map((row) => row.relative - row.low),
                color: C.good,
                thickness: 1,
              },
              name: 'against the autosomal median',
              hovertemplate: 'chr%{x}<br>%{y:.4f}× median<extra></extra>',
            },
            {
              x: chroms,
              y: rows.map((row) => row.absolute),
              type: 'scatter',
              mode: 'markers',
              marker: { size: 8, color: C.machinery, symbol: 'diamond-open' },
              name: 'against total k-mer mass',
              hovertemplate: 'chr%{x}<br>%{y:.4f}× absolute<extra></extra>',
            },
          ]}
          layout={{
            xaxis: { title: { text: 'chromosome' }, type: 'category' },
            yaxis: { title: { text: 'dosage (1 = one copy per copy expected)' } },
            legend: { orientation: 'h', y: 1.14 },
            shapes: [
              {
                type: 'rect' as const,
                xref: 'paper' as const,
                x0: 0,
                x1: 1,
                y0: 0.97,
                y1: 1.03,
                fillcolor: C.absent,
                opacity: 0.15,
                line: { width: 0 },
              },
            ],
          }}
        />
      </Exhibit>

      {shared.length > 0 && (
        <Exhibit
          title="Two instruments, one question"
          reading={
            `Both routes are read as a cell fraction and put on the same axis. They share nothing ` +
            `past the raw reads, so agreement is evidence and disagreement would name one of them wrong.`
          }
          legend={
            <>
              <span className="text-machinery-400">Blue</span> — the cell fraction implied by k-mer
              dosage, <code>f = 2(ratio − 1)</code>, which inverts a gain and reads a loss as a
              negative number rather than folding it. <span className="text-good-400">Green</span> —
              the allele-balance estimate with its interval, from the heterozygous sites of the same
              contig. Only autosomes appear: X and Y have too few heterozygous calls for the green
              route to have an opinion, which is itself the reason this exhibit exists.
            </>
          }
          source={source}
          cachedAt={cachedAt}
          origin={origin}
          data={shared}
        >
          <Plot
            height={340}
            data={[
              {
                x: shared.map((row) => row.chrom),
                y: shared.map((row) => implied(row.relative)),
                type: 'scatter',
                mode: 'markers',
                marker: { size: 10, color: C.machinery },
                error_y: {
                  type: 'data',
                  symmetric: false,
                  array: shared.map((row) => implied(row.high) - implied(row.relative)),
                  arrayminus: shared.map((row) => implied(row.relative) - implied(row.low)),
                  color: C.machinery,
                  thickness: 1,
                },
                name: 'k-mer dosage',
                hovertemplate: 'chr%{x}<br>implied fraction %{y:.3f}<extra></extra>',
              },
              {
                x: shared.map((row) => row.chrom),
                y: shared.map((row) => allele.get(row.chrom)?.f_hat ?? null),
                type: 'scatter',
                mode: 'markers',
                marker: { size: 8, color: C.good, symbol: 'square' },
                error_y: {
                  type: 'data',
                  symmetric: false,
                  array: shared.map((row) => {
                    const hit = allele.get(row.chrom);
                    return hit ? hit.f_high - hit.f_hat : 0;
                  }),
                  arrayminus: shared.map((row) => {
                    const hit = allele.get(row.chrom);
                    return hit ? hit.f_hat - hit.f_low : 0;
                  }),
                  color: C.good,
                  thickness: 1,
                },
                name: 'allele balance',
                hovertemplate: 'chr%{x}<br>fraction %{y:.3f}<extra></extra>',
              },
            ]}
            layout={{
              xaxis: { title: { text: 'chromosome' }, type: 'category' },
              yaxis: { title: { text: 'cell fraction implied' } },
              legend: { orientation: 'h', y: 1.14 },
              shapes: [
                {
                  type: 'line' as const,
                  xref: 'paper' as const,
                  x0: 0,
                  x1: 1,
                  y0: 0,
                  y1: 0,
                  line: { color: C.absent, width: 1, dash: 'dot' as const },
                },
              ],
            }}
          />
        </Exhibit>
      )}

      <Exhibit
        title="What the pass actually counted"
        reading={
          thinning !== undefined && thinning < 1
            ? `${swept?.toLocaleString()} of 272 shards were swept — ${(thinning * 100).toFixed(1)}% of the library. Shards are flowcell partitions, not genomic ones, so this is a uniform thinning: the ratio between chromosomes is unbiased and only its variance rises.`
            : 'Every shard in the read store was swept.'
        }
        legend={
          <>
            One row per contig. <strong>probes</strong> — reference-unique 31-mers assigned to it;
            nothing else in the genome can testify about that chromosome. <strong>silent</strong> —
            probes never hit at all, shown because a probe set that saw nothing reads as a dosage of
            zero unless you can see it was never counted. <strong>disagreement</strong> — how far
            the two denominators part company, which is where a moved median would show itself
            first.
          </>
        }
        source={source}
        cachedAt={cachedAt}
        origin={origin}
        data={rows}
      >
        <DataTable
          rows={rows}
          rowKey={(row) => row.chrom}
          columns={[
            { key: 'chrom', header: 'contig', render: (row) => `chr${row.chrom}` },
            {
              key: 'probes',
              header: 'probes',
              align: 'right',
              render: (row) => row.probes.toLocaleString(),
            },
            {
              key: 'silent_share',
              header: 'silent',
              align: 'right',
              render: (row) => `${(row.silent_share * 100).toFixed(1)}%`,
            },
            {
              key: 'mean_count',
              header: 'mean hits',
              align: 'right',
              render: (row) => stat(row.mean_count),
            },
            {
              key: 'relative',
              header: '÷ median',
              align: 'right',
              render: (row) =>
                `${row.relative.toFixed(4)} [${row.low.toFixed(4)}, ${row.high.toFixed(4)}]`,
            },
            {
              key: 'absolute',
              header: '÷ total mass',
              align: 'right',
              render: (row) => row.absolute.toFixed(4),
            },
            {
              key: 'disagreement',
              header: 'disagreement',
              align: 'right',
              render: (row) => `${(row.disagreement * 100).toFixed(2)}%`,
            },
          ]}
        />
      </Exhibit>
    </div>
  );
}
