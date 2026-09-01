import { useMemo } from 'react';

import { useFlowcell } from '../../api/hooks';
import type { FlowcellBinRow } from '../../api/types';
import { Select, Toggle } from '../../components/Controls';
import { Exhibit } from '../../components/Exhibit';
import { baseLayout, Plot, scene3d } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { int } from '../../lib/format';
import { C, DENSITY_SCALE } from '../../lib/palette';
import { useUrlNumber, useUrlToggle } from '../../lib/urlstate';

const LANE_VALUES = [1, 2, 3, 4];
const READ_VALUES = [1, 2];
const LANES = LANE_VALUES.map((v) => ({ value: v, label: `lane ${v}` }));
const READS = READ_VALUES.map((v) => ({ value: v, label: `R${v}` }));

/** Collapse the tile dimension: sum over tiles to get one occupancy map. */
function surfaceMatrix(rows: FlowcellBinRow[]) {
  const xs = [...new Set(rows.map((r) => r.xb))].sort((a, b) => a - b);
  const ys = [...new Set(rows.map((r) => r.yb))].sort((a, b) => a - b);
  const xi = new Map(xs.map((v, i) => [v, i]));
  const yi = new Map(ys.map((v, i) => [v, i]));
  const z = ys.map(() => Array(xs.length).fill(0) as number[]);
  for (const r of rows) {
    const i = yi.get(r.yb);
    const j = xi.get(r.xb);
    if (i !== undefined && j !== undefined) z[i][j] += r.n;
  }
  return { xs, ys, z };
}

/**
 * Flowcell occupancy — the second of three honest 3D views.
 *
 * A read is not just a sequence: it has a physical address on the sequencer's glass. The
 * 2D map sums over tiles and shows where clusters formed; the 3D scatter keeps the tile
 * axis, which is what reveals whether a defect is one tile or the whole surface. That
 * third axis is real data, not decoration.
 */
export function Flowcell() {
  // `?fc.lane=3&fc.read=2&fc.3d=1` names one flowcell view exactly. See lib/urlstate.
  const [lane, setLane] = useUrlNumber('fc.lane', 1, LANE_VALUES);
  const [read, setRead] = useUrlNumber('fc.read', 1, READ_VALUES);
  const [threeD, setThreeD] = useUrlToggle('fc.3d');
  const q = useFlowcell(lane, read, 0);

  const cap = 6000; // 3D scatter stays interactive up to a few thousand markers
  const legend = useMemo(
    () => (
      <>
        Each cell is a 1000 × 1000 pixel patch of the flowcell surface. Colour follows the number of
        reads whose cluster centre falls in that patch, on a dark →{' '}
        <span style={{ color: '#1d4ed8' }}>blue</span> →{' '}
        <span style={{ color: '#a855f7' }}>purple</span> ramp (purple = densest). In 3D the tile
        axis is kept: x and y are surface coordinates, z is the tile number, and marker size and
        colour are the read count — so a bad tile shows up as one horizontal plane, a bad edge as a
        wall.
      </>
    ),
    [],
  );

  return (
    <Exhibit
      title="Flowcell occupancy — where on the glass the reads came from"
      controls={
        <>
          <Select value={lane} options={LANES} onChange={setLane} label="lane" />
          <Select value={read} options={READS} onChange={setRead} label="read" />
          <Toggle on={threeD} onChange={setThreeD}>
            {threeD ? '3D by tile' : '2D map'}
          </Toggle>
          <span className="text-[11px] text-zinc-600">one shard · live ≈2.5 s</span>
        </>
      }
      legend={legend}
      reading="Occupancy is even across the surface with a mild edge falloff — the normal pattern. A hot spot, a dead tile or a bright edge would mean a fraction of the reads are instrument artefacts rather than DNA."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={threeD ? 560 : 440}>
        {(rows) => {
          if (rows.length === 0)
            return <p className="p-6 text-center text-sm text-zinc-500">no bins returned</p>;
          const tiles = new Set(rows.map((r) => r.tile));
          const totalReads = rows.reduce((a, r) => a + r.n, 0);
          if (threeD) {
            const sample =
              rows.length > cap
                ? rows.filter((_, i) => i % Math.ceil(rows.length / cap) === 0)
                : rows;
            return (
              <>
                <Plot
                  height={540}
                  data={[
                    {
                      type: 'scatter3d',
                      mode: 'markers',
                      x: sample.map((r) => r.xb),
                      y: sample.map((r) => r.yb),
                      z: sample.map((r) => r.tile),
                      marker: {
                        size: 2.6,
                        color: sample.map((r) => r.n),
                        colorscale: DENSITY_SCALE,
                        opacity: 0.75,
                        colorbar: {
                          title: { text: 'reads', font: { color: C.inkDim, size: 11 } },
                          thickness: 12,
                          len: 0.6,
                          tickfont: { color: C.inkDim, size: 10 },
                          outlinewidth: 0,
                        },
                      },
                      hovertemplate:
                        'tile %{z}<br>x-bin %{x}, y-bin %{y}<br>%{marker.color:,} reads<extra></extra>',
                    },
                  ]}
                  layout={baseLayout({
                    margin: { l: 0, r: 0, t: 0, b: 0 },
                    scene: scene3d({
                      xaxis: {
                        title: { text: 'x bin (×1000 px)' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      yaxis: {
                        title: { text: 'y bin (×1000 px)' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      zaxis: {
                        title: { text: 'tile' },
                        gridcolor: C.grid,
                        tickfont: { color: C.inkDim, size: 10 },
                      },
                      camera: { eye: { x: 1.6, y: -1.6, z: 0.8 } },
                    }),
                  })}
                />
                <p className="mt-1 text-[11px] text-zinc-500">
                  drag to rotate · {int(sample.length)} of {int(rows.length)} bins plotted,{' '}
                  {tiles.size} tiles
                </p>
              </>
            );
          }
          const { xs, ys, z } = surfaceMatrix(rows);
          return (
            <>
              <Plot
                height={420}
                data={[
                  {
                    type: 'heatmap',
                    x: xs,
                    y: ys,
                    z,
                    colorscale: DENSITY_SCALE,
                    colorbar: {
                      title: { text: 'reads', font: { color: C.inkDim, size: 11 } },
                      thickness: 12,
                      len: 0.85,
                      tickfont: { color: C.inkDim, size: 10 },
                      outlinewidth: 0,
                    },
                    hovertemplate:
                      'x-bin %{x}, y-bin %{y}<br>%{z:,} reads (all tiles)<extra></extra>',
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 52, r: 10, t: 8, b: 44 },
                  xaxis: {
                    title: {
                      text: 'x position on the flowcell (×1000 px)',
                      font: { color: C.inkDim, size: 12 },
                    },
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 10 },
                  },
                  yaxis: {
                    title: { text: 'y position (×1000 px)', font: { color: C.inkDim, size: 12 } },
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 10 },
                  },
                })}
              />
              <p className="mt-1 text-[11px] text-zinc-500">
                lane {lane} R{read}, shard 0 · {tiles.size} tiles · {int(rows.length)} bins ·{' '}
                {int(totalReads)} reads placed
              </p>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
