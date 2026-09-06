/**
 * BeginnerGuide — this iteration, read from the top by someone who has never seen a
 * genomics submission.
 *
 * Everything on the page below is written for a reader who already knows what a decode
 * table or an epcr column is. This panel is the six sentences that come first, and every
 * number in them is read off the payload rather than typed: a future iteration with a
 * different gene, a different row count or a different reply set produces a correct
 * walkthrough with no edit here.
 *
 * House pattern throughout: `technical term (plain-English meaning)`, with the term linked
 * to its full entry in the one dictionary at `/learn#<slug>`. The jargon is never removed,
 * only paired — the reader has to recognise the real word in a tool flag or a paper later.
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { SubmissionIteration } from '../../api/types';
import { cx, WELL } from '../../lib/ui';
import { cellNumber, decodeColumn, primaryGene, STATE_MEANING } from './iteration';

/** `term (plain meaning)`, the term linked to its dictionary entry. */
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

/** The first sentence of a row's notes — enough to say what it claims, without the dossier. */
function firstClause(notes: string): string {
  const body = notes.split('|').pop() ?? notes;
  return body.split(';')[0]!.trim();
}

/** The bits figure out of the decode table's summary sentence, when it states one. */
function gainPhrase(summary: string): string | null {
  const match = /expected information gain\s+([\d.]+)\s*bits/i.exec(summary);
  return match ? `${match[1]} bits` : null;
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

export function BeginnerGuide({ iteration }: { iteration: SubmissionIteration }) {
  const rows = iteration.selectors.rows;
  const primary = rows.filter((r) => r.finding_type === 'primary');
  const secondary = rows.filter((r) => r.finding_type === 'secondary');
  const top = rows[0];
  const gene = primaryGene(iteration.selectors);
  const table = iteration.decode_table;
  const priorIdx = decodeColumn(table, 'prior');
  const replies = table.rows.length;
  const best = table.rows
    .map((r) => cellNumber(r[priorIdx]))
    .reduce<number | null>((a, b) => (b !== null && (a === null || b > a) ? b : a), null);
  const gain = gainPhrase(table.summary);
  const spent = iteration.audit.probes.length;

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
            plain="one frozen folder of everything the organisers receive"
          />{' '}
          holds a file of {rows.length} rows, and the organisers&rsquo; scorer grades those rows.{' '}
          {primary.length} are primary claims about the child&rsquo;s disease
          {gene ? <> in {gene}</> : null}; {secondary.length} are{' '}
          <T
            slug="secondary-incidental-finding"
            term="secondary findings"
            plain="unrelated but medically useful things noticed on the way"
          />
          , which are reported for a clinician and cannot compete with the primary answer.
        </Step>

        <Step n={2} title="What the top row claims.">
          {top ? (
            <>
              Row 1, <span className="font-medium text-chrome-100">{top.label}</span>:{' '}
              {firstClause(top.notes)}. Read as a{' '}
              <T
                slug="compound-heterozygous-comp-het"
                term="compound heterozygote"
                plain="two different broken copies of one gene, one inherited from each parent"
              />{' '}
              — two separate{' '}
              <T slug="allele" term="alleles" plain="one specific version of one spot in the DNA" />
              , not one mutation seen twice.
            </>
          ) : (
            <>No row has been designed for this iteration yet.</>
          )}
        </Step>

        <Step n={3} title="How the scorer answers.">
          Two numbers come back.{' '}
          <T
            slug="rank-points"
            term="rank points"
            plain="credit for how high in the file the right answer sits"
          />{' '}
          — rank 1 is worth 100, ranks 2–3 fifty, 4–5 twenty-five, 6–10 ten — and{' '}
          <T
            slug="f-max"
            term="F-max"
            plain="how well the submitted set overlaps the answer key; 1.0 is exact"
          />
          . So the order of the rows is itself a claim, which is what the{' '}
          <T
            slug="epcr"
            term="epcr"
            plain="the confidence column, which has to keep descending down the file"
          />{' '}
          ladder below shows.
        </Step>

        <Step n={4} title="Why the reply is worth having.">
          The{' '}
          <T
            slug="decode-table"
            term="decode table"
            plain="every answer the scorer could give, written down before it is asked"
          />{' '}
          lists {replies} distinguishable replies
          {best !== null ? (
            <> — the most likely one carries {best.toFixed(2)} of the prior</>
          ) : null}
          {gain ? (
            <>
              {' '}
              — for an{' '}
              <T
                slug="expected-information-gain"
                term="expected information gain"
                plain="how much uncertainty the answer is expected to remove"
              />{' '}
              of {gain}
            </>
          ) : null}
          . Each reply names the next iteration, so the upload is informative whatever it says.
        </Step>

        <Step n={5} title="Why no position appears anywhere.">
          A genomic position identifies the child, so none is committed. Every row is stored as a{' '}
          <T
            slug="selector-submission"
            term="selector"
            plain="a WHERE clause naming what an allele is — gene, consequence, rarity — instead of where it sits"
          />
          , and the{' '}
          <T
            slug="lineage-edge"
            term="lineage"
            plain="the recorded edge saying which source and transform produced a table"
          />{' '}
          and{' '}
          <T
            slug="audit-trail"
            term="audit trail"
            plain="the append-only ledger of what was spent and what changed a belief"
          />{' '}
          sections below let a reviewer rebuild the file from {iteration.contributions.length}{' '}
          contributing steps and {iteration.hypotheses.length} registered{' '}
          <T
            slug="hypothesis"
            term="hypotheses"
            plain="a claim filed with its prediction and what would disprove it, before the test"
          />
          .
        </Step>

        <Step n={6} title="Where this folder stands.">
          State <span className="font-mono text-chrome-100">{iteration.state}</span> —{' '}
          {STATE_MEANING[iteration.state]}. {spent === 0 ? 'No' : String(spent)} of six{' '}
          <T
            slug="oracle"
            term="oracle"
            plain="the challenge scorer, reachable only by uploading; each reply is permanent"
          />{' '}
          uploads have been spent on it, and a{' '}
          <T
            slug="frozen-iteration"
            term="frozen iteration"
            plain="an uploaded folder that is never edited again"
          />{' '}
          only ever gains a successor.
        </Step>
      </ol>
    </section>
  );
}
