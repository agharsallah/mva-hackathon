import { describe, expect, it } from 'vitest';

import { DENSITY_SCALE } from '../../lib/palette';
import { toGeometry } from '../adapters';
import { selectionAt } from '../core/pick';
import { sceneFields } from './datums';
import { describeDatumLine, describeScene, num } from './describe';
import { filterScene, recolour, sceneEncodings } from './filter';
import type { Datum3D, NumericEncoding, Scene3D } from './types';

const BY_VALUE: NumericEncoding = {
  id: 'calls',
  kind: 'numeric',
  label: 'calls per bin',
  field: 'value',
  scale: DENSITY_SCALE,
  lowMeans: 'a quiet bin',
  highMeans: 'a dense bin',
};

const POINTS: Datum3D[] = [
  { id: 'a', label: 'bin a', at: [0, 0, 12], value: 12, meta: { klass: 'cold', reads: 1234567 } },
  {
    id: 'b',
    label: 'bin b',
    at: [1, 0, 4200000],
    value: 4200000,
    meta: { klass: 'hot', reads: 9 },
  },
  { id: 'c', label: 'bin c', at: [2, 1, 7], value: 7, meta: { klass: 'hot', reads: null } },
];

const SCENE: Scene3D = {
  kind: 'points',
  title: 'Calls per bin',
  axes: {
    x: { label: 'megabase', unit: 'Mb' },
    y: { label: 'chromosome', categories: ['one', 'two'] },
    z: { label: 'calls', unit: 'count' },
  },
  color: BY_VALUE,
  encodings: [
    BY_VALUE,
    {
      id: 'klass',
      kind: 'categorical',
      label: 'class',
      field: 'klass',
      tones: { hot: 'broken', cold: 'machinery' },
      means: 'one colour per class',
    },
  ],
  points: POINTS,
  links: [{ from: 'a', to: 'c', label: '2 Mb apart' }],
};

