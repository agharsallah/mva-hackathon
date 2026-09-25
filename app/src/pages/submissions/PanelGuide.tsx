/**
 * The beginner walkthrough for a **panel-judged** iteration — Track 2 today.
 *
 * `BeginnerGuide` explains a scored submission: rows, ranks, a decode table, an epcr ladder.
 * None of that exists here, because Track 2 has no scorer: it is read by people. So this is
 * the same six-step shape asking the questions that *do* apply — what is being sent, what it
 * argues, who grades it, why no position appears, and where the folder stands — with every
 * number read off the payload rather than typed, exactly as the scored guide does. What the
 * report argues is read off its own title and method words (`reportTerms`), so an iteration
 * built on a shortlist and one built on converging generators each describe themselves.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { SubmissionIteration } from '../../api/types';
import { cx, WELL } from '../../lib/ui';
import {
  figureDirs,
  PANEL_DELIVERABLES,
  reportSections,
  reportTerms,
  reportTitle,
  STATE_MEANING,
} from './iteration';

/** `term (plain meaning)`, the term linked to its entry in the one dictionary. */
function T({ slug, term, plain }: { slug: string; term: string; plain: ReactNode }) {
  return (
    <span>
      <Link
        to={`/learn#${slug}`}
        className="font-medium text-machinery-300 underline decoration-machinery-800 underline-offset-2 hover:text-machinery-200"
      >
        {term}
      </Link>{' '}
      <span className="text-chrome-400">({plain})</span>
    </span>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="grid grid-cols-[1.75rem_1fr] gap-x-2">
      <span className="font-mono text-micro text-chrome-400">{n}.</span>
      <p className="max-w-[95ch] text-sm leading-relaxed text-chrome-300">
        <span className="mr-1 font-semibold text-chrome-100">{title}</span>
        {children}
      </p>
    </li>
  );
}

export function PanelGuide({ iteration }: { iteration: SubmissionIteration }) {
  const files = iteration.deliverables;
  const uploaded = files.filter((d) => d.kind === 'report-pdf' || d.kind === 'methods-xlsx');
  const figures = iteration.figures.length;
  const dirs = figureDirs(iteration.figures.map((f) => f.path));
  const markdown = iteration.report.markdown;
  const title = reportTitle(markdown);
  const sections = reportSections(markdown);
  const terms = reportTerms(markdown);

  return (
    <section className={cx(WELL, 'space-y-3')} data-testid="beginner-guide">
      <h3 className="text-sm font-semibold tracking-tight text-chrome-100">
        Start here — this iteration in six steps
      </h3>
      <ol className="space-y-2">
        <Step n={1} title="What is being sent.">
          One{' '}
          <T
            slug="submission-iteration"
            term="iteration"
            plain="one folder of everything the organisers receive"
          />{' '}
          of {files.length} files. {uploaded.length} of them leave this repository —{' '}
          {uploaded.map((d) => d.name).join(' and ')} — alongside{' '}
          {PANEL_DELIVERABLES.slice(2).join(' and ')}.
        </Step>

        <Step n={2} title="Who grades it, and how.">
          Nothing here is scored by a program.{' '}
          <T
            slug="track-2-drug-repurposing"
            term="Track 2"
            plain="the drug-repurposing half of the challenge"
          />{' '}
          is read by a panel, so the folder carries no predictions file, no{' '}
          <T
            slug="decode-table"
            term="decode table"
            plain="every reply a scorer could give, written down before it is asked"
          />{' '}
          and no{' '}
          <T
            slug="selector-submission"
            term="selectors"
            plain="the WHERE clause behind a submitted row"
          />
          : those exist to design a scored upload, and there is no score to design for.
        </Step>

        <Step n={3} title="What it argues.">
          {title ? (
            <>
              The report&rsquo;s own title says it: &ldquo;{title}&rdquo;
              {sections > 0 ? <>, over {sections} numbered sections</> : null}.{' '}
            </>
          ) : (
            <>No report has been written into this folder yet. </>
          )}
          {terms.length > 0 ? (
            <>
              It argues with{' '}
              {terms.map((t, i) => (
                <span key={t.slug}>
                  {i > 0 ? (i === terms.length - 1 ? ' and ' : ', ') : null}
                  <T slug={t.slug} term={t.term} plain={t.plain} />
                </span>
              ))}
              .{' '}
            </>
          ) : null}
          The{' '}
          <Link
            to="/track2"
            className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-200"
          >
            Track 2 page
          </Link>{' '}
          renders the tables behind it, with the grading visible.
        </Step>

        <Step n={4} title="What backs it.">
          {iteration.contributions.length} roadmap steps contributed, {iteration.hypotheses.length}{' '}
          <T
            slug="hypothesis"
            term="hypotheses"
            plain="a claim filed with its prediction and what would disprove it, before the test"
          />{' '}
          were registered before their tests ran, and the report cites {figures} rendered figure
          {figures === 1 ? '' : 's'}
          {dirs.length > 0 ? (
            <>
              {' '}
              committed under{' '}
              {dirs.map((d, i) => (
                <span key={d}>
                  {i > 0 ? ', ' : null}
                  <span className="font-mono">{d}</span>
                </span>
              ))}
            </>
          ) : null}
          . Each contribution below links to the append-only entry that produced it.
        </Step>

        <Step n={5} title="Why no position appears anywhere.">
          A genomic position identifies the child, so none is committed — here or in the report. The
          argument is made from the{' '}
          <T
            slug="mechanism-card"
            term="mechanism card"
            plain="what is broken, in which pathway, what follows from it — by variant class, never by position"
          />
          , which names the alleles by their consequence class.
        </Step>

        <Step n={6} title="Where this folder stands.">
          State <span className="font-mono text-chrome-100">{iteration.state}</span> —{' '}
          {STATE_MEANING[iteration.state]}. Track 2 accepts{' '}
          <strong className="text-chrome-100">one submission</strong>
          {iteration.uploaded ? (
            <>, and this folder is it: it is frozen and only ever gains a successor.</>
          ) : (
            <>
              , and it has not been made: this folder will be re-read and re-rendered before it
              goes.
            </>
          )}
        </Step>
      </ol>
    </section>
  );
}
