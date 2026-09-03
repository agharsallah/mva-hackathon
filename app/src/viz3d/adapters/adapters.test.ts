import { describe, expect, it } from 'vitest';

import { DENSITY_SCALE, TONE_MARK } from '../../lib/palette';
import { hexToRgb, sampleScale } from '../core/colorRamp';
import { sceneDatums } from '../spec/datums';
import type { GeometryBuffers, NumericEncoding, PickRange, Scene3D, Vec3 } from '../spec/types';
import { toGeometry } from '.';
import { backboneOwners, RING_SEGMENTS, sampleBackbone, SAMPLES_PER_SEGMENT } from './protein';

const BY_VALUE: NumericEncoding = {
  id: 'v',
  kind: 'numeric',
  label: 'value',
  field: 'value',
  scale: DENSITY_SCALE,
  domain: [0, 10],
  lowMeans: 'low',
  highMeans: 'high',
};

const AXES = {
  x: { label: 'x', unit: 'index' },
  y: { label: 'y', unit: 'index' },
  z: { label: 'z', unit: 'count' },
};

const POINTS: Scene3D = {
  kind: 'points',
  title: 'points',
  axes: AXES,
  color: BY_VALUE,
  points: [
    { id: 'a', label: 'a', at: [0, 0, 0], value: 0 },
    { id: 'b', label: 'b', at: [4, 2, 10], value: 10, meta: { klass: 'hot' } },
    { id: 'c', label: 'c', at: [2, 1, 5], value: 5, tone: 'good' },
  ],
  links: [{ from: 'a', to: 'b', label: '4 index apart' }],
};

const SURFACE: Scene3D = {
  kind: 'surface',
  title: 'surface',
  axes: AXES,
  color: BY_VALUE,
  grid: {
    x: [0, 1, 2],
    y: ['p', 'q'],
    z: [
      [1, null, 3],
      [4, 5, 6],
    ],
  },
};

const KARYOTYPE: Scene3D = {
  kind: 'karyotype',
  title: 'karyotype',
  axes: AXES,
  color: BY_VALUE,
  chromosomes: [
    { name: 'one', length: 100, copies: 2 },
    { name: 'two', length: 60, copies: 3 },
  ],
};

const PROTEIN: Scene3D = {
  kind: 'protein',
  title: 'protein',
  axes: AXES,
  color: BY_VALUE,
  backbone: [
    [0, 0, 0],
    [2, 0, 0],
    [4, 1, 0],
    [6, 1, 1],
  ],
  residues: [
    { id: 'r1', label: 'r1', at: [0, 0, 0], value: 0 },
    { id: 'r2', label: 'r2', at: [4, 1, 0], value: 10 },
  ],
  links: [{ from: 'r1', to: 'r2', label: '7.1 Å' }],
};

/** The contract a raycast depends on: every index has exactly one owner. */
function expectTiles(table: readonly PickRange[], total: number): void {
  const sorted = [...table].sort((a, b) => a.from - b.from);
  expect(sorted[0].from).toBe(0);
  expect(sorted[sorted.length - 1].to).toBe(total);
  sorted.forEach((range, index) => {
    expect(range.to).toBeGreaterThan(range.from);
    if (index > 0) expect(range.from).toBe(sorted[index - 1].to);
  });
}

const vertexCount = (buffers: GeometryBuffers): number => buffers.positions.length / 3;

