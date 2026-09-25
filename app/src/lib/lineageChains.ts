/**
 * A large lineage, split into the chains a reader can follow one at a time.
 *
 * The ledger grows by whole chains: iteration 4 recorded `it4.*` and a second case
 * recorded `transfer.BLM.*`, and drawn together they are one column of a hundred boxes.
 * Each chain is read off the edge's own target name — nothing here knows an iteration:
 *
 * - `transfer.<case>.<table>` → `transfer.<case>` (one chain per transfer case),
 * - `<prefix>.<table>` → `<prefix>` (e.g. `it4`),
 * - a bare table name → its schema (`track2`, `results`, `submissions`).
 *
 * A chain carries its own edges **plus every edge reached by walking back** through the
 * tables they name as sources, so a chain is always drawn down to its roots. A chain whose
 * every edge is already reached from another one (the Track 1 tables a Track 2 chain rests
 * on) is not offered on its own: it is part of each chain that walks into it.
 */

import { useMemo } from 'react';

import { useUrlState } from './urlstate';

/** The edge fields the split needs; both lineage payloads carry at least these. */
export interface ChainEdge {
  produced_at: string;
  target_schema: string;
  target_table: string;
  source_ref: string;
}

export interface Chain<E extends ChainEdge> {
  id: string;
  /** The chain's own edges, then the ones reached by walking back. */
  edges: E[];
  /** How many of `edges` were recorded for this chain, not reached from it. */
  own: number;
  /** The newest `produced_at` among its own edges. */
  newest: string;
  /** A transfer case: the same pipeline run on another disease. */
  transfer: boolean;
}

/** Above this many edges one diagram stops being readable, so the view offers chains. */
export const SPLIT_ABOVE = 60;

export const TRANSFER_PREFIX = 'transfer.';

export function chainOf(edge: ChainEdge): string {
  const table = edge.target_table;
  if (table.startsWith(TRANSFER_PREFIX)) {
    const parts = table.split('.');
    return parts.length > 2 ? `${parts[0]}.${parts[1]}` : table;
  }
  const dot = table.indexOf('.');
  return dot > 0 ? table.slice(0, dot) : edge.target_schema;
}

/** The two names an edge's target answers to, as the API's walk indexes them. */
const targetKeys = (e: ChainEdge): string[] => [
  `${e.target_schema}.${e.target_table}`,
  e.target_table,
];

/** Every edge reachable from `seed` by following `source_ref` back to a recorded target. */
function closure<E extends ChainEdge>(seed: E[], byTarget: Map<string, E[]>): E[] {
  const out = [...seed];
  const seen = new Set(out);
  const visited = new Set<string>();
  const frontier = seed.map((e) => e.source_ref);
  while (frontier.length > 0) {
    const ref = frontier.pop()!;
    if (visited.has(ref)) continue;
    visited.add(ref);
    for (const edge of byTarget.get(ref) ?? []) {
      if (seen.has(edge)) continue;
      seen.add(edge);
      out.push(edge);
      frontier.push(edge.source_ref);
    }
  }
  return out;
}

/**
 * The chains of `edges`, the proband's own first (newest first), transfer cases after.
 * Returns one chain per prefix even for a small lineage; the view decides whether to split.
 */
export function splitChains<E extends ChainEdge>(edges: E[]): Chain<E>[] {
  const byTarget = new Map<string, E[]>();
  const groups = new Map<string, E[]>();
  for (const edge of edges) {
    for (const key of targetKeys(edge)) byTarget.set(key, [...(byTarget.get(key) ?? []), edge]);
    const id = chainOf(edge);
    groups.set(id, [...(groups.get(id) ?? []), edge]);
  }

  const chains = [...groups.entries()].map(([id, own]) => ({
    id,
    edges: closure(own, byTarget),
    own: own.length,
    newest: own.reduce((a, e) => (e.produced_at > a ? e.produced_at : a), ''),
    transfer: id.startsWith(TRANSFER_PREFIX),
  }));

  // Drop a chain whose every edge another chain already walks into.
  const listed = chains.filter((c) => {
    const others = new Set(chains.filter((o) => o !== c).flatMap((o) => o.edges));
    return groups.get(c.id)!.some((e) => !others.has(e));
  });

  // A cycle could leave every chain reached from another; then offer them all.
  return (listed.length > 0 ? listed : chains).sort(
    (a, b) =>
      Number(a.transfer) - Number(b.transfer) ||
      b.newest.localeCompare(a.newest) ||
      a.id.localeCompare(b.id),
  );
}

/** The picker's value for "every chain in one diagram". */
export const ALL_CHAINS = 'all';

export interface ChainView<E extends ChainEdge> {
  /** Empty when the lineage is small enough to draw whole; the picker is then hidden. */
  chains: Chain<E>[];
  picked: string;
  setPicked: (id: string) => void;
  /** The edges to draw for the current pick. */
  edges: E[];
}

/**
 * Which chain to draw, held in the URL (`?chain=it4`) so one address cites one diagram.
 * A lineage at or under {@link SPLIT_ABOVE} edges is drawn whole and offers no picker.
 */
export function useChainView<E extends ChainEdge>(edges: E[]): ChainView<E> {
  const chains = useMemo(() => (edges.length > SPLIT_ABOVE ? splitChains(edges) : []), [edges]);
  const ids = useMemo(() => [...chains.map((c) => c.id), ALL_CHAINS], [chains]);
  const [picked, setPicked] = useUrlState('chain', chains[0]?.id ?? ALL_CHAINS, ids);
  const chain = chains.find((c) => c.id === picked);
  return { chains, picked, setPicked, edges: chain ? chain.edges : edges };
}

/**
 * The roots a chain's diagram rests on: every source one of its edges names, plus every
 * source no edge names at all (a claim read off disk, such as the clinical document), which
 * belongs to whichever chain is shown.
 */
export function sourcesFor<S extends { ref: string }>(
  sources: S[],
  all: ChainEdge[],
  shown: ChainEdge[],
): S[] {
  if (shown === all) return sources;
  const named = new Set(all.map((e) => e.source_ref));
  const drawn = new Set(shown.map((e) => e.source_ref));
  return sources.filter((s) => drawn.has(s.ref) || !named.has(s.ref));
}
