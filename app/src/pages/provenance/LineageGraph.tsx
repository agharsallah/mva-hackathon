import { useMemo, useState } from 'react';

import { useLineage, useReferenceProvenance } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { bytes as fmtBytes, int } from '../../lib/format';
import { C } from '../../lib/palette';
import {
  buildGraph,
  type Edge,
  type Node,
  type ReferenceJoin,
  referenceJoin,
  withReferenceServices,
} from './graph';

const NODE_W = 210;
const NODE_H = 62;
const GAP_X = 120;
const GAP_Y = 26;
const PAD = 16;

/**
 * Lineage as a drawn graph, not a table.
 *
 * Seven rows do not need a graph library — the layout is a longest-path levelling and the
 * render is plain SVG, which keeps the diagram reproducible from source (a repo rule) and
 * adds no dependency. Hovering an edge shows the transform that produced the target.
 */
export function LineageGraph() {
  const q = useLineage();
  // A second endpoint, joined in the client on purpose: the warehouse records no edge from
  // a public service to a committed file, because the file was fetched rather than
  // computed. The dotted "manifest" edges below say so on the diagram itself.
  const ref = useReferenceProvenance();
  const join = useMemo(() => referenceJoin(ref.data?.data ?? []), [ref.data]);
  const [hovered, setHovered] = useState<Edge | null>(null);

  return (
    <Exhibit
      title="Lineage — every derived table and what produced it"
      legend={
        <>
          Nodes are datasets, arrows are transforms, and flow reads left to right.{' '}
          <Chip color={C.raw}>
            delivered object (the raw input; a padlock means its sha256 was verified)
          </Chip>{' '}
          · <Chip color={C.machinery}>derived table</Chip>, joined by solid arrows — each one a row
          the warehouse actually recorded. The number inside a node is its row count.{' '}
          <Chip color={C.raw}>public reference service (dashed)</Chip> nodes and their{' '}
          <strong>dotted, &ldquo;manifest&rdquo;-labelled</strong> arrows are a weaker claim on
          purpose: they are a client-side join over the committed provenance manifests, not a
          lineage edge, because reference data is <em>fetched</em> — there is no upstream table and
          no transform to record.
          {join.sink
            ? ` Those services account for ${join.sink.files} committed files, ${fmtBytes(join.sink.bytes)}.`
            : ''}{' '}
          Hover an arrow to read the transform and the tool that ran it.
        </>
      }
      reading="Nothing in this app is more than two hops from a hash-verified delivered object. That is the whole point of the diagram: any number on any page can be walked back to bytes whose checksum was confirmed. The dotted half says the same thing about the public inputs by a different mechanism — a manifest (URL + release + sha256) rather than a recorded derivation."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(rows) => <GraphSvg rows={rows} join={join} hovered={hovered} setHovered={setHovered} />}
      </Loaded>
    </Exhibit>
  );
}

