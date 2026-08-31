import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';

/**
 * The method loop, drawn rather than described: claim → predict → test → verdict → revise.
 *
 * Inline SVG, no dependency. It is the same loop `docs/method.md` renders in Mermaid; this
 * is the browser's copy of it, and the colours are the repo's palette so the page reads
 * the same way every other exhibit does.
 */

interface Station {
  x: number;
  label: string;
  sub: string;
  fill: string;
  stroke: string;
}

const W = 132;
const H = 62;
const Y = 34;
const GAP = 42;

const STATIONS: Station[] = [
  { x: 8, label: 'Claim', sub: 'falsifiable, registered', fill: '#1e3a8a55', stroke: C.machinery },
  { x: 8 + (W + GAP), label: 'Predict', sub: 'what we should see', fill: '#1e3a8a55', stroke: C.machinery },
  { x: 8 + 2 * (W + GAP), label: 'Test', sub: 'an executed run', fill: '#1e3a8a55', stroke: C.machinery },
  { x: 8 + 3 * (W + GAP), label: 'Verdict', sub: 'the evidence weighed', fill: '#78350f55', stroke: C.decision },
];

const REVISE_X = 8 + 1.5 * (W + GAP);

export function LoopDiagram() {
  const total = 8 + 4 * W + 3 * GAP + 8;
  return (
    <Exhibit
      title="The loop a claim goes through"
      legend={
        <>
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the three stations that turn a claim
          into an observation. <Chip color={C.decision}>yellow = the decision point</Chip> — the verdict,
          where evidence becomes a status and a confidence.{' '}
          <Chip color={C.absent}>grey dashed = the feedback edge</Chip> — a verdict that is not settled
          sends a <em>new revision</em> of the claim back to the start. Solid arrows are the forward path;
          nothing on this diagram is ever overwritten, because every pass appends a row.
        </>
      }
      reading="Read it left to right once, then follow the dashed edge back: the register's whole job is to make that return trip leave a trace instead of quietly rewriting what was believed before."
      source="docs/method.md — the same loop, rendered client-side"
    >
      <svg viewBox={`0 0 ${total} 150`} className="w-full" role="img" aria-label="claim, predict, test, verdict, revise">
        <defs>
          <marker id="sci-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={C.inkDim} />
          </marker>
          <marker id="sci-arrow-dim" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={C.absent} />
          </marker>
        </defs>

        {STATIONS.map((s, i) => (
          <g key={s.label}>
            <rect x={s.x} y={Y} width={W} height={H} rx={8} fill={s.fill} stroke={s.stroke} strokeWidth={1.2} />
            <text x={s.x + W / 2} y={Y + 25} textAnchor="middle" fontSize={13} fontWeight={600} fill={C.ink}>
              {s.label}
            </text>
            <text x={s.x + W / 2} y={Y + 43} textAnchor="middle" fontSize={10} fill={C.inkDim}>
              {s.sub}
            </text>
            {i < STATIONS.length - 1 && (
              <line
                x1={s.x + W + 4}
                y1={Y + H / 2}
                x2={s.x + W + GAP - 4}
                y2={Y + H / 2}
                stroke={C.inkDim}
                strokeWidth={1.2}
                markerEnd="url(#sci-arrow)"
              />
            )}
          </g>
        ))}

        {/* The return trip: a verdict that is not settled becomes a new revision. */}
        <path
          d={`M ${STATIONS[3].x + W / 2} ${Y + H + 6} V 126 H ${8 + W / 2} V ${Y + H + 6}`}
          fill="none"
          stroke={C.absent}
          strokeWidth={1.2}
          strokeDasharray="5 4"
          markerEnd="url(#sci-arrow-dim)"
        />
        <text x={REVISE_X} y={122} textAnchor="middle" fontSize={10.5} fill={C.absent}>
          revise — a new revision row, never an edit
        </text>

        <text x={8} y={18} fontSize={10.5} fill={C.inkDim}>
          stated before the run
        </text>
        <line x1={8} y1={23} x2={8 + 2 * W + GAP} y2={23} stroke={C.machineryDim} strokeWidth={1} />
      </svg>
    </Exhibit>
  );
}
