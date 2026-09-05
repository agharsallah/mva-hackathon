/**
 * Where the Track 2 tables came from: the roots they rest on, and the recorded edges.
 *
 * Drawn the same way the submission and warehouse lineage graphs are — levelled nodes,
 * plain SVG, no graph library — because the property that matters is the same: every drug
 * named in the report must be walkable back to a public reply whose digest was recorded.
 */

import { useMemo, useState } from 'react';

import type { Track2Lineage, Track2Source } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { buildTrack2Graph, type GraphEdge, type GraphNode, KIND_ORDER } from './lineageGraph';

const NODE_W = 230;
const NODE_H = 58;
const GAP_X = 110;
const GAP_Y = 18;
const PAD = 14;

/** The repo's colour convention over the source kinds plus the produced tables. */
function strokeOf(kind: string): string {
  if (kind === 'card' || kind === 'submission') return C.raw;
  if (kind === 'output') return C.good;
  return C.machinery;
}

/** A public API is fetched, not derived, so its box is dashed — as on Provenance. */
const dashOf = (kind: string): string | undefined => (kind === 'api' ? '4 3' : undefined);

const shortSha = (sha: string): string => sha.slice(0, 12);

export function Track2LineageView({
  lineage,
  source,
}: {
  lineage: Track2Lineage;
  source?: string;
}) {
  const graph = useMemo(() => buildTrack2Graph(lineage.edges), [lineage.edges]);
  const [hovered, setHovered] = useState<GraphEdge | null>(null);

  const grouped = KIND_ORDER.map((kind) => ({
    kind,
    sources: lineage.sources.filter((s) => s.kind === kind),
  })).filter((g) => g.sources.length > 0);

  return (
    <Exhibit
      title="Lineage — what the Track 2 tables rest on"
      legend={
        <>
          Nodes are datasets, arrows are recorded derivations, flow reads left to right.{' '}
          <Chip color={C.raw}>purple = the raw input</Chip> — the mechanism card and the Track 1
          iteration it was written from, the only things here nobody fetched.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the public APIs; a{' '}
          <strong>dashed</strong> box is fetched rather than derived, so it carries a manifest
          instead of an edge. <Chip color={C.good}>green = the goal</Chip> — the five snapshot
          tables. A <Badge tone="good">sha256</Badge> tag means the digest is recorded; the number
          inside a node is its row count. Hover an arrow for the transform.
        </>
      }
      reading="Two hops separate every drug name in this report from a cached public reply whose digest is recorded — and the mechanism card is a root beside the APIs, which is the structural form of the rule that a candidate is only worth naming if a cited path runs from the allele to its target."
      data={lineage}
      source={source}
    >
      <div className="space-y-3">
        {!lineage.available && (
          <Callout tone="broken" title="Warehouse unreachable — lineage roots from disk only">
            No derivation edge could be read, so the graph below is empty. That is a missing
            measurement, not an absence of lineage: the roots listed underneath come from the five
            provenance manifests on disk and are still true.{' '}
            <span className="font-mono text-micro">{lineage.note}</span>
          </Callout>
        )}

        {graph.nodes.length > 0 ? (
          <GraphSvg graph={graph} hovered={hovered} setHovered={setHovered} />
        ) : (
          lineage.available && (
            <Callout tone="decision" title="No edge recorded yet">
              The warehouse answered and holds no <span className="font-mono">track2</span>{' '}
              derivation edge. Record one with{' '}
              <span className="font-mono">mva-drugs snapshot --record-lineage</span>.{' '}
              <span className="font-mono text-micro">{lineage.note}</span>
            </Callout>
          )
        )}

        <div className="grid gap-3 lg:grid-cols-2">
          {grouped.map((g) => (
            <div key={g.kind} className={cx(WELL, 'space-y-2')}>
              <h4 className="flex items-baseline gap-2 text-xs font-semibold text-chrome-200">
                <span
                  aria-hidden
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{ background: strokeOf(g.kind) }}
                />
                {g.kind}
                <span className="font-mono text-micro text-chrome-600">
                  {g.sources.length} source{g.sources.length === 1 ? '' : 's'}
                </span>
              </h4>
              <ul className="space-y-2">
                {g.sources.map((s) => (
                  <SourceItem key={`${s.kind}:${s.ref}`} source={s} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </Exhibit>
  );
}

function SourceItem({ source }: { source: Track2Source }) {
  return (
    <li className="space-y-0.5">
      <div className="font-mono text-xs break-all text-chrome-100">{source.ref}</div>
      <div className="flex flex-wrap items-center gap-2 text-micro text-chrome-500">
        {source.version && <span className="font-mono">{source.version}</span>}
        {source.sha256 && (
          <Badge tone="good" title={source.sha256}>
            sha256 {shortSha(source.sha256)}
          </Badge>
        )}
      </div>
      <p className="text-micro leading-relaxed text-chrome-400">{source.note}</p>
    </li>
  );
}

function GraphSvg({
  graph,
  hovered,
  setHovered,
}: {
  graph: ReturnType<typeof buildTrack2Graph>;
  hovered: GraphEdge | null;
  setHovered: (e: GraphEdge | null) => void;
}) {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const perLevel = new Map<number, number>();
  for (const n of graph.nodes) perLevel.set(n.level, (perLevel.get(n.level) ?? 0) + 1);
  const maxSlots = Math.max(...perLevel.values());
  const width = PAD * 2 + graph.levels * NODE_W + (graph.levels - 1) * GAP_X;
  const height = PAD * 2 + maxSlots * NODE_H + (maxSlots - 1) * GAP_Y;

  const x = (n: GraphNode) => PAD + n.level * (NODE_W + GAP_X);
  const y = (n: GraphNode) => {
    const count = perLevel.get(n.level) ?? 1;
    const block = count * NODE_H + (count - 1) * GAP_Y;
    return PAD + (height - PAD * 2 - block) / 2 + n.slot * (NODE_H + GAP_Y);
  };

  return (
    <>
      <div className="overflow-x-auto rounded-card border border-line bg-chrome-950/60">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width={width}
          height={height}
          className="block"
          role="img"
          aria-label={`${graph.nodes.length} datasets joined by ${graph.edges.length} recorded derivations`}
        >
          <defs>
            <marker
              id="track2-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 z" fill={C.inkDim} />
            </marker>
          </defs>

          {graph.edges.map((e, i) => {
            const a = byId.get(e.from);
            const b = byId.get(e.to);
            if (!a || !b) return null;
            const x1 = x(a) + NODE_W;
            const y1 = y(a) + NODE_H / 2;
            const x2 = x(b);
            const y2 = y(b) + NODE_H / 2;
            const mid = (x1 + x2) / 2;
            const hot = hovered === e;
            const d = `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
            return (
              <g key={i} onMouseEnter={() => setHovered(e)} onMouseLeave={() => setHovered(null)}>
                <path
                  d={d}
                  fill="none"
                  stroke={hot ? C.decision : C.inkDim}
                  strokeWidth={hot ? 2.2 : 1.2}
                  opacity={hot ? 1 : 0.55}
                  markerEnd="url(#track2-arrow)"
                />
                <path d={d} fill="none" stroke="transparent" strokeWidth={14} />
              </g>
            );
          })}

          {graph.nodes.map((n) => (
            <g key={n.id}>
              <rect
                x={x(n)}
                y={y(n)}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill={C.panel}
                stroke={strokeOf(n.kind)}
                strokeDasharray={dashOf(n.kind)}
                strokeWidth={1.2}
              />
              <text
                x={x(n) + 12}
                y={y(n) + 22}
                fill={C.ink}
                fontSize="12"
                fontFamily="ui-monospace, monospace"
              >
                {n.label.length > 28 ? `${n.label.slice(0, 27)}…` : n.label}
              </text>
              <text x={x(n) + 12} y={y(n) + 38} fill={C.inkDim} fontSize="10">
                {n.sublabel}
                {n.verified ? ' · sha256 ✓' : ''}
              </text>
              <text
                x={x(n) + 12}
                y={y(n) + 51}
                fill={strokeOf(n.kind)}
                fontSize="10"
                fontFamily="ui-monospace, monospace"
              >
                {n.rows === null ? n.kind : `${int(n.rows)} rows`}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="min-h-[34px] rounded-card border border-line bg-panel p-2 text-micro">
        {hovered ? (
          <>
            <span className="font-mono text-decision-400">{hovered.from}</span>
            <span className="text-chrome-500"> → </span>
            <span className="font-mono text-decision-400">{hovered.to}</span>
            <span className="text-chrome-400"> — {hovered.transform}</span>
            <span className="text-chrome-600"> [{hovered.tool}]</span>
          </>
        ) : (
          <span className="text-chrome-600">
            hover an arrow to read its transform · {graph.nodes.length} nodes, {graph.edges.length}{' '}
            edges, {graph.levels} levels
          </span>
        )}
      </div>
    </>
  );
}
