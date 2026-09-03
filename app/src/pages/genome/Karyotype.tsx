import { useContigDensity } from '../../api/hooks';
import { Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C, DENSITY_SCALE } from '../../lib/palette';
import { chromOrder } from './order';

/**
 * Karyotype ideogram. Bar length is the chromosome's real length in the GRCh38
 * coordinate system, so the picture is to scale; fill is call density, which normalises
 * away the length and shows where the caller was busiest per megabase.
 */
export function Karyotype() {
  const q = useContigDensity();
  return (
    <Exhibit
      title="Karyotype — chromosomes to scale, coloured by call density"
      legend={
        <>
          One horizontal bar per canonical chromosome, length = its real GRCh38 length in megabases.
          Fill follows variants per Mb on a dark →{' '}
          <span style={{ color: C.densityBlue }}>blue</span> →{' '}
          <span style={{ color: C.raw }}>purple</span> ramp (purple = densest, the raw-input end of
          the repo's scale). Bar length is a property of the reference; colour is a property of this
          sample.
        </>
      }
      reading="Lengths differ by 5× but densities only by about 1.25× across the autosomes — the callset is spread evenly. X and Y are the exception: a single copy yields far fewer heterozygous calls per Mb."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(rows) => {
          const ordered = [...rows]
            .filter((r) => r.chrom.replace(/^chr/, '') !== 'MT')
            .sort((a, b) => chromOrder(b.chrom) - chromOrder(a.chrom));
          const densest = [...ordered].sort((a, b) => b.variants_per_mb - a.variants_per_mb)[0];
          return (
            <>
              <Plot
                height={500}
                data={[
                  {
                    type: 'bar',
                    orientation: 'h',
                    y: ordered.map((r) => r.chrom),
                    x: ordered.map((r) => r.length / 1e6),
                    marker: {
                      color: ordered.map((r) => r.variants_per_mb),
                      colorscale: DENSITY_SCALE,
                      line: { color: C.grid, width: 1 },
                      colorbar: {
                        title: { text: 'var/Mb', font: { color: C.inkDim, size: 11 } },
                        tickfont: { color: C.inkDim, size: 10 },
                        thickness: 12,
                        len: 0.7,
                        outlinewidth: 0,
                      },
                    },
                    customdata: ordered.map((r) => [
                      r.n_records,
                      r.variants_per_mb,
                      r.pct_of_callset,
                    ]),
                    hovertemplate:
                      'chr%{y}<br>%{x:.1f} Mb long<br>%{customdata[0]:,} records<br>' +
                      '%{customdata[1]:.1f} var/Mb<br>%{customdata[2]:.2f}% of the callset<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 44, r: 20, t: 10, b: 44 },
                  bargap: 0.35,
                  xaxis: {
                    title: {
                      text: 'chromosome length (Mb, GRCh38)',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 10 },
                  },
                  showlegend: false,
                })}
              />
              {densest && (
                <p className="mt-2 text-micro text-chrome-500">
                  densest contig <span className="font-mono text-raw-400">chr{densest.chrom}</span>{' '}
                  at {dec(densest.variants_per_mb, 1)} var/Mb over {int(densest.n_records)} records
                </p>
              )}
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
