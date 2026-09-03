import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { GeneRanking } from './phenotype/GeneRanking';
import { MatchBreakdown } from './phenotype/MatchBreakdown';
import { ParentalDelta } from './phenotype/ParentalDelta';
import { TermSet } from './phenotype/TermSet';

/**
 * Phenotype — the only page whose numbers never touched the callset.
 *
 * Every other page in this app reasons forward from the sequencer: five million variants,
 * narrowed by filters, down to a candidate. This one reasons from the clinic instead —
 * eight symptoms a doctor wrote down, against public curation of what every gene is known
 * to cause — and it deliberately has no access to the variants, the candidate panel, or
 * the candidate list.
 *
 * That deliberate blindness is the entire point. The candidate list so far came out of an
 * eight-gene panel chosen by hand from what is known about this disease, which means it
 * cannot corroborate itself: the search found those genes because it only looked at them.
 * A ranking that never saw the panel and puts the same gene near the top of five thousand
 * is evidence of a different kind.
 */
export default function PhenotypePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            The child arrived with <strong>eight symptoms</strong>, written as ontology codes rather
            than prose. This page turns them into a ranking over every gene medicine has curated —
            roughly five thousand — <strong>without reading a single variant</strong>. It is the
            independent check on everything else in this app: the candidate list came from a panel
            of eight genes chosen because of what this disease is, and a prior cannot be its own
            evidence.
          </>
        }
        terms={[
          {
            term: 'HPO',
            plain: (
              <>
                the Human Phenotype Ontology — a controlled vocabulary of clinical features where
                each feature is a stable id, like an enum value instead of a string literal, so two
                doctors writing &ldquo;small head&rdquo; produce the same token
              </>
            ),
          },
          {
            term: 'information content',
            plain: (
              <>
                how surprising a feature is, as <code>−log(share of genes that cause it)</code>. A
                symptom thousands of genes produce proves nothing; one a handful produce proves a
                great deal. This is what stops a vague match scoring
              </>
            ),
          },
          {
            term: 'common ancestor',
            plain: (
              <>
                two features are compared by walking the ontology, never by comparing text.
                &ldquo;Rhabdomyosarcoma&rdquo; and &ldquo;nephroblastoma&rdquo; share no words and
                meet one step up at &ldquo;neoplasm&rdquo;; how rare <em>that</em> shared term is is
                how alike they are
              </>
            ),
          },
          {
            term: 'best-match-average',
            plain: (
              <>
                each feature takes its single strongest partner on the other side, and those bests
                are averaged. Taking the best lets a real match survive six unrelated features;
                averaging stops one lucky pairing carrying the score
              </>
            ),
          },
        ]}
      />

      <Callout tone="machinery" title="This is not Exomiser, and the difference is deliberate">
        Exomiser is the standard tool for this and it is a Java application whose data ships as H2
        database files — 31.5 GB unpacked, with no Python reader. Its <em>phenotype</em> inputs,
        though, are plain text, and the published optimisation study (Genome Medicine 17:127, 2025)
        measures its <strong>human-only</strong> configuration at 82.8% top-10 against 66.6% for the
        cross-species default. So the two components that are genuinely hard to reproduce — the
        protein-interaction random walk and the mouse and zebrafish models — are the ones the
        evidence says to switch off. What is left is a graph walk and a logarithm, which is what
        runs here: no JVM, under 100 MB of reference data. Nothing on this page may be reported as
        Exomiser output.
      </Callout>

      <Section title="The input">
        <TermSet />
      </Section>

      <Section title="The ranking">
        <GeneRanking />
        <MatchBreakdown />
      </Section>

      <Section title="The modelling choice inside the term set">
        <ParentalDelta />
      </Section>

      <Callout tone="decision" title="What a rank here is, and what it is not">
        This ranking is over <strong>genes</strong>, not variants. It says a gene is a plausible
        cause of these symptoms; it says nothing about which copies of it are broken, and fusing the
        two would launder a phenotype prior into per-variant evidence and count it twice. The
        confirmatory test is still outstanding: join this ranking to the callset&rsquo;s rare
        protein-altering alleles and check whether the top-ranked genes carrying a candidate pair
        are the ones the panel-first route already produced. That test can still refute what this
        page suggests, which is exactly why it is worth running.
      </Callout>
    </div>
  );
}
