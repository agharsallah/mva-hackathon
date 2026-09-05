/**
 * ReplyOdds — the decode table as one bar of prior mass.
 *
 * The table above is exact but wide; this is the same rows read as the question they
 * actually answer: *how much of our belief does each possible reply account for?* Segment
 * width is the prior mass on that reply, and the colour is the table's own tone rule, so a
 * reader sees at a glance that most of the mass sits on the green segment (the reply we
 * expect) and that the yellow one is the ambiguity capping the information gain.
 *
 * Numbers are parsed defensively: the payload's cells are the markdown's strings, and an em
 * dash means "no value", not zero.
 */

import type { DecodeTable } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cellNumber, decodeColumn, decodeRows, type DecodeTone } from './iteration';

const TONE_COLOR: Record<DecodeTone, string> = {
  good: C.good,
  broken: C.broken,
  decision: C.decision,
  machinery: C.machinery,
};

const W = 800;
const BAR_Y = 16;
const BAR_H = 34;

interface Segment {
  label: string;
  tone: DecodeTone;
  mass: number;
  fmax: number | null;
}

function segments(table: DecodeTable): Segment[] {
  const priorIdx = decodeColumn(table, 'prior');
  const survivorIdx = decodeColumn(table, 'survivor');
  const fmaxIdx = decodeColumn(table, 'max');
  return decodeRows(table)
    .map((row) => ({
      label: (row.cells[survivorIdx] ?? '').trim() || 'unlabelled reply',
      tone: row.tone,
      mass: cellNumber(row.cells[priorIdx]) ?? 0,
      fmax: cellNumber(row.cells[fmaxIdx]),
    }))
    .filter((s) => s.mass > 0)
    .sort((a, b) => b.mass - a.mass);
}

export function ReplyOdds({ table, source }: { table: DecodeTable; source?: string }) {
  const rows = segments(table);
  const total = rows.reduce((sum, s) => sum + s.mass, 0) || 1;

  let cursor = 0;
  const placed = rows.map((s) => {
    const x = (cursor / total) * W;
    cursor += s.mass;
    return { ...s, x, width: (s.mass / total) * W };
  });

  return (
    <Exhibit
      title="Reply odds — where the prior mass sits before the upload"
      legend={
        <>
          One segment per distinguishable reply, width = its share of the prior (the stated belief
          before the probe is spent, not a measurement).{' '}
          <Chip color={C.good}>green = the goal</Chip> — a full match at rank 1.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — a reply two hypotheses share,
          so it narrows without deciding. <Chip color={C.broken}>red = lost points</Chip> — no match
          at all. <Chip color={C.machinery}>blue = neutral machinery</Chip> — an informative wrong
          answer naming which alternative pairing is real. Hover a segment for its F-max.
        </>
      }
      reading="This is the shape of the bet. A submission is worth sending when the mass is neither concentrated on one reply (nothing to learn) nor spread evenly (nothing expected); the summary line beside the bar prices that in bits."
      data={table.rows}
      source={source}
    >
      <div className="space-y-3">
        <svg
          viewBox={`0 0 ${W} ${BAR_Y + BAR_H + 8}`}
          role="img"
          aria-label="prior mass per possible scorer reply, as one segmented bar"
          className="w-full"
        >
          {placed.map((s) => (
            <g key={s.label}>
              <rect
                x={s.x}
                y={BAR_Y}
                width={Math.max(1, s.width - 1)}
                height={BAR_H}
                fill={TONE_COLOR[s.tone]}
                data-reply={s.label}
              >
                <title>
                  {s.label} · prior mass {s.mass.toFixed(2)}
                  {s.fmax === null ? '' : ` · F-max ${s.fmax.toFixed(3)}`}
                </title>
              </rect>
              {s.width > 46 && (
                <text
                  x={s.x + s.width / 2}
                  y={BAR_Y + BAR_H / 2 + 4}
                  fontSize={11}
                  textAnchor="middle"
                  fill={C.onFill}
                >
                  {s.mass.toFixed(2)}
                </text>
              )}
            </g>
          ))}
          <text x={0} y={10} fontSize={10} fill={C.inkDim}>
            prior mass, most likely reply first →
          </text>
        </svg>

        <div className="grid gap-3 md:grid-cols-[2fr_1fr]">
          <ul className="space-y-1 text-xs text-chrome-300">
            {placed.map((s) => (
              <li key={s.label} className="flex items-baseline gap-2">
                <span
                  className="inline-block h-2 w-2 shrink-0 rounded-sm"
                  style={{ background: TONE_COLOR[s.tone] }}
                  aria-hidden="true"
                />
                <span className="font-mono text-chrome-400">{s.mass.toFixed(2)}</span>
                <span>{s.label}</span>
              </li>
            ))}
          </ul>
          <p
            className="rounded-control border border-line-soft bg-well p-2 text-xs leading-relaxed text-chrome-300"
            data-testid="reply-odds-summary"
          >
            <span className="mr-1 font-semibold text-chrome-100">The price of asking</span>
            {table.summary}
          </p>
        </div>
      </div>
    </Exhibit>
  );
}
