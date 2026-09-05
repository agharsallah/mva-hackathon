import { Link } from 'react-router-dom';

import { useTrack2 } from '../api/hooks';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
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
 * The page is a report *in progress* on purpose. The mechanism it argues from rests on a
 * pair the oracle has not confirmed, so the one suggestion Track 2 ends with is produced
 * once, after every Track 1 iteration is merged. What exists today is the argument, the
 * search space it implies, the candidates the public sources returned, and the audit trail
 * behind all three — laid out so a reviewer can check each step rather than trust it.
 */
export default function Track2Page() {
  const q = useTrack2();

  return (
    <div className="space-y-6">
      <Callout tone="decision" title="This page ends in a suggestion; it does not contain one yet">
        The mechanism argument rests on a variant pair that only an{' '}
        <Link
          to="/probes"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          oracle
        </Link>{' '}
        reply confirms. Every Track 1 iteration revises the mechanism card — a new version with a
        history entry, never an edit — and the snapshot is re-run against it.{' '}
        <strong>
          The final drug suggestion is produced once, after all Track 1 iterations are merged
        </strong>
        : their evidence and the register combined, the ranking re-run on the confirmed pair, and
        one Track 2 submission written. Everything below is the material that merge will read.
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
    </div>
  );
}
