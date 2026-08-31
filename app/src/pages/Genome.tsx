import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { AlleleBalance } from './genome/AlleleBalance';
import { DepthVaf } from './genome/DepthVaf';
import { Karyotype } from './genome/Karyotype';
import { DensityBins } from './genome/DensityBins';

export default function GenomePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            MVA means cells carry the wrong number of chromosomes. If that were happening in the sequenced
            tissue at appreciable fraction, it would leave two measurable traces: heterozygous sites on the
            affected chromosome would stop reading 50/50, and that chromosome's read depth would shift away
            from the rest of the genome. This page tests both, chromosome by chromosome, and then looks at how
            calls are distributed along each one.
          </>
        }
        terms={[
          {
            term: 'VAF (variant allele fraction)',
            plain: 'the share of reads at a site that show the variant — about 0.5 is expected for a heterozygous site on two intact copies',
          },
          {
            term: 'heterozygous',
            plain: 'the two copies of a chromosome differ at this position: one reference, one variant',
          },
          {
            term: 'aneuploidy',
            plain: 'a cell has an extra or missing whole chromosome; "mosaic" means only some cells do',
          },
          {
            term: 'depth (×)',
            plain: 'reads stacked over a position; a lost chromosome copy halves it, a gained one raises it ~1.5×',
          },
          {
            term: 'contig',
            plain: 'a named sequence in the reference. 25 are the real chromosomes; the other 1,665 are alternate haplotypes and unplaced scaffolds',
          },
          {
            term: 'megabase (Mb)',
            plain: 'one million DNA letters — the bin size used for the density views',
          },
          {
            term: 'centromere',
            plain: 'the highly repetitive middle of a chromosome; reads cannot be placed uniquely there, so callers go quiet',
          },
          {
            term: 'hemizygous',
            plain: 'only one copy exists (X and Y in a male sample), so a "heterozygous" call there is suspicious by construction',
          },
        ]}
        caveat="A bulk whole-genome sample averages over millions of cells. Low-fraction mosaicism dilutes into the noise, so a clean result here bounds the effect — it does not disprove mosaicism outright."
      />

      <Callout tone="decision" title="The headline result, stated before you look">
        MVA is defined by aneuploidy, and this genome shows none at the whole-chromosome level. Every autosome
        sits on the 0.5 allele-balance line and at the autosomal mean depth. The only flagged contig is Y, and
        that is expected: the sample is male, so Y has a single copy and its heterozygous calls are mapping
        artefacts rather than biology. <strong>Consequence for the case:</strong> the causal mechanism must be
        a coding change in a chromosome-segregation gene, not a detectable copy-number event — which is exactly
        what a recessive compound-heterozygous MVA gene predicts.
      </Callout>

      <Section title="Is any chromosome present in the wrong number of copies?">
        <div className="grid gap-4 xl:grid-cols-2">
          <AlleleBalance />
          <DepthVaf />
        </div>
      </Section>

      <Section title="How is the callset laid out over the genome?">
        <div className="space-y-4">
          <Karyotype />
          <DensityBins />
        </div>
      </Section>
    </div>
  );
}
