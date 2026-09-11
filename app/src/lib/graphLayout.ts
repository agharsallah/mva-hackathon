/**
 * Levelled layout for a small directed graph, shared by every lineage view.
 *
 * The three lineage panels (`provenance`, `submissions`, `track2`) each hand-rolled the
 * same arithmetic with different constants, and a fourth caller was about to. The maths is
 * tiny and identical: nodes carry a level and a slot, levels march left to right, and each
 * level is centred vertically against the tallest one.
 *
 * Geometry is a parameter rather than a constant because the three panels genuinely differ
 * — a node showing a file path needs more width than one showing a table name.
 */

/** What the layout needs from a node; callers carry whatever else they render. */
export interface Placed {
  level: number;
  slot: number;
}

export interface Geometry {
  nodeWidth: number;
  nodeHeight: number;
  gapX: number;
  gapY: number;
  pad: number;
}

export const DEFAULT_GEOMETRY: Geometry = {
  nodeWidth: 240,
  nodeHeight: 58,
  gapX: 120,
  gapY: 18,
  pad: 14,
};

export interface Layout {
  width: number;
  height: number;
  /** Left edge of a node's box. */
  x: (node: Placed) => number;
  /** Top edge of a node's box. */
  y: (node: Placed) => number;
}

/**
 * Place `nodes` across `levels` columns.
 *
 * An empty graph still produces a valid (if tiny) canvas rather than `NaN` dimensions from
 * `Math.max()` over nothing — a lineage view with no recorded edges is a real state, and it
 * renders as an empty box rather than a broken one.
 */
export function layout(
  nodes: Placed[],
  levels: number,
  geometry: Geometry = DEFAULT_GEOMETRY,
): Layout {
  const { nodeWidth, nodeHeight, gapX, gapY, pad } = geometry;
  const perLevel = new Map<number, number>();
  for (const node of nodes) perLevel.set(node.level, (perLevel.get(node.level) ?? 0) + 1);
  const maxSlots = perLevel.size > 0 ? Math.max(...perLevel.values()) : 0;
  const columns = Math.max(levels, 1);

  const width = pad * 2 + columns * nodeWidth + (columns - 1) * gapX;
  const height = pad * 2 + Math.max(maxSlots, 1) * nodeHeight + (Math.max(maxSlots, 1) - 1) * gapY;

  return {
    width,
    height,
    x: (node) => pad + node.level * (nodeWidth + gapX),
    y: (node) => {
      const count = perLevel.get(node.level) ?? 1;
      const block = count * nodeHeight + (count - 1) * gapY;
      return pad + (height - pad * 2 - block) / 2 + node.slot * (nodeHeight + gapY);
    },
  };
}

/** The cubic the lineage views draw between two boxes: out of the right edge, into the left. */
export function edgePath(
  from: Placed,
  to: Placed,
  place: Layout,
  geometry: Geometry = DEFAULT_GEOMETRY,
): string {
  const x1 = place.x(from) + geometry.nodeWidth;
  const y1 = place.y(from) + geometry.nodeHeight / 2;
  const x2 = place.x(to);
  const y2 = place.y(to) + geometry.nodeHeight / 2;
  const mid = (x1 + x2) / 2;
  return `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
}
