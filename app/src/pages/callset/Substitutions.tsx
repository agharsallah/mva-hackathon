import { useSubstitutions, useTsTv } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec, int } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Substitution spectrum. Chemistry, not biology, sets the expectation: C→T and its
 * mirror G→A dominate every human callset because methylated cytosine deaminates.
 * A spectrum that does *not* look like this is the classic sign of a technical artefact,
 * so this figure is the callset's authenticity check.
 */
export function Substitutions() {
  const q = useSubstitutions();
  const t = useTsTv();
  return (
    <Exhibit
      title="Substitution spectrum — which letter changes into which"
      legend={
        <>
          Twelve possible single-letter swaps.{' '}
          <Chip color={C.good}>
            transition (A↔G or C↔T — chemically easy, expected to dominate)
          </Chip>{' '}
          · <Chip color={C.machinery}>transversion (every other swap)</Chip>. Bar height = record
          count. The dashed <span style={{ color: C.decision }}>yellow</span> line is the mean
          transversion level, for scale.
        </>
      }
      reading="C>T and G>A are the two tall bars — the same event seen from either DNA strand. Ts/Tv 1.94 is squarely in the normal human whole-genome range, so the callset is not artefact-driven."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(rows) => {
          const transversions = rows.filter((r) => !r.is_transition);
          const meanTv =
            transversions.reduce((a, r) => a + r.count, 0) / Math.max(1, transversions.length);
          const ordered = [...rows].sort((a, b) => {
            if (a.is_transition !== b.is_transition) return a.is_transition ? -1 : 1;
            return b.count - a.count;
          });
          return (
            <>
              <Plot
                height={320}
                data={[
                  {
                    type: 'bar',
                    x: ordered.map((r) => r.sub_type),
                    y: ordered.map((r) => r.count),
                    marker: {
                      color: ordered.map((r) => (r.is_transition ? C.good : C.machinery)),
                      line: { width: 0 },
                    },
                    customdata: ordered.map((r) =>
                      r.is_transition ? 'transition' : 'transversion',
                    ),
                    hovertemplate: '%{x} — %{customdata}<br>%{y:,} records<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 70, r: 16, t: 8, b: 44 },
                  bargap: 0.28,
                  xaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                    categoryorder: 'array',
                    categoryarray: ordered.map((r) => r.sub_type),
                  },
                  yaxis: {
                    title: { text: 'records', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: meanTv,
                      y1: meanTv,
                      line: { color: C.decision, width: 1.2, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      xref: 'paper',
                      x: 0.995,
                      y: meanTv,
                      text: `mean transversion ${int(Math.round(meanTv))}`,
                      showarrow: false,
                      xanchor: 'right',
                      yanchor: 'bottom',
                      font: { color: C.decision, size: 10 },
                    },
                  ],
                  showlegend: false,
                })}
              />
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-micro text-chrome-400">
                <span>
                  Ts/Tv{' '}
                  <span className="font-mono text-good-300">{dec(t.data?.data.ratio ?? 0, 2)}</span>{' '}
                  (expected ≈2.0)
                </span>
                {t.data && (
                  <>
                    <span>
                      transitions{' '}
                      <span className="font-mono text-chrome-300">{int(t.data.data.ts)}</span>
                    </span>
                    <span>
                      transversions{' '}
                      <span className="font-mono text-chrome-300">{int(t.data.data.tv)}</span>
                    </span>
                  </>
                )}
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
