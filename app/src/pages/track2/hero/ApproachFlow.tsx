/**
 * Panel (a) of the hero: **the approach**, as five boxes and four arrows.
 *
 * It is the whole of Track 2 in one line — what went in, what the card made of it, what was
 * searched, how it was graded, and what came out — and every box is an anchor into the
 * section below that shows its working. Nothing is typed: the counts come from
 * `approachSteps`, which reads them off the payload.
 */

import { Badge } from '../../../components/Badge';
import { Chip, Exhibit } from '../../../components/Exhibit';
import { C } from '../../../lib/palette';
import { cx, RULE, TINT } from '../../../lib/ui';
import type { ApproachStep } from './heroModel';

export function ApproachFlow({ steps, source }: { steps: ApproachStep[]; source?: string }) {
  return (
    <Exhibit
      title="The approach — five stages, left to right"
      id="track2-approach"
      legend={
        <>
          <Chip color={C.raw}>purple = the raw input</Chip> — the two things this project was given:
          the confirmed variant pair and the child&rsquo;s clinical terms.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the card and the public
          database search, which any card would get.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — the ladder, whose rungs were
          written down before any drug was looked up. <Chip color={C.good}>green = the goal</Chip>{' '}
          and <Chip color={C.broken}>red = set aside</Chip> — the two halves of the output. Each box
          links to the section that shows its working; the arrow is a dependency, not a date.
        </>
      }
      reading="Read left to right: nothing downstream can be argued from more than the box before it, which is why the do-not table (red) sits beside the shortlist (green) rather than under it."
      data={steps}
      source={source}
    >
      <ol
        className="grid gap-2 md:grid-cols-2 xl:grid-cols-[repeat(5,minmax(0,1fr))]"
        data-testid="approach-flow"
      >
        {steps.map((step, i) => (
          <li key={step.id} data-box={step.id} className="relative flex">
            <a
              href={`#${step.anchor}`}
              className={cx(
                'flex w-full flex-col gap-1 rounded-card border-l-2 p-3 transition',
                RULE[step.tone],
                TINT[step.tone],
                'hover:brightness-125 focus:outline-none focus-visible:ring-1 focus-visible:ring-focus',
              )}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-micro text-chrome-500">{i + 1}</span>
                <span aria-hidden="true" className="text-micro text-chrome-600 xl:hidden">
                  {i < steps.length - 1 ? '↓' : '✓'}
                </span>
              </span>
              <span className="text-sm leading-snug font-semibold text-chrome-100">
                {step.title}
              </span>
              <span className="text-micro leading-relaxed text-chrome-400">{step.detail}</span>
              {step.outcomes && (
                <span className="mt-1 flex flex-wrap gap-1">
                  {step.outcomes.map((o) => (
                    <Badge key={o.text} tone={o.tone}>
                      {o.text}
                    </Badge>
                  ))}
                </span>
              )}
            </a>
            {i < steps.length - 1 && (
              <span
                aria-hidden="true"
                className="absolute top-1/2 -right-2 hidden -translate-y-1/2 text-chrome-600 xl:block"
              >
                →
              </span>
            )}
          </li>
        ))}
      </ol>
    </Exhibit>
  );
}
