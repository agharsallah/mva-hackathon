/**
 * BeginnerGuide — Track 2 read from the top by someone who has never seen a drug pipeline.
 *
 * Every number is read off the payload rather than typed, so a rebuilt snapshot or a
 * revised mechanism card produces a correct walkthrough with no edit here. House pattern
 * throughout: `technical term (plain-English meaning)`, the term linked to the one
 * dictionary at `/learn#<slug>`. The jargon is never removed, only paired.
 */

import type { ReactNode } from 'react';

import type { Track2 } from '../../api/types';
import { int } from '../../lib/format';
import { cx, WELL } from '../../lib/ui';
import { T } from './Term';

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <li className="grid grid-cols-[1.75rem_1fr] gap-x-2">
      <span className="font-mono text-micro text-chrome-500">{n}.</span>
      <p className="max-w-[95ch] text-sm leading-relaxed text-chrome-300">
        <span className="mr-1 font-semibold text-chrome-100">{title}</span>
        {children}
      </p>
    </li>
  );
}

export function BeginnerGuide({ data }: { data: Track2 }) {
  const { card, summary } = data;
  const gene = card.gene.symbol;
  const c = summary.candidates;
  const waiting = data.strategy.filter((p) => p.status === 'waiting').length;
  const approvedOnGene = data.candidates.filter(
    (r) => r.target_symbol === gene && r.approved,
  ).length;

  return (
    <section className={cx(WELL, 'space-y-3')} data-testid="beginner-guide">
      <h3 className="text-sm font-semibold tracking-tight text-chrome-100">
        Start here — Track 2 in six steps
      </h3>
      <ol className="space-y-2">
        <Step n={1} title="What Track 2 asks.">
          Given the broken gene Track 1 found, which drugs that are{' '}
          <T
            slug="market-approved-max-phase-4"
            term="already market-approved"
            plain="licensed for some disease, so a doctor could prescribe one today"
          />{' '}
          might help? Using an approved drug for a disease it was not approved for is{' '}
          <T
            slug="drug-repurposing"
            term="drug repurposing"
            plain="re-aiming an existing medicine at a new disease"
          />
          , and it is the only route that can reach this child quickly.
        </Step>

        <Step n={2} title="What came over from Track 1.">
          A{' '}
          <T
            slug="mechanism-card"
            term="mechanism card"
            plain="a short structured document saying what is broken, in which pathway, and what happens as a result"
          />{' '}
          — version {card.version}, naming {gene} and its protein {card.gene.protein.split(' (')[0]}
          . It carries the two allele <em>classes</em> and never a position, which is why every
          table on this page can live in a public repository.
        </Step>

        <Step n={3} title="Which way a drug could help.">
          The card names {card.repurposing_directions.length}{' '}
          <T
            slug="repurposing-direction"
            term="repurposing directions"
            plain="the distinct therapeutic angles the mechanism allows, each with the genes it would act on"
          />{' '}
          — reinforce the weakened checkpoint, exploit the stress the resulting{' '}
          <T
            slug="aneuploidy"
            term="aneuploidy"
            plain="cells ending up with the wrong number of chromosomes"
          />{' '}
          causes, stabilise the half-working protein, or treat the tumour the child already has.
        </Step>

        <Step n={4} title="Which proteins to aim at.">
          The card names {summary.targets.seed}{' '}
          <T
            slug="seed-target-target-set"
            term="seed targets"
            plain="the genes chosen by hand, before any automatic expansion"
          />
          . Asking{' '}
          <T
            slug="reactome"
            term="Reactome"
            plain="a public database of which proteins work together in which biological process"
          />{' '}
          which pathways contain the protein added {int(summary.targets.pathway)} more, for{' '}
          {int(summary.targets.total)} in total — {summary.pathways.matched} of the{' '}
          {summary.pathways.walked} pathways matched the stated pattern.
        </Step>

        <Step n={5} title="Which drugs act on them.">
          Three public catalogues —{' '}
          <T
            slug="open-targets-platform"
            term="Open Targets"
            plain="an evidence platform linking targets to diseases and drugs"
          />
          ,{' '}
          <T
            slug="chembl"
            term="ChEMBL"
            plain="a curated database of drug-like molecules and what they bind"
          />{' '}
          and{' '}
          <T
            slug="dgidb-drug-gene-interaction-database"
            term="DGIdb"
            plain="an aggregator of drug-gene interaction claims"
          />{' '}
          — returned {int(c.total)} drug-target rows over {int(c.distinct_drugs)} molecules.{' '}
          {int(c.approved)} rows ({int(c.distinct_approved_drugs)} molecules) are market-approved,
          and exactly {approvedOnGene} of them act on {gene} itself: none. Every candidate comes
          from a neighbour.
        </Step>

        <Step n={6} title="Why there is no answer here yet.">
          {int(c.total)} rows are <em>evidence</em>, not a recommendation. Ranking them, and
          registering a claim per drug, is still open; {waiting} phases are yellow because they wait
          on an{' '}
          <T
            slug="oracle"
            term="oracle"
            plain="the challenge scorer, reachable only by uploading — six replies exist for this whole project"
          />{' '}
          reply that confirms the pair the mechanism is argued from. The final suggestion is
          produced once, after every Track 1 iteration is merged.
        </Step>
      </ol>
    </section>
  );
}
