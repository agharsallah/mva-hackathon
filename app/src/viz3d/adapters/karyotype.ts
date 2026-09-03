/**
 * `karyotype` -> one box per chromosome, height = copy number.
 *
 * The third axis is the copy count, which is the only thing that makes this kind worth 3D at
 * all: a genome with every autosome at two copies renders as a flat plate, and that flatness
 * *is* the finding. Bands are not drawn as separate segments — a band is a colour claim about
 * a sub-region, and this kind's job is the copy-number silhouette; use `surface` for banding.
 *
 * Each chromosome owns 24 consecutive vertices (four per cube face, so the lighting gets real
 * per-face normals), so `pickTable` tiles the vertex index space exactly.
 */

import { sceneDatums } from '../spec/datums';
import type { Adapter, GeometryBuffers, PickRange, Scene3D, Vec3 } from '../spec/types';
import { boundsOf, datumColors, linkLines, normaliser } from './normalise';

type KaryotypeScene = Extract<Scene3D, { kind: 'karyotype' }>;

const VERTS_PER_BOX = 24;

/** The six faces as (corner offsets, normal), in unit-cube space. */
const FACES: readonly { corners: readonly Vec3[]; normal: Vec3 }[] = [
  {
    normal: [0, 0, 1],
    corners: [
      [-1, -1, 1],
      [1, -1, 1],
      [1, 1, 1],
      [-1, 1, 1],
    ],
  },
  {
    normal: [0, 0, -1],
    corners: [
      [-1, 1, -1],
      [1, 1, -1],
      [1, -1, -1],
      [-1, -1, -1],
    ],
  },
  {
    normal: [1, 0, 0],
    corners: [
      [1, -1, -1],
      [1, 1, -1],
      [1, 1, 1],
      [1, -1, 1],
    ],
  },
  {
    normal: [-1, 0, 0],
    corners: [
      [-1, -1, 1],
      [-1, 1, 1],
      [-1, 1, -1],
      [-1, -1, -1],
    ],
  },
  {
    normal: [0, 1, 0],
    corners: [
      [-1, 1, 1],
      [1, 1, 1],
      [1, 1, -1],
      [-1, 1, -1],
    ],
  },
  {
    normal: [0, -1, 0],
    corners: [
      [-1, -1, -1],
      [1, -1, -1],
      [1, -1, 1],
      [-1, -1, 1],
    ],
  },
];

export const karyotypeGeometry: Adapter<KaryotypeScene> = (scene): GeometryBuffers => {
  const datums = sceneDatums(scene);
  const unit = normaliser(boundsOf(datums.map((d) => d.at)));
  const colors = datumColors(datums, scene.color);

  const n = datums.length;
  const positions = new Float32Array(n * VERTS_PER_BOX * 3);
  const boxColors = new Float32Array(n * VERTS_PER_BOX * 3);
  const normals = new Float32Array(n * VERTS_PER_BOX * 3);
  const indices = new Uint32Array(n * 36);
  const pickTable: PickRange[] = [];

  scene.chromosomes.forEach((bar, index) => {
    // Half-extents: the full length on x, a thin lane on y, half the copy count on z so the
    // bar stands on the z = 0 plane.
    const half: Vec3 = [
      unit.toUnitLength(bar.length / 2),
      unit.toUnitLength(0.35),
      unit.toUnitLength(bar.copies / 2),
    ];
    const centre = unit.toUnit(datums[index].at);
    let v = index * VERTS_PER_BOX;
    FACES.forEach((face, faceIndex) => {
      face.corners.forEach((corner) => {
        positions.set(
          [
            centre[0] + corner[0] * half[0],
            centre[1] + corner[1] * half[1],
            centre[2] + corner[2] * half[2],
          ],
          v * 3,
        );
        normals.set(face.normal, v * 3);
        boxColors.set(colors.subarray(index * 3, index * 3 + 3), v * 3);
        v++;
      });
      const base = index * VERTS_PER_BOX + faceIndex * 4;
      indices.set([base, base + 1, base + 2, base, base + 2, base + 3], index * 36 + faceIndex * 6);
    });
    pickTable.push({
      id: bar.name,
      from: index * VERTS_PER_BOX,
      to: (index + 1) * VERTS_PER_BOX,
    });
  });

  return {
    kind: 'karyotype',
    draw: 'mesh',
    positions,
    colors: boxColors,
    normals,
    indices,
    pickTable,
    links: linkLines(scene, datums, unit),
    bounds: unit.bounds,
    extent: unit.extent,
  };
};
