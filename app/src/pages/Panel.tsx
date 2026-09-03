import { Link } from 'react-router-dom';

import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { ConstraintScorecard } from './panel/ConstraintScorecard';
import { GeneBackground } from './panel/GeneBackground';
import { GeneScorecard } from './panel/GeneScorecard';
import { LocusExplorer } from './panel/LocusExplorer';
import { PairMatrix } from './panel/PairMatrix';
import { ProteinCompareSection } from './panel/protein/compare/ProteinCompareSection';
import { ProteinExplorer } from './panel/protein/ProteinExplorer';
import { SuppressedCalls } from './panel/SuppressedCalls';

export default function PanelPage() {
  return (
    <div className="space-y-6">
      <Callout tone="decision" title="What to look for on this page">
        The compound-heterozygous pair has to be{' '}
        <em>two different damaging variants in one gene</em>. That means a gene needs at least two
        candidate records, and it means suppressed records count: if half a gene's evidence is
        behind a FILTER, the pair may be half-hidden. <strong>TRIP13</strong> is the standout — an
        established MVA gene with 12 records of which 6 are suppressed. <strong>BUB1B</strong>, the
        canonical MVA gene, has the lowest PASS share among the well-covered genes at 95.0 %.
      </Callout>

      <Explainer
        intro={
          <>
            MVA has a small set of genes behind it in the literature, all of them parts of the
            machinery that makes sure a dividing cell hands each daughter exactly one copy of every
            chromosome. This page narrows the 5 million genome-wide records down to those gene
            intervals, asks how much evidence each gene actually has, and then lets you open one
            gene and look at every record inside it.
          </>
        }
        terms={[
          {
            term: 'gene panel',
            plain:
              'a hand-picked list of gene intervals to search first — an allowlist over the genome',
          },
          {
            term: 'BED file',
            plain:
              'the interval format the panel is stored in: contig, start, end, name — one row per region',
          },
          {
            term: 'spindle assembly checkpoint (SAC)',
            plain:
              'the cell’s pre-division gate: it halts division until every chromosome is correctly attached. Break it and chromosomes get miscounted — that is MVA',
          },
          {
            term: 'BUB1B',
            plain:
              'encodes BUBR1, the core SAC protein; biallelic variants in it are the canonical cause of MVA (MVA type 1)',
          },
          {
            term: 'CEP57 / TRIP13',
            plain:
              'the two other established MVA genes (types 2 and 3) — centrosome anchoring and checkpoint silencing',
          },
          {
            term: 'compound heterozygote',
            plain:
              'two different broken copies of one gene, one from each parent. Each alone is harmless; together the gene has no working copy',
          },
          {
            term: 'biallelic',
            plain:
              'both copies of the gene are affected — either the same variant twice (homozygous) or two different ones (compound het)',
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
            plain:
              'records divided by the gene’s length in megabases; it makes a small gene comparable to a large one',
          },
        ]}
        caveat="Density per gene is a coverage and evidence measure, not a pathogenicity measure. A gene with more records is not more likely to be causal — it is only better observed."
      />

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
        title="Is any of that unusual for where the gene sits?"
        subtitle="each gene's density and PASS share z-scored against the 1 Mb windows of its own chromosome and of the whole callset"
      >
        <GeneBackground />
      </Section>

      <Section
        title="What did the caller throw away here?"
        subtitle={
          <>
            Every other exhibit on this page reads <span className="font-mono">PASS</span> records
            only. This one reads the rest. A <span className="font-mono">FILTER</span> value is a
            warning label the caller wrote on a record it <em>kept</em>, not a deletion — and the
            heaviest label genome-wide, <span className="font-mono">MQ40</span>, fires precisely in
            repetitive sequence where a real variant is hardest to call. The compound-heterozygous
            pair needs two damaging alleles in one gene, so if the second one is behind a flag, a
            PASS-only search reports the gene as carrying one.
          </>
        }
      >
        <SuppressedCalls />
      </Section>

      <Section
        title="Open one gene"
        subtitle="the live endpoint pushes the contig down into the raw variant table — about 5 s on first request, cached after"
      >
        <LocusExplorer />
      </Section>

      <Section
        title="Where do those alleles sit in the folded protein?"
        subtitle={
          <>
            The lollipop above is a 1D axis: it answers <em>which domain</em>. It cannot answer the
            question that decides a compound heterozygote, which is whether the two alleles are
            close <em>in space</em> — a protein folds, so two residues 300 amino acids apart on the
            chain can pack into one binding pocket while two neighbours point at opposite faces.
            This exhibit draws the fold itself: a tube through the{' '}
            <strong>alpha carbons (Cα)</strong> — the one backbone atom every amino acid has, so a
            chain of Cα positions is the protein&apos;s spine — and measures the straight-line{' '}
            <strong>Cα distance</strong> between alleles in <strong>ångström</strong> (Å, 10⁻¹⁰ m; a
            chemical bond is ~1.5 Å, a whole domain ~30–40 Å across). The coordinates are an{' '}
            <strong>AlphaFold</strong> prediction, not an experiment, so every residue carries{' '}
            <strong>pLDDT</strong> — AlphaFold&apos;s own 0–100 confidence in{' '}
            <em>that residue's position</em>. Below 70 the position supports no spatial claim and
            the exhibit greys it out by default. Think of it as a type system for the picture: the
            geometry is only as trustworthy as the confidence annotation at both ends of the
            measurement.
          </>
        }
      >
        <ProteinExplorer />
      </Section>

      <Section
        title="Is that fold unusual, or is that just what AlphaFold looks like?"
        subtitle={
          <>
            One predicted model gives no scale. &quot;62 % of this protein is above pLDDT 70&quot;
            is unreadable until the same number sits beside another protein&apos;s — so this section
            widens the exhibit from the eight annotated panel genes to a curated{' '}
            <strong>structure set</strong>: the panel, the other established MVA and{' '}
            <strong>spindle-assembly-checkpoint</strong> genes, and an extended reference group. Two
            of those three groups are <strong>fold-only</strong>: the AlphaFold model is public
            reference data, identical for every human, but <em>no allele is painted on it</em> — the
            variant calls were annotated only over the eight-gene panel BED (see &quot;Open one
            gene&quot; above), so an off-panel gene has an empty candidate list{' '}
            <strong>because the annotation never ran there</strong>, not because the proband is
            clean at that locus. That distinction is the reason every off-panel canvas carries a
            callout and every off-panel allele cell reads <em>n/a — fold only</em> instead of 0. In
            software terms: the annotation stage&apos;s input was an allowlist of eight intervals,
            so the absence of a row outside it is a statement about the pipeline&apos;s scope, never
            about the data.
          </>
        }
      >
        <ProteinCompareSection />
      </Section>

      <Section
        title="Which pairs inside a gene could actually be the answer?"
        subtitle={
          <>
            The answer to Track 1 is a <em>pair</em>, so the object to look at is the grid of pairs,
            not a list of variants. A compound heterozygote needs the two variants on{' '}
            <em>opposite</em> copies of the chromosome (<strong>trans</strong>); two on the same
            copy (<strong>cis</strong>) leave one working copy and are not a diagnosis. The only
            phase evidence in this data is physical phasing — variants seen together on one read
            pair — which reaches about 300 bp, so it settles a handful of pairs and leaves the rest
            open. That matters for the{' '}
            <Link
              to="/probes"
              className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
            >
              scorer
            </Link>{' '}
            directly: submitting a cis pair is a wrong answer that looks well-formed, and a
            proven-trans pair is the strongest configuration evidence available without parental
            samples.
          </>
        }
      >
        <PairMatrix />
      </Section>
    </div>
  );
}
