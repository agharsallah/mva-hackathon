/**
 * The evidence ladder — every graded drug against every direction, as one matrix.
 *
 * The exhibit exists to make one failure mode impossible to miss. A drug that is already
 * being trialled in the child's tumour reaches a high rung *automatically*: approved, US
 * label, registered study. That says nothing about the broken checkpoint — it says the drug
 * is already being tried. Those cells are blue. Only a cell where a person read a paper on
 * the mechanism is green or yellow, and the `*` says even that result was inherited from a
 * same-axis compound rather than measured on this molecule.
 *
 * Rows at rung 1 (named, never submitted) are not drawn: 361 of the 432 graded rows sit
 * there, and a matrix of them would hide the 71 that carry a claim.
 */

import type { CardEvidenceLadder, LadderRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { StatTile } from '../../components/StatTile';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BADGE, cx, WELL } from '../../lib/ui';
import { ladderMatrix, type LadderMatrixRow, MIN_SHOWN_RUNG } from './ladderModel';
import { T } from './Term';

function Cell({ row, direction }: { row: LadderMatrixRow; direction: string }) {
  const cell = row.cells[direction];
  if (!cell) return <span className="text-micro text-chrome-700">·</span>;
  const { rung, proxy, curated_rung, flags } = cell.row;
  const title = [
    `rung ${rung ?? '—'}: ${cell.row.rung_label}`,
    `automated ${cell.row.automated_rung ?? '—'}, curated ${curated_rung ?? '—'}`,
    flags.length ? `flags ${flags.join(', ')}` : null,
    proxy ? 'proxy: the cited result is for a same-axis compound' : null,
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <span
      title={title}
      data-rung={rung ?? ''}
      data-tone={cell.tone}
      className={cx(
        'tabular-nums inline-flex min-w-[2.25rem] items-center justify-center rounded-control border px-1.5 py-0.5 font-mono text-micro',
        BADGE[cell.tone],
      )}
    >
      {rung ?? '—'}
      {proxy ? '*' : ''}
    </span>
  );
}

