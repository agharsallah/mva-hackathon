/**
 * `protein` -> a smooth tube through the backbone, plus one sphere per residue datum.
 *
 * Why 3D genuinely earns its place here: a 1D residue axis (the domain lollipop) answers
 * "which domain", but two questions a sequence axis cannot see — are two marked residues
 * *spatially adjacent*, and does a residue sit on a partner interface — need the fold.
 *
 * The curve is sampled here, in plain TypeScript, rather than by `three.CatmullRomCurve3`:
 * the per-residue colour and the pick ranges are the part that must be correct, and keeping
 * them out of three is what makes them unit-testable. three only ever sees buffers.
 */

import { sceneDatums } from '../spec/datums';
import type { Adapter, GeometryBuffers, PickRange, Scene3D, Vec3 } from '../spec/types';
import {
  boundsOf,
  datumColors,
  linkLines,
  type Normaliser,
  normaliser,
  tilePickTable,
} from './normalise';

type ProteinScene = Extract<Scene3D, { kind: 'protein' }>;

/** Curve samples per backbone segment, and vertices per tube ring. */
export const SAMPLES_PER_SEGMENT = 6;
export const RING_SEGMENTS = 8;
/** Tube radius and residue-sphere radius, in unit-box units. */
const TUBE_RADIUS = 0.02;
const RESIDUE_RADIUS = 0.05;

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a: Vec3, b: Vec3): number => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const scale = (a: Vec3, k: number): Vec3 => [a[0] * k, a[1] * k, a[2] * k];

function unitVector(a: Vec3, fallback: Vec3 = [0, 0, 1]): Vec3 {
  const length = Math.hypot(a[0], a[1], a[2]);
  return length < 1e-9 ? fallback : scale(a, 1 / length);
}

/** Uniform Catmull–Rom, the same basis `three.CatmullRomCurve3` uses at `curveType: 'catmullrom'`. */
function catmullRom(p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, t: number): Vec3 {
  const t2 = t * t;
  const t3 = t2 * t;
  return [0, 1, 2].map(
    (i) =>
      0.5 *
      (2 * p1[i] +
        (-p0[i] + p2[i]) * t +
        (2 * p0[i] - 5 * p1[i] + 4 * p2[i] - p3[i]) * t2 +
        (-p0[i] + 3 * p1[i] - 3 * p2[i] + p3[i]) * t3),
  ) as unknown as Vec3;
}

/**
 * The centreline: `SAMPLES_PER_SEGMENT` points per backbone segment plus the final point.
 * Exported because it is the piece worth asserting on directly.
 */
export function sampleBackbone(
  backbone: readonly Vec3[],
  perSegment = SAMPLES_PER_SEGMENT,
): Vec3[] {
  if (backbone.length === 0) return [];
  if (backbone.length === 1) return [backbone[0]];
  const out: Vec3[] = [];
  const at = (i: number): Vec3 => backbone[Math.min(Math.max(i, 0), backbone.length - 1)];
  for (let i = 0; i < backbone.length - 1; i++) {
    for (let s = 0; s < perSegment; s++) {
      out.push(catmullRom(at(i - 1), at(i), at(i + 1), at(i + 2), s / perSegment));
    }
  }
  out.push(backbone[backbone.length - 1]);
  return out;
}

/** Parallel-transported frames, so the tube does not twist between rings. */
function frames(centreline: readonly Vec3[]): { tangent: Vec3; normal: Vec3; binormal: Vec3 }[] {
  if (centreline.length === 0) return [];
  const tangents = centreline.map((_, i) => {
    const next = centreline[Math.min(i + 1, centreline.length - 1)];
    const prev = centreline[Math.max(i - 1, 0)];
    return unitVector(sub(next, prev));
  });
  let normal = unitVector(cross(tangents[0], [0, 0, 1]), unitVector(cross(tangents[0], [0, 1, 0])));
  return tangents.map((tangent) => {
    // Project the previous normal onto the plane perpendicular to this tangent.
    normal = unitVector(sub(normal, scale(tangent, dot(normal, tangent))), normal);
    return { tangent, normal, binormal: unitVector(cross(tangent, normal)) };
  });
}

/**
 * Which residue owns each centreline sample — the tube's per-ring colour and its pick ranges.
 *
 * The fast path is arithmetic, not a search. `sampleBackbone` emits `perSegment` points for
 * backbone atom `i`, covering the curve parameter range `[i, i+1)`, then the final atom, so
 * sample `k` sits at parameter `k / perSegment` and its nearer atom is `round(k / perSegment)`.
 * A `protein` scene's `backbone[i]` *is* `residues[i]`'s Cα — the index alignment
 * `spec/filter.ts` preserves when it trims — so that atom index is the residue index.
 *
 * The scan it replaces was O(samples x residues): for a 1,050-residue chain that is 6,295 x
 * 1,050 ~= 6.6 M distance evaluations, each allocating a `Vec3`, redone on every recolour and
 * every filter toggle.
 *
 * A scene whose two arrays are *not* index-aligned carries no such mapping (nothing says which
 * residue an atom belongs to), so it keeps the nearest-neighbour scan and stays correct.
 */
