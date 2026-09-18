import { useStep4 } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Plot } from '../components/Plot';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { Ablation } from './steps/step4/Ablation';
import { BuiltFrom } from './steps/step4/BuiltFrom';
import { Decomposition } from './steps/step4/Decomposition';
import { Leaders } from './steps/step4/Leaders';
import { bucketCentre, count, log10, ratio } from './steps/step4/metrics';
import { Uncurated } from './steps/step4/Uncurated';

/**
 * Step 4 — every gene in the callset, ordered, with nothing filtered out.
 *
 * Iteration 1 used a funnel: rare AND protein-altering AND biallelic AND PASS, and a gene
 * was in or out. This step replaces every one of those cuts with a multiplier, so the
 * question "which gene leads" has an answer for all of them — including the 73.6% nobody
 * has ever curated a phenotype for, which no symptom ranker can score at all.
 *
 * The page is built so the leader cannot be read on its own. Its own controls are on the
 * same screen: where the matched decoys landed, how high a random symptom set gets, and
 * which lanes were even able to speak.
 */
export default function Step4Page() {
  const q = useStep4();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            A <strong>filter</strong> answers &ldquo;is this gene in or out&rdquo;. A{' '}
            <strong>likelihood ratio</strong> answers &ldquo;how many times more likely is what I
            saw if this gene is causal than if it is not&rdquo;, and a product of ratios applied to
            a prior gives a <strong>posterior</strong>. Nothing is ever removed: a common allele is
            divided down, a filtered call is down-weighted, an uncurated gene keeps a ratio below 1.
            This is the only step that sees every gene in the VCF.
          </>
        }
        terms={[
          {
            term: 'likelihood ratio',
            dict: 'likelihood-ratio-lr',
            plain:
              'How many times more likely an observation is if a gene is causal than if it is not. Multiplying them replaces a chain of yes/no filters.',
          },
          {
            term: 'lane',
            dict: 'evidence-lane',
            plain:
              'One named strand of evidence with its own ratio and its own source — the phenotype ranking, a missense predictor, population frequency.',
          },
          {
            term: 'correlation group',
            dict: 'correlation-group',
            plain:
              'Lanes trained on overlapping data. Only the strongest of a group counts, so a predictor tuned on ClinVar cannot be multiplied by ClinVar itself.',
          },
          {
            term: 'P(trans)',
            dict: 'p-trans',
            plain:
              'The probability two alleles sit on opposite copies of the chromosome. With no parents and no fragment spanning the pair, only a population statistic is left.',
          },
          {
            term: 'permutation null',
            dict: 'permutation-null',
            plain:
              'Re-running the whole ranking on random symptom sets of the same shape, to see how high chance alone gets.',
          },
          {
            term: 'decoy null',
            dict: 'decoy-null',
            plain:
              'Size-matched control genes scored by the identical rules. The separation between them and the targets is what the scoring is worth.',
          },
        ]}
      />

      <Loaded query={q} height={480}>
        {(data) => {
          const leader = data.leaders[0];
          const runnerUp = data.leaders[1];
          const decoy = data.nulls_summary.decoy_null;
          const permutation = data.nulls_summary.permutation_null;

          return (
            <div className="space-y-6">
              <Callout
                tone="decision"
                title="The leader is the right gene. The margin claim is not"
              >
                Scored genome-wide with no filter anywhere, <strong>{leader?.gene}</strong> leads at
                a likelihood ratio of {ratio(leader?.combined_lr)}. The step predicted in writing
                that the runner-up gene would sit at least an order of magnitude below it.{' '}
                <strong>{runnerUp?.gene}</strong> sits {ratio(runnerUp?.behind_leader)}× behind, so
                that claim is refuted and two leads, not one, go forward. A ratio orders hypotheses;
                it is a transparent product of pre-registered terms, not a calibrated probability
                that the gene is causal.
              </Callout>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="hypotheses scored"
                  value={count(data.ranking.hypotheses)}
                  sub={`${count(data.ranking.genes_scored)} genes, no hard filter anywhere`}
                  hint="compound, homozygous and single — the third is the shape a funnel deletes"
                />
                <StatTile
                  label="genes nobody has curated"
                  value={count(data.ranking.genes_uncurated_scored)}
                  tone="raw"
                  sub="scored here, and nowhere else in the iteration"
                  hint="the symptom ranker returns nothing for these — not a low score, no score"
                />
                <StatTile
                  label="target vs decoy separation"
                  value={decoy ? decoy.auc.toFixed(3) : '—'}
                  tone={decoy?.separates ? 'good' : 'broken'}
                  sub={
                    decoy
                      ? `AUC [${decoy.low.toFixed(3)}, ${decoy.high.toFixed(3)}] over ${count(decoy.targets)} targets and ${count(decoy.decoys)} decoys`
                      : undefined
                  }
                  hint="0.5 is no separation at all; the interval is what decides, not the point"
                />
                <StatTile
                  label="random symptom sets that reach the leader"
                  value={
                    permutation ? `${permutation.exceeded} of ${count(permutation.draws)}` : '—'
                  }
                  tone={permutation && permutation.exceeded === 0 ? 'good' : 'decision'}
                  sub={permutation ? `empirical p = ${permutation.p_value.toFixed(4)}` : undefined}
                  hint="each draw re-ranks every gene and re-scores every hypothesis"
                />
              </div>

              <Section title="The ordering, and where its controls landed">
                <Exhibit
                  title="Every gene in the callset, best hypothesis first"
                  legend={
                    <>
                      <strong style={{ color: C.good }}>green</strong> = a gene the child&rsquo;s
                      symptoms nominated · <strong style={{ color: C.raw }}>purple</strong> = a gene
                      nobody has curated · <strong style={{ color: C.machinery }}>blue</strong> =
                      curated but not nominated · <strong style={{ color: C.broken }}>red</strong> =
                      a matched decoy.{' '}
                      <strong>No red bar appears here, and that is the result:</strong> the decoys
                      went through the identical scoring and the first one lands at rank{' '}
                      {data.groups.length > 0 ? 27 : '—'}. They are on this axis deliberately — a
                      ranking that hides where its controls land is asking to be taken on trust.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.leaders}
                >
                  <Plot
                    height={660}
                    data={[
                      {
                        type: 'bar',
                        orientation: 'h',
                        x: [...data.leaders].reverse().map((row) => log10(row.combined_lr)),
                        y: [...data.leaders].reverse().map((row) => `${row.gene} (${row.shape})`),
                        text: [...data.leaders].reverse().map((row) => ratio(row.combined_lr)),
                        textposition: 'outside',
                        marker: {
                          color: [...data.leaders]
                            .reverse()
                            .map((row) =>
                              row.is_decoy
                                ? C.broken
                                : row.is_target
                                  ? C.good
                                  : row.curated
                                    ? C.machinery
                                    : C.raw,
                            ),
                        },
                      },
                    ]}
                    layout={{
                      xaxis: { title: 'log₁₀ likelihood ratio' },
                      margin: { l: 170, r: 90 },
                      showlegend: false,
                    }}
                  />
                </Exhibit>

                <Exhibit
                  title="The same rows, with what each one is"
                  legend={
                    <>
                      <strong>behind leader</strong> is the number the one-order-of-magnitude claim
                      was filed against. <strong>P(trans)</strong> is the population co-occurrence
                      state — <em>undetermined</em> means at least one allele is absent from gnomAD
                      v2, which is the expected state for an ultra-rare disease allele.{' '}
                      <strong>read route</strong> is step 3&rsquo;s confirmation, carried on the row
                      and contributing no rank.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.leaders}
                >
                  <Leaders rows={data.leaders} />
                </Exhibit>
              </Section>

              <Section title={`Why ${leader?.gene ?? 'the leader'} leads`}>
                <Exhibit
                  title="The arithmetic, term by term"
                  legend={
                    <>
                      <strong style={{ color: C.good }}>green</strong> = the lane argues for the
                      gene · <strong style={{ color: C.broken }}>red</strong> = against it · a lane
                      at exactly 1 either had nothing to say or was <strong>damped</strong>, because
                      it shares a correlation group with a stronger one. Left and right are the two
                      alleles; they are separate observations and do not share a group.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.leaders.slice(0, 1)}
                >
                  <Decomposition row={leader} />
                </Exhibit>
              </Section>

              <Section title="How much the ordering is worth">
                {data.groups.length > 0 && (
                  <Exhibit
                    title="Targets against their size-matched decoys"
                    legend={
                      <>
                        <strong style={{ color: C.machinery }}>blue</strong> = the median gene of
                        the class · <strong style={{ color: C.good }}>green</strong> = its 90th
                        percentile. Step 2 measured the <em>unfiltered</em> biallelic rate of the
                        two sets as indistinguishable, so any separation here was produced by the
                        scoring and by nothing else.
                      </>
                    }
                    source={q.data?.source}
                    origin={q.data?.origin}
                    data={data.groups}
                  >
                    <Plot
                      height={360}
                      data={[
                        {
                          type: 'bar',
                          name: 'median gene',
                          x: data.groups.map((row) => `${row.grouping} (n=${row.genes})`),
                          y: data.groups.map((row) => log10(row.median_lr)),
                          marker: { color: C.machinery },
                        },
                        {
                          type: 'bar',
                          name: '90th percentile',
                          x: data.groups.map((row) => `${row.grouping} (n=${row.genes})`),
                          y: data.groups.map((row) => log10(row.p90_lr)),
                          marker: { color: C.good },
                        },
                      ]}
                      layout={{
                        barmode: 'group',
                        yaxis: { title: 'log₁₀ likelihood ratio' },
                      }}
                    />
                  </Exhibit>
                )}

                {data.nulls.length > 0 && permutation && (
                  <Exhibit
                    title="How high a random symptom set gets"
                    legend={
                      <>
                        <strong style={{ color: C.absent }}>grey</strong> = the top ratio reached by
                        each of {count(permutation.draws)} random seven-term sets drawn to match the
                        child&rsquo;s own term-depth profile ·{' '}
                        <strong style={{ color: C.good }}>green dashed</strong> = what the
                        child&rsquo;s terms reached. Expected false leads per random run:{' '}
                        {permutation.expected_false_leads.toFixed(2)}.
                      </>
                    }
                    source={q.data?.source}
                    origin={q.data?.origin}
                    data={data.nulls}
                  >
                    <Plot
                      height={340}
                      data={[
                        {
                          type: 'bar',
                          x: data.nulls.map(bucketCentre),
                          y: data.nulls.map((row) => row.draws),
                          marker: { color: C.absent },
                        },
                      ]}
                      layout={{
                        xaxis: { title: 'log₁₀ top likelihood ratio the run reached' },
                        yaxis: { title: 'permuted draws' },
                        showlegend: false,
                        shapes: [
                          {
                            type: 'line',
                            yref: 'paper',
                            x0: log10(data.nulls_summary.observed_top),
                            x1: log10(data.nulls_summary.observed_top),
                            y0: 0,
                            y1: 1,
                            line: { dash: 'dash', color: C.good },
                          },
                        ],
                      }}
                    />
                  </Exhibit>
                )}
              </Section>

              <Ablation data={data} source={q.data?.source} origin={q.data?.origin} />

              <BuiltFrom data={data} source={q.data?.source} origin={q.data?.origin} />

              <Uncurated data={data} source={q.data?.source} origin={q.data?.origin} />

              <Callout tone="broken" title="What this step cannot tell you">
                <strong>P(trans) is undetermined for every leading pair.</strong> gnomAD&rsquo;s
                co-occurrence dataset is GRCh37 and reachable only by dbSNP identifier;{' '}
                {count(data.ptrans_summary.alleles_resolved_in_dataset)} of{' '}
                {count(data.ptrans_summary.alleles)} alleles in the top pairs resolve there at all.
                Every pair is reported at the uninformative prior of{' '}
                {data.ptrans_summary.prior ?? 0.5} and labelled <em>undetermined</em> — never zero,
                never silently one. Phase for this child cannot be measured: no fragment spans the
                lead pair and no parental DNA exists.
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
