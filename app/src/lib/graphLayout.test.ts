import { describe, expect, it } from 'vitest';

import { DEFAULT_GEOMETRY, edgePath, layout } from './graphLayout';

const G = DEFAULT_GEOMETRY;

describe('levelled graph layout', () => {
  it('marches levels left to right by one node plus one gap', () => {
    const place = layout(
      [
        { level: 0, slot: 0 },
        { level: 1, slot: 0 },
      ],
      2,
    );
    expect(place.x({ level: 1, slot: 0 }) - place.x({ level: 0, slot: 0 })).toBe(
      G.nodeWidth + G.gapX,
    );
  });

  it('centres a short column against the tallest one', () => {
    const nodes = [
      { level: 0, slot: 0 },
      { level: 1, slot: 0 },
      { level: 1, slot: 1 },
      { level: 1, slot: 2 },
    ];
    const place = layout(nodes, 2);
    const tall = place.y({ level: 1, slot: 1 });
    const lone = place.y({ level: 0, slot: 0 });
    expect(lone).toBeCloseTo(tall, 5);
  });

  it('sizes the canvas to the widest column', () => {
    const place = layout(
      [
        { level: 0, slot: 0 },
        { level: 0, slot: 1 },
      ],
      1,
    );
    expect(place.height).toBe(G.pad * 2 + 2 * G.nodeHeight + G.gapY);
  });

  it('gives an empty graph a real canvas rather than NaN', () => {
    const place = layout([], 0);
    expect(Number.isFinite(place.width)).toBe(true);
    expect(Number.isFinite(place.height)).toBe(true);
  });

  it('draws an edge out of the right edge and into the left', () => {
    const from = { level: 0, slot: 0 };
    const to = { level: 1, slot: 0 };
    const place = layout([from, to], 2);
    const d = edgePath(from, to, place);
    expect(d.startsWith(`M${place.x(from) + G.nodeWidth},`)).toBe(true);
    expect(d).toContain(`${place.x(to)},`);
  });
});
