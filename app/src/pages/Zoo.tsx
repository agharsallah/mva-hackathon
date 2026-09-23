import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { AgreementMatrix } from './zoo/AgreementMatrix';
import { CaseBanner } from './zoo/CaseBanner';
import { ConfirmedRankBars } from './zoo/ConfirmedRankBars';
import { CoverageTable } from './zoo/CoverageTable';
import { Disagreements } from './zoo/Disagreements';
import { GeneScores } from './zoo/GeneScores';
import { useZooRanks } from './zoo/hooks';
import { ModelCards } from './zoo/ModelCards';
import { ModelReport } from './zoo/ModelReport';
import { resolveGene, useGeneParam, useModelParam } from './zoo/route';
import { RunManifest } from './zoo/RunManifest';
import { ZooLineage } from './zoo/ZooLineage';

/**
 * The model zoo — several independent variant-effect models asked the same question, kept
 * apart, and merged only at the end.
 *
 * Every other page in this app argues towards one answer. This one deliberately does not: it
 * runs several programs that were built by different groups on different evidence, keeps each
 * one's ranking separate, and shows where they agree, where they disagree and where each one
 * has nothing to say. The merge is the last step and is printed twice — with and without the
 * lane that was trained on curated verdicts — so a reader can see how much of the consensus
 * comes from a catalogue this case might already be in.
 *
 * **Nothing on this page is typed into it.** The gene, the iteration, the lanes, the
 * percentiles and the costs all arrive from `/api/zoo/*`, which reads them from the run
 * configuration and the warehouse. Point the configuration at another illness and the page
 * follows — that is the deliverable here, as much as this case's answer is.
 */
export default function ZooPage() {
  const [modelKey, setModelKey] = useModelParam();
  const [geneParam, setGene] = useGeneParam();
  const ranks = useZooRanks();
  const gene = resolveGene(geneParam, ranks.data?.data.case) ?? '';

  return (
    <div className="space-y-6">
      <Callout tone="machinery" title="Several opinions, kept apart on purpose">
        A single pathogenicity score is one laboratory&rsquo;s judgement wearing the clothes of a
        measurement. The zoo asks several, records each one&rsquo;s coverage and blind spots before
        looking at any result, and merges them by <em>rank</em> rather than by score — so no
        lane&rsquo;s arbitrary scale can dominate, and a lane with nothing to say about a pair
        contributes nothing to it instead of voting it down.
      </Callout>

      <Explainer
        intro={
          <>
            Each lane below is a published model that turns one DNA change into one number:
            &ldquo;how damaging does this look?&rdquo; They disagree, they cover different kinds of
            change, and two of them were trained on data that already contains verdicts about known
            variants. This page shows all of that before it shows a consensus.
          </>
        }
        terms={[
          {
            term: 'model zoo',
            dict: 'model-zoo',
            plain: (
              <>
                a set of independent scorers run side by side under one interface, so each keeps its
                own result instead of being folded into a single pipeline output
              </>
            ),
          },
          {
            term: 'catalogue-adjacent',
            dict: 'catalogue-adjacent',
            plain: (
              <>
                a model trained on curated verdicts about known variants. It may be right for the
                wrong reason here — recognising a catalogue entry rather than judging the change —
                so the consensus is computed with and without it
              </>
            ),
          },
          {
            term: 'inference tier',
            dict: 'inference-tier',
            plain: (
              <>
                what it costs to ask this model one question: tier 1 is a lookup in a precomputed
                table, tier 2 a local CPU process, tier 3 a remote GPU
              </>
            ),
          },
          {
            term: 'Spearman rank correlation (ρ)',
            dict: 'spearman-rank-correlation-ρ',
            plain: (
              <>
                how alike two orderings are, ignoring the numbers themselves: 1 is the same order, 0
                unrelated, negative opposite. It is the right comparison here because two
                lanes&rsquo; scores are on different scales
              </>
            ),
          },
          {
            term: 'reciprocal rank fusion (RRF)',
            dict: 'reciprocal-rank-fusion-rrf',
            plain: (
              <>
                the merge: each lane contributes <code>1/(k + rank)</code> for a pair and the sums
                are re-ranked, so a pair needs several lanes to like it rather than one lane to love
                it
              </>
            ),
          },
          {
            term: 'allele id',
            dict: 'allele-id',
            plain: (
              <>
                the hash that names one DNA change across every table here. It is the only variant
                key that leaves the machine — the position itself never does
              </>
            ),
          },
        ]}
        caveat={
          <>
            A percentile on this page is a position inside <em>one lane&rsquo;s own</em> ranking of
            the pairs it could score. It is not a probability, not a diagnosis, and not comparable
            between lanes except through the rank-based merge at the bottom of the second section.
          </>
        }
      />

      <Section
        title="The case and the roster"
        subtitle="Which case the zoo was pointed at, which models answered, and how much of the callset each could see."
      >
        <CaseBanner />
        <ModelCards />
        <CoverageTable />
      </Section>

      <Section
        title="Agreement, consensus and dispute"
        subtitle="Where the lanes line up, where the merge puts the case pair, and the alleles they argue about."
      >
        <AgreementMatrix />
        <ConfirmedRankBars />
        <Disagreements onGene={setGene} />
      </Section>

      <Section
        title="One lane, in full"
        subtitle="The generated report for a single lane, with the one written section marked as written."
      >
        <ModelReport modelKey={modelKey} onModelKey={setModelKey} />
      </Section>

      <Section
        title="Any gene, not just this one"
        subtitle="The reusable entry point: a symbol in, every allele and every lane's opinion out."
      >
        <GeneScores key={gene} gene={gene} onGene={setGene} />
      </Section>

      <Section
        title="Cost and provenance"
        subtitle="What the run took, what exactly ran, and how every table on this page was produced."
      >
        <RunManifest />
        <ZooLineage />
      </Section>

      <Callout tone="decision" title="What a consensus rank here is, and what it is not">
        The merge ranks <em>pairs</em> by how consistently the lanes put them near the top. A pair
        can rank poorly here and still be the answer — the missense-only lanes (the coverage table
        names them) cannot score a truncating change, so a pair with a truncating half is unrankable
        by them and carries the opinion of whichever lane could see it. Read the consensus together
        with the coverage table above it; on its own it measures the roster as much as it measures
        the pair.
      </Callout>
    </div>
  );
}
