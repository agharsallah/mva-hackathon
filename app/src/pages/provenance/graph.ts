/**
 * Turn the flat lineage rows into a layered directed graph.
 *
 * Each row says "this table was produced from that source by this transform", which is an
 * edge. Levels come from the longest path to a node, so raw inputs sit on the left and
 * everything derived from them moves right — the reading order of a data flow.
 */

import type { LineageRow } from '../../api/types';

export interface Node {
  id: string;
  label: string;
  sublabel?: string;
  kind: 'object' | 'table';
  rows: number | null;
  level: number;
  /** Index within the level, used for the vertical position. */
  slot: number;
  verified: boolean;
}

export interface Edge {
  from: string;
  to: string;
  transform: string;
  tool: string;
}

function targetId(r: LineageRow): string {
  return `${r.target_schema}.${r.target_table}`;
}

/** A source_ref may name several objects ("a.gz (8 files)") — keep it as one node. */
function shorten(ref: string): string {
  const tail = ref.split('/').pop() ?? ref;
  return tail.length > 42 ? `${tail.slice(0, 39)}…` : tail;
}

export function buildGraph(rows: LineageRow[]): { nodes: Node[]; edges: Edge[]; levels: number } {
  const nodes = new Map<string, Node>();
  const edges: Edge[] = [];

  const put = (id: string, node: Omit<Node, 'level' | 'slot'>) => {
    const existing = nodes.get(id);
    if (existing) {
      // A node can appear as both a target and a source; keep the richer description.
      if (existing.rows === null && node.rows !== null) existing.rows = node.rows;
      return;
    }
    nodes.set(id, { ...node, level: 0, slot: 0 });
  };

  for (const r of rows) {
    const sid = r.source_ref;
    put(sid, {
      id: sid,
      label: shorten(r.source_ref),
      sublabel: r.source_kind === 'object' ? 'delivered object' : 'table',
      kind: r.source_kind === 'object' ? 'object' : 'table',
      rows: null,
      verified: !!r.source_sha256,
    });
    const tid = targetId(r);
    put(tid, {
      id: tid,
      label: r.target_table,
      sublabel: r.target_schema,
      kind: 'table',
      rows: r.target_rows,
      verified: false,
    });
    edges.push({ from: sid, to: tid, transform: r.transform, tool: r.tool });
  }

  // Longest-path levelling. The graph is tiny and acyclic, so iterate to a fixed point.
  const incoming = new Map<string, Edge[]>();
  for (const e of edges) {
    const list = incoming.get(e.to) ?? [];
    list.push(e);
    incoming.set(e.to, list);
  }
  for (let pass = 0; pass < nodes.size + 1; pass++) {
    let changed = false;
    for (const node of nodes.values()) {
      const preds = incoming.get(node.id) ?? [];
      const want = preds.reduce((max, e) => Math.max(max, (nodes.get(e.from)?.level ?? 0) + 1), 0);
      if (want > node.level) {
        node.level = want;
        changed = true;
      }
    }
    if (!changed) break;
  }

  const perLevel = new Map<number, number>();
  const ordered = [...nodes.values()].sort(
    (a, b) => a.level - b.level || a.label.localeCompare(b.label),
  );
  for (const node of ordered) {
    const slot = perLevel.get(node.level) ?? 0;
    node.slot = slot;
    perLevel.set(node.level, slot + 1);
  }

  return { nodes: ordered, edges, levels: Math.max(...ordered.map((n) => n.level), 0) + 1 };
}
