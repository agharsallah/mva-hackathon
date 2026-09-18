/**
 * Panel (b) of the hero: **the suggestion** — the eleven drugs the report may argue, as
 * cards grouped by the direction they were found under.
 *
 * The table below the page says the same thing in columns; this says it in the order a
 * reader asks for it — the tumour first, then the two mechanism angles — with the curated
 * sentence a person wrote next to each drug rather than a rung number alone.
 */

import { useState } from 'react';

import type { ShortlistRow, Track2EvidenceRow } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { Chip, Exhibit } from '../../../components/Exhibit';
import { C } from '../../../lib/palette';
import { cx, RULE, WELL } from '../../../lib/ui';
import { PmidList } from '../Pmids';
import { T } from '../Term';
import {
  ANCHOR,
  claimOf,
  type DirectionGroup,
  evidenceFor,
  pediatricMarks,
  proxyLabel,
  proxyOf,
  shortlistTone,
  titleCase,
} from './heroModel';

const CLAIM_CHARS = 160;

export interface SuggestionProps {
  groups: DirectionGroup[];
  evidence: Track2EvidenceRow[];
  /** The do-not rows the card marks `caution` — the red strip under the cards. */
  caution: ShortlistRow[];
  /** Rows whose only evidence is a registered trial in the tumour. */
  contextOnly: number;
  tumourContext: string;
  /** The chemotherapy already being given, so a caution chip can say which are standard. */
  standardOfCare: string[];
  source?: string;
}

export function Suggestion({
  groups,
  evidence,
  caution,
  contextOnly,
  tumourContext,
  standardOfCare,
  source,
}: SuggestionProps) {
  const total = groups.reduce((n, g) => n + g.rows.length, 0);
  const soc = new Set(standardOfCare.map((d) => d.toUpperCase()));
  const cautionStandard = caution.filter((r) => soc.has(r.drug_name.toUpperCase()));

  return (
    <Exhibit
      title={`The suggestion — ${total} drugs, grouped by what they would act on`}
      id="track2-suggestion"
      legend={
        <>
          One card per drug. The rung badge is the kind of evidence, never a ranking:{' '}
          <Chip color={C.good}>green = rung 4 or 5</Chip> (a trial in a related indication),{' '}
          <Chip color={C.decision}>yellow = rung 2 or 3</Chip> (a cell or animal model — a real
          result with no clinical evidence behind it). <Chip color={C.broken}>red = set aside</Chip>{' '}
          — the caution strip at the bottom, drugs the mechanism argues against. A{' '}
          <Badge tone="decision">proxy</Badge> tag means the paper tested a same-axis compound, not
          this molecule, and names which. Every PubMed id opens the paper.
        </>
      }
      reading={`${total} drugs carry a mechanism result a person read; ${contextOnly} more reach a high rung only because they are already in ${tumourContext} trials, and are listed rather than claimed. This is a shortlist — hypotheses for follow-up, not evidence that a medicine works.`}
      data={groups}
      source={source}
    >
      <div className="space-y-4" data-testid="suggestion-panel">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          Each card is one row of the{' '}
          <T
            slug="shortlist"
            term="shortlist"
            plain="the graded rows the report may argue: rung 2 or better, not standard of care, not an anti-direction"
          />{' '}
          below, with the sentence from the paper that put it there. The groups are{' '}
          <T
            slug="repurposing-direction"
            term="repurposing directions"
            plain="one therapeutic angle the mechanism allows, with the genes it would act on"
          />{' '}
          — a drug inherits the direction it was found under and is never argued outside it.
        </p>

        {groups.map((group) => (
          <Group key={group.id} group={group} evidence={evidence} />
        ))}

        <div className={cx(WELL, 'border-l-2 space-y-2', RULE.broken)} data-testid="caution-strip">
          <h4 className="text-sm font-semibold text-broken-300">What to be careful with</h4>
          <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-300">
            {caution.length}{' '}
            <T
              slug="anti-direction-the-do-not-table"
              term="anti-direction"
              plain="a drug class the mechanism says would make things worse"
            />{' '}
            rows: spindle poisons, which work by tripping the very checkpoint this child is short
            of.{' '}
            {cautionStandard.length > 0 && (
              <>
                <strong className="text-broken-300">
                  {cautionStandard.map((r) => titleCase(r.drug_name)).join(' and ')}
                </strong>{' '}
                are{' '}
                <T
                  slug="standard-of-care-excluded-from-a-repurposing"
                  term="standard of care"
                  plain="the chemotherapy already given for this tumour"
                />{' '}
                for {tumourContext}.{' '}
              </>
            )}
            This is a flag <strong>for the treating team</strong>, never advice to withhold
            treatment: a theoretical mechanism concern does not outweigh a regimen with survival
            data behind it.
          </p>
          <ul className="flex flex-wrap gap-1.5" data-testid="caution-chips">
            {caution.map((row) => (
              <li key={`${row.drug_name}:${row.direction_id}`}>
                <Badge tone="broken" title={row.why}>
                  {titleCase(row.drug_name)}
                  {soc.has(row.drug_name.toUpperCase()) ? ' · standard of care' : ''}
                </Badge>
              </li>
            ))}
          </ul>
        </div>

        <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-500">
          <a
            href={`#${ANCHOR.shortlist}`}
            className="underline decoration-chrome-700 underline-offset-2 hover:text-chrome-300"
          >
            {contextOnly} more approved drugs
          </a>{' '}
          reach the top rung only because they are already in {tumourContext} trials — listed below,
          not claimed.
        </p>
      </div>
    </Exhibit>
  );
}

