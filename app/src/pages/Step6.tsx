import { useStep6 } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { AgreementMatrix } from './steps/step6/AgreementMatrix';
import { Decision } from './steps/step6/Decision';
import { count } from './steps/step6/metrics';
import { RouteGraph } from './steps/step6/RouteGraph';
import { Routes } from './steps/step6/Routes';
import { Sensitivity } from './steps/step6/Sensitivity';

/**
 * Step 6 — one ranking out of three, and the table that says what carries it.
 *
 * The page is arranged so the fused ranking cannot be read on its own. Reciprocal rank
 * fusion treats every list it is handed as a separate witness, and these lists are not: two
 * of them ranked on the same eight symptom terms, two read the same callset, and one was
 * seeded with another's top 20. So the dependency graph comes before the leaderboard, and
 * the leave-one-route-out table sits on the same screen as it — because if silencing a
 * single instrument moves the leader, "independent routes converge" is not a sentence this
 * step is entitled to write.
 */
export default function Step6Page() {
  const q = useStep6();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Four instruments have now looked at this case from four directions. This step asks the
            only question left before the answer is checked: <strong>do they agree</strong>, and if
            they do, <strong>is that agreement worth anything</strong>? A route that cannot tell a
            candidate from a size-matched control does not get a vote. The ones that do are merged
            by <strong>reciprocal rank fusion</strong>, the result is written to a file and{' '}
            <strong>hashed before anyone compares it</strong> to what iteration 1 found, and then
            every route is taken away in turn to see whether the answer was ever really a consensus.
          </>
        }
        terms={[
          {
            term: 'reciprocal rank fusion',
            dict: 'reciprocal-rank-fusion-rrf',
            plain:
              'Merging ranked lists by adding 1/(k + rank) from each. It needs no training and no shared score scale — only the orderings.',
          },
          {
            term: 'rank inheritance',
            dict: 'rank-inheritance',
            plain:
              'A route that orders genes has its rank copied onto every pair in that gene. It is how a gene-level list joins a pair-level fusion, and it is why ties appear.',
          },
          {
            term: 'confirmation route',
            dict: 'ranking-route-vs-confirmation-route',
            plain:
              'An instrument that finds things reliably but orders them no better than chance. It answers yes/no questions about a candidate and contributes no rank.',
          },
          {
            term: 'independent-evidence count',
            dict: 'independent-evidence-count',
            plain:
              'How many genuinely different raw sources speak for a candidate, after routes that read the same source are counted once.',
          },
          {
            term: 'leave-one-route-out',
            dict: 'leave-one-route-out',
            plain:
              'Re-running the fusion with one instrument silenced. If the winner changes, that instrument was carrying the result on its own.',
          },
          {
            term: 'blind protocol',
            dict: 'blind-protocol',
            plain:
              'Iteration 2 re-derives the case as if no candidate were known. The gene is written all over this repository, so the blinding is a procedural rule a reviewer can check, not a secret.',
          },
        ]}
      />

      <Loaded query={q} height={520}>
        {(data, meta) => {
          const carried = data.stability.filter((row) => !row.leader_kept_rank_one);
          const leader = data.leaders.find((row) => row.fused_rank === 1);
          const shared = data.edges.filter((edge) => edge.shared_input).length;
          const chrome = { source: meta.source, cachedAt: meta.cachedAt, origin: meta.origin };

          return (
            <div className="space-y-6">
              <Callout
                tone={carried.length === 0 ? 'good' : 'decision'}
                title={
                  carried.length === 0
                    ? 'No single route carries the fused result'
                    : 'The fusion is corroboration, not independent rediscovery'
                }
              >
                {leader && (
                  <>
                    <strong>{leader.gene}</strong> leads the fused ranking of{' '}
                    {count(data.fusion.frozen?.rows)} pairs, on{' '}
                    <strong>{leader.independent_evidence} of 4</strong> disjoint sources.{' '}
                  </>
                )}
                {carried.length > 0 && (
                  <>
                    But silencing the <strong>{carried.map((r) => r.removed).join(' or ')}</strong>{' '}
                    route moves it to rank{' '}
                    <strong>
                      {carried.map((r) => r.leader_rank ?? 'outside the table').join(', ')}
                    </strong>
                    . One instrument is carrying the ordering and the other two reorder its top, so
                    the honest sentence is &ldquo;the genome-wide ranker nominates and the others
                    corroborate&rdquo;.{' '}
                  </>
                )}
                {shared > 0 && (
                  <>
                    {shared} of {data.edges.length} dependency edges are a <em>shared raw input</em>
                    , which is exactly what reciprocal rank fusion cannot see and why the
                    independent-evidence count is printed beside every score.
                  </>
                )}
              </Callout>

              <Section title="Four instruments, and which of them earned a vote">
                <Routes rows={data.routes} {...chrome} />
                <RouteGraph routes={data.routes} edges={data.edges} {...chrome} />
              </Section>

              <Section title="The fused ranking">
                <AgreementMatrix
                  cells={data.matrix}
                  routes={data.routes}
                  leaders={data.leaders}
                  {...chrome}
                />
              </Section>

              <Section title="What happens when a route is taken away">
                <Sensitivity
                  stability={data.stability}
                  reach={data.reach}
                  evidence={data.evidence}
                  {...chrome}
                />
              </Section>

              <Section title="The frozen ranking, and the decision it licenses">
                <Decision fusion={data.fusion} decision={data.decision} {...chrome} />
              </Section>

              <Callout tone="broken" title="What this step cannot tell you">
                The symptom-nominated target set is an <strong>enrichment, never coverage</strong> —
                held-out recall@300 is 0.335 [0.318, 0.350], so &ldquo;absent from this
                ranking&rdquo; means &ldquo;no route nominated it&rdquo;, never
                &ldquo;excluded&rdquo;. 73.6% of protein-coding genes carry no curated phenotype at
                all. Phase is <strong>unmeasured</strong> for the leading pair, not absent: no
                read-backed phase block reaches its coding span and P(trans) is undetermined,
                because 5 of 50 leading alleles reach gnomAD v2. The likelihood route&rsquo;s
                permutation null is p = 0.056, which is not a small number.{' '}
                <strong>Rank inheritance</strong> means the top of the ranking is a handful of
                genes, not a handful of candidates — a gene with eleven scored pairs occupies eleven
                rows. And the confirmation triple is measured per <strong>gene</strong>, not per
                allele, because the k-mer genotype table carries no variant identifier to join on.
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
