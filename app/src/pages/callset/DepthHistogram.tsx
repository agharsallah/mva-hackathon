import { useDepthDistribution } from '../../api/hooks';
import { Exhibit } from '../../components/Exhibit';
import { baseLayout, Plot } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Depth distribution. One clean mode is the signal of a healthy library: a second bump
 * would mean a systematic subpopulation (contamination, a copy-number event, a mismapped
 * region class). The log y-axis is what makes the tails inspectable at all.
 */
export function DepthHistogram() {
  const q = useDepthDistribution();
  return (
    <Exhibit
      title="Read depth across called sites"
      legend={
        <>
          <span style={{ color: C.machinery }}>Blue bars</span> = number of called sites at each
          depth (neutral machinery). y is a log scale, so a bar one gridline lower holds ten times
          fewer sites. The dashed <span style={{ color: C.decision }}>yellow</span> line marks the
          mode — the single most common depth.
        </>
      }
      reading="Unimodal, mode at about 44×. One peak means one homogeneous library; the long thin right tail is repetitive sequence where reads pile up."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(rows) => {
          const mode = rows.reduce((best, r) => (r.count > best.count ? r : best), rows[0]);
          return (
            <>
              <Plot
                height={320}
                data={[
                  {
                    type: 'bar',
                    x: rows.map((r) => r.bin),
                    y: rows.map((r) => r.count),
                    marker: { color: C.machinery, line: { width: 0 } },
                    hovertemplate: '%{x}× depth<br>%{y:,} sites<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 66, r: 16, t: 8, b: 46 },
                  bargap: 0.06,
                  xaxis: {
                    title: { text: 'read depth (×)', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    type: 'log',
                    title: { text: 'called sites (log)', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      yref: 'paper',
                      y0: 0,
                      y1: 1,
                      x0: mode.bin,
                      x1: mode.bin,
                      line: { color: C.decision, width: 1.4, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      x: mode.bin,
                      yref: 'paper',
                      y: 1,
                      text: `mode ${mode.bin}×`,
                      showarrow: false,
                      yanchor: 'top',
                      xanchor: 'left',
                      font: { color: C.decision, size: 11 },
                    },
                  ],
                  showlegend: false,
                })}
              />
              <p className="mt-1 text-[11px] text-zinc-500">
                {rows.length} depth bins · mode {mode.bin}× holding {int(mode.count)} sites
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