function GraphSvg({
  rows,
  join,
  hovered,
  setHovered,
}: {
  rows: Parameters<typeof buildGraph>[0];
  join: ReferenceJoin;
  hovered: Edge | null;
  setHovered: (e: Edge | null) => void;
}) {
  const { nodes, edges, levels } = useMemo(
    () => withReferenceServices(buildGraph(rows), join),
    [rows, join],
  );
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const perLevel = useMemo(() => {
    const m = new Map<number, number>();
    for (const n of nodes) m.set(n.level, (m.get(n.level) ?? 0) + 1);
    return m;
  }, [nodes]);

  const maxSlots = Math.max(...[...perLevel.values()]);
  const width = PAD * 2 + levels * NODE_W + (levels - 1) * GAP_X;
  const height = PAD * 2 + maxSlots * NODE_H + (maxSlots - 1) * GAP_Y;

  const x = (n: Node) => PAD + n.level * (NODE_W + GAP_X);
  const y = (n: Node) => {
    const count = perLevel.get(n.level) ?? 1;
    const blockH = count * NODE_H + (count - 1) * GAP_Y;
    return PAD + (height - PAD * 2 - blockH) / 2 + n.slot * (NODE_H + GAP_Y);
  };

  return (
    <>
      <div className="overflow-x-auto rounded-card border border-line bg-chrome-950/60">
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="block">
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 z" fill={C.inkDim} />
            </marker>
            <marker
              id="arrowHot"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="8"
              markerHeight="8"
              orient="auto"
            >
              <path d="M0,0 L10,5 L0,10 z" fill={C.decision} />
            </marker>
          </defs>

          {edges.map((e, i) => {
            const a = byId.get(e.from);
            const b = byId.get(e.to);
            if (!a || !b) return null;
            const x1 = x(a) + NODE_W;
            const y1 = y(a) + NODE_H / 2;
            const x2 = x(b);
            const y2 = y(b) + NODE_H / 2;
            const mid = (x1 + x2) / 2;
            const hot = hovered === e;
            const manifest = e.kind === 'manifest';
            return (
              <g key={i} onMouseEnter={() => setHovered(e)} onMouseLeave={() => setHovered(null)}>
                <path
                  d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke={hot ? C.decision : manifest ? C.raw : C.inkDim}
                  strokeWidth={hot ? 2.2 : 1.2}
                  strokeDasharray={manifest ? '4 4' : undefined}
                  opacity={hot ? 1 : 0.55}
                  markerEnd={hot ? 'url(#arrowHot)' : 'url(#arrow)'}
                />
                {manifest && (
                  <text x={mid} y={(y1 + y2) / 2 - 4} fill={C.raw} fontSize="9" textAnchor="middle">
                    manifest
                  </text>
                )}
                {/* Fat invisible hit area so the thin curve is easy to hover. */}
                <path
                  d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                />
              </g>
            );
          })}

          {nodes.map((n) => {
            // A service node is a raw input too — purple — but dashed, because it is a
            // manifest claim rather than a delivered object the warehouse hashed.
            const isRaw = n.kind === 'object' || n.kind === 'service';
            return (
              <g key={n.id}>
                <rect
                  x={x(n)}
                  y={y(n)}
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill={isRaw ? 'rgba(168,85,247,0.12)' : 'rgba(59,130,246,0.10)'}
                  stroke={isRaw ? C.raw : C.machinery}
                  strokeWidth={1.2}
                  strokeDasharray={n.kind === 'service' ? '4 3' : undefined}
                />
                <text
                  x={x(n) + 12}
                  y={y(n) + 22}
                  fill={C.ink}
                  fontSize="12"
                  fontFamily="ui-monospace, monospace"
                >
                  {n.label}
                </text>
                <text x={x(n) + 12} y={y(n) + 38} fill={C.inkDim} fontSize="10">
                  {n.sublabel}
                  {n.verified ? ' · sha256 ✓' : ''}
                </text>
                <text
                  x={x(n) + 12}
                  y={y(n) + 53}
                  fill={isRaw ? C.raw : C.machinery}
                  fontSize="10"
                  fontFamily="ui-monospace, monospace"
                >
                  {n.rows === null ? '' : `${int(n.rows)} rows`}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 min-h-[34px] rounded-card border border-line bg-panel p-2 text-micro">
        {hovered ? (
          <>
            <span className="font-mono text-decision-400">{hovered.from.split('/').pop()}</span>
            <span className="text-chrome-500"> → </span>
            <span className="font-mono text-decision-400">{hovered.to}</span>
            <span className="text-chrome-400"> — {hovered.transform}</span>
            {hovered.kind === 'manifest' && (
              <span className="ml-1 rounded-pill bg-raw-500/15 px-1 py-px text-raw-300">
                manifest
              </span>
            )}
            <span className="text-chrome-600"> [{hovered.tool}]</span>
          </>
        ) : (
          <span className="text-chrome-600">
            hover an arrow to read its transform · {nodes.length} nodes, {edges.length} edges,{' '}
            {levels} levels · dotted = a provenance manifest, not a lineage edge
          </span>
        )}
      </div>
    </>
  );
}
