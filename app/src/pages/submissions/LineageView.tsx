import { useMemo, useState } from 'react';

import type { LineageSource, SubmissionLineage } from '../../api/types';
import { Badge } from '../../components/Badge';
import { ChainPicker } from '../../components/ChainPicker';
import { Toggle } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { int } from '../../lib/format';
import { clipLabel, edgePath, type Geometry, layout } from '../../lib/graphLayout';
import { sourcesFor, useChainView } from '../../lib/lineageChains';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { useUrlToggle } from '../../lib/urlstate';
import { shortSha } from './iteration';
import {
  buildSubmissionGraph,
  FOLD_ROOTS_ABOVE,
  foldRoots,
  type GraphEdge,
  type GraphNode,
  KIND_ORDER,
} from './lineageGraph';

/**
 * Where this submission came from: the roots it rests on, and the recorded edges that
 * connect them to the folder.
 *
 * The graph is drawn the same way `pages/provenance/LineageGraph` draws the warehouse's —
 * levelled nodes, plain SVG, no graph library — because the property that matters is the
 * same one: every claim must be walkable back to bytes whose checksum was confirmed.
 */

/** Wider boxes than the warehouse view: a submission node shows a file path, not a table. */
const GEOMETRY: Geometry = { nodeWidth: 250, nodeHeight: 58, gapX: 130, gapY: 18, pad: 14 };
const { nodeWidth: NODE_W, nodeHeight: NODE_H } = GEOMETRY;

/** The repo's colour convention, applied to the source kinds plus the sink. */
function strokeOf(kind: string): string {
  if (kind === 'raw' || kind === 'clinical' || kind === 'card') return C.raw;
  if (kind === 'submission') return C.good;
  return C.machinery;
}

/** Reference inputs and public APIs are fetched, not derived: dashed, like on Provenance. */
const dashOf = (kind: string): string | undefined =>
  kind === 'reference' || kind === 'api' ? '4 3' : undefined;

