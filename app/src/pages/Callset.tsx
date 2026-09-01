import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { Funnel } from './callset/Funnel';
import { DepthHistogram } from './callset/DepthHistogram';
import { Substitutions } from './callset/Substitutions';
import { IndelLengths } from './callset/IndelLengths';
import { ZygositySplit } from './callset/ZygositySplit';
import { HeaderFields } from './callset/HeaderFields';

export default function CallsetPage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            The callset is a delivered artefact, produced by somebody else's pipeline. Before using it to make
            a clinical claim we have to know two things: is it a normal, healthy callset (or is it full of
            technical artefacts), and what exactly did the caller decide to suppress. Read this page as quality
            control on the input, not as biology.
          </>
        }
        terms={[
          {
            term: 'variant caller',
            plain: 'the program that turned piles of reads into variant records; think of it as a lossy compiler with heuristics',
          },
          {
            term: 'FILTER',
            plain: 'the caller’s heuristic vetoes on a record. PASS means no veto fired; a non-PASS record is suppressed, not deleted',
          },
          {
            term: 'QUAL',
            plain: 'the caller’s confidence that there is a variant here at all, on a phred scale',
          },
          {
            term: 'phred quality',
            plain: 'a log-scale error probability. Q10 = 1 in 10 wrong, Q20 = 1 in 100, Q30 = 1 in 1000',
          },
          {
            term: 'MQ (mapping quality)',
            plain: 'the aligner’s confidence that the reads belong at this locus at all. MQ40 filter = below 40, so possibly mismapped',
          },
          {
            term: 'QD (quality by depth)',
            plain: 'QUAL divided by depth — catches sites that look confident only because they are deeply covered',
          },
          {
            term: 'transition / transversion',
            plain: 'A↔G and C↔T are transitions (chemically easy); the other eight swaps are transversions. Their ratio is a callset sanity check',
          },
          {
            term: 'frameshift',
            plain: 'an insertion or deletion whose length is not a multiple of three; it garbles every amino acid downstream and usually kills the protein',
          },
        ]}
        caveat="Suppressed records stay in scope for this case. In an N-of-1 search, discarding 271,414 records because a general-purpose heuristic disliked them is a decision, not a given."
      />

      <Callout tone="decision" title="Why the suppressed set matters here">
        94.58 % of records are PASS, which is normal. The remaining <strong>271,414</strong> failed a heuristic
        built for population-scale studies where a false positive is expensive and a false negative is cheap.
        For one child with an undiagnosed condition that trade is inverted. Any candidate gene must therefore be
        checked in the suppressed set too — the Panel page does exactly that, and TRIP13 is the case in point
        (half its records are non-PASS).
      </Callout>

      <Section title="What survived the caller's filters">
        <Funnel />
      </Section>

      <Section title="Is this a normal, healthy callset?">
        <div className="grid gap-4 xl:grid-cols-2">
          <DepthHistogram />
          <Substitutions />
          <IndelLengths />
        </div>
      </Section>

      <Section
        title="One copy or two — and the trap in how bcftools labelled it"
        subtitle="The stats file calls this section “allele frequency”. With one sample it is nothing of the kind."
      >
        <ZygositySplit />
      </Section>

      <Section
        title="What the callset says about itself"
        subtitle="The VCF header is a self-describing schema. This is the evidence that it ships no annotation worth ranking on."
      >
        <HeaderFields />
      </Section>
    </div>
  );
}