export function EvidenceLadderExhibit({
  ladder,
  rungs,
  shortlistSize,
  source,
}: {
  ladder: LadderRow[];
  rungs?: CardEvidenceLadder;
  shortlistSize: number;
  source?: string;
}) {
  const matrix = ladderMatrix(ladder);
  const curated = matrix.rows.filter((r) => r.curated).length;
  const bestRungs = [...matrix.byBestRung.entries()].sort((a, b) => b[0] - a[0]);

  const columns: Column<LadderMatrixRow>[] = [
    {
      key: 'drug_name',
      header: 'drug',
      render: (r) => <span className="font-mono text-xs text-chrome-100">{r.drug_name}</span>,
    },
    {
      key: 'evidence',
      header: 'evidence',
      sortValue: (r) => (r.curated ? 1 : 0),
      render: (r) => (
        <Badge tone={r.curated ? 'good' : 'machinery'}>
          {r.curated ? 'curated' : 'automated only'}
        </Badge>
      ),
    },
    ...matrix.directions.map((d) => ({
      key: d,
      header: d,
      align: 'right' as const,
      sortValue: (r: LadderMatrixRow) => r.cells[d]?.row.rung ?? null,
      render: (r: LadderMatrixRow) => <Cell row={r} direction={d} />,
    })),
    {
      key: 'best',
      header: 'best rung',
      align: 'right',
      render: (r) => (
        <span className="tabular-nums font-mono text-xs text-chrome-300">{r.best}</span>
      ),
    },
  ];

  return (
    <Exhibit
      title="The evidence ladder — every graded drug against every direction"
      legend={
        <>
          One row per drug, one column per{' '}
          <T
            slug="repurposing-direction"
            term="direction"
            plain="one therapeutic angle the mechanism allows"
          />
          ; the cell is the{' '}
          <T
            slug="rung"
            term="rung"
            plain="the highest kind of evidence the drug passed, 1 to 5 — never a score"
          />
          . <Chip color={C.good}>green = a curated result at rung 4 or 5</Chip> — a person read a
          paper <em>and</em> there is clinical evidence.{' '}
          <Chip color={C.decision}>yellow = a curated result at rung 2 or 3</Chip> — a real cell or
          animal result, nothing clinical yet.{' '}
          <Chip color={C.machinery}>blue = automated tests alone</Chip> — approval, a label and a
          registered trial in the tumour: already being tried, not a mechanism finding.{' '}
          <Chip color={C.broken}>red = a flagged row</Chip> — an anti-direction (A1/A2) or the
          standard of care, where a high rung is a warning rather than a candidate. A{' '}
          <span className="font-mono">*</span> marks{' '}
          <T
            slug="proxy-evidence"
            term="proxy evidence"
            plain="the cited result is for a same-axis compound, not this molecule"
          />
          . A <span className="font-mono">·</span> means the drug was never graded on that
          direction. Rung-1 rows are not drawn.
        </>
      }
      reading={`${matrix.rows.length} drugs reach rung ${MIN_SHOWN_RUNG} or better on at least one direction, of which ${curated} carry a result a person read; the rest are blue, and blue is the whole reason this exhibit exists. ${shortlistSize} rows survive into the shortlist.`}
      data={{ rows: matrix.rows.length, directions: matrix.directions, curated }}
      source={source}
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          The{' '}
          <T
            slug="evidence-ladder"
            term="evidence ladder"
            plain="five fixed rungs, written on the card before any drug was looked up, saying what kind of evidence a candidate has"
          />{' '}
          is a grading scheme fixed before the data arrived — the equivalent of writing the
          assertions before running the suite. Two tests can put a drug on a rung and they are kept
          in separate columns:{' '}
          <T
            slug="automated-versus-curated-rung"
            term="automated versus curated"
            plain="what a program can look up for any card, versus one paper read by a person"
          />
          . The distinction matters because the automated half is exactly what a{' '}
          <T
            slug="decoy-mechanism-card"
            term="decoy card"
            plain="the same pipeline run on a gene that is not the answer"
          />{' '}
          also earns, and the decoy control below measures how much of it that is.
        </p>

        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile
            label="drugs graded"
            tone="machinery"
            value={int(matrix.rows.length)}
            sub={`of ${int(ladder.length)} rows in the ladder, rung ${MIN_SHOWN_RUNG}+`}
          />
          <StatTile
            label="with a curated result"
            tone="good"
            value={int(curated)}
            sub="a PMID read by a person, not a database lookup"
          />
          <StatTile
            label="automated only"
            value={int(matrix.rows.length - curated)}
            sub="what a decoy card would also have got"
          />
          <StatTile
            label="shortlist"
            tone="good"
            value={int(shortlistSize)}
            sub="rows the report may argue from"
          />
        </div>

        <div className={cx(WELL, 'flex flex-wrap gap-4 text-micro')} data-testid="ladder-funnel">
          <span className="font-semibold text-chrome-300">drugs by best rung</span>
          {bestRungs.map(([rung, n]) => (
            <span key={rung} className="tabular-nums font-mono text-chrome-400">
              rung {rung}: <span className="text-chrome-200">{int(n)}</span>
            </span>
          ))}
        </div>

        <DataTable<LadderMatrixRow>
          rows={matrix.rows}
          rowKey={(r) => r.drug_name}
          filterable
          filterLabel="find a drug"
          maxHeight={520}
          columns={columns}
        />

        {rungs && <RungDefinitions ladder={rungs} />}
      </div>
    </Exhibit>
  );
}

/** The five rungs as the card states them — the definitions, not a restatement of them. */
function RungDefinitions({ ladder }: { ladder: CardEvidenceLadder }) {
  return (
    <div className={WELL} data-testid="rung-definitions">
      <p className="mb-2 text-xs text-chrome-300">
        <span className="font-semibold">The rungs, as the card states them</span> — {ladder.purpose}
      </p>
      <ul className="space-y-1">
        {ladder.rungs.map((r) => (
          <li key={r.rung} className="flex gap-3 text-micro leading-relaxed">
            <Badge tone={r.rung >= 4 ? 'good' : r.rung >= 2 ? 'decision' : 'neutral'}>
              rung {r.rung}
            </Badge>
            <span className="text-chrome-200">{r.label}</span>
            <span className="max-w-[70ch] text-chrome-500">{r.test}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 max-w-[95ch] text-micro leading-relaxed text-chrome-400">{ladder.rule}</p>
    </div>
  );
}