describe('describeScene', () => {
  it('is deterministic — the same scene gives a byte-identical description', () => {
    expect(describeScene(SCENE, ['b'])).toEqual(describeScene(SCENE, ['b']));
  });

  it('reports the kind, the count and every axis with its unit', () => {
    const d = describeScene(SCENE);
    expect(d.kind).toBe('points');
    expect(d.count).toBe(3);
    expect(d.axes.map((a) => a.label)).toEqual(['megabase', 'chromosome', 'calls']);
    expect(d.axes[0].unit).toBe('Mb');
    expect(d.axes[1].categories).toEqual(['one', 'two']);
  });

  it('says what the colour means, not what colour it is', () => {
    const d = describeScene(SCENE);
    expect(d.color.means).toContain('a quiet bin');
    expect(d.text).not.toMatch(/#[0-9a-f]{6}/i);
  });

  it('ranks the extremes and names the highlighted datums', () => {
    const d = describeScene(SCENE, ['c']);
    expect(d.top[0].id).toBe('b');
    expect(d.bottom[0].id).toBe('c');
    expect(d.highlighted.map((h) => h.id)).toEqual(['c']);
    expect(d.text).toContain('Highlighted: bin c');
  });

  it('ignores a highlighted id the scene does not contain', () => {
    expect(describeScene(SCENE, ['nope']).highlighted).toEqual([]);
    expect(describeScene(SCENE, ['nope']).text).toContain('Nothing is highlighted');
  });

  it('renders every declared link with the label the page wrote', () => {
    expect(describeScene(SCENE).links).toEqual(['bin a ↔ bin c (2 Mb apart)']);
  });

  /**
   * The repo's binding rule: no genomic coordinate is ever exported. A coordinate's shape is a
   * bare run of 7+ digits, so every number here is grouped or compacted — this test is the
   * mechanical guard, mirroring `src/test/patient-data.test.ts`.
   */
  it('never emits a bare digit run long enough to be a coordinate', () => {
    const description = describeScene(SCENE, ['b']);
    const text = JSON.stringify(description);
    expect(text).not.toMatch(/\d{7,}/);
    // 4200000 is an integer, so it is grouped ('4,200,000'); a fractional millions value
    // would be compacted to '4.20 M' instead. Either way the digit run stays under seven.
    expect(description.text).toContain('4,200,000');
    expect(num(4200000.5)).toBe('4.20 M');
  });

  it('num() groups, compacts or dashes, and never returns a long run', () => {
    expect(num(1234567)).toBe('1,234,567');
    expect(num(1234567.89)).toBe('1.23 M');
    expect(num(null)).toBe('—');
    expect(num(Infinity)).toBe('—');
    expect(num(12.5)).toBe('12.50');
  });
});

describe('describeDatumLine', () => {
  it('leads with the label and the encoded field, then the other facts', () => {
    const line = describeDatumLine(POINTS[0], 'value');
    expect(line.startsWith('bin a · 12')).toBe(true);
    expect(line).toContain('reads 1,234,567');
  });

  it('writes a null meta field as a dash', () => {
    expect(describeDatumLine(POINTS[2])).toContain('reads —');
  });
});

describe('fields, filtering and recolouring', () => {
  it('classifies value and each meta key from the data', () => {
    const fields = sceneFields(POINTS);
    expect(fields.map((f) => f.name)).toEqual(['value', 'klass', 'reads']);
    expect(fields[1]).toEqual({ name: 'klass', kind: 'categorical', values: ['cold', 'hot'] });
    expect(fields[0].kind).toBe('numeric');
  });

  it('filters a points scene down and leaves the rest of the scene alone', () => {
    const kept = filterScene(SCENE, (d) => d.value < 100);
    expect(kept.kind === 'points' && kept.points.map((p) => p.id)).toEqual(['a', 'c']);
    expect(kept.title).toBe(SCENE.title);
  });

  it('nulls a filtered surface cell instead of dropping a row', () => {
    const grid: Scene3D = {
      ...SCENE,
      kind: 'surface',
      grid: { x: [0, 1], y: ['p'], z: [[1, 9]] },
    };
    const kept = filterScene(grid, (d) => d.value > 5);
    expect(kept.kind === 'surface' && kept.grid.z).toEqual([[null, 9]]);
  });

  /**
   * The trap finding: a protein tube is coloured and picked from `residues[i]` <-> `backbone[i]`,
   * so dropping a residue without dropping its atom paints every later ring in a neighbour's
   * colour and mislabels its pick range.
   */
  it('trims a protein backbone at the same indices as its residues', () => {
    const protein: Scene3D = {
      ...SCENE,
      kind: 'protein',
      backbone: [
        [0, 0, 0],
        [1, 0, 0],
        [2, 0, 0],
      ],
      residues: [
        { id: 'r1', label: 'r1', at: [0, 0, 0], value: 1 },
        { id: 'r2', label: 'r2', at: [1, 0, 0], value: 200 },
        { id: 'r3', label: 'r3', at: [2, 0, 0], value: 3 },
      ],
    };
    const kept = filterScene(protein, (d) => d.value < 100);
    expect(kept.kind === 'protein' && kept.residues.map((r) => r.id)).toEqual(['r1', 'r3']);
    expect(kept.kind === 'protein' && kept.backbone).toEqual([
      [0, 0, 0],
      [2, 0, 0],
    ]);
  });

  it('refuses to trim a protein whose backbone is not index-aligned with its residues', () => {
    const ragged: Scene3D = {
      ...SCENE,
      kind: 'protein',
      backbone: [
        [0, 0, 0],
        [1, 0, 0],
        [2, 0, 0],
      ],
      residues: [
        { id: 'r1', label: 'r1', at: [0, 0, 0], value: 1 },
        { id: 'r3', label: 'r3', at: [2, 0, 0], value: 200 },
      ],
    };
    expect(filterScene(ragged, (d) => d.value < 100)).toBe(ragged);
  });

  it('swaps the active encoding by id and ignores an unknown one', () => {
    expect(recolour(SCENE, 'klass').color.id).toBe('klass');
    expect(recolour(SCENE, 'nope').color.id).toBe('calls');
    expect(sceneEncodings(SCENE).map((e) => e.id)).toEqual(['calls', 'klass']);
  });
});

describe('picking', () => {
  it('resolves an instance index back to the datum the adapter tiled it to', () => {
    const buffers = toGeometry(SCENE);
    expect(selectionAt(SCENE, buffers, 'primary', 1)?.id).toBe('b');
    expect(selectionAt(SCENE, buffers, 'primary', 99)).toBeNull();
    expect(selectionAt(SCENE, buffers, 'instances', 0)).toBeNull();
  });
});