export function LineageView({ lineage, source }: { lineage: SubmissionLineage; source?: string }) {
  const view = useChainView(lineage.edges);
  const full = useMemo(() => buildSubmissionGraph(view.edges), [view.edges]);
  // A big chain folds its roots by kind; the reader can unfold them. The roots stay listed
  // below either way, so folding hides boxes, never records.
  const [unfold, setUnfold] = useUrlToggle('lin.roots');
  const rootCount = full.nodes.filter((n) => n.level === 0).length;
  const foldable = rootCount > FOLD_ROOTS_ABOVE;
  const graph = useMemo(() => (unfold ? full : foldRoots(full)), [full, unfold]);
  const [hovered, setHovered] = useState<GraphEdge | null>(null);
  const grouped = groupByKind(sourcesFor(lineage.sources, lineage.edges, view.edges));

  return (
    <Exhibit
      title="Lineage — what this submission rests on"
      legend={
        <>
          Nodes are datasets, arrows are recorded derivations, and flow reads left to right.{' '}
          <Chip color={C.raw}>purple = the raw input</Chip> — the delivered callset, the clinical
          document and a mechanism card, the things nobody here fetched or computed.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — warehouse result tables and
          committed or downloaded files; a <strong>dashed</strong> box is public reference data or a
          public API, fetched rather than derived, so it carries a manifest instead of an edge.{' '}
          <Chip color={C.good}>green = the goal</Chip> — the iteration folder itself. A padlock-free{' '}
          <Badge tone="good">sha256</Badge> tag means the digest is recorded; the number inside a
          node is its row count; a box reading <em>n file roots</em> is several roots of one kind
          folded together. Hover an arrow for the transform and the tool that ran it.
        </>
      }
      reading={reading(full)}
      data={lineage}
      source={source}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <ChainPicker view={view} total={lineage.edges.length} />
          {foldable && (
            <Toggle on={unfold} onChange={setUnfold}>
              {unfold ? `showing all ${rootCount} roots` : `show all ${rootCount} roots`}
            </Toggle>
          )}
        </div>
        {foldable && !unfold && (
          <p className="text-micro text-chrome-400">
            {rootCount} roots are folded into one box per kind so the derivations stay readable;
            every root is still listed under the graph.
          </p>
        )}
        {!lineage.available && (
          <Callout tone="broken" title="Database unreachable — lineage roots from disk only">
            The warehouse could not be reached, so no derivation edge could be read and the graph
            below is empty. That is a missing measurement, not an absence of lineage: the roots
            listed underneath were read off disk and are still true.{' '}
            <span className="font-mono text-micro">{lineage.note}</span>
          </Callout>
        )}

        {graph.nodes.length > 0 ? (
          <GraphSvg graph={graph} hovered={hovered} setHovered={setHovered} />
        ) : (
          lineage.available && (
            <Callout tone="decision" title="No edge recorded yet">
              The warehouse answered, and holds no derivation edge for this iteration. Record one
              with <span className="font-mono">resolve_submission_spec.py --record-lineage</span>.{' '}
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

/** Sources grouped by kind: the known kinds in diagram order, then any other kind by name. */
function groupByKind(sources: LineageSource[]) {
  const known = KIND_ORDER as readonly string[];
  const extra = [...new Set(sources.map((s) => s.kind))].filter((k) => !known.includes(k)).sort();
  return [...known, ...extra]
    .map((kind) => ({ kind, sources: sources.filter((s) => s.kind === kind) }))
    .filter((g) => g.sources.length > 0);
}

/** The exhibit's reading, counted off the diagram drawn rather than typed. */
function reading(graph: ReturnType<typeof buildSubmissionGraph>): string {
  if (graph.nodes.length === 0) {
    return 'No derivation edge to read: the roots below are the ones knowable from disk.';
  }
  const roots = graph.nodes.filter((n) => n.level === 0);
  const hops = graph.levels - 1;
  const sink = graph.nodes.some((n) => n.kind === 'submission');
  const kinds = new Set(roots.map((n) => n.kind));
  const both = kinds.has('clinical') && kinds.has('raw');
  return (
    `${roots.length} roots, at most ${hops} recorded hop${hops === 1 ? '' : 's'} from ` +
    `${sink ? 'the folder the organisers would receive' : 'the tables this iteration argues from'}` +
    (both
      ? ' — and the clinical document is a root beside the callset, the structural form of the rule that both data sources are cross-referenced.'
      : '. Every root is named with the version and digest the recorder read.')
  );
}

function SourceItem({ source }: { source: LineageSource }) {
  return (
    <li className="space-y-0.5">
      <div className="font-mono text-xs break-all text-chrome-100">{source.ref}</div>
      <div className="flex flex-wrap items-center gap-2 text-micro text-chrome-400">
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
  graph: ReturnType<typeof buildSubmissionGraph>;
  hovered: GraphEdge | null;
  setHovered: (e: GraphEdge | null) => void;
}) {
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const place = layout(graph.nodes, graph.levels, GEOMETRY);
  const { width, height } = place;
  const x = (n: GraphNode) => place.x(n);
  const y = (n: GraphNode) => place.y(n);

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
              id="sub-arrow"
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
            const hot = hovered === e;
            const d = edgePath(a, b, place, GEOMETRY);
            return (
              <g key={i} onMouseEnter={() => setHovered(e)} onMouseLeave={() => setHovered(null)}>
                <path
                  d={d}
                  fill="none"
                  stroke={hot ? C.decision : C.inkDim}
                  strokeWidth={hot ? 2.2 : 1.2}
                  opacity={hot ? 1 : 0.55}
                  markerEnd="url(#sub-arrow)"
                />
                <path d={d} fill="none" stroke="transparent" strokeWidth={14} />
              </g>
            );
          })}

          {graph.nodes.map((n) => (
            <g key={n.id}>
              <title>{`${n.id} — ${n.sublabel}`}</title>
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
                {clipLabel(n.label, 30)}
              </text>
              <text x={x(n) + 12} y={y(n) + 38} fill={C.inkDim} fontSize="10">
                {clipLabel(n.sublabel, n.verified ? 23 : 34)}
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
            <span className="font-mono text-decision-300">{hovered.from}</span>
            <span className="text-chrome-400"> → </span>
            <span className="font-mono text-decision-300">{hovered.to}</span>
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
