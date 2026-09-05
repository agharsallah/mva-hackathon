/**
 * The lineage edges of one iteration, laid out as a layered graph.
 *
 * Same approach as `pages/provenance/graph.ts` — longest-path levelling, then plain SVG,
 * no graph library, so the diagram stays reproducible from its own source. It is a
 * separate function rather than a shared one because the shapes differ: a submission's
 * edges all point at a single target (`submissions/<track>/iteration-<n>`), so the graph is
 * a fan-in whose left column is the roots this answer rests on, and the node's label is a
 * source *kind* rather than a schema.
 */

import type { SubmissionLineageEdge } from '../../api/types';

/** The five root kinds, in the order the diagram stacks them. */
export const KIND_ORDER = ['raw', 'clinical', 'reference', 'table', 'file'] as const;

export interface GraphNode {
  id: string;
  label: string;
  sublabel: string;
  /** `submission` is the single sink; every other node is one of the source kinds. */
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

export interface SubmissionGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  levels: number;
}

/** `submissions/track1/iteration-1` → `track1/iteration-1`; a table keeps its full name. */
function tail(ref: string): string {
  const parts = ref.split('/');
  return parts.length > 2 ? parts.slice(-2).join('/') : ref;
}

const rank = (kind: string): number => {
  const i = (KIND_ORDER as readonly string[]).indexOf(kind);
  return i === -1 ? KIND_ORDER.length : i;
};

/**
 * Build the graph. Sources sit on level 0 ordered by kind (raw first, the way the repo's
 * colour convention reads), the submission on level 1.
 *
 * Returns an empty graph for an empty edge list — the caller renders the "database
 * unreachable" notice rather than an empty box, which is why this never invents a node.
 */
export function buildSubmissionGraph(edges: SubmissionLineageEdge[]): SubmissionGraph {
  if (edges.length === 0) return { nodes: [], edges: [], levels: 0 };

  const nodes = new Map<string, GraphNode>();
  const out: GraphEdge[] = [];

  for (const e of edges) {
    if (!nodes.has(e.source_ref)) {
      nodes.set(e.source_ref, {
        id: e.source_ref,
        label: tail(e.source_ref),
        sublabel: e.source_version || e.source_kind,
        kind: e.source_kind,
        rows: null,
        level: 0,
        slot: 0,
        verified: !!e.source_sha256,
      });
    }
    const targetId = `${e.target_schema}/${e.target_table}`;
    if (!nodes.has(targetId)) {
      nodes.set(targetId, {
        id: targetId,
        label: e.target_table,
        sublabel: e.target_schema,
        kind: 'submission',
        rows: e.target_rows,
        level: 1,
        slot: 0,
        verified: false,
      });
    }
    out.push({
      from: e.source_ref,
      to: targetId,
      transform: e.transform,
      tool: e.tool,
      notes: e.notes,
    });
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

  return {
    nodes: ordered,
    edges: out,
    levels: Math.max(...ordered.map((n) => n.level)) + 1,
  };
}
