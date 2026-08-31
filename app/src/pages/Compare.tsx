import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { RarityScatter } from './compare/RarityScatter';
import { CandidateTable } from './compare/CandidateTable';
import { CandidateFunnel } from './compare/CandidateFunnel';
import { ObservedExpected } from './compare/ObservedExpected';

/**
 * Compare — this patient against the normal population.
 *
 * Every other page reads the case in isolation. This one is the only page that asks the
 * comparative question, in two directions: is a given variant unusual in healthy people
 * (gnomAD), and is the callset itself unusual as a piece of engineering (published QC
 * norms). Both are baselines; a claim is only interesting as a departure from one.
 */
export default function ComparePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Nothing about a variant is remarkable on its own — five million records is what a normal genome
            looks like. What makes one interesting is being <em>rare</em>. So this page holds the case up
            against two baselines. The first is <strong>gnomAD</strong>, an aggregate database of roughly
            800,000 mostly-healthy people&apos;s genomes: think of it as a read-only index of how often each
            variant shows up in the general population. If a variant is common there, healthy people carry it,
            so it cannot by itself cause a severe childhood disease — a causal rare-disease variant has to be
            rare in gnomAD or absent from it entirely. The second baseline is a set of published{' '}
            <strong>quality-control norms</strong> for healthy genomes: if this callset&apos;s own engineering
            numbers sit where a normal genome&apos;s do, its biology is worth believing.
          </>
        }
        terms={[
          {
            term: 'gnomAD',
            plain:
              'the Genome Aggregation Database — ~800k mostly-healthy exomes and genomes pooled into per-variant frequency counts. The population baseline for "is this normal?"',
          },
          {
            term: 'allele frequency (AF)',
            plain:
              'the share of chromosomes in that population carrying the variant. 0.30 = common; 1e-5 = one in a hundred thousand; absent = it has never been seen',
          },
          {
            term: 'grpmax',
            plain:
              'the highest AF across gnomAD’s individual population groups. A variant can look rare overall and still be common in one ancestry — grpmax is the number that catches that',
          },
          {
            term: 'novel variant',
            plain:
              'absent from gnomAD entirely. Null AF, not zero AF: the database has no row, which is a different claim from "measured at zero"',
          },
          {
            term: 'VAF (variant allele fraction)',
            plain:
              'the share of this patient’s own sequencing reads at that site carrying the variant. ≈0.5 = one of two copies (heterozygous); ≈1.0 = both copies',
          },
          {
            term: 'consequence / IMPACT',
            plain:
              'what the variant does to the gene product, as predicted by VEP, bucketed HIGH (truncates the protein) → MODERATE (swaps an amino acid) → LOW (silent) → MODIFIER (non-coding)',
          },
          {
            term: 'ClinVar',
            plain:
              'a public registry of variant–disease assertions submitted by clinical labs. "Pathogenic" there means somebody has already argued this variant causes disease',
          },
          {
            term: 'carrier frequency',
            plain:
              'for a recessive disease, healthy people carry one broken copy. So the causal variant is allowed to appear in gnomAD at low frequency — what must be vanishingly rare is inheriting two',
          },
          {
            term: 'observed vs expected',
            plain:
              'a QC pattern: put the measured number next to the range published for healthy genomes. Agreement is not a result, it is permission to trust the results',
          },
        ]}
        caveat="gnomAD is a frequency baseline, not a health baseline. It contains people with undiagnosed conditions and is unevenly sampled across ancestries — a variant absent from gnomAD may be genuinely novel or may simply belong to an under-represented population. Rarity narrows the list; it never proves causality."
      />

      <Callout tone="decision" title="What to look for on this page">
        Two things have to be true at once for a variant to survive here: it must be{' '}
        <strong>rare or absent in gnomAD</strong>, and it must be able to <strong>change the protein</strong>.
        Almost everything fails one of the two — that is the point of the funnel. Then check the third exhibit
        before believing any of it: if the callset&apos;s own QC numbers do not sit where a healthy genome&apos;s
        sit, the biology above is resting on a shaky measurement.
      </Callout>

      <Section
        title="How rare is each panel variant in healthy people?"
        subtitle="log-frequency against the patient's own read evidence — the novel lane at the far left is the interesting one"
      >
        <RarityScatter />
      </Section>

      <Section
        title="What survives both filters?"
        subtitle="rare in the population and protein-altering — a short list is the intended outcome"
      >
        <CandidateTable />
      </Section>

      <Section
        title="What did every filter cost?"
        subtitle="the whole narrowing argument in nine stages — and the point where the scope stops being the genome"
      >
        <CandidateFunnel />
      </Section>

      <Section
        title="Is the callset itself normal?"
        subtitle="the measured QC aggregates against published healthy-genome ranges"
      >
        <ObservedExpected />
      </Section>
    </div>
  );
}