describe.each([
  ['points', POINTS],
  ['surface', SURFACE],
  ['karyotype', KARYOTYPE],
  ['protein', PROTEIN],
] as const)('%s adapter', (_name, scene) => {
  const buffers = toGeometry(scene);

  it('reports its own kind', () => {
    expect(buffers.kind).toBe(scene.kind);
  });

  it('emits one rgb triple per position', () => {
    expect(buffers.colors.length).toBe(buffers.positions.length);
    expect(buffers.positions.length % 3).toBe(0);
  });

  it('tiles its primary index space with no gap and no overlap', () => {
    expectTiles(buffers.pickTable, vertexCount(buffers));
  });

  it('names only real datum ids in the pick table', () => {
    const ids = new Set(sceneDatums(scene).map((d) => d.id));
    for (const range of buffers.pickTable) expect(ids.has(range.id)).toBe(true);
  });

  it('normalises into a unit box centred on the origin', () => {
    const longest = Math.max(
      ...[0, 1, 2].map((i) => buffers.bounds.max[i] - buffers.bounds.min[i]),
    );
    expect(longest).toBeCloseTo(2, 6);
    [0, 1, 2].forEach((i) => {
      expect(buffers.bounds.min[i] + buffers.bounds.max[i]).toBeCloseTo(0, 6);
    });
  });

  it('keeps the data-space extent for the axis labels', () => {
    const datums = sceneDatums(scene);
    expect(buffers.extent.max[2]).toBeGreaterThanOrEqual(
      Math.max(...datums.map((d) => d.at[2])) - 1e-6,
    );
  });

  it('draws every declared link as one line segment', () => {
    const links = scene.links ?? [];
    if (links.length === 0) return expect(buffers.links).toBeUndefined();
    expect(buffers.links?.positions).toHaveLength(links.length * 6);
    expect(buffers.links?.labels.map((l) => l.text)).toEqual(links.map((l) => l.label));
  });
});

describe('points adapter', () => {
  const buffers = toGeometry(POINTS);

  it('emits one instance per point, with a radius each', () => {
    expect(buffers.draw).toBe('instances');
    expect(vertexCount(buffers)).toBe(3);
    expect(buffers.radii).toHaveLength(3);
  });

  it('colours by the encoded field', () => {
    const want = sampleScale(DENSITY_SCALE, 0);
    [0, 1, 2].forEach((i) => expect(buffers.colors[i]).toBeCloseTo(want[i], 6));
  });

  it('lets an explicit datum tone override the encoding', () => {
    const want = hexToRgb(TONE_MARK.good);
    [0, 1, 2].forEach((i) => expect(buffers.colors[6 + i]).toBeCloseTo(want[i], 6));
  });
});

describe('surface adapter', () => {
  const buffers = toGeometry(SURFACE);

  it('drops an unmeasured cell rather than interpolating across it', () => {
    // 6 grid slots, one null -> 5 cells, 4 vertices and 6 indices each.
    expect(buffers.pickTable).toHaveLength(5);
    expect(vertexCount(buffers)).toBe(20);
    expect(buffers.indices).toHaveLength(30);
  });

  it('gives every vertex an explicit up normal', () => {
    expect(buffers.normals).toHaveLength(60);
    expect(buffers.normals?.[2]).toBe(1);
  });
});

describe('karyotype adapter', () => {
  const buffers = toGeometry(KARYOTYPE);

  it('emits a 24-vertex box per chromosome so each face gets a real normal', () => {
    expect(vertexCount(buffers)).toBe(48);
    expect(buffers.indices).toHaveLength(72);
    expect(buffers.pickTable.map((r) => r.id)).toEqual(['one', 'two']);
  });
});