function Group({ group, evidence }: { group: DirectionGroup; evidence: Track2EvidenceRow[] }) {
  return (
    <section data-direction={group.id} className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <Badge tone="machinery">{group.id}</Badge>
        <h4 className="text-sm font-semibold text-chrome-100">{group.gloss}</h4>
        <span className="text-micro text-chrome-500">{group.name}</span>
      </div>
      <ul className="grid gap-2 md:grid-cols-2">
        {group.rows.map((row) => (
          <DrugCard
            key={`${row.drug_name}:${row.direction_id}`}
            row={row}
            rows={evidenceFor(evidence, row)}
          />
        ))}
      </ul>
    </section>
  );
}

function DrugCard({ row, rows }: { row: ShortlistRow; rows: Track2EvidenceRow[] }) {
  const [open, setOpen] = useState(false);
  const tone = shortlistTone(row);
  const claim = claimOf(rows);
  const proxy = proxyOf(rows);
  const marks = pediatricMarks(row);
  const long = claim.length > CLAIM_CHARS;
  const shown = open || !long ? claim : `${claim.slice(0, CLAIM_CHARS).trimEnd()}…`;

  return (
    <li
      data-drug={row.drug_name}
      className={cx(
        'space-y-2 rounded-card border border-line bg-panel-raised p-3 border-l-2',
        RULE[tone],
      )}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <h5 className="text-sm font-semibold text-chrome-100">{titleCase(row.drug_name)}</h5>
        <Badge tone={tone} title={row.why}>
          rung {row.rung ?? '—'}
        </Badge>
        {proxy && (
          <Badge tone="decision" title={`the paper tested ${proxy}, not this molecule`}>
            proxy · {proxyLabel(proxy)}
          </Badge>
        )}
      </div>

      {claim !== '' && (
        <p className="max-w-[60ch] text-micro leading-relaxed text-chrome-300">
          {shown}
          {long && (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className="ml-1 text-machinery-300 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200"
            >
              {open ? 'less' : 'read more'}
            </button>
          )}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {marks.label && (
          <Badge tone="machinery" title="the US label carries a section 8.4 Pediatric Use">
            <span aria-hidden="true" className="mr-1">
              §
            </span>
            label 8.4
          </Badge>
        )}
        {marks.study && (
          <Badge tone="machinery" title="at least one registered study admits children">
            <span aria-hidden="true" className="mr-1">
              ⚕
            </span>
            study admits children
          </Badge>
        )}
        {!marks.label && !marks.study && <Badge tone="neutral">no paediatric pointer</Badge>}
        <PmidList pmids={row.curated_pmids} />
      </div>
    </li>
  );
}
