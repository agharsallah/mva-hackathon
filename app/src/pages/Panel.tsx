import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { GeneScorecard } from './panel/GeneScorecard';
import { ConstraintScorecard } from './panel/ConstraintScorecard';
import { LocusExplorer } from './panel/LocusExplorer';
import { PairMatrix } from './panel/PairMatrix';

export default function PanelPage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            MVA has a small set of genes behind it in the literature, all of them parts of the machinery that
            makes sure a dividing cell hands each daughter exactly one copy of every chromosome. This page
            narrows the 5 million genome-wide records down to those gene intervals, asks how much evidence each
            gene actually has, and then lets you open one gene and look at every record inside it.
          </>
        }
        terms={[
          {
            term: 'gene panel',
            plain: 'a hand-picked list of gene intervals to search first — an allowlist over the genome',
          },
          {
            term: 'BED file',
            plain: 'the interval format the panel is stored in: contig, start, end, name — one row per region',
          },
          {
            term: 'spindle assembly checkpoint (SAC)',
            plain: 'the cell’s pre-division gate: it halts division until every chromosome is correctly attached. Break it and chromosomes get miscounted — that is MVA',
          },
          {
            term: 'BUB1B',
            plain: 'encodes BUBR1, the core SAC protein; biallelic variants in it are the canonical cause of MVA (MVA type 1)',
          },
          {
            term: 'CEP57 / TRIP13',
            plain: 'the two other established MVA genes (types 2 and 3) — centrosome anchoring and checkpoint silencing',
          },
          {
            term: 'compound heterozygote',
            plain: 'two different broken copies of one gene, one from each parent. Each alone is harmless; together the gene has no working copy',
          },
          {
            term: 'biallelic',
            plain: 'both copies of the gene are affected — either the same variant twice (homozygous) or two different ones (compound het)',
          },
          {
            term: 'constraint (LOEUF / pLI)',
            plain:
              'how strongly the healthy population avoids losing a copy of a gene. LOEUF low (<0.35) or pLI near 1 = intolerant. It is a dominant-disease prior and inverts on recessive genes — see the constraint exhibit',
          },
          {
            term: 'ClinVar P/LP',
            plain:
              'the count of variants in a gene that clinical labs have already classified Pathogenic or Likely-pathogenic in the public ClinVar registry',
          },
          {
            term: 'variants per Mb',
            plain: 'records divided by the gene’s length in megabases; it makes a small gene comparable to a large one',
          },
        ]}
        caveat="Density per gene is a coverage and evidence measure, not a pathogenicity measure. A gene with more records is not more likely to be causal — it is only better observed."
      />

      <Callout tone="decision" title="What to look for on this page">
        The compound-heterozygous pair has to be <em>two different damaging variants in one gene</em>. That means
        a gene needs at least two candidate records, and it means suppressed records count: if half a gene's
        evidence is behind a FILTER, the pair may be half-hidden. <strong>TRIP13</strong> is the standout — an
        established MVA gene with 12 records of which 6 are suppressed. <strong>BUB1B</strong>, the canonical
        MVA gene, has the lowest PASS share among the well-covered genes at 95.0 %.
      </Callout>

      <Section title="Which candidate genes have evidence, and how much of it is suppressed?">
        <GeneScorecard />
      </Section>

      <Section
        title="What does the healthy population already say about these genes?"
        subtitle="constraint and ClinVar burden — background on each gene, deliberately not a ranking"
      >
        <ConstraintScorecard />
      </Section>

      <Section
        title="Open one gene"
        subtitle="the live endpoint pushes the contig down into the raw variant table — about 5 s on first request, cached after"
      >
        <LocusExplorer />
      </Section>

      <Section
        title="Which pairs inside a gene could actually be the answer?"
        subtitle={
          <>
            The answer to Track 1 is a <em>pair</em>, so the object to look at is the grid of pairs, not a
            list of variants. A compound heterozygote needs the two variants on <em>opposite</em> copies of
            the chromosome (<strong>trans</strong>); two on the same copy (<strong>cis</strong>) leave one
            working copy and are not a diagnosis. The only phase evidence in this data is physical phasing —
            variants seen together on one read pair — which reaches about 300 bp, so it settles a handful of
            pairs and leaves the rest open. That matters for the scorer directly: submitting a cis pair is a
            wrong answer that looks well-formed, and a proven-trans pair is the strongest configuration
            evidence available without parental samples.
          </>
        }
      >
        <PairMatrix />
      </Section>
    </div>
  );
}