describe('protein adapter', () => {
  const buffers = toGeometry(PROTEIN);

  it('samples the backbone at a fixed rate, ending on the last atom', () => {
    const centreline = sampleBackbone(PROTEIN.kind === 'protein' ? PROTEIN.backbone : []);
    expect(centreline).toHaveLength((4 - 1) * SAMPLES_PER_SEGMENT + 1);
    expect(centreline[0]).toEqual([0, 0, 0]);
    expect(centreline[centreline.length - 1]).toEqual([6, 1, 1]);
  });

  it('builds a closed tube of rings around it', () => {
    const rings = (4 - 1) * SAMPLES_PER_SEGMENT + 1;
    expect(buffers.draw).toBe('mesh');
    expect(vertexCount(buffers)).toBe(rings * RING_SEGMENTS);
    expect(buffers.indices).toHaveLength((rings - 1) * RING_SEGMENTS * 6);
  });

  it('paints the tube per residue: every range names a residue and the ends differ', () => {
    const ids = buffers.pickTable.map((r) => r.id);
    expect(new Set(ids)).toEqual(new Set(['r1', 'r2']));
    expect(ids[0]).toBe('r1');
    expect(ids[ids.length - 1]).toBe('r2');
    const first = [0, 1, 2].map((i) => buffers.colors[i]);
    const last = [0, 1, 2].map((i) => buffers.colors[buffers.colors.length - 3 + i]);
    expect(first).not.toEqual(last);
  });

  it('adds one instanced sphere per residue, picked in instance index space', () => {
    expect(buffers.instances?.positions).toHaveLength(6);
    expect(buffers.instances?.pickTable).toEqual([
      { id: 'r1', from: 0, to: 1 },
      { id: 'r2', from: 1, to: 2 },
    ]);
  });

  it('survives an empty scene instead of throwing', () => {
    const empty = toGeometry({ ...PROTEIN, kind: 'protein', backbone: [], residues: [] });
    expect(empty.pickTable).toEqual([]);
    expect(empty.positions).toHaveLength(0);
  });
});

/**
 * The O(1) owner derivation replacing the nearest-neighbour scan. The two paths are asserted
 * to agree on a chain where the answer is unambiguous, so the fast path is not just fast.
 */
describe('backboneOwners', () => {
  const backbone: Vec3[] = [
    [0, 0, 0],
    [10, 0, 0],
    [20, 0, 0],
    [30, 0, 0],
  ];
  const centreline = sampleBackbone(backbone);

  it('maps each sample to the nearer atom by arithmetic when the arrays are index-aligned', () => {
    const owners = backboneOwners(centreline, backbone, backbone);
    expect(owners).toHaveLength(centreline.length);
    expect(owners[0]).toBe(0);
    expect(owners[owners.length - 1]).toBe(backbone.length - 1);
    expect(Math.max(...owners)).toBe(backbone.length - 1);
    // Sample k sits at parameter k / SAMPLES_PER_SEGMENT.
    owners.forEach((owner, sample) => {
      expect(owner).toBe(Math.min(Math.round(sample / SAMPLES_PER_SEGMENT), backbone.length - 1));
    });
  });

  it('agrees with the nearest-neighbour scan wherever one atom is strictly nearer', () => {
    const scan = centreline.map((point) => {
      let best = 0;
      backbone.forEach((atom, index) => {
        const here = Math.hypot(point[0] - atom[0], point[1] - atom[1], point[2] - atom[2]);
        const there = Math.hypot(
          point[0] - backbone[best][0],
          point[1] - backbone[best][1],
          point[2] - backbone[best][2],
        );
        if (here < there) best = index;
      });
      return best;
    });
    // The exact midpoint of a segment is a tie: `Math.round` breaks it upward, the scan keeps
    // the first atom it saw. Both name a nearest atom, so only the strict cases are compared.
    const fast = backboneOwners(centreline, backbone, backbone);
    const tie = (sample: number) => sample % SAMPLES_PER_SEGMENT === SAMPLES_PER_SEGMENT / 2;
    const strict = fast.map((owner, sample) => (tie(sample) ? null : owner));
    expect(strict).toEqual(scan.map((owner, sample) => (tie(sample) ? null : owner)));
    expect(strict.filter((o) => o === null)).not.toHaveLength(0);
  });

  it('falls back to the scan when backbone and residues are not index-aligned', () => {
    const residues: Vec3[] = [
      [0, 0, 0],
      [30, 0, 0],
    ];
    const owners = backboneOwners(centreline, backbone, residues);
    expect(new Set(owners)).toEqual(new Set([0, 1]));
    expect(owners[0]).toBe(0);
    expect(owners[owners.length - 1]).toBe(1);
  });
});
