/**
 * The Track 2 lineage edges, laid out as a layered graph.
 *
 * Same approach as `pages/submissions/lineageGraph.ts` and `pages/provenance/graph.ts` —
 * longest-path levelling, then plain SVG, no graph library, so the diagram is reproducible
 * from its own source. It is a local copy rather than a shared function because the shapes
 * differ: a submission fans *in* to one folder, whereas Track 2 fans *out* — one mechanism
 * card and a handful of public APIs produce five tables, and the target set is itself a
 * source for three of them. So this one has real intermediate nodes and needs levelling,
 * which the submission version deliberately does not.
 */

import type { Track2LineageEdge } from '../../api/types';

/** The source kinds, in the order the diagram stacks them. */
export const KIND_ORDER = ['card', 'submission', 'api', 'table'] as const;

export interface GraphNode {
  id: string;
  label: string;
  sublabel: string;
  kind: string;
  rows: number | null;
  level: number;
  slot: number;
  verified: boolean;
}

export interface GraphEdge {
  from: string;
  to: string;
  transform: string;
  tool: string;
  notes: string;
}

export interface Track2Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  levels: number;
}

const rank = (kind: string): number => {
  const i = (KIND_ORDER as readonly string[]).indexOf(kind);
  return i === -1 ? KIND_ORDER.length : i;
};

/** `https://api.platform.opentargets.org/api/v4/graphql` → `api.platform.opentargets.org`. */
function shortRef(ref: string): string {
  if (ref.startsWith('http')) {
    const match = /^https?:\/\/([^/]+)/.exec(ref);
    if (match) return match[1]!;
  }
  const parts = ref.split('/');
  return parts.length > 2 ? parts.slice(-2).join('/') : ref;
}

/**
 * Build the graph. A node's level is the longest path to it, so a table that is itself a
 * source (`track2.targets`) sits one column right of the roots and one left of the tables
 * derived from it.
 *
 * Returns an empty graph for an empty edge list — the caller renders the "warehouse
 * unreachable" notice rather than an empty box, so this never invents a node.
 */
export function buildTrack2Graph(edges: Track2LineageEdge[]): Track2Graph {
  if (edges.length === 0) return { nodes: [], edges: [], levels: 0 };

  const nodes = new Map<string, GraphNode>();
  const out: GraphEdge[] = [];
  const targetId = (e: Track2LineageEdge) => `${e.target_schema}.${e.target_table}`;

  for (const e of edges) {
    const tid = targetId(e);
    if (!nodes.has(e.source_ref)) {
      nodes.set(e.source_ref, {
        id: e.source_ref,
        label: shortRef(e.source_ref),
        sublabel: e.source_version || e.source_kind,
        kind: e.source_kind,
        rows: null,
        level: 0,
        slot: 0,
        verified: !!e.source_sha256,
      });
    }
    const existing = nodes.get(tid);
    if (existing) {
      // A node that is both a source and a target (`track2.targets`) keeps its row count.
      existing.rows = e.target_rows;
      existing.kind = 'output';
    } else {
      nodes.set(tid, {
        id: tid,
        label: e.target_table,
        sublabel: e.target_schema,
        kind: 'output',
        rows: e.target_rows,
        level: 1,
        slot: 0,
        verified: false,
      });
    }
    out.push({
      from: e.source_ref,
      to: tid,
      transform: e.transform,
      tool: e.tool,
      notes: e.notes,
    });
  }

  // Longest-path levelling: repeat until nothing moves. The edge count here is tens, so
  // the naive fixed point is cheaper than building an index.
  for (let pass = 0; pass < nodes.size; pass++) {
    let moved = false;
    for (const e of out) {
      const from = nodes.get(e.from)!;
      const to = nodes.get(e.to)!;
      if (to.level <= from.level) {
        to.level = from.level + 1;
        moved = true;
      }
    }
    if (!moved) break;
  }

  const ordered = [...nodes.values()].sort(
    (a, b) => a.level - b.level || rank(a.kind) - rank(b.kind) || a.label.localeCompare(b.label),
  );
  const perLevel = new Map<number, number>();
  for (const node of ordered) {
    const slot = perLevel.get(node.level) ?? 0;
    node.slot = slot;
    perLevel.set(node.level, slot + 1);
  }

  return { nodes: ordered, edges: out, levels: Math.max(...ordered.map((n) => n.level)) + 1 };
}
