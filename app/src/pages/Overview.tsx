import { Link } from 'react-router-dom';

import { useObservedExpected, useOverview } from '../api/hooks';
import { JourneyMap } from '../components';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { NormChip } from '../components/NormChip';
import { pickNorm } from '../components/pickNorm';
import { ErrorCard, Skeleton } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { compact, dec, int, pct } from '../lib/format';
import { GenotypeDonut } from './overview/GenotypeDonut';

export default function OverviewPage() {
  const q = useOverview();
  // Same payload the Compare page grades against, reused here so a tile can say whether
  // its own figure is normal. Its loading state is never waited on: a tile renders
  // exactly as before until the verdict arrives, and forever if there is no norm for it.
  const norms = useObservedExpected().data?.data;

  return (
    <div className="space-y-6">
      <Section
        title="The case in numbers"
        subtitle="all figures from executed runs over the delivered objects"
      >
        {q.isPending && (
          <Skeleton height={220} variant="tiles" framed label="Loading the case numbers" />
        )}
        {q.error && <ErrorCard error={q.error} />}
        {q.data && (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4">
              <StatTile
                label="variants called"
                value={compact(q.data.data.total_variants)}
                sub={`${int(q.data.data.total_variants)} records`}
                tone="raw"
                hint="Rows in the delivered VCF, one per ALT record."
                chip={
                  <NormChip row={pickNorm(norms, ['variant_sites_per_genome', 'total_variants'])} />
                }
              />
              <StatTile
                label="PASS share"
                value={pct((q.data.data.pass_variants / q.data.data.total_variants) * 100)}
                sub={`${int(q.data.data.pass_variants)} PASS · ${int(
                  q.data.data.total_variants - q.data.data.pass_variants,
                )} suppressed`}
                tone="good"
                hint="Suppressed records are kept: a filtered call is a hypothesis, not a deletion."
              />
              <StatTile
                label="compound-het sites (1/2)"
                value={compact(q.data.data.multiallelic_sites)}
                sub={`${int(q.data.data.multiallelic_sites)} sites, both copies altered`}
                tone="decision"
                hint="Two different non-reference alleles at one site."
              />
              <StatTile
                label="Ts/Tv"
                value={dec(q.data.data.tstv, 2)}
                sub="≈2.0 expected for a clean human WGS callset"
                tone="good"
                chip={<NormChip row={pickNorm(norms, ['tstv_genome_wide', 'tstv'])} />}
              />
              <StatTile
                label="reads sequenced"
                value={compact(q.data.data.total_reads)}
                sub={`${int(q.data.data.total_reads)} × ${q.data.data.read_length} bp`}
                tone="raw"
              />
              <StatTile
                label="coverage"
                value={`${dec(q.data.data.est_coverage_x, 1)}×`}
                sub={`raw · ${dec(q.data.data.mean_depth_x, 0)}× mean called depth`}
                tone="good"
                chip={<NormChip row={pickNorm(norms, ['mean_coverage_wgs', 'mean_depth'])} />}
              />
              <StatTile
                label="samples"
                value={int(q.data.data.samples)}
                sub="no trio — parents were not sequenced"
                tone="decision"
                hint="Any inheritance claim must come from evidence other than parental genotypes."
              />
              <StatTile
                label="probe budget"
                value={`${q.data.data.probe_budget_spent}/${q.data.data.probe_budget_total}`}
                sub="oracle queries spent"
                tone={q.data.data.probe_budget_spent === 0 ? 'good' : 'decision'}
              />
            </div>
            <div className="grid gap-3 lg:grid-cols-3">
              <Callout tone="decision" title="The single-sample constraint">
                A compound heterozygote is normally proven by showing one variant came from each
                parent. With no trio, the only genotype-level proof available is the{' '}
                <strong>1/2</strong> call: {int(q.data.data.multiallelic_sites)} sites where the
                caller itself recorded two different alternate alleles on the two copies. No parents
                were sequenced, so nothing here can be <strong>phased by inheritance</strong>{' '}
                (assigned to the copy it came from) — the app never shows a parent column.
              </Callout>
              <Callout tone="neutral" title="Contigs">
                {q.data.data.canonical_contigs} canonical chromosomes out of{' '}
                {int(q.data.data.all_contigs)} contigs in the reference header. The other{' '}
                {int(q.data.data.all_contigs - q.data.data.canonical_contigs)} are alternate
                haplotypes and unplaced scaffolds — excluded from every per-chromosome figure so
                densities stay comparable.
              </Callout>
              <Callout
                tone={q.data.data.all_hashes_verified ? 'good' : 'broken'}
                title="Provenance"
              >
                {q.data.data.delivery_objects} delivered objects,{' '}
                {q.data.data.all_hashes_verified
                  ? 'every sha256 verified'
                  : 'HASH VERIFICATION INCOMPLETE'}
                .{' '}
                <Link
                  to="/catalog"
                  className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
                >
                  inventory on the Catalog page
                </Link>
              </Callout>
            </div>
          </>
        )}
      </Section>

      <Section
        title="Five questions, in reading order"
        subtitle="each page serves one question; the header shows which"
      >
        <JourneyMap />
      </Section>

      <Explainer
        intro={
          <>
            The clinical question is Mosaic Variegated Aneuploidy (MVA) — cells ending up with the
            wrong number of chromosomes. The task: find the causal{' '}
            <strong>compound heterozygous</strong> pair — two different broken copies of one gene,
            one inherited from each parent. This dataset holds <strong>one sample</strong> only.
          </>
        }
        terms={[
          {
            term: 'variant',
            dict: 'variant',
            plain:
              'one row in the callset: a position where this genome differs from the reference',
          },
          {
            term: 'VCF (Variant Call Format)',
            dict: 'vcf-variant-call-format',
            plain:
              'the row-oriented text format the variants were delivered in, one record per line',
          },
          {
            term: 'SNP (single nucleotide polymorphism)',
            plain: 'a one-letter substitution, e.g. C changed to T',
          },
          {
            term: 'indel (insertion or deletion)',
            dict: 'indel',
            plain: 'letters added or removed rather than swapped',
          },
          {
            term: 'FILTER / PASS',
            dict: 'filter-pass',
            plain:
              'the caller’s heuristic veto; non-PASS records are suppressed, not deleted — they are still a search space',
          },
          {
            term: 'multiallelic site (genotype 1/2)',
            dict: '1-2-genotype-multiallelic-site',
            plain:
              'the two copies carry two different variants — a compound heterozygote established by the genotype field alone',
          },
          {
            term: 'Ts/Tv (transition / transversion ratio)',
            dict: 'ti-tv-ratio',
            plain:
              'a sanity check on the callset; ~2.0 is normal for human whole genomes, far off means artefacts',
          },
          {
            term: 'coverage / depth (×)',
            dict: 'coverage-depth-e-g-30',
            plain:
              'how many sequencing reads stack over an average base; more depth means more confident calls',
          },
          {
            term: 'read',
            dict: 'read',
            plain:
              'one short sequenced fragment (149 letters here); a genome is reconstructed by piling up a billion of them',
          },
          {
            term: 'probe budget',
            dict: 'probe-ledger',
            plain:
              'this challenge allows 6 oracle queries in total — a hard, non-renewable resource',
          },
        ]}
        caveat="Every figure in this app is an aggregate. No individual genomic coordinate is stored in this repository."
      />

      <Section title="What the genotypes already tell us">
        <GenotypeDonut />
      </Section>
    </div>
  );
}
