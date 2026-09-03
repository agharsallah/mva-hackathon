import { useMemo } from 'react';

import { useBafBins } from '../../api/hooks';
import type { BafBinRow } from '../../api/types';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C, DENSITY_SCALE, DEPTH_SCALE, DIVERGING_SCALE } from '../../lib/palette';
import { useUrlEnum, useUrlState } from '../../lib/urlstate';
import { CHROM_ORDER, chromOrder } from './order';

type Metric = 'vaf' | 'dp' | 'n_het';

const METRICS: { value: Metric; label: string }[] = [
  { value: 'vaf', label: 'BAF deviation from 0.5' },
  { value: 'dp', label: 'mean read depth' },
  { value: 'n_het', label: 'heterozygous calls' },
];

/** The contig vocabulary the `baf.chrom` URL parameter accepts; anything else reads as `all`. */
const CONTIGS = ['all', ...CHROM_ORDER.filter((c) => c !== 'MT')];

/** Half-width of the colour range for the diverging view: ±0.15 BAF around 0.5. */
const VAF_SPAN = 0.15;

/** Below this many heterozygous calls a bin is a guess, not a measurement. */
const THIN = 20;

function cell(row: BafBinRow, metric: Metric): number {
  if (metric === 'dp') return row.mean_dp;
  if (metric === 'n_het') return row.n_het;
  return row.mean_vaf;
}

/**
 * Reshape the long rows into a chromosome × megabase matrix.
 *
 * Two matrices come back, not one. `z` holds the metric for bins that are actually
 * measured; `thin` holds the same cells for bins under the confidence floor and is drawn
 * as a separate flat-grey layer. Painting a 6-call bin with the same saturated colour as a
 * 1,800-call bin is the single easiest way for a heatmap to invent a finding.
 */
function matrix(rows: BafBinRow[], metric: Metric) {
  const chroms = [...new Set(rows.map((r) => r.chrom))].sort(
    (a, b) => chromOrder(b) - chromOrder(a),
  );
  const maxMb = Math.max(0, ...rows.map((r) => r.mb));
  const index = new Map(chroms.map((c, i) => [c, i]));
  const blank = () => chroms.map(() => Array<number | null>(maxMb + 1).fill(null));
  const z = blank();
  const thin = blank();
  const meta: (BafBinRow | null)[][] = chroms.map(() =>
    Array<BafBinRow | null>(maxMb + 1).fill(null),
  );

  for (const r of rows) {
    const i = index.get(r.chrom);
    if (i === undefined) continue;
    meta[i][r.mb] = r;
    (r.low_confidence ? thin : z)[i][r.mb] = cell(r, metric);
  }
  return { chroms, z, thin, meta, x: Array.from({ length: maxMb + 1 }, (_, i) => i) };
}

/** Hover text is built once per cell so every metric shows the same five facts. */
function hover(meta: (BafBinRow | null)[][]): string[][] {
  return meta.map((row) =>
    row.map((r) =>
      r === null
        ? ''
        : [
            `<b>chr${r.chrom} @ ${r.mb} Mb</b>`,
            `${int(r.n_het)} heterozygous calls${r.low_confidence ? ' — LOW CONFIDENCE' : ''}`,
            `mean BAF ${dec(r.mean_vaf, 4)} (${r.vaf_deviation >= 0 ? '+' : ''}${dec(r.vaf_deviation, 4)})`,
            `median ${dec(r.median_vaf, 4)} · spread ${r.sd_vaf === null ? '—' : dec(r.sd_vaf, 4)}`,
            `${dec(r.pct_in_0_40_0_60, 1)} % inside 0.40–0.60`,
            `mean depth ${dec(r.mean_dp, 1)}×`,
          ].join('<br>'),
    ),
  );
}

/**
 * The karyogram: allele balance re-asked one megabase at a time.
 *
 * `AlleleBalance` averages a whole chromosome, which is the right grain for "is chr21
 * present three times" and the wrong grain for MVA, where the event can be a segment and
 * is carried by only some cells. A shifted 20 Mb arm inside a 250 Mb chromosome moves the
 * chromosome mean by almost nothing; here it would be a visible band.
 */
