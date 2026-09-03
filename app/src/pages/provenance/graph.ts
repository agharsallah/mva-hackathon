/**
 * Turn the flat lineage rows into a layered directed graph.
 *
 * Each row says "this table was produced from that source by this transform", which is an
 * edge. Levels come from the longest path to a node, so raw inputs sit on the left and
 * everything derived from them moves right — the reading order of a data flow.
 */

import type { LineageRow, ReferenceProvenanceRow } from '../../api/types';

export interface Node {
  id: string;
  label: string;
  sublabel?: string;
  /**
   * `service` is a public reference service the build tools fetch from. It is not a
   * warehouse node: it comes from a client-side join over the provenance manifests, not
   * from `warehouse.data_lineage`.
   */
  kind: 'object' | 'table' | 'service';
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
  /**
   * `manifest` edges are NOT recorded lineage. The warehouse has no edge from a public
   * service to a committed file — the file was fetched, not computed — so these are drawn
   * dotted and labelled so the graph's lineage claims stay literally true.
   */
  kind?: 'lineage' | 'manifest';
}

/** The node every reference service points at. Not a warehouse table. */
export const REFERENCE_SINK = 'reference files + fixtures';

function targetId(r: LineageRow): string {
  return `${r.target_schema}.${r.target_table}`;
}

/** A source_ref may name several objects ("a.gz (8 files)") — keep it as one node. */
function shorten(ref: string): string {
  return clip(ref.split('/').pop() ?? ref, 42);
}

/** Plain truncation — no path-splitting, so a release like `hp/releases/2026-06-23` keeps
 * its prefix instead of collapsing to the date. */
function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
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
    edges.push({ from: sid, to: tid, transform: r.transform, tool: r.tool, kind: 'lineage' });
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

/** `https://rest.ensembl.org/lookup/id` → `rest.ensembl.org`. `file://` inputs are local
 * reads, not services, so they get no node. */
function serviceHost(url: string): string | null {
  if (!url.startsWith('http://') && !url.startsWith('https://')) return null;
  const host = url.slice(url.indexOf('://') + 3).split(/[/?#]/)[0];
  return host === '' ? null : host.toLowerCase();
}

export interface ReferenceJoin {
  /** One per distinct remote input host, sorted; each is a purple raw-input node. */
  services: Array<{ host: string; inputs: string[]; releases: string[] }>;
  /** The single sink the services feed, or null when no manifest has a remote input. */
  sink: { files: number; bytes: number } | null;
}

/**
 * Fold the provenance manifests into "which public services were fetched from, and how
 * many committed files came out". A join done here in the client, on purpose: the
 * warehouse holds no such edge and inventing one in `data_lineage` would be a fabricated
 * lineage row.
 */
export function referenceJoin(rows: ReferenceProvenanceRow[]): ReferenceJoin {
  const byHost = new Map<string, { inputs: Set<string>; releases: Set<string> }>();
  let files = 0;
  let bytes = 0;
  for (const row of rows) {
    let remote = false;
    for (const input of row.inputs) {
      const host = serviceHost(input.url);
      if (host === null) continue;
      remote = true;
      const seen = byHost.get(host) ?? { inputs: new Set(), releases: new Set() };
      seen.inputs.add(input.name);
      if (input.release) seen.releases.add(input.release);
      byHost.set(host, seen);
    }
    if (!remote) continue;
    files += row.outputs.length;
    bytes += row.outputs.reduce((n, o) => n + (o.bytes ?? 0), 0);
  }
  const services = [...byHost.entries()]
    .map(([host, seen]) => ({
      host,
      inputs: [...seen.inputs].sort(),
      releases: [...seen.releases].sort(),
    }))
    .sort((a, b) => a.host.localeCompare(b.host));
  return { services, sink: services.length === 0 ? null : { files, bytes } };
}

/**
 * Append the reference services and their sink to a lineage graph.
 *
 * The services are placed on level 0 beside the delivered objects (both are raw inputs)
 * and the sink one level right of them, so the manifest join reads left-to-right like the
 * rest of the diagram without disturbing any levelled lineage node.
 *
 * Two properties this function owes its caller:
 *
 * - **It returns a new graph.** The nodes it re-slots are copies, so calling it twice on one
 *   graph (a second memo, a test) cannot corrupt the input's `slot` fields.
 * - **`levels` counts the sink.** The sink sits on level 1, so the answer is at least 2 even
 *   when the lineage itself is one level deep — otherwise `LineageGraph`'s `width`
 *   (`PAD * 2 + levels * NODE_W`) is computed too narrow and the sink renders outside the
 *   viewBox.
 */
export function withReferenceServices(
  graph: { nodes: Node[]; edges: Edge[]; levels: number },
  join: ReferenceJoin,
): { nodes: Node[]; edges: Edge[]; levels: number } {
  if (join.sink === null) return graph;
  const services: Node[] = join.services.map((s) => ({
    id: `service:${s.host}`,
    label: s.host,
    // Releases can be a sentence ("per gene — see genes[].latest_version"), which would
    // run past the node box; the manifest table on the same page carries them in full.
    sublabel:
      s.releases.length > 0
        ? `public service · ${clip(s.releases.join(', '), 30)}`
        : 'public service',
    kind: 'service',
    rows: null,
    level: 0,
    slot: 0,
    verified: false,
  }));
  const sink: Node = {
    id: REFERENCE_SINK,
    label: REFERENCE_SINK,
    sublabel: `${join.sink.files} committed files · sha256 in the manifest`,
    kind: 'service',
    // `rows` draws as "N rows" in the SVG; a file count is not a row count, so it stays
    // null and the count sits in the sublabel instead.
    rows: null,
    level: 1,
    slot: 0,
    verified: false,
  };
  const edges: Edge[] = services.map((s) => ({
    from: s.id,
    to: sink.id,
    transform: 'fetched — recorded in a provenance manifest, not in warehouse.data_lineage',
    tool: 'the build tool that wrote the manifest',
    kind: 'manifest',
  }));
  // Copies, never the caller's objects: `slot` is rewritten below.
  const nodes = [...graph.nodes.map((node) => ({ ...node })), ...services, sink];
  const perLevel = new Map<number, number>();
  // Services sort *after* the lineage nodes on their level, so the manifest half of the
  // diagram sits together at the bottom instead of threading dotted edges through it.
  const rank = (n: Node) => (n.kind === 'service' ? 1 : 0);
  const ordered = nodes.sort(
    (a, b) => a.level - b.level || rank(a) - rank(b) || a.label.localeCompare(b.label),
  );
  for (const node of ordered) {
    const slot = perLevel.get(node.level) ?? 0;
    node.slot = slot;
    perLevel.set(node.level, slot + 1);
  }
  return {
    nodes: ordered,
    edges: [...graph.edges, ...edges],
    levels: Math.max(graph.levels, sink.level + 1),
  };
}
