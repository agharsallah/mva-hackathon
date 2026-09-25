/**
 * The lineage edges of one iteration, laid out as a layered graph.
 *
 * Same approach as `pages/provenance/graph.ts` — longest-path levelling
 * (`lib/graphLayout.ts`), then plain SVG, no graph library, so the diagram stays reproducible
 * from its own source. A scored iteration is mostly a fan-in to its folder
 * (`submissions/<track>/iteration-<n>`); a panel-judged one has no folder edge and walks from
 * the tables its entries recorded, so both shapes go through the same levelling. A node's
 * label is a source *kind* rather than a schema.
 */

import type { SubmissionLineageEdge } from '../../api/types';
import { assignSlots, levelLongestPath } from '../../lib/graphLayout';

/** The root kinds, in the order the diagram stacks them; an unlisted kind sorts last. */
export const KIND_ORDER = [
  'raw',
  'clinical',
  'card',
  'reference',
  'file',
  'api',
  'derived',
  'table',
] as const;

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
 * Build the graph. Roots sit on level 0 ordered by kind (raw first, the way the repo's colour
 * convention reads); every derived table sits one column right of its deepest source, and
 * the iteration folder — a target in schema `submissions` — is the green sink.
 *
 * A table that is both a target and a source is one node, whichever spelling the source
 * used (`results.gene_biallelic`, or a bare `track1/iteration-1`), so a walked chain draws
 * as a chain rather than as two disconnected fans.
 *
 * Returns an empty graph for an empty edge list — the caller renders the "database
 * unreachable" notice rather than an empty box, which is why this never invents a node.
 */
export function buildSubmissionGraph(edges: SubmissionLineageEdge[]): SubmissionGraph {
  if (edges.length === 0) return { nodes: [], edges: [], levels: 0 };

  const nodes = new Map<string, GraphNode>();
  const out: GraphEdge[] = [];
  const targetId = (e: SubmissionLineageEdge) => `${e.target_schema}.${e.target_table}`;
  const bare = new Map(edges.map((e) => [e.target_table, targetId(e)]));
  const sourceId = (ref: string) => (bare.has(ref) && !ref.includes('.') ? bare.get(ref)! : ref);
  const sinkKind = (e: SubmissionLineageEdge) =>
    e.target_schema === 'submissions' ? 'submission' : 'table';

  for (const e of edges) {
    const sid = sourceId(e.source_ref);
    if (!nodes.has(sid)) {
      nodes.set(sid, {
        id: sid,
        label: tail(e.source_ref),
        sublabel: e.source_version || e.source_kind,
        kind: e.source_kind,
        rows: null,
        level: 0,
        slot: 0,
        verified: !!e.source_sha256,
      });
    }
    const tid = targetId(e);
    const existing = nodes.get(tid);
    if (existing) {
      existing.rows = e.target_rows;
      existing.kind = sinkKind(e);
      existing.label = e.target_table;
    } else {
      nodes.set(tid, {
        id: tid,
        label: e.target_table,
        sublabel: e.target_schema,
        kind: sinkKind(e),
        rows: e.target_rows,
        level: 1,
        slot: 0,
        verified: false,
      });
    }
    out.push({
      from: sid,
      to: tid,
      transform: e.transform,
      tool: e.tool,
      notes: e.notes,
    });
  }

  const levels = levelLongestPath(nodes, out);
  const ordered = [...nodes.values()].sort(
    (a, b) => a.level - b.level || rank(a.kind) - rank(b.kind) || a.label.localeCompare(b.label),
  );
  assignSlots(ordered);

  return { nodes: ordered, edges: out, levels };
}
