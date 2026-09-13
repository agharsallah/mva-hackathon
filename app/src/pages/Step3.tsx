import { useStep3 } from '../api/hooks';
import { Section } from '../components/Controls';
import { Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Plot } from '../components/Plot';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { Confirmation } from './steps/step3/Confirmation';
import { Leads } from './steps/step3/Leads';
import { count, fitted, reachLabel, share, targetTotals } from './steps/step3/metrics';

/**
 * Step 3 — the same reads, read a third way.
 *
 * Step 2 found alleles by aligning reads and running two callers over them. Both are models
 * with assumptions: where a read belongs, what a haplotype looks like. This step counts how
 * often each allele's 31-letter spelling appears and asks neither question. Where the two
 * agree an allele has survived a genuinely disjoint instrument; where they disagree, the
 * disagreement is the finding.
 *
 * The page leads with the result that cost step 2 its headline: the 1,199 alleles the
 * delivered callset never reported are confirmed at about a third, while the alleles it did
 * report are confirmed at about nineteen in twenty. Same instrument, same run, same genes.
 */
export default function Step3Page() {
  const q = useStep3();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Step 2 read the raw reads with an <strong>aligner</strong> and two{' '}
            <strong>callers</strong>. This step reads the same bytes with neither: it writes out the
            31 letters around each allele twice — as the reference has them, as the allele has them
            — and <strong>counts</strong> how often each spelling appears. One copy puts a spelling
            into about half the reads covering it, two into nearly all, none into a handful from
            sequencing error.
          </>
        }
        terms={[
          {
            term: 'k-mer genotype',
            dict: 'k-mer-genotype',
            plain:
              'Reading how many copies of a gene carry an allele by counting its 31-letter spelling in the reads, with no aligner and no caller in the chain.',
          },
          {
            term: 'negative binomial',
            dict: 'negative-binomial',
            plain:
              'A distribution for counts that are more spread out than chance alone would make them — which sequencing depth always is.',
          },
          {
            term: 'no-call',
            dict: 'no-call',
            plain:
              '"The instrument could not say." Recorded as its own answer, because it is a different finding from "the allele is absent".',
          },
          {
            term: 'reachability',
            dict: 'reachability',
            plain:
              'Whether a gene can be measured at all here — enough unique bait, and reads the aligner was willing to place.',
          },
        ]}
      />

      <Callout tone="broken" title="The claim this step was built around is refuted">
        Step 2 found 1,199 alleles the delivered callset never reported, and six of ten target genes
        reached a biallelic candidate <em>only</em> through them. This step predicted, in writing
        and before it ran, that at least 80% would be confirmed by an independent instrument. About
        a third were. Every biallelic count that rested on them is an upper bound, and the read
        route now carries a measured per-allele error rate instead of a caveat.
      </Callout>

      <Loaded query={q} height={420}>
        {(data) => {
          const reported = targetTotals(data.confirmation, false);
          const novel = targetTotals(data.confirmation, true);
          const lambda = fitted(data.calibration, 'lambda_per_copy');
          const vmr = fitted(data.calibration, 'variance_to_mean');
          const noCall = data.calls.reduce(
            (sum, row) => sum + (row.call === 'no-call' ? row.alleles : 0),
            0,
          );

          return (
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="vendor-reported alleles confirmed"
                  value={share(reported.rate)}
                  tone="good"
                  sub={`${count(reported.confirmed)} of ${count(reported.probed)} in target genes`}
                  hint="this is the control: it says the instrument works"
                />
                <StatTile
                  label="vendor-unreported alleles confirmed"
                  value={share(novel.rate)}
                  tone="broken"
                  sub={`${count(novel.confirmed)} of ${count(novel.probed)}; the claim named 80%`}
                  hint="same instrument, same run, same genes — so this is about the alleles"
                />
                <StatTile
                  label="per-copy coverage, fitted"
                  value={lambda ? `${lambda.toFixed(2)}×` : '—'}
                  sub={
                    lambda
                      ? `${(2 * lambda).toFixed(1)}× diploid, against 35.2× predicted from read length alone`
                      : undefined
                  }
                  hint="a k-mer is only seen when a read contains it whole: 44.08 × 119/149"
                />
                <StatTile
                  label="no-calls"
                  value={count(noCall)}
                  tone="decision"
                  sub="mostly published alleles that could not be given three usable probes"
                  hint="recorded as an answer, not dropped"
                />
              </div>

              <Section title="What a second instrument says about the first one's alleles">
                <Exhibit
                  title="Confirmation, split by whether the delivered callset had ever seen the allele"
                  legend={
                    <>
                      <strong style={{ color: C.good }}>green</strong> = genes the symptoms
                      nominated · <strong>grey</strong> = the matched decoys ·{' '}
                      <strong style={{ color: C.decision }}>dashed</strong> = the 80% this step
                      pre-registered. Targets and decoys sit on top of each other in both columns,
                      which is what H020&rsquo;s refutation predicts: the read route has no
                      discriminating power of its own.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.contrast}
                >
                  <Plot
                    height={360}
                    data={[
                      {
                        type: 'bar',
                        name: 'target genes',
                        x: data.contrast.map((row) => row.allele_set),
                        y: data.contrast.map((row) => row.target_rate),
                        marker: { color: C.good },
                      },
                      {
                        type: 'bar',
                        name: 'decoy genes',
                        x: data.contrast.map((row) => row.allele_set),
                        y: data.contrast.map((row) => row.decoy_rate),
                        marker: { color: C.absent },
                      },
                    ]}
                    layout={{
                      barmode: 'group',
                      yaxis: { title: 'confirmed', tickformat: '.0%', range: [0, 1.05] },
                      shapes: [
                        {
                          type: 'line',
                          xref: 'paper',
                          x0: 0,
                          x1: 1,
                          y0: 0.8,
                          y1: 0.8,
                          line: { dash: 'dash', color: C.decision },
                        },
                      ],
                    }}
                  />
                </Exhibit>
                <Exhibit
                  title="The same numbers, counted"
                  legend={
                    <>
                      Four numbers rather than one rate. A single confirmation figure invites
                      reading a target-gene result as worth more than a decoy&rsquo;s, which is the
                      reading the decoy set exists to prevent.
                    </>
                  }
                  source={q.data?.source}
                  data={data.contrast}
                >
                  <Confirmation rows={data.contrast} />
                </Exhibit>
              </Section>

              <Section title="What the model said, and where it declined to say">
                <Exhibit
                  title="Calls per tier, no-call included"
                  legend={
                    <>
                      <strong style={{ color: C.good }}>green</strong> = heterozygous ·{' '}
                      <strong style={{ color: C.machinery }}>blue</strong> = homozygous alternate ·{' '}
                      <strong>grey</strong> = homozygous reference ·{' '}
                      <strong style={{ color: C.broken }}>red</strong> = no-call. A no-call is a bar
                      here and not a gap: &ldquo;could not say&rdquo; and &ldquo;not there&rdquo;
                      are different findings.
                    </>
                  }
                  source={q.data?.source}
                  data={data.calls}
                >
                  <Plot
                    height={360}
                    data={['het', 'hom-alt', 'hom-ref', 'no-call'].map((label, index) => ({
                      type: 'bar' as const,
                      name: label,
                      x: [...new Set(data.calls.map((row) => row.tier))],
                      y: [...new Set(data.calls.map((row) => row.tier))].map((tier) =>
                        data.calls
                          .filter((row) => row.tier === tier && row.call === label)
                          .reduce((sum, row) => sum + row.alleles, 0),
                      ),
                      marker: { color: [C.good, C.machinery, C.absent, C.broken][index] },
                    }))}
                    layout={{ barmode: 'stack', yaxis: { title: 'alleles' } }}
                  />
                </Exhibit>
              </Section>

              <Section title="What could be measured at all">
                <Exhibit
                  title="Genes the stage-0 gate excluded still yield some genotypes"
                  legend={
                    <>
                      The reachability rule was fixed <em>before</em> the run: a gene is excluded
                      when its bait density is below half the median, or more than half its reads
                      carry MAPQ&nbsp;0. It predicted excluded genes would yield none. They yield
                      some — so the rule is reported as conservative rather than absolute, and an
                      absence inside one is still not a finding.
                    </>
                  }
                  source={q.data?.source}
                  data={data.reach}
                >
                  <Plot
                    height={320}
                    data={[
                      {
                        type: 'bar',
                        x: data.reach.map(reachLabel),
                        y: data.reach.map((row) => row.confident_fraction ?? 0),
                        text: data.reach.map((row) => `${count(row.genes)} genes`),
                        textposition: 'outside',
                        marker: {
                          color: data.reach.map((row) => (row.reachable ? C.good : C.broken)),
                        },
                      },
                    ]}
                    layout={{
                      yaxis: {
                        title: 'alleles called confidently',
                        tickformat: '.0%',
                        range: [0, 1.05],
                      },
                    }}
                  />
                </Exhibit>
                {vmr !== undefined && (
                  <Exhibit
                    title="The fit, and the checks that say whether to believe it"
                    legend={
                      <>
                        Every row is a number the model was fitted to, not chosen. The
                        variance-to-mean ratio is {vmr.toFixed(2)} where a Poisson model predicts
                        exactly 1 — so a Poisson model would have been about three times too
                        confident about every count it saw.
                      </>
                    }
                    source={q.data?.source}
                    data={data.calibration}
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="text-xs text-chrome-400">
                          <tr className="border-b border-chrome-800">
                            <th className="py-1 pr-3 text-left">metric</th>
                            <th className="py-1 pr-3 text-right">value</th>
                            <th className="py-1 text-left">what it is</th>
                          </tr>
                        </thead>
                        <tbody className="tabular-nums">
                          {data.calibration.map((row) => (
                            <tr key={row.metric} className="border-b border-chrome-900/60">
                              <td className="py-1 pr-3 font-medium">{row.metric}</td>
                              <td className="py-1 pr-3 text-right">{row.value.toLocaleString()}</td>
                              <td className="py-1 text-chrome-400">{row.note}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Exhibit>
                )}
              </Section>

              <Section title="Every gene still carrying two confirmed alleles">
                <Exhibit
                  title="Confirmed biallelic genes, targets and decoys together"
                  legend={
                    <>
                      No rarity or consequence filter is applied here, and that is why the decoys
                      keep pace: everybody carries roughly two heterozygous differences per gene.
                      The discriminating power is in the filter, never in the gene list — the same
                      lesson step 2 recorded.
                    </>
                  }
                  source={q.data?.source}
                  data={data.leads}
                >
                  <Leads rows={data.leads} />
                </Exhibit>
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
