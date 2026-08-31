import { useMemo, useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { useLineage } from '../../api/hooks';
import { C } from '../../lib/palette';
import { int } from '../../lib/format';
import { buildGraph, type Edge, type Node } from './graph';

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
  const [hovered, setHovered] = useState<Edge | null>(null);

  return (
    <Exhibit
      title="Lineage — every derived table and what produced it"
      legend={
        <>
          Nodes are datasets, arrows are transforms, and flow reads left to right.{' '}
          <Chip color={C.raw}>delivered object (the raw input; a padlock means its sha256 was verified)</Chip> ·{' '}
          <Chip color={C.machinery}>derived table</Chip>. The number inside a node is its row count. Hover an
          arrow to read the transform and the tool that ran it.
        </>
      }
      reading="Nothing in this app is more than two hops from a hash-verified delivered object. That is the whole point of the diagram: any number on any page can be walked back to bytes whose checksum was confirmed."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(rows) => <GraphSvg rows={rows} hovered={hovered} setHovered={setHovered} />}
      </Loaded>
    </Exhibit>
  );
}

function GraphSvg({
  rows,
  hovered,
  setHovered,
}: {
  rows: Parameters<typeof buildGraph>[0];
  hovered: Edge | null;
  setHovered: (e: Edge | null) => void;
}) {
  const { nodes, edges, levels } = useMemo(() => buildGraph(rows), [rows]);
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
      <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950/60">
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="block">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill={C.inkDim} />
            </marker>
            <marker id="arrowHot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
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
            return (
              <g key={i} onMouseEnter={() => setHovered(e)} onMouseLeave={() => setHovered(null)}>
                <path
                  d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                  fill="none"
                  stroke={hot ? C.decision : C.inkDim}
                  strokeWidth={hot ? 2.2 : 1.2}
                  opacity={hot ? 1 : 0.55}
                  markerEnd={hot ? 'url(#arrowHot)' : 'url(#arrow)'}
                />
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
            const isRaw = n.kind === 'object';
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
                />
                <text x={x(n) + 12} y={y(n) + 22} fill={C.ink} fontSize="12" fontFamily="ui-monospace, monospace">
                  {n.label}
                </text>
                <text x={x(n) + 12} y={y(n) + 38} fill={C.inkDim} fontSize="10">
                  {n.sublabel}
                  {n.verified ? ' · sha256 ✓' : ''}
                </text>
                <text x={x(n) + 12} y={y(n) + 53} fill={isRaw ? C.raw : C.machinery} fontSize="10" fontFamily="ui-monospace, monospace">
                  {n.rows === null ? '' : `${int(n.rows)} rows`}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 min-h-[34px] rounded-lg border border-zinc-800 bg-zinc-900/40 p-2 text-[11px]">
        {hovered ? (
          <>
            <span className="font-mono text-amber-400">{hovered.from.split('/').pop()}</span>
            <span className="text-zinc-500"> → </span>
            <span className="font-mono text-amber-400">{hovered.to}</span>
            <span className="text-zinc-400"> — {hovered.transform}</span>
            <span className="text-zinc-600"> [{hovered.tool}]</span>
          </>
        ) : (
          <span className="text-zinc-600">
            hover an arrow to read its transform · {nodes.length} nodes, {edges.length} edges,{' '}
            {levels} levels
          </span>
        )}
      </div>
    </>
  );
}
