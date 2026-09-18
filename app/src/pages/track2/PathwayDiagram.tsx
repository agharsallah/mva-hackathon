/**
 * The mechanism, drawn: from the two alleles down to the points a drug could act on.
 *
 * Drawn with boxes and rules rather than one wide SVG on purpose: it has to stay legible at
 * 1280 px and reflow to a single column on a phone, which a fixed viewBox cannot do. The
 * chain itself is derived in `pathwayModel`, so this file is layout only.
 */

import type { Track2 } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, RULE, TINT } from '../../lib/ui';
import { type Branch, stages } from './pathwayModel';
import { T } from './Term';

export function PathwayDiagram({ data, source }: { data: Track2; source?: string }) {
  const rows = stages(data);

  return (
    <Exhibit
      title="From the two alleles to the points a drug could act on"
      id="track2-pathway"
      legend={
        <>
          <Chip color={C.raw}>purple = the raw input</Chip> — the two alleles, as classes, never
          positions. <Chip color={C.machinery}>blue = neutral machinery</Chip> — the protein
          consequence the card argues from. <Chip color={C.broken}>red = broken</Chip> — each step
          of the damage, and the two branches with nothing on them: a direction with no approved
          drug, and a drug class the mechanism warns against.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — the three directions a drug
          was actually argued for, with the shortlisted names under each. A dotted branch carries no
          candidate; the arrow down the spine is a consequence, not a timeline.
        </>
      }
      reading="Read the spine downwards: each step follows from the one above it. A direction is only defensible where it attaches — a statin acts on the tumour at the bottom, not on the checkpoint at the top, and the page never argues one for the other."
      data={rows}
      source={source}
    >
      <ol className="space-y-1" data-testid="pathway-diagram">
        {rows.map((stage, i) => (
          <li key={stage.id} data-stage={stage.id}>
            <div className="grid items-stretch gap-2 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
              <div
                className={cx('rounded-card border-l-2 p-3', RULE[stage.tone], TINT[stage.tone])}
              >
                <h4 className="text-sm leading-snug font-semibold text-chrome-100">
                  {stage.title}
                </h4>
                <p className="mt-1 text-micro leading-relaxed text-chrome-400">{stage.detail}</p>
              </div>
              <ul className="grid content-start gap-2">
                {stage.branches.map((branch) => (
                  <BranchBox key={branch.id} branch={branch} />
                ))}
              </ul>
            </div>
            {i < rows.length - 1 && (
              <div
                aria-hidden="true"
                className="py-0.5 pl-6 font-mono text-micro text-chrome-600 md:w-5/12"
              >
                ↓
              </div>
            )}
          </li>
        ))}
      </ol>

      <p className="mt-3 max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
        The top branch is the honest one to notice first: D1 is what the{' '}
        <T
          slug="mechanism-card"
          term="mechanism card"
          plain="the structured hand-off from Track 1 — what is broken, in which pathway, what follows from it"
        />{' '}
        points at, and it holds no market-approved drug at all. Everything argued below it acts on a{' '}
        <em>consequence</em> of the{' '}
        <T
          slug="hypomorph-hypomorphic"
          term="hypomorph"
          plain="a copy of the gene that still works, but not enough"
        />
        , not on the checkpoint itself.
      </p>
    </Exhibit>
  );
}

function BranchBox({ branch }: { branch: Branch }) {
  return (
    <li
      data-branch={branch.id}
      className={cx(
        'rounded-card p-3',
        branch.dotted ? 'border border-dashed' : 'border-l-2',
        branch.dotted
          ? 'border-broken-900/70 bg-broken-950/10'
          : cx(RULE[branch.tone], TINT[branch.tone]),
      )}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <Badge tone={branch.tone}>{branch.id}</Badge>
        <h5 className="text-sm leading-snug font-semibold text-chrome-100">{branch.title}</h5>
      </div>
      <p className="mt-1 text-micro leading-relaxed text-chrome-400">{branch.detail}</p>
      {branch.drugs.length > 0 && (
        <p className="mt-2 flex flex-wrap gap-1.5">
          {branch.drugs.map((d) => (
            <span
              key={d}
              className="rounded-pill border border-decision-800 bg-decision-950/60 px-2 py-0.5 text-micro text-decision-300"
            >
              {d}
            </span>
          ))}
        </p>
      )}
    </li>
  );
}
