import { useCycleQuality } from '../../api/hooks';
import { Toggle } from '../../components/Controls';
import { Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout, scene3d } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec } from '../../lib/format';
import { C, QUALITY_SCALE, SERIES } from '../../lib/palette';
import { useUrlToggle } from '../../lib/urlstate';

/**
 * Per-cycle quality — the third and last honest 3D view.
 *
 * A sequencer reads a fragment one letter per cycle, and confidence decays as the cycles
 * go on. Eight overlaid lines answer "does quality hold up?"; the surface answers
 * "is the decay the same everywhere, or is one partition worse?" — a question with a
 * genuine third axis (partition), which is the only reason 3D is used.
 */
export function CycleQuality() {
  // `cq.3d`, distinct from Flowcell's `fc.3d`: both exhibits sit on the Reads page and each
  // keeps its own 2D/3D choice. See lib/urlstate.
  const [threeD, setThreeD] = useUrlToggle('cq.3d');
  const q = useCycleQuality();
  return (
    <Exhibit
      title="Quality across the read — where confidence decays"
      controls={
        <Toggle on={threeD} onChange={setThreeD}>
          {threeD ? '3D surface' : '2D lines'}
        </Toggle>
      }
      legend={
        <>
          x = sequencing cycle (letter 1 to 149 of the read), y = mean phred quality at that cycle.
          Solid lines are <span style={{ color: SERIES[0] }}>R1</span> partitions, dashed lines are{' '}
          <span style={{ color: SERIES[4] }}>R2</span>; one line per lane. The dashed{' '}
          <span style={{ color: C.good }}>green</span> line at Q30 is the 1-error-in-1000 level. In
          3D: x = cycle, y = partition, z = mean quality, on a{' '}
          <span style={{ color: C.broken }}>red (low)</span> →{' '}
          <span style={{ color: C.good }}>green (high)</span> ramp.
        </>
      }
      reading="R2 decays visibly faster than R1 — the same fragments, read second, after the chemistry has degraded. This is real and it is why R2's Q30 share is 90.0 % against R1's 92.9 %."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={threeD ? 540 : 400}>
        {(rows) => {
          const keys = [...new Set(rows.map((r) => `${r.lane}:${r.read_num}`))].sort();
          const series = keys.map((k) => {
            const [lane, readNum] = k.split(':').map(Number);
            const pts = rows
              .filter((r) => r.lane === lane && r.read_num === readNum)
              .sort((a, b) => a.cycle - b.cycle);
            return { lane, readNum, pts };
          });
          if (threeD) {
            const cycles = [...new Set(rows.map((r) => r.cycle))].sort((a, b) => a - b);
            const z = series.map((s) => s.pts.map((p) => p.mean_q));
            return (
              <>
                <Plot
                  height={520}
                  data={[
                    {
                      type: 'surface',
                      x: cycles,
                      y: series.map((s) => `L${s.lane} R${s.readNum}`),
                      z,
                      colorscale: QUALITY_SCALE,
                      colorbar: {
                        title: { text: 'mean Q', font: { color: C.inkDim, size: 11 } },
                        thickness: 12,
                        len: 0.6,
                        tickfont: { color: C.inkDim, size: 10 },
                        outlinewidth: 0,
                      },
                      hovertemplate: '%{y} @ cycle %{x}<br>mean Q %{z:.2f}<extra></extra>',
                    },
                  ]}
                  layout={baseLayout({
                    margin: { l: 0, r: 0, t: 0, b: 0 },
                    scene: scene3d({
                      xaxis: {
                        title: { text: 'cycle' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      yaxis: {
                        title: { text: 'partition' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      zaxis: {
                        title: { text: 'mean phred' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      camera: { eye: { x: 1.7, y: -1.5, z: 0.85 } },
                      aspectratio: { x: 1.7, y: 1, z: 0.6 },
                    }),
                  })}
                />
                <p className="mt-1 text-[11px] text-zinc-500">
                  drag to rotate · the R2 half of the y axis sits visibly lower at high cycle
                  numbers
                </p>
              </>
            );
          }
          const lastR1 = avg(
            series.filter((s) => s.readNum === 1).map((s) => s.pts[s.pts.length - 1].mean_q),
          );
          const lastR2 = avg(
            series.filter((s) => s.readNum === 2).map((s) => s.pts[s.pts.length - 1].mean_q),
          );
          return (
            <>
              <Plot
                height={380}
                data={series.map((s, i) => ({
                  type: 'scatter',
                  mode: 'lines',
                  name: `L${s.lane} R${s.readNum}`,
                  x: s.pts.map((p) => p.cycle),
                  y: s.pts.map((p) => p.mean_q),
                  line: {
                    color: s.readNum === 1 ? shade(SERIES[0], i) : shade(SERIES[4], i),
                    width: 1.8,
                    dash: s.readNum === 1 ? 'solid' : 'dot',
                  },
                  hovertemplate: `L${s.lane} R${s.readNum}<br>cycle %{x}<br>mean Q %{y:.2f}<extra></extra>`,
                }))}
                layout={baseLayout({
                  margin: { l: 60, r: 16, t: 8, b: 46 },
                  xaxis: {
                    title: {
                      text: 'sequencing cycle (base position in the read)',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: 'mean phred quality', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  shapes: [
                    {
                      type: 'line',
                      xref: 'paper',
                      x0: 0,
                      x1: 1,
                      y0: 30,
                      y1: 30,
                      line: { color: C.good, width: 1.2, dash: 'dash' },
                    },
                  ],
                  annotations: [
                    {
                      xref: 'paper',
                      x: 0.005,
                      y: 30,
                      text: 'Q30 — 1 error in 1000',
                      showarrow: false,
                      xanchor: 'left',
                      yanchor: 'bottom',
                      font: { color: C.good, size: 10 },
                    },
                  ],
                  legend: { orientation: 'h', y: 1.14, x: 0, font: { color: C.inkDim, size: 10 } },
                })}
              />
              <p className="mt-1 text-[11px] text-zinc-500">
                last cycle mean: R1{' '}
                <span className="font-mono text-blue-400">{dec(lastR1, 2)}</span> · R2{' '}
                <span className="font-mono text-purple-400">{dec(lastR2, 2)}</span> — a{' '}
                {dec(lastR1 - lastR2, 2)} phred gap by the end of the read
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}

function avg(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

/** Darken a hex colour progressively so eight lines stay distinguishable. */
function shade(hex: string, i: number): string {
  const f = 1 - (i % 4) * 0.16;
  const n = parseInt(hex.slice(1), 16);
  const r = Math.round(((n >> 16) & 255) * f);
  const g = Math.round(((n >> 8) & 255) * f);
  const b = Math.round((n & 255) * f);
  return `rgb(${r},${g},${b})`;
}
