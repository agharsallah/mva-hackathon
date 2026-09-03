import { useMemo } from 'react';

import { useDensityBins } from '../../api/hooks';
import type { DensityBinRow } from '../../api/types';
import { Select, Toggle } from '../../components/Controls';
import { Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout, scene3d } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C, DENSITY_SCALE, QUALITY_SCALE } from '../../lib/palette';
import { useUrlEnum, useUrlState, useUrlToggle } from '../../lib/urlstate';
import { CHROM_ORDER, chromOrder } from './order';

type Metric = 'n' | 'pass_pct' | 'mean_qual';

const METRICS: { value: Metric; label: string }[] = [
  { value: 'n', label: 'calls per Mb' },
  { value: 'pass_pct', label: 'PASS share per Mb' },
  { value: 'mean_qual', label: 'mean QUAL per Mb' },
];

/** The contig vocabulary the `bins.chrom` URL parameter accepts; anything else reads as `all`. */
const CONTIGS = ['all', ...CHROM_ORDER.filter((c) => c !== 'MT')];

function cell(row: DensityBinRow, metric: Metric): number {
  if (metric === 'n') return row.n;
  if (metric === 'mean_qual') return row.mean_qual;
  return row.n === 0 ? 0 : (row.pass_n / row.n) * 100;
}

/** Reshape the long rows into a chrom × Mb matrix, which is what both views need. */
function matrix(rows: DensityBinRow[], metric: Metric) {
  const chroms = [...new Set(rows.map((r) => r.chrom))].sort(
    (a, b) => chromOrder(b) - chromOrder(a),
  );
  const maxMb = Math.max(...rows.map((r) => r.mb));
  const index = new Map(chroms.map((c, i) => [c, i]));
  const z: (number | null)[][] = chroms.map(() => Array<number | null>(maxMb + 1).fill(null));
  for (const r of rows) {
    const i = index.get(r.chrom);
    if (i !== undefined) z[i][r.mb] = cell(r, metric);
  }
  return { chroms, z, x: Array.from({ length: maxMb + 1 }, (_, i) => i) };
}

/**
 * Precomputed 1 Mb density bins — one honest use of a 3D view.
 *
 * The data really is three-dimensional (chromosome × position × count), and the surface
 * makes the shared structure visible at a glance: every chromosome has the same deep
 * trough where the caller goes quiet. In 2D that reads as 24 separate dips; in 3D it reads
 * as one ridge line, which is the correct interpretation.
 */
export function DensityBins() {
  // Selections live in the URL (`?bins.chrom=7&bins.metric=mean_qual&bins.3d=1`) so a figure
  // in the report can be cited by link. See lib/urlstate.
  const [chrom, setChrom] = useUrlState('bins.chrom', 'all', CONTIGS);
  const [metric, setMetric] = useUrlEnum<Metric>(
    'bins.metric',
    'n',
    METRICS.map((m) => m.value),
  );
  const [threeD, setThreeD] = useUrlToggle('bins.3d');
  const q = useDensityBins(chrom === 'all' ? undefined : chrom);

  const chromOptions = useMemo(
    () => CONTIGS.map((c) => ({ value: c, label: c === 'all' ? 'all canonical' : `chr${c}` })),
    [],
  );

  const scale = metric === 'mean_qual' ? QUALITY_SCALE : DENSITY_SCALE;

  return (
    <Exhibit
      title="Density along each chromosome — 1 Mb bins"
      controls={
        <>
          <Select value={chrom} options={chromOptions} onChange={setChrom} label="contig" />
          <Select value={metric} options={METRICS} onChange={setMetric} label="metric" />
          <Toggle on={threeD} onChange={setThreeD}>
            {threeD ? '3D surface' : '2D heat strips'}
          </Toggle>
        </>
      }
      legend={
        <>
          Each row is one chromosome, each column one megabase of position.{' '}
          {metric === 'mean_qual' ? (
            <>
              Colour follows mean QUAL on a <span style={{ color: C.broken }}>red (low)</span> →{' '}
              <span style={{ color: C.decision }}>yellow</span> →{' '}
              <span style={{ color: C.good }}>green (high)</span> ramp.
            </>
          ) : (
            <>
              Colour follows {metric === 'n' ? 'the call count' : 'the PASS share'} on a dark →{' '}
              <span style={{ color: C.densityBlue }}>blue</span> →{' '}
              <span style={{ color: C.raw }}>purple</span> ramp (purple = highest). Blank cells are
              past the end of that chromosome.
            </>
          )}{' '}
          In 3D the same matrix becomes a surface: x = megabase, y = chromosome, z = the metric.
        </>
      }
      reading="The deep trough that repeats on every chromosome is the centromere — highly repetitive sequence where reads cannot be placed uniquely, so the caller emits almost nothing. It is a property of the reference, not of this patient."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={threeD ? 560 : 460}>
        {(rows) => {
          const { chroms, z, x } = matrix(rows, metric);
          const label = METRICS.find((m) => m.value === metric)!.label;
          if (threeD) {
            return (
              <>
                <Plot
                  height={540}
                  data={[
                    {
                      type: 'surface',
                      z,
                      x,
                      y: chroms,
                      colorscale: scale,
                      showscale: true,
                      colorbar: {
                        thickness: 12,
                        len: 0.6,
                        tickfont: { color: C.inkDim, size: 10 },
                        outlinewidth: 0,
                      },
                      contours: { z: { show: true, usecolormap: true, project: { z: true } } },
                      hovertemplate: 'chr%{y} @ %{x} Mb<br>' + label + ' %{z:.1f}<extra></extra>',
                    },
                  ]}
                  layout={baseLayout({
                    margin: { l: 0, r: 0, t: 0, b: 0 },
                    scene: scene3d({
                      xaxis: {
                        title: { text: 'position (Mb)' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      yaxis: {
                        title: { text: 'chromosome' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      zaxis: {
                        title: { text: label },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      camera: { eye: { x: 1.7, y: -1.5, z: 0.9 } },
                      aspectratio: { x: 1.8, y: 1, z: 0.6 },
                    }),
                  })}
                />
                <p className="mt-1 text-micro text-chrome-500">
                  drag to rotate · {int(rows.length)} bins across {chroms.length} contigs
                </p>
              </>
            );
          }
          return (
            <>
              <Plot
                height={Math.max(200, 18 * chroms.length + 90)}
                data={[
                  {
                    type: 'heatmap',
                    z,
                    x,
                    y: chroms,
                    colorscale: scale,
                    hoverongaps: false,
                    colorbar: {
                      thickness: 12,
                      len: 0.85,
                      tickfont: { color: C.inkDim, size: 10 },
                      outlinewidth: 0,
                    },
                    hovertemplate: 'chr%{y} @ %{x} Mb<br>' + label + ' %{z:.1f}<extra></extra>',
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
              <p className="mt-1 text-micro text-chrome-500">
                {int(rows.length)} bins across {chroms.length} contigs
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
