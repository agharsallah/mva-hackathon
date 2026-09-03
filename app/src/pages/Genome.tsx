import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { AlleleBalance } from './genome/AlleleBalance';
import { BafKaryogram } from './genome/BafKaryogram';
import { DensityBins } from './genome/DensityBins';
import { DepthVaf } from './genome/DepthVaf';
import { Karyotype } from './genome/Karyotype';

export default function GenomePage() {
  return (
    <div className="space-y-6">
      <Callout tone="decision" title="The headline result, stated before you look">
        MVA is defined by aneuploidy, and this genome shows none at the whole-chromosome level.
        Every autosome sits on the 0.5 allele-balance line and at the autosomal mean depth. The only
        flagged contig is Y, and that is expected: the sample is male, so Y has a single copy and
        its heterozygous calls are mapping artefacts rather than biology.{' '}
        <strong>Consequence for the case:</strong> the causal mechanism must be a coding change in a
        chromosome-segregation gene, not a detectable copy-number event — which is exactly what a
        recessive compound-heterozygous MVA gene predicts.
      </Callout>

      <Explainer
        intro={
          <>
            MVA means cells carry the wrong number of chromosomes. If that were happening in the
            sequenced tissue at appreciable fraction, it would leave two measurable traces:
            heterozygous sites on the affected chromosome would stop reading 50/50, and that
            chromosome's read depth would shift away from the rest of the genome.
          </>
        }
        terms={[
          {
            term: 'VAF (variant allele fraction)',
            dict: 'vaf-variant-allele-fraction',
            plain:
              'the share of reads at a site that show the variant — about 0.5 is expected for a heterozygous site on two intact copies',
          },
          {
            term: 'heterozygous',
            dict: 'zygosity',
            plain:
              'the two copies of a chromosome differ at this position: one reference, one variant',
          },
          {
            term: 'aneuploidy',
            dict: 'aneuploidy',
            plain:
              'a cell has an extra or missing whole chromosome; "mosaic" means only some cells do',
          },
          {
            term: 'depth (×)',
            dict: 'coverage-depth-e-g-30',
            plain:
              'reads stacked over a position; a lost chromosome copy halves it, a gained one raises it ~1.5×',
          },
          {
            term: 'contig',
            dict: 'contig',
            plain:
              'a named sequence in the reference. 25 are the real chromosomes; the other 1,665 are alternate haplotypes and unplaced scaffolds',
          },
          {
            term: 'megabase (Mb)',
            plain: 'one million DNA letters — the bin size used for the density views',
          },
          {
            term: 'centromere',
            plain:
              'the highly repetitive middle of a chromosome; reads cannot be placed uniquely there, so callers go quiet',
          },
          {
            term: 'hemizygous',
            plain:
              'only one copy exists (X and Y in a male sample), so a "heterozygous" call there is suspicious by construction',
          },
        ]}
        caveat="A bulk whole-genome sample averages over millions of cells. Low-fraction mosaicism dilutes into the noise, so a clean result here bounds the effect — it does not disprove mosaicism outright."
      />

      <Section title="Is any chromosome present in the wrong number of copies?">
        <div className="grid gap-4 lg:grid-cols-2">
          <AlleleBalance />
          <DepthVaf />
        </div>
      </Section>

      <Section
        title="Would a shifted segment survive the chromosome average?"
        subtitle="A whole-chromosome mean hides a mosaic arm. The same allele-balance question, re-asked one megabase at a time."
      >
        <BafKaryogram />
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
