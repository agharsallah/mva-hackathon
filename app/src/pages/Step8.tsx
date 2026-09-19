import { useStep8 } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { Baseline } from './steps/step8/Baseline';
import { Deviation } from './steps/step8/Deviation';
import { Dosage } from './steps/step8/Dosage';
import { Limits } from './steps/step8/Limits';
import { dev, fraction } from './steps/step8/metrics';
import { Models } from './steps/step8/Models';

/**
 * Step 8 — how small a mosaic could we have seen?
 *
 * The page is arranged so the sample's answer cannot be read before the instrument's. Entry
 * 037 reported every autosome flat, using a statistic with no power for a mosaic gain: at
 * cell fraction f the heterozygous sites split into two bands symmetric about the centre, so
 * their mean does not move and "flat" is what any gain of any size would have produced. A
 * deviation chart shown first would invite exactly the same mistake a second time.
 *
 * So the power comparison and the detection limit come first, the sample's deviations
 * second, and the model comparison — which cannot separate the two trisomies at all — last.
 */
export default function Step8Page() {
  const q = useStep8();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            The disease this case is about is named for <strong>mosaic aneuploidy</strong>: some
            cells carry the wrong number of copies of a chromosome, and a different chromosome in
            different cells. Iteration 1 reported every autosome flat — but with a statistic that
            has <strong>no power for a mosaic gain</strong>, so that was an untested claim rather
            than a negative result. This step re-tests it with a statistic that does have power, and
            — the half that matters more — states{' '}
            <strong>how small an event each chromosome could have shown</strong>. A negative result
            without that number is not a result.
          </>
        }
        terms={[
          {
            term: 'B-allele fraction',
            dict: 'baf-b-allele-frequency',
            plain:
              'At a heterozygous site, the share of reads carrying the non-reference allele. Two intact copies put it near one half.',
          },
          {
            term: 'fold-over B-deviation',
            dict: 'b-deviation-bdev',
            plain:
              'Take |BAF − centre| at each site *before* averaging. A mosaic gain splits sites into two bands symmetric about the centre, so the plain mean does not move and the folded one does.',
          },
          {
            term: 'beta-binomial over-dispersion',
            dict: 'beta-binomial',
            plain:
              'Real allele balance scatters wider than a coin flip would. One parameter, rho, absorbs that — and without it every chromosome would look significant.',
          },
          {
            term: 'detection limit',
            dict: 'detection-limit',
            plain:
              'The smallest fraction of cells an event could have been in and still been found, at eight chances in ten. It is a property of the chromosome, not of the sample.',
          },
          {
            term: 'copy-neutral loss of heterozygosity',
            dict: 'copy-neutral-loss-of-heterozygosity-cn-loh',
            plain:
              'One copy replaced by a duplicate of the other. The allele balance shifts exactly as a gain would; only the read depth says which happened.',
          },
        ]}
      />

      <Loaded query={q} height={520}>
        {(data, meta) => {
          const chrome = { source: meta.source, cachedAt: meta.cachedAt, origin: meta.origin };
          const folded = data.limits.filter((row) => row.statistic === 'bdev');
          const meanStat = data.limits.filter((row) => row.statistic === 'mean_baf');
          const reached = folded.filter((row) => row.f80 !== null);
          const worst = reached.length
            ? Math.max(...reached.map((row) => row.f80 as number))
            : null;
          const flagged = data.bdev.filter((row) => row.arm === '' && row.exceeds_null);
          const autosomal = flagged.filter((row) => row.chrom !== 'X' && row.chrom !== 'Y');

          return (
            <div className="space-y-6">
              <Callout
                tone={autosomal.length === 0 ? 'good' : 'decision'}
                title={
                  autosomal.length === 0
                    ? 'Nothing above its own limit — and the limit is now a number'
                    : 'Contigs above their null, and what else could put them there'
                }
              >
                Fold-over deviation reaches 80% power on{' '}
                <strong>
                  {reached.length} of {folded.length}
                </strong>{' '}
                contigs; the statistic entry 037 used reaches it on{' '}
                <strong>{meanStat.filter((row) => row.f80 !== null).length}</strong>.{' '}
                {worst !== null && (
                  <>
                    The weakest autosome here still detects a mosaic present in{' '}
                    <strong>{fraction(worst)}</strong> of cells.{' '}
                  </>
                )}
                {autosomal.length > 0 && (
                  <>
                    <strong>{autosomal.map((row) => `chr${row.chrom}`).join(', ')}</strong> sit
                    above the null built from the genome-wide over-dispersion — read the ρ column
                    below before reading that as mosaicism, because a contig dispersed by its own
                    repeats exceeds that null too.{' '}
                  </>
                )}
                Every number on this page folds around {dev(data.constants.centre)}, not 0.5:
                reference reads map more readily, and folding around a half would turn that constant
                offset into a constant deviation everywhere.
              </Callout>

              <Section title="What this instrument could have seen">
                <Limits limits={data.limits} {...chrome} />
              </Section>

              <Section title="What this sample shows">
                <Deviation
                  bdev={data.bdev}
                  fractions={data.fractions}
                  models={data.models}
                  constants={data.constants}
                  {...chrome}
                />
              </Section>

              <Section title="The same question, asked of the raw reads">
                <Callout tone="machinery" title="A second instrument, blind in the opposite places">
                  Everything above reads the <em>called variants</em> — where allele balance sits at
                  heterozygous sites. This reads the <em>raw reads</em>: reference-unique 31-mers
                  are assigned one chromosome each and counted across the read store, so a
                  chromosome present in more copies is hit more often, in proportion. The two share
                  nothing past the FASTQ. Dosage sees <strong>X and Y</strong>, where this proband
                  has almost no heterozygous calls for the allele route to read; it is blind to{' '}
                  <strong>copy-neutral loss of heterozygosity</strong>, which changes whose copy is
                  present without changing how much sequence there is. Where both can see, they must
                  agree — and if they did not, the step would name one of them wrong rather than
                  average them.
                </Callout>
                <Dosage dosage={data.dosage ?? []} fractions={data.fractions} {...chrome} />
              </Section>

              <Section title="Which mechanism, if any, the data can name">
                <Callout tone="broken" title="None of them, and the table says why">
                  The five-model comparison put a trisomy first on almost every contig, at margins
                  in the hundreds — and{' '}
                  <strong>every one of those fits ends at a parameter bound</strong>. A boundary
                  solution is not an estimate: it says the shape the data wants is outside this
                  family rather than inside it at that value. The fitted &ldquo;cell fraction&rdquo;
                  tracks the fitted noise share, not anything biological. The one contig fitted
                  entirely in the interior is the one the family calls normal. So{' '}
                  <strong>no mechanism is reported for any chromosome</strong>, and the
                  allele-balance result above is untouched by it — that test compares against a null
                  fitted outside the family, which a nested comparison cannot do.
                </Callout>
                <Models fits={data.models} verdicts={data.verdicts} {...chrome} />
              </Section>

              <Section title="The denominator, and what a variegated genome does to it">
                <Baseline
                  baseline={data.baseline}
                  multi={data.multi}
                  density={data.density}
                  {...chrome}
                />
              </Section>

              <Callout tone="broken" title="What this step cannot tell you">
                <strong>Which tissue this is.</strong> Neither the clinical document nor the
                delivery says what was sequenced, and a karyotype&rsquo;s aneuploid fraction is
                measured in cultured cells. Every result here is &ldquo;in the sequenced
                sample&rdquo;, never equated with the diagnosis and never read as a severity
                statement — the clinical document lists no karyotype and no term a blood-DNA
                fraction would predict. <strong>Where an event is.</strong> The tables behind this
                page were aggregated to chromosome and arm before they existed, so a mosaic confined
                to part of an arm is invisible; whole-arm and whole-chromosome events are what is
                testable. <strong>Which trisomy.</strong> Mitotic and meiotic trisomy are nested
                models — the second is the first plus a balanced tract — so their margin is bounded
                below by one BIC penalty and a trisomy can be led but never confidently called.{' '}
                <strong>Anything below the identifiability floor.</strong> With the over-dispersion
                fitted per chromosome, a mixture under roughly 15% is absorbed by a single wider
                band; the detection limit above is lower than that because it compares against a
                null fitted elsewhere, which the model comparison cannot do.
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