export function backboneOwners(
  centreline: readonly Vec3[],
  backbone: readonly Vec3[],
  residues: readonly Vec3[],
  perSegment = SAMPLES_PER_SEGMENT,
): number[] {
  if (backbone.length !== residues.length || residues.length === 0) {
    return nearestResidue(centreline, residues);
  }
  const last = residues.length - 1;
  return centreline.map((_, sample) => Math.min(Math.round(sample / perSegment), last));
}

/** Index of the residue nearest each centreline sample, in data space. O(n x m). */
function nearestResidue(centreline: readonly Vec3[], residues: readonly Vec3[]): number[] {
  return centreline.map((point) => {
    let best = 0;
    let bestDistance = Infinity;
    residues.forEach((residue, index) => {
      const d = sub(point, residue);
      const distance = dot(d, d);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = index;
      }
    });
    return best;
  });
}

function tubePickTable(
  owners: readonly number[],
  ids: readonly string[],
  ringSegments: number,
): PickRange[] {
  const out: PickRange[] = [];
  if (ids.length === 0) return out;
  owners.forEach((owner, ring) => {
    const last = out[out.length - 1];
    if (last && last.id === ids[owner]) last.to = (ring + 1) * ringSegments;
    else out.push({ id: ids[owner], from: ring * ringSegments, to: (ring + 1) * ringSegments });
  });
  return out;
}

function buildTube(
  centreline: readonly Vec3[],
  unit: Normaliser,
  colors: Float32Array,
  owners: readonly number[],
): Pick<GeometryBuffers, 'positions' | 'colors' | 'normals' | 'indices'> {
  const rings = centreline.length;
  const count = rings * RING_SEGMENTS;
  const positions = new Float32Array(count * 3);
  const normals = new Float32Array(count * 3);
  const tubeColors = new Float32Array(count * 3);
  const indices = new Uint32Array(Math.max(rings - 1, 0) * RING_SEGMENTS * 6);
  const frame = frames(centreline);

  centreline.forEach((point, ring) => {
    const centre = unit.toUnit(point);
    const { normal, binormal } = frame[ring];
    for (let j = 0; j < RING_SEGMENTS; j++) {
      const angle = (j / RING_SEGMENTS) * Math.PI * 2;
      const radial: Vec3 = [
        normal[0] * Math.cos(angle) + binormal[0] * Math.sin(angle),
        normal[1] * Math.cos(angle) + binormal[1] * Math.sin(angle),
        normal[2] * Math.cos(angle) + binormal[2] * Math.sin(angle),
      ];
      const v = ring * RING_SEGMENTS + j;
      positions.set(
        [
          centre[0] + radial[0] * TUBE_RADIUS,
          centre[1] + radial[1] * TUBE_RADIUS,
          centre[2] + radial[2] * TUBE_RADIUS,
        ],
        v * 3,
      );
      normals.set(radial, v * 3);
      tubeColors.set(colors.subarray(owners[ring] * 3, owners[ring] * 3 + 3), v * 3);
    }
  });

  for (let ring = 0; ring < rings - 1; ring++) {
    for (let j = 0; j < RING_SEGMENTS; j++) {
      const j2 = (j + 1) % RING_SEGMENTS;
      const a = ring * RING_SEGMENTS + j;
      const b = ring * RING_SEGMENTS + j2;
      const c = (ring + 1) * RING_SEGMENTS + j2;
      const d = (ring + 1) * RING_SEGMENTS + j;
      indices.set([a, b, c, a, c, d], (ring * RING_SEGMENTS + j) * 6);
    }
  }
  return { positions, colors: tubeColors, normals, indices };
}

export const proteinGeometry: Adapter<ProteinScene> = (scene): GeometryBuffers => {
  const residues = sceneDatums(scene);
  const unit = normaliser(boundsOf([...scene.backbone, ...residues.map((d) => d.at)]));
  const colors = datumColors(residues, scene.color);
  const centreline = sampleBackbone(scene.backbone);
  const owners = backboneOwners(
    centreline,
    scene.backbone,
    residues.map((d) => d.at),
  );
  const tube = buildTube(centreline, unit, colors, owners);

  const spherePositions = new Float32Array(residues.length * 3);
  const radii = new Float32Array(residues.length);
  residues.forEach((datum, index) => {
    spherePositions.set(unit.toUnit(datum.at), index * 3);
    radii[index] = (scene.radius === undefined ? RESIDUE_RADIUS : scene.radius) * (datum.size ?? 1);
  });

  return {
    kind: 'protein',
    draw: 'mesh',
    ...tube,
    pickTable: tubePickTable(
      owners,
      residues.map((d) => d.id),
      RING_SEGMENTS,
    ),
    instances: {
      positions: spherePositions,
      colors,
      radii,
      pickTable: tilePickTable(residues),
    },
    links: linkLines(scene, residues, unit),
    bounds: unit.bounds,
    extent: unit.extent,
  };
};
