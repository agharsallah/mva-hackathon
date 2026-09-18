/**
 * Step 7's half of the Track 2 report: the grading, in the order a reader needs it.
 *
 * The snapshot answers *which drugs exist*. These six sections answer *which of them may be
 * argued, which must not be, and how much of either a wrong gene would also have produced*
 * — so they sit immediately after the mechanism argument and before the raw search space
 * that produced them.
 *
 * Everything is read off the payload. A checkout that has never run `tools/track2_enrich.py`
 * has none of these tables, and each section simply does not render rather than drawing an
 * empty frame that reads as "nothing found".
 */

import type { Track2 } from '../../api/types';
import { Section } from '../../components/Controls';
import { DecoyControl } from './DecoyControl';
import { DoNotTable } from './DoNotTable';
import { EvidenceLadderExhibit } from './EvidenceLadder';
import { splitShortlist } from './ladderModel';
import { MeasuredFacts } from './MeasuredFacts';
import { PediatricPointers } from './PediatricPointers';
import { Shortlist } from './Shortlist';

export function Grading({ data, source }: { data: Track2; source?: string }) {
  const facts = data.card.measured_facts ?? [];
  const ladder = data.evidence_ladder ?? [];
  const shortlist = data.shortlist ?? [];
  const doNot = data.do_not ?? [];
  const comparison = data.decoy_comparison ?? [];
  const decoys = data.decoys ?? [];
  const pediatricTrials = data.pediatric_trials ?? [];
  const { argue } = splitShortlist(shortlist);

  return (
    <>
      {facts.length > 0 && (
        <Section
          title="Measured facts"
          subtitle="what iteration 2 measured about the genotype, and the one thing it did not"
        >
          <MeasuredFacts facts={facts} source={source} />
        </Section>
      )}

      {ladder.length > 0 && (
        <Section
          title="The evidence ladder"
          subtitle="every approved drug placed on a rung, with the automated and the curated test side by side"
        >
          <EvidenceLadderExhibit
            ladder={ladder}
            rungs={data.card.evidence_ladder}
            shortlistSize={shortlist.length}
            source={source}
          />
        </Section>
      )}

      {shortlist.length > 0 && (
        <Section
          title="The shortlist"
          subtitle="the rows that carry a mechanism argument, and the rows that only carry a trial"
        >
          <Shortlist shortlist={shortlist} source={source} />
        </Section>
      )}

      {(doNot.length > 0 || (data.card.anti_directions ?? []).length > 0) && (
        <Section
          title="The do-not table"
          subtitle="the classes the mechanism argues against, and the chemotherapy that is already being given"
        >
          <DoNotTable
            rows={doNot}
            antiDirections={data.card.anti_directions ?? []}
            standardOfCare={data.card.case.context_standard_of_care}
            source={source}
          />
        </Section>
      )}

      {comparison.length > 0 && (
        <Section
          title="The decoy control"
          subtitle="the same pipeline on a gene that is not the answer — the negative control this search needed"
        >
          <DecoyControl comparison={comparison} decoys={decoys} source={source} />
        </Section>
      )}

      {argue.length > 0 && (
        <Section
          title="Paediatric pointers"
          subtitle="what the labels and the registry say about giving each shortlisted drug to a child"
        >
          <PediatricPointers
            argue={argue}
            ladder={ladder}
            pediatricTrials={pediatricTrials}
            source={source}
          />
        </Section>
      )}
    </>
  );
}
