import { Link } from 'react-router-dom';

import { useStep1 } from '../../api/hooksSteps';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';
import { DecoyCard } from '../steps/step1/DecoyCard';
import { Overlap } from '../steps/step1/Overlap';
import { RecallCurve } from '../steps/step1/RecallCurve';
import { Tiers } from '../steps/step1/Tiers';

/**
 * How far this ranking actually reaches — the measurement the ranking table cannot make.
 *
 * The table above says where each gene landed. It cannot say how often a ranking like it
 * contains the right gene at all, how much of the genome it can score, whether a second
 * ranker agrees, or how often a random gene set would look as good. Those four are step 1's
 * output, served by `/api/steps/step-1`, and they belong beside the ranking rather than only
 * on the step page — a rank with no recall behind it invites being read as coverage.
 */
export function Reach() {
  const q = useStep1();

  return (
    <Loaded query={q} height={360}>
      {(data) => {
        const full = data.benchmark_full ?? data.benchmark;
        const atTarget = full?.curve.find((p) => p.n === data.target_n) ?? null;
        const promised = data.gates.find((g) => g.claim === 'H012')?.predicted ?? 0.9;

        return (
          <div className="space-y-4">
            <Exhibit
              title="How often a ranking like this contains the causal gene"
              legend={
                <>
                  <Chip color={C.machinery}>blue</Chip> = the sampled run ·{' '}
                  <Chip color={C.good}>green</Chip> = the full eligible population · shaded band =
                  95% bootstrap interval · <Chip color={C.decision}>amber dashes</Chip> = the cutoff
                  the target set is taken at · <Chip color={C.broken}>red dots</Chip> = the recall
                  promised before the run.
                </>
              }
              reading={
                <>
                  Measured by deleting each held-out disease&rsquo;s own contribution to its
                  gene&rsquo;s curation, degrading the term list the way a clinic would record it,
                  and ranking. At the {data.target_n}-gene cutoff, recall is{' '}
                  <strong>{atTarget ? atTarget.recall.toFixed(3) : '—'}</strong> — so this ranking
                  is an <strong>enrichment, not coverage</strong>, and a gene low on the table above
                  is not thereby excluded. The full working is on{' '}
                  <Link to="/steps/step-1" className="underline underline-offset-2">
                    step 1
                  </Link>
                  .
                </>
              }
              source={q.data?.source}
              cachedAt={q.data?.cachedAt}
              origin={q.data?.origin}
              data={{ sample: data.benchmark, full: data.benchmark_full }}
            >
              <RecallCurve
                sample={data.benchmark}
                full={data.benchmark_full}
                targetN={data.target_n}
                promised={promised}
              />
            </Exhibit>

            <Exhibit
              title="Where a rank becomes a tier, and which rows earned it"
              legend={
                <>
                  <Chip color={C.good}>green</Chip> = the top of the pure symptom score ·{' '}
                  <Chip color={C.machinery}>blue</Chip> = the rest of the window ·{' '}
                  <Chip color={C.decision}>amber</Chip> = admitted by the chromosome-instability
                  mechanism rule regardless of rank — prior knowledge, not evidence.
                </>
              }
              reading={
                <>
                  The table above is the pure-score ranking: every row in it earned its position.
                  The target set adds {int(data.set_sizes.by_mechanism_rule)} genes that did not,
                  and tags them, because a rediscovery claim may only be made on a gene the symptoms
                  actually ranked. {int(data.curation.uncurated)} protein-coding genes (
                  {pct(data.curation.fraction, 1)}) appear in neither, having no curation to score.
                </>
              }
              source={q.data?.source}
              origin={q.data?.origin}
              data={data.tiers}
            >
              <Tiers payload={data} />
            </Exhibit>

            <Exhibit
              title="Does an independent ranker nominate the same genes?"
              legend={
                <>
                  <Chip color={C.good}>green</Chip> = shared with the ranking above ·{' '}
                  <Chip color={C.broken}>red</Chip> = only that ranker ·{' '}
                  <Chip color={C.decision}>amber dashes</Chip> = the 50% agreement predicted before
                  the run.
                </>
              }
              reading={
                <>
                  Neither hosted ranker reaches it. Each is counted over the window it actually
                  filled, not over the {data.target_n} requested. Low agreement does not say which
                  ranking is right — it says one ranker is not a second opinion, which is why the
                  later steps corroborate with DNA rather than with more rankings.
                </>
              }
              source={q.data?.source}
              origin={q.data?.origin}
              data={data.overlap}
            >
              <Overlap rows={data.overlap} />
            </Exhibit>

            <Exhibit
              title="The decoy set — what a gene list of this shape finds by chance"
              legend={
                <>
                  <Chip color={C.broken}>red</Chip> = genes that should find nothing ·{' '}
                  <Chip color={C.decision}>amber</Chip> = genes excluded before the draw because the
                  child&rsquo;s features are curated for them.
                </>
              }
              reading={
                <>
                  Matched to the nominated genes on coding length and exon count and drawn once from
                  a recorded seed. Every rule the target genes are put through is put through these
                  too, which is the only way &ldquo;this gene looks interesting&rdquo; acquires a
                  denominator.
                </>
              }
              source={q.data?.source}
              origin={q.data?.origin}
              data={data.decoys}
            >
              <DecoyCard payload={data} />
            </Exhibit>
          </div>
        );
      }}
    </Loaded>
  );
}
