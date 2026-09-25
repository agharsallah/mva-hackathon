import { Link } from 'react-router-dom';

import { useTrack2 } from '../api/hooks';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { HubLinks } from './iterations/HubLinks';
import { iterationHubLinks } from './iterations/model';
import { TrackMap } from './steps/ResearchMap';
import { Report } from './track2/Report';

/**
 * Track 2 — drug repurposing: the report in progress, with its evidence and its strategy.
 *
 * Track 1 asks *which two broken copies of which gene explain this child*. Track 2 asks the
 * next question: given that answer, **which already-approved drug could act on the mechanism
 * it implies** — and how strong is the evidence for each? It is a separately scored
 * deliverable, and the only part of the work that could reach the child, because a
 * repurposed drug is one that already exists.
 *
 * The pair the mechanism argues from is confirmed by the oracle, so the card is at version 3
 * and step 7's grading is real: every approved drug on every direction placed on a rung, a
 * shortlist, a do-not table, and a decoy control that says how much of the list a wrong gene
 * would also have produced. The page still ends in a *shortlist* — hypotheses for follow-up,
 * not evidence that a medicine works — because the one final suggestion is produced after
 * every Track 1 iteration is merged. Everything is laid out so a reviewer can check each
 * step rather than trust it.
 */
export default function Track2Page() {
  const q = useTrack2();

  return (
    <div className="space-y-6">
      <HubLinks links={iterationHubLinks()} />

      <Callout
        tone="good"
        title="The pair is confirmed; this page ends in a shortlist, not a prescription"
      >
        The variant pair the mechanism argues from is confirmed: the{' '}
        <Link
          to="/probes"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          oracle
        </Link>{' '}
        answered iteration 1 with a full match at rank 1, so the mechanism card moved to{' '}
        <strong>version 3</strong> — measured facts F1&ndash;F9, the anti-directions, and the
        evidence ladder the grading below is built on. What follows is therefore a graded list with
        its negative control beside it, not a guess.{' '}
        <strong>
          It is still a shortlist: hypotheses for follow-up, not evidence that a medicine works
        </strong>{' '}
        — the challenge&rsquo;s own words. The final drug suggestion is produced once, after all
        Track 1 iterations are merged, and everything below is the material that merge will read.
      </Callout>

      <Explainer
        intro={
          <>
            <strong>Drug repurposing</strong> means aiming a medicine that is already licensed for
            one disease at a different one. It is the only therapeutic route that can move at the
            speed of a sick child: the safety work is done, the dose is known, a doctor can
            prescribe it. The catch is that the argument has to be airtight — a drug name without a
            cited path from the broken allele to the drug&rsquo;s target is worth nothing, so this
            page shows the path before it shows the names.
          </>
        }
        terms={[
          {
            term: 'drug repurposing',
            dict: 'drug-repurposing',
            plain:
              'using an already-approved drug for a disease it was never approved for — the whole of Track 2',
          },
          {
            term: 'market-approved',
            dict: 'market-approved-max-phase-4',
            plain:
              'licensed and prescribable today. ChEMBL phase 4 or an FDA label is the evidence; the challenge admits nothing else',
          },
          {
            term: 'mechanism card',
            dict: 'mechanism-card',
            plain:
              'the structured hand-off from Track 1: what is broken, in which pathway, what follows from it — by variant class, never by position',
          },
          {
            term: 'repurposing direction',
            dict: 'repurposing-direction',
            plain:
              'one therapeutic angle the mechanism allows, with the genes it would act on. Every candidate inherits the direction it was found under',
          },
          {
            term: 'seed target',
            dict: 'seed-target-target-set',
            plain:
              'a gene the card names by hand. The seeds are the argument; everything else is search',
          },
          {
            term: 'pathway expansion',
            dict: 'pathway-expansion-reactome',
            plain:
              'asking a pathway database which proteins work alongside the broken one, and treating those as targets too',
          },
          {
            term: 'mechanism of action',
            dict: 'mechanism-of-action-moa',
            plain:
              'what a drug does to its target — inhibits it, activates it, degrades it. The direction of the effect is what decides whether a drug helps or harms here',
          },
          {
            term: 'Open Targets',
            dict: 'open-targets-platform',
            plain: 'a public platform linking genes to diseases and to the drugs that act on them',
          },
          {
            term: 'ChEMBL',
            dict: 'chembl',
            plain:
              'a curated database of drug-like molecules, their targets and how far each got in clinical trials',
          },
          {
            term: 'DGIdb',
            dict: 'dgidb-drug-gene-interaction-database',
            plain: 'an aggregator of drug-gene interaction claims from many source databases',
          },
          {
            term: 'Reactome',
            dict: 'reactome',
            plain: 'a public database of which proteins take part in which biological process',
          },
          {
            term: 'ClinicalTrials.gov',
            dict: 'clinicaltrials-gov',
            plain:
              'the public registry every clinical study must be listed in — evidence a drug has been given in a context, never that it worked',
          },
          {
            term: 'lineage edge',
            dict: 'lineage-edge',
            plain:
              'one recorded derivation: this table was produced from that source by this transform',
          },
          {
            term: 'evidence ladder',
            dict: 'evidence-ladder',
            plain:
              'five fixed rungs, written on the card before any drug was looked up, saying what kind of evidence a candidate has — never a score',
          },
          {
            term: 'anti-direction',
            dict: 'anti-direction-the-do-not-table',
            plain:
              'a drug class the mechanism says would make things worse. The do-not table is, clinically, the more useful half of Track 2',
          },
          {
            term: 'decoy mechanism card',
            dict: 'decoy-mechanism-card',
            plain:
              'the same pipeline run on a gene that is not the answer — the negative control for the whole search',
          },
          {
            term: 'hypothesis',
            dict: 'hypothesis',
            plain:
              'a claim filed with its prediction and its refutation condition before the test runs. Track 2 filed two before it searched at all',
          },
        ]}
        caveat="Nothing on this page is a treatment recommendation. Every row is a public database record about a drug and a protein, not about this child; a candidate becomes a proposal only after a scored, cited path from the allele to the target is registered and argued. Confidence figures in the register are a stated triage heuristic with their arithmetic printed on the Science page — never a probability."
      />

      <Loaded query={q} height={420} label="Loading the Track 2 report">
        {(_data, meta) => <Report result={meta} />}
      </Loaded>

      <Section
        title="The iterations"
        subtitle="Where each route's Track 2 step stands; a tile opens that iteration's page."
      >
        <TrackMap track="track2" />
      </Section>
    </div>
  );
}
