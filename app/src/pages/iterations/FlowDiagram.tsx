import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { IterationsOverview } from '../../api/types';
import { C, TONE_MARK } from '../../lib/palette';
import { STATE_TONE } from '../submissions/iteration';
import { iterationNumber, primaryResearch, shortReply } from './model';

/**
 * Which research iterations each submission folder cites, as a two-column flow: research
 * iterations on the left, folders on the right, one line per citation. The two numberings do
 * not line up (Track 2's iteration-4 folder is built from research iteration 4 alone, and no
 * Track 1 folder carries a 4), and this is the one picture that shows it.
 *
 * Plain SVG, no graph library: two columns need no layout engine. Hovering a node lights
 * its own lines; a folder is a link to its dossier.
 */

const W = 820;
const NODE_W = 260;
const NODE_H = 40;
const GAP = 14;
const PAD = 8;

interface Node {
  id: string;
  label: string;
  sub: string;
  color: string;
  dashed: boolean;
  x: number;
  y: number;
}

export function FlowDiagram({ data }: { data: IterationsOverview }) {
  const navigate = useNavigate();
  const [hot, setHot] = useState<string | null>(null);

  const folders = [...data.submissions].sort(
    (a, b) => a.track.localeCompare(b.track) || a.number - b.number,
  );
  const rows = Math.max(data.research.length, folders.length);
  const height = PAD * 2 + rows * NODE_H + (rows - 1) * GAP;
  const offset = (n: number) => (height - (n * NODE_H + (n - 1) * GAP)) / 2;

  const left: Node[] = data.research.map((r, i) => ({
    id: r.iteration,
    label: `research iteration ${iterationNumber(r.iteration)}`,
    sub: r.declared ? `${r.steps} steps · ${r.entries.count} entries` : 'plan only — no steps',
    color: r.declared ? C.machinery : C.absent,
    dashed: !r.declared,
    x: PAD,
    y: offset(data.research.length) + i * (NODE_H + GAP),
  }));
  const right: Node[] = folders.map((s, i) => ({
    id: s.key,
    label: s.key,
    sub: `${s.state} · ${s.judged_by}${s.reply ? ` · ${shortReply(s.reply)}` : ''}`,
    color: TONE_MARK[STATE_TONE[s.state]],
    dashed: false,
    x: W - PAD - NODE_W,
    y: offset(folders.length) + i * (NODE_H + GAP),
  }));
  const at = new Map([...left, ...right].map((n) => [n.id, n]));
  const links = folders.flatMap((s) => {
    const primary = primaryResearch(s);
    return s.research.map((r) => ({ from: r, to: s.key, built: r === primary }));
  });

  return (
    <div className="overflow-x-auto rounded-card border border-line bg-chrome-950/60">
      <svg
        viewBox={`0 0 ${W} ${height}`}
        width="100%"
        style={{ minWidth: 560, maxWidth: W }}
        className="block"
        role="group"
        aria-label={`${links.length} citations from ${left.length} research iterations to ${right.length} submission folders`}
      >
        {links.map((l) => {
          const a = at.get(l.from);
          const b = at.get(l.to);
          if (!a || !b) return null;
          const lit = hot === l.from || hot === l.to;
          const x1 = a.x + NODE_W;
          const y1 = a.y + NODE_H / 2;
          const x2 = b.x;
          const y2 = b.y + NODE_H / 2;
          const mid = (x1 + x2) / 2;
          return (
            <path
              key={`${l.from}>${l.to}`}
              d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
              fill="none"
              stroke={l.built || lit ? b.color : C.inkDim}
              strokeWidth={lit ? 2.4 : l.built ? 2 : 1.2}
              strokeDasharray={l.built ? undefined : '4 4'}
              opacity={hot && !lit ? 0.15 : lit || l.built ? 1 : 0.55}
            />
          );
        })}
        {[...left, ...right].map((n) => {
          const folder = n.x > PAD;
          const box = (
            <>
              <title>{folder ? `${n.label} — open its dossier` : n.label}</title>
              <rect
                x={n.x}
                y={n.y}
                width={NODE_W}
                height={NODE_H}
                rx={6}
                fill={C.panel}
                stroke={n.color}
                strokeWidth={hot === n.id ? 2.2 : 1.4}
                strokeDasharray={n.dashed ? '4 3' : undefined}
              />
              <text
                x={n.x + 10}
                y={n.y + 17}
                fill={C.ink}
                fontSize="12"
                fontFamily="ui-monospace, monospace"
              >
                {n.label}
              </text>
              <text x={n.x + 10} y={n.y + 32} fill={C.inkDim} fontSize="10">
                {n.sub.length > 42 ? `${n.sub.slice(0, 41)}…` : n.sub}
              </text>
            </>
          );
          const hover = { onMouseEnter: () => setHot(n.id), onMouseLeave: () => setHot(null) };
          if (!folder) {
            return (
              <g key={n.id} {...hover}>
                {box}
              </g>
            );
          }
          const to = `/submissions?it=${n.id}`;
          return (
            <a
              key={n.id}
              href={to}
              {...hover}
              onFocus={() => setHot(n.id)}
              onBlur={() => setHot(null)}
              onClick={(e) => {
                e.preventDefault();
                navigate(to);
              }}
            >
              {box}
            </a>
          );
        })}
      </svg>
    </div>
  );
}