export function BafKaryogram() {
  // `baf.*`, not `bins.*`: this exhibit shares the Genome page with DensityBins, and the two
  // contig pickers are independent selections. See lib/urlstate.
  const [chrom, setChrom] = useUrlState('baf.chrom', 'all', CONTIGS);
  const [metric, setMetric] = useUrlEnum<Metric>(
    'baf.metric',
    'vaf',
    METRICS.map((m) => m.value),
  );
  const q = useBafBins(chrom === 'all' ? undefined : chrom);

  const chromOptions = useMemo(
    () => CONTIGS.map((c) => ({ value: c, label: c === 'all' ? 'all canonical' : `chr${c}` })),
    [],
  );

  return (
    <Exhibit
      title="BAF karyogram — allele balance per megabase"
      controls={
        <>
          <Select value={chrom} options={chromOptions} onChange={setChrom} label="contig" />
          <Select value={metric} options={METRICS} onChange={setMetric} label="metric" />
        </>
      }
      legend={
        <>
          <strong>B-allele fraction (BAF)</strong> — at a heterozygous site the two inherited copies
          differ, so on a normal two-copy region the variant should appear in about half the reads:
          BAF ≈ <span className="font-mono">0.5</span>. A mosaic gain or loss makes the two alleles
          unequally represented, so the bin&apos;s BAF shifts off 0.5 and its depth moves with it —
          both in proportion to how many cells carry the event. One row per chromosome (karyotype
          order), one column per megabase.{' '}
          {metric === 'vaf' ? (
            <>
              Colour is mean BAF on a diverging ramp centred on 0.5:{' '}
              <Chip color={C.good}>0.5, balanced</Chip> ·{' '}
              <Chip color={C.broken}>≤ {dec(0.5 - VAF_SPAN, 2)}, variant under-represented</Chip> ·{' '}
              <Chip color={C.raw}>≥ {dec(0.5 + VAF_SPAN, 2)}, over-represented</Chip>.
            </>
          ) : metric === 'dp' ? (
            <>
              Colour is mean read depth on a dark → <span style={{ color: C.machinery }}>blue</span>{' '}
              → white ramp. A lost copy halves depth; a gained one raises it ~1.5×.
            </>
          ) : (
            <>
              Colour is the number of heterozygous calls in the bin, dark →{' '}
              <span style={{ color: C.densityBlue }}>blue</span> →{' '}
              <span style={{ color: C.raw }}>purple</span>.
            </>
          )}{' '}
          <Chip color={C.unmeasured}>flat grey</Chip> = fewer than {THIN} heterozygous calls, so the
          bin is <em>unmeasured</em>, not balanced — mostly centromeres, acrocentric arms, and the
          single-copy X and Y. Blank cells are past the end of that chromosome.
        </>
      }
      reading={
        <>
          A flat green field is the honest negative: at this resolution no segment&apos;s allele
          balance leaves the 0.5 line and no arm steps in depth. That bounds the mosaic fraction —
          it does not disprove it. The VCF is a coarse instrument: it reports one
          already-thresholded genotype per site, so a low-fraction aneuploid clone stays under its
          floor. The read-level path is the lower floor, and it is where a negative here has to be
          re-tested before it becomes a claim.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(rows) => {
          const { chroms, z, thin, meta, x } = matrix(rows, metric);
          const text = hover(meta);
          const values = rows.filter((r) => !r.low_confidence).map((r) => cell(r, metric));
          const top = values.length ? Math.max(...values) : 1;
          const range =
            metric === 'vaf'
              ? { zmin: 0.5 - VAF_SPAN, zmax: 0.5 + VAF_SPAN }
              : { zmin: 0, zmax: top };
          const scale =
            metric === 'vaf' ? DIVERGING_SCALE : metric === 'dp' ? DEPTH_SCALE : DENSITY_SCALE;
          const thinCount = rows.filter((r) => r.low_confidence).length;
          const worst = [...rows]
            .filter((r) => !r.low_confidence)
            .sort((a, b) => Math.abs(b.vaf_deviation) - Math.abs(a.vaf_deviation))[0];

          return (
            <>
              <Plot
                height={Math.max(220, 19 * chroms.length + 100)}
                data={[
                  {
                    type: 'heatmap',
                    z,
                    x,
                    y: chroms,
                    text,
                    ...range,
                    colorscale: scale,
                    hoverongaps: false,
                    colorbar: {
                      thickness: 12,
                      len: 0.85,
                      tickfont: { color: C.inkDim, size: 10 },
                      outlinewidth: 0,
                      title: {
                        text: METRICS.find((m) => m.value === metric)!.label,
                        font: { color: C.inkDim, size: 10 },
                      },
                    },
                    hovertemplate: '%{text}<extra></extra>',
                  },
                  // Second layer, no colour bar: the bins whose count is too small to
                  // read as a measurement. One flat grey, so they cannot be mistaken for
                  // a value on the scale above.
                  {
                    type: 'heatmap',
                    z: thin,
                    x,
                    y: chroms,
                    text,
                    colorscale: [
                      [0, C.unmeasured],
                      [1, C.unmeasured],
                    ],
                    showscale: false,
                    hoverongaps: false,
                    hovertemplate: '%{text}<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 44, r: 10, t: 8, b: 44 },
                  xaxis: {
                    title: {
                      text: 'position along the chromosome (Mb)',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 10 },
                  },
                })}
              />
              <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-micro text-chrome-500">
                <span>
                  {int(rows.length)} bins across {chroms.length} contigs
                </span>
                <span>
                  <span className="font-mono text-chrome-400">{int(thinCount)}</span> under {THIN}{' '}
                  het calls (rendered unmeasured)
                </span>
                {worst && (
                  <span>
                    largest measured deviation:{' '}
                    <span className="font-mono text-chrome-400">
                      chr{worst.chrom} {worst.vaf_deviation >= 0 ? '+' : ''}
                      {dec(worst.vaf_deviation, 4)}
                    </span>{' '}
                    at {int(worst.n_het)} calls, depth {dec(worst.mean_dp, 1)}×
                  </span>
                )}
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
