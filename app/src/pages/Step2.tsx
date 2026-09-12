import { useStep2 } from '../api/hooks';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Plot } from '../components/Plot';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { Contrast } from './steps/step2/Contrast';
import { Gates } from './steps/step2/Gates';
import { Leads } from './steps/step2/Leads';
import { count, metric, percent } from './steps/step2/metrics';

/**
 * Step 2 — what the raw reads say, found without the vendor's caller.
 *
 * The one page in the app built entirely from a *second, independent* read of the data:
 * 1.07 billion raw reads filtered by a reference k-mer bait, aligned, and called by two
 * callers that share no code with the pipeline that produced the delivered callset.
 *
 * Every block is an aggregate. The four tables behind it carry real genomic positions of
 * the proband and none of their rows crosses the API boundary — the grouping happens in
 * SQL, so there is no coordinate here to withhold.
 *
 * The page keeps two uncomfortable results in plain view, because they are the step's
 * most useful output: a pre-registered gate that failed and cannot be reached by any
 * available parameter, and a decoy set that matches the target set exactly once every
 * allele is scored.
 */
export default function Step2Page() {
  const q = useStep2();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Step 1 chose 404 genes from the child&rsquo;s symptoms with the DNA never opened. This
            step goes to the <strong>raw reads</strong> and asks what alleles they carry in those
            genes — plus 396 <em>decoy</em> genes that should find nothing — using a{' '}
            <strong>k-mer bait</strong> instead of a genome-wide alignment, and callers that share
            no code with the vendor&rsquo;s.
          </>
        }
        terms={[
          {
            term: 'k-mer bait',
            dict: 'k-mer-bait',
            plain:
              'Every 31-letter window of the genes we care about, used as a filter: a read sharing one probably came from there, and everything else is discarded unread.',
          },
          {
            term: 'stride',
            dict: 'stride',
            plain:
              'Testing every 16th position of a read instead of all of them — fifteen times less work, at a measured cost in sensitivity of about 10%.',
          },
          {
            term: 'decoy set',
            dict: 'decoy-set',
            plain:
              'Genes matched to the targets on shape but carrying none of the symptoms. Running the same rules over them measures how often the method nominates a gene by chance.',
          },
          {
            term: 'method class',
            dict: 'method-class',
            plain:
              'The kind of evidence a caller uses, not its name. Two callers of the same class mostly share a blind spot; agreement across classes is real corroboration.',
          },
          {
            term: 'ascertainment circularity',
            dict: 'ascertainment-circularity',
            plain:
              'Scoring your discoveries with a resource built from what you were trying to improve on, so the new route can only rediscover the old one.',
          },
        ]}
      />

      <Callout tone="broken" title="Two results this page does not hide">
        The <strong>off-target gate failed</strong> — 8.79% of the bait also occurs elsewhere in the
        genome, against a pre-registered 5%, and no available padding or k reaches it. And once the
        alleles only these callers found were annotated too, the{' '}
        <strong>decoy set matched the target set exactly</strong>: 10 genes of 396 each. The claim
        that predicted otherwise is recorded as refuted, and the read route enters the final fusion
        at reduced weight.
      </Callout>

      <Loaded query={q} height={420}>
        {(data) => {
          const funnel = data.funnel;
          const scanned = metric(funnel, 'pass', 'reads_scanned');
          const matched = metric(funnel, 'pass', 'reads_matched');
          const novel = data.by_tier.reduce((sum, t) => sum + t.novel_qualifying, 0);
          const phase = data.phase[0];

          return (
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="reads swept"
                  value={count(scanned)}
                  sub={`${count(metric(funnel, 'pass', 'shards'))} shards, one pass`}
                />
                <StatTile
                  label="reads kept"
                  value={count(matched)}
                  tone="good"
                  sub={`${percent(metric(funnel, 'pass', 'matched_fraction'), 3)} of the store, against a bait covering 1.361% of the genome`}
                  hint="the agreement between these two numbers is the bait working"
                />
                <StatTile
                  label="median depth"
                  value={`${metric(funnel, 'coverage', 'median_depth')?.toFixed(1) ?? '—'}×`}
                  sub={`${count(metric(funnel, 'coverage', 'below_floor'))} of ${count(metric(funnel, 'coverage', 'regions'))} intervals below 10×`}
                />
                <StatTile
                  label="alleles the callset missed"
                  value={count(novel)}
                  tone="decision"
                  sub="qualifying, and unvalidated until step 3 checks them"
                  hint="scored here for the first time; scoring only vendor-reported alleles was a circle"
                />
              </div>

              <Section title="Did the instrument do what it promised?">
                <Exhibit
                  title="The pre-registered gates, including the one that failed"
                  legend={
                    <>
                      One row per promise made <em>before</em> the run.{' '}
                      <Chip color={C.good}>green</Chip> = the measurement kept it ·{' '}
                      <Chip color={C.broken}>red</Chip> = it did not, and the gate stays on the page
                      anyway.
                    </>
                  }
                  reading={
                    <>
                      Four of five held. The off-target gate did not, and a companion measurement
                      showed the threshold is unreachable at any padding or k available here — so
                      the honest record is a failed gate and a per-gene reachability column beside
                      every result, not a quietly relaxed number.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={funnel}
                >
                  <Gates rows={funnel} />
                </Exhibit>
              </Section>

              <Section title="What actually discriminates">
                <Exhibit
                  title="The filter, not the symptom-derived gene list"
                  legend={
                    <>
                      <Chip color={C.good}>green</Chip> = the 396 genes the symptoms nominated ·{' '}
                      <Chip color={C.broken}>red</Chip> = the 396 matched decoys that should find
                      nothing. Same reads, same enumeration; only the filter differs between the two
                      pairs.
                    </>
                  }
                  reading={
                    <>
                      Count any gene with two heterozygous variants and the{' '}
                      <strong>decoys win</strong>, because everyone carries about two differences
                      per gene. Require the alleles to be rare and protein-altering and the rate
                      falls fifty-fold — to exactly the same value in both sets. All of the
                      discriminating power is in the filter, and none of it is measurably in the
                      gene list.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.contrast}
                >
                  <Contrast rows={data.contrast} />
                </Exhibit>

                <Exhibit
                  title="Every gene the filter leaves standing"
                  legend={
                    <>
                      <Chip color={C.good}>green tier</Chip> = a symptom-derived target ·{' '}
                      <Chip color={C.broken}>red tier</Chip> = a decoy. <strong>novel</strong>{' '}
                      counts alleles the delivered callset never reported; a depth in red is below
                      10× and the row should not be trusted.
                    </>
                  }
                  reading={
                    <>
                      Twenty genes, ten of each kind, in the order the query produced — not
                      re-sorted. The first row is a decoy. Exactly one of the twenty carries an
                      allele with a ClinVar pathogenic assertion, and that flag comes from a public
                      catalogue rather than from the reads, which is the honest measure of how far
                      this route gets on its own.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.leads}
                >
                  <Leads rows={data.leads} />
                </Exhibit>
              </Section>

              <Section title="Does a second opinion agree?">
                <Exhibit
                  title="Two independent callers against the delivered callset"
                  legend={
                    <>
                      <Chip color={C.good}>green</Chip> = measured agreement ·{' '}
                      <Chip color={C.decision}>amber</Chip> = the pre-registered 0.99 line. Counted
                      only at single-base substitutions where both callers emit a genotype.
                    </>
                  }
                  reading={
                    <>
                      Both clear the line, which is the check that licenses everything else on this
                      page. It says nothing about indels: the delivered callset is unnormalised and
                      its indels are not comparable without a left-alignment this query cannot do.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.concordance}
                >
                  <Plot
                    height={260}
                    data={[
                      {
                        type: 'bar',
                        orientation: 'h',
                        x: data.concordance.map((r) => r.concordance),
                        y: data.concordance.map((r) => r.caller),
                        marker: { color: C.good },
                        text: data.concordance.map(
                          (r) => `${r.agreed.toLocaleString()} / ${r.co_called.toLocaleString()}`,
                        ),
                        textposition: 'inside',
                        hovertemplate: '%{y}: %{x:.4f}<extra></extra>',
                      },
                    ]}
                    layout={{
                      xaxis: { range: [0.97, 1], title: 'genotype concordance' },
                      shapes: [
                        {
                          type: 'line',
                          x0: 0.99,
                          x1: 0.99,
                          yref: 'paper',
                          y0: 0,
                          y1: 1,
                          line: { color: C.decision, dash: 'dash' },
                        },
                      ],
                    }}
                  />
                </Exhibit>
              </Section>

              <Section title="What the bait's own geometry invents">
                <Exhibit
                  title="Structural variants, before and after the artefact controls"
                  legend={
                    <>
                      <Chip color={C.good}>green</Chip> = credible: over half the call&rsquo;s span
                      is baited territory and it is away from an edge ·{' '}
                      <Chip color={C.decision}>amber</Chip> = within one insert-size of a bait
                      boundary · <Chip color={C.broken}>red</Chip> = spanning the unbaited gaps the
                      bait itself created.
                    </>
                  }
                  reading={
                    <>
                      A baited alignment is islands of coverage with emptiness between them, and a
                      read-pair caller reports the emptiness as one enormous event — the first run
                      produced a 13 Mb deletion and a 40 Mb inversion in a living child. The
                      precision column is Kosugi 2019&rsquo;s published short-read prior for each
                      type, not a measurement of ours.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.sv_consensus}
                >
                  <Plot
                    height={300}
                    data={[
                      {
                        type: 'bar',
                        x: data.sv_consensus.map((r) => r.sv_type),
                        y: data.sv_consensus.map((r) => r.consensus_calls),
                        marker: {
                          color: data.sv_consensus.map((r) =>
                            r.spans_unbaited ? C.broken : r.bait_edge ? C.decision : C.good,
                          ),
                        },
                        hovertemplate:
                          '%{x}: %{y} calls<br>median %{customdata:,} bp<extra></extra>',
                        customdata: data.sv_consensus.map((r) => r.median_length ?? 0),
                      },
                    ]}
                    layout={{
                      yaxis: { title: 'two-method-class consensus calls', type: 'log' },
                      barmode: 'stack',
                    }}
                  />
                </Exhibit>
              </Section>

              <Section title="Where the reads could not reach">
                <Exhibit
                  title="Genes the bait covers thinly, and the phase it could not close"
                  legend={
                    <>
                      <Chip color={C.broken}>red</Chip> = below half the median bait density, so
                      &ldquo;nothing found here&rdquo; is a statement about the bait rather than
                      about the gene. None of them is a core-tier target.
                    </>
                  }
                  reading={
                    <>
                      {data.unreachable.length} of {data.by_tier.reduce((s, t) => s + t.genes, 0)}{' '}
                      genes fall below the reachability line, and read-backed phasing produced{' '}
                      {phase ? phase.blocks.toLocaleString() : '—'} blocks with a median span of{' '}
                      {phase ? phase.median_span.toLocaleString() : '—'} bp — far shorter than the
                      distance between the lead gene&rsquo;s two alleles, which is why neither
                      &lsquo;same copy&rsquo; nor &lsquo;different copies&rsquo; could be shown.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.unreachable}
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-xs text-chrome-400">
                        <tr className="border-b border-chrome-800">
                          <th className="py-1 pr-3 text-left">gene</th>
                          <th className="py-1 pr-3 text-left">tier</th>
                          <th className="py-1 pr-3 text-right">bait density</th>
                          <th className="py-1 text-right">k-mers lost to repeats</th>
                        </tr>
                      </thead>
                      <tbody className="tabular-nums">
                        {data.unreachable.map((row) => (
                          <tr key={row.symbol} className="border-b border-chrome-900/60">
                            <td className="py-1 pr-3 font-medium">{row.symbol}</td>
                            <td className="py-1 pr-3 text-chrome-400">{row.tier}</td>
                            <td className="py-1 pr-3 text-right text-broken-400">
                              {row.density.toFixed(3)}
                            </td>
                            <td className="py-1 text-right">{(row.lost * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Exhibit>
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
