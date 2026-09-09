/**
 * EpcrLadder — the submitted rows drawn against the scorer's rank-point tiers.
 *
 * The table above says what each row claims; this says why it sits where it sits. Rank is
 * not decoration: the scorer pays 100 points for the right answer at rank 1, 50 at ranks
 * 2–3, 25 at 4–5 and 10 at 6–10, so the tiers are drawn as background bands and the bar
 * length is the row's epcr. Reading the two together answers the question the design
 * actually turns on — the alternative pairings are parked in ranks 2–5 because that band is
 * where a wrong first guess still earns half credit, and the incidental findings go below.
 *
 * Inline SVG rather than a chart library: eight bars and four bands need no runtime, and an
 * SVG stays legible in the report PDF and in both themes.
 */

import type { SelectorRow, Selectors } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { fmtEpcr, RANK_TIERS, rankPoints } from './iteration';

const ROW_H = 26;
const TOP = 22;
const W = 800;
const BAR_X = 250;
const BAR_W = 440;
const PTS_X = W - 8;

const toneOf = (row: SelectorRow) => (row.finding_type === 'primary' ? C.good : C.machinery);

/** The band a rank falls in, as `[firstRank, lastRank]` clipped to the rows actually drawn. */
function bands(rows: SelectorRow[]) {
  const last = rows.length;
  return RANK_TIERS.filter((t) => t.from <= last).map((t) => ({
    ...t,
    to: Math.min(t.to, last),
  }));
}

export function EpcrLadder({ selectors, source }: { selectors: Selectors; source?: string }) {
  const rows = [...selectors.rows].sort((a, b) => a.rank - b.rank);
  const height = TOP + rows.length * ROW_H + 26;
  const y = (i: number) => TOP + i * ROW_H;

  return (
    <Exhibit
      title="Rank ladder — epcr against what each rank is worth"
      legend={
        <>
          One bar per submitted row, length = its <span className="font-mono">epcr</span> (estimated
          probability of causal relationship, 0 to 1). <Chip color={C.good}>green = primary</Chip> —
          a scored answer to the challenge question.{' '}
          <Chip color={C.machinery}>blue = secondary</Chip> — an incidental finding, reported for
          clinical follow-up and not scored. The shaded background bands are the scorer&rsquo;s
          rank-point tiers: 100 points at rank 1, 50 at ranks 2–3, 25 at 4–5, 10 at 6–10, nothing
          below. The dashed rule marks epcr 0.5.
        </>
      }
      reading="The epcr column must strictly descend, so ordering is a claim rather than a formatting choice. Read the bands as the price of being wrong at the top: the four alternative pairings of the same two genes sit at ranks 2–5 because a full match anywhere in that block still earns half or a quarter of the rank points and, more importantly, tells the next iteration exactly which pairing is real."
      data={selectors.rows}
      source={source}
    >
      <svg
        viewBox={`0 0 ${W} ${height}`}
        role="img"
        aria-label="submitted rows as bars by epcr, over the scorer's rank-point tiers"
        className="w-full"
      >
        {bands(rows).map((band) => (
          <g key={band.points}>
            <rect
              x={0}
              y={y(band.from - 1) - 3}
              width={W}
              height={(band.to - band.from + 1) * ROW_H}
              fill={C.decisionFill}
              opacity={band.points / 220}
            />
            <text
              x={PTS_X}
              y={y(band.from - 1) + 11}
              textAnchor="end"
              fontSize={10}
              fill={C.inkDim}
            >
              {band.points} rank pts
            </text>
          </g>
        ))}

        <line
          x1={BAR_X + BAR_W / 2}
          y1={TOP - 6}
          x2={BAR_X + BAR_W / 2}
          y2={height - 22}
          stroke={C.grid}
          strokeDasharray="3 3"
        />

        {rows.map((row, i) => (
          <g key={row.rank} data-rank={row.rank} data-finding={row.finding_type}>
            <text x={8} y={y(i) + 12} fontSize={11} fill={C.inkDim} fontFamily="monospace">
              #{row.rank}
            </text>
            <text x={40} y={y(i) + 12} fontSize={11} fill={C.ink}>
              {row.label}
            </text>
            <rect
              x={BAR_X}
              y={y(i) + 3}
              width={Math.max(2, row.epcr * BAR_W)}
              height={ROW_H - 10}
              rx={2}
              fill={toneOf(row)}
            >
              <title>
                rank {row.rank} · epcr {fmtEpcr(row.epcr)} · worth {rankPoints(row.rank)} rank
                points if this row is the answer
              </title>
            </rect>
            <text
              x={BAR_X + Math.max(2, row.epcr * BAR_W) + 6}
              y={y(i) + 12}
              fontSize={10}
              fill={C.inkDim}
              fontFamily="monospace"
            >
              {fmtEpcr(row.epcr)}
            </text>
          </g>
        ))}

        {[0, 0.5, 1].map((t) => (
          <text
            key={t}
            x={BAR_X + t * BAR_W}
            y={height - 8}
            fontSize={10}
            textAnchor="middle"
            fill={C.inkDim}
            fontFamily="monospace"
          >
            {t.toFixed(1)}
          </text>
        ))}
        <text x={8} y={height - 8} fontSize={10} fill={C.inkDim}>
          epcr →
        </text>
      </svg>
    </Exhibit>
  );
}
