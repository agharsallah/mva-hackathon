import type { Step6Edge, Step6Route } from '../../../api/types';
import { Exhibit } from '../../../components/Exhibit';
import { DEFAULT_GEOMETRY, edgePath, layout, type Placed } from '../../../lib/graphLayout';
import { C } from '../../../lib/palette';

/**
 * The route-dependency graph: who read whose output, and which raw inputs two routes share.
 *
 * **Not a lineage view.** The three lineage panels draw datasets and the transformations
 * between them; this draws *instruments* and what they consumed, and the edge that matters
 * most here — two routes reading the same raw source — is not a transformation at all. It
 * shares `lib/graphLayout`, which is the arithmetic those panels already share, and nothing
 * else.
 *
 * A dashed edge is a shared input. Those are the edges the independent-evidence count
 * collapses, and seeing them is the only way a reader can tell four routes agreeing from
 * one witness answering four times.
 */

const GEOMETRY = { ...DEFAULT_GEOMETRY, nodeWidth: 190, nodeHeight: 52, gapX: 130, gapY: 22 };

type Node = Placed & { id: string; label: string; sub: string; kind: 'input' | 'route' };

function build(routes: Step6Route[], edges: Step6Edge[]): Node[] {
  const routeNames = new Set(routes.map((row) => row.route));
  const inputs = [...new Set(edges.map((e) => e.source).filter((s) => !routeNames.has(s)))].sort();

  const nodes: Node[] = inputs.map((id, slot) => ({
    id,
    label: id,
    sub: 'raw input',
    kind: 'input',
    level: 0,
    slot,
  }));
  routes.forEach((row, slot) => {
    nodes.push({
      id: row.route,
      label: row.route,
      sub: row.admitted ? `ranks ${row.unit}s` : 'weight 0',
      kind: 'route',
      level: 1,
      slot,
    });
  });
  return nodes;
}

export function RouteGraph({
  routes,
  edges,
  source,
  cachedAt,
  origin,
}: {
  routes: Step6Route[];
  edges: Step6Edge[];
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const nodes = build(routes, edges);
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const place = layout(nodes, 2, GEOMETRY);
  const admitted = new Map(routes.map((row) => [row.route, row.admitted]));
  const shared = edges.filter((edge) => edge.shared_input);

  const toneOf = (node: Node) => {
    if (node.kind === 'input') return C.raw;
    return admitted.get(node.id) ? C.good : C.broken;
  };

  return (
    <Exhibit
      title="Which route read what, and where two of them read the same thing"
      reading={`${shared.length} of ${edges.length} edges are a shared raw input. Routes joined by one are not independent witnesses, however separately they were built.`}
      legend={
        <>
          <span style={{ color: C.raw }}>■</span> raw input ·{' '}
          <span style={{ color: C.good }}>■</span> a route entitled to rank ·{' '}
          <span style={{ color: C.broken }}>■</span> a route measured to order nothing, carried at
          weight 0. A <strong>dashed</strong> edge is a raw source two routes share — collapsed by
          the independent-evidence count. A <strong>solid</strong> edge is one route consuming
          another&rsquo;s output. Hover an edge for what was consumed.
        </>
      }
      source={source}
      cachedAt={cachedAt}
      origin={origin}
      data={{ routes, edges }}
    >
      <div className="overflow-x-auto">
        <svg
          width={place.width}
          height={place.height}
          viewBox={`0 0 ${place.width} ${place.height}`}
          role="img"
          aria-label="Route dependency graph"
        >
          <g fill="none">
            {edges.map((edge) => {
              const from = byId.get(edge.source);
              const to = byId.get(edge.target);
              if (!from || !to) return null;
              // A route-to-route edge runs inside one column, so the shared cubic would
              // collapse to a point. It is drawn as an arc above the column instead.
              const sameLevel = from.level === to.level;
              const path = sameLevel ? arc(from, to, place) : edgePath(from, to, place, GEOMETRY);
              return (
                <path
                  key={`${edge.source}->${edge.target}`}
                  d={path}
                  stroke={edge.shared_input ? C.decision : C.machinery}
                  strokeWidth={edge.shared_input ? 2 : 1.4}
                  strokeDasharray={edge.shared_input ? '5 4' : undefined}
                  opacity={0.85}
                >
                  <title>{`${edge.source} → ${edge.target}: ${edge.consumed}`}</title>
                </path>
              );
            })}
          </g>
          {nodes.map((node) => (
            <g key={node.id} transform={`translate(${place.x(node)}, ${place.y(node)})`}>
              <rect
                width={GEOMETRY.nodeWidth}
                height={GEOMETRY.nodeHeight}
                rx={6}
                fill={C.panel}
                stroke={toneOf(node)}
                strokeWidth={1.5}
              />
              <text x={12} y={21} fill={toneOf(node)} fontSize={13} fontWeight={600}>
                {node.label}
              </text>
              <text x={12} y={39} fill={C.inkDim} fontSize={11}>
                {node.sub}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </Exhibit>
  );
}

/** An edge between two nodes in the same column, drawn as an arc clear of the boxes. */
function arc(from: Node, to: Node, place: ReturnType<typeof layout>): string {
  const x = place.x(from) + GEOMETRY.nodeWidth;
  const y1 = place.y(from) + GEOMETRY.nodeHeight / 2;
  const y2 = place.y(to) + GEOMETRY.nodeHeight / 2;
  const bulge = x + 46;
  return `M${x},${y1} C${bulge},${y1} ${bulge},${y2} ${x},${y2}`;
}
