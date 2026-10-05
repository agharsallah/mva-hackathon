/**
 * `surface` -> one raised quad per measured grid cell (a stepped heightfield, not a smoothed
 * sheet).
 *
 * Why quads and not an interpolated mesh: the data a `SurfaceGrid` carries in this repo is
 * *binned* — events per bin, mean quality per cycle. A smooth surface would invent values
 * between bins and imply a continuity the measurement does not have. A cell with `z === null`
 * is dropped entirely rather than interpolated across, so "not measured" reads as a hole.
 *
 * Each cell owns exactly four consecutive vertices, so `pickTable` tiles the vertex index
 * space with no gap and no overlap.
 */

import { sceneDatums } from '../spec/datums';
import type { Adapter, GeometryBuffers, PickRange, Scene3D } from '../spec/types';
import { boundsOf, datumColors, linkLines, normaliser } from './normalise';

type SurfaceScene = Extract<Scene3D, { kind: 'surface' }>;

const VERTS_PER_CELL = 4;

export const surfaceGeometry: Adapter<SurfaceScene> = (scene): GeometryBuffers => {
  const datums = sceneDatums(scene);
  const unit = normaliser(boundsOf(datums.map((d) => d.at)));
  const colors = datumColors(datums, scene.color);

  const xs = scene.grid.x;
  const halfX = unit.toUnitLength(xs.length > 1 ? Math.abs(xs[1] - xs[0]) / 2 : 0.5);
  const halfY = unit.toUnitLength(0.5);

  const positions = new Float32Array(datums.length * VERTS_PER_CELL * 3);
  const cellColors = new Float32Array(datums.length * VERTS_PER_CELL * 3);
  const normals = new Float32Array(datums.length * VERTS_PER_CELL * 3);
  const indices = new Uint32Array(datums.length * 6);
  const pickTable: PickRange[] = [];

  datums.forEach((datum, cell) => {
    const [cx, cy, cz] = unit.toUnit(datum.at);
    const corners = [
      [cx - halfX, cy - halfY, cz],
      [cx + halfX, cy - halfY, cz],
      [cx + halfX, cy + halfY, cz],
      [cx - halfX, cy + halfY, cz],
    ];
    corners.forEach((corner, corner_index) => {
      const v = cell * VERTS_PER_CELL + corner_index;
      positions.set(corner, v * 3);
      // z is up in this module's convention, so every cell's face normal is +z.
      normals.set([0, 0, 1], v * 3);
      cellColors.set(colors.subarray(cell * 3, cell * 3 + 3), v * 3);
    });
    const base = cell * VERTS_PER_CELL;
    indices.set([base, base + 1, base + 2, base, base + 2, base + 3], cell * 6);
    pickTable.push({ id: datum.id, from: base, to: base + VERTS_PER_CELL });
  });

  return {
    kind: 'surface',
    draw: 'mesh',
    positions,
    colors: cellColors,
    normals,
    indices,
    pickTable,
    links: linkLines(scene, datums, unit),
    bounds: unit.bounds,
    extent: unit.extent,
  };
};
