import { useSteps } from '../api/hooks';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { BlindChecklist } from './steps/BlindChecklist';
import { StepCard } from './steps/StepCard';

/**
 * Steps — the research journey, and what each step actually claimed.
 *
 * Every other page shows a *result*. This one shows the process that produced it: what
 * question each step was asked, what was predicted before the run, and what the run did to
 * the prediction. A refuted claim is as visible as a supported one — more so, because the
 * refutations are where the plan changed.
 *
 * Nothing on this page is hand-written prose about a step. The step map declares the goals,
 * the register holds the claims, the blind gate reads the entries, and the figure directory
 * says what was drawn. Add a step — or a whole iteration — and it appears here.
 */
export default function StepsPage() {
  const q = useSteps();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            A <strong>step</strong> is one question, asked once, with its answer written down before
            the data could talk back. Each card below carries the question, the claims filed against
            it — <em>with their refutation conditions, written before the run</em> — and what became
            of them.
          </>
        }
        terms={[
          {
            term: 'hypothesis',
            dict: 'hypothesis',
            plain:
              'A claim written down before the run, together with the observation that would kill it.',
          },
          {
            term: 'refutation condition',
            dict: 'refutation-condition',
            plain:
              'What has to be seen for the claim to be wrong — fixed in advance, so a result cannot be reinterpreted afterwards to fit.',
          },
          {
            term: 'blind protocol',
            plain:
              'A rule that this iteration may not read the earlier one\u2019s answer until the step that exists to compare them.',
          },
          {
            term: 'recall@N',
            plain:
              'Out of many test cases, the share whose right answer appears in the top N of a ranking.',
          },
        ]}
      />

      <Callout tone="machinery" title="Why the refutations matter more than the confirmations">
        A prediction that cannot fail is not a prediction. Iteration 2 filed four claims about the
        symptom ranker before running it; three were refuted, and the largest of them — that a
        300-gene target set would recall 90% of causal genes — changed the plan rather than being
        explained away. Measured recall is 0.36, so the target set is an{' '}
        <strong>enrichment, never coverage</strong>, and the genome-wide ranking of step 4 is the
        safety net. That is what this page is for.
      </Callout>

      <Loaded query={q} height={420}>
        {(data) => {
          const research = data.steps.filter((s) => s.kind !== 'platform');
          const settled = research.filter((s) =>
            s.hypotheses.some((h) => h.status === 'supported' || h.status === 'refuted'),
          );
          const claims = research.flatMap((s) => s.hypotheses);
          const refuted = claims.filter((h) => h.status === 'refuted');

          return (
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile label="iteration" value={data.iteration} hint="the one being worked" />
                <StatTile
                  label="steps with a verdict"
                  value={`${settled.length} / ${research.length}`}
                  hint="a step is finished when its claims have verdicts, not when its code runs"
                />
                <StatTile
                  label="claims filed"
                  value={claims.length}
                  tone={claims.length > 0 ? 'good' : 'neutral'}
                  hint="each with a prediction and a refutation condition, filed before its run"
                />
                <StatTile
                  label="refuted"
                  value={refuted.length}
                  tone={refuted.length > 0 ? 'broken' : 'neutral'}
                  hint="kept, not deleted — a refutation is a result"
                />
              </div>

              <Section title="The journey">
                <Exhibit
                  title="Every step of this iteration, and where it stands"
                  legend={
                    <>
                      One card per declared step, in dependency order.{' '}
                      <Chip color={C.good}>green</Chip> = finished ·{' '}
                      <Chip color={C.decision}>amber</Chip> = being worked ·{' '}
                      <Chip color={C.machinery}>blue</Chip> = platform machinery, which records
                      decisions rather than claims · <Chip color={C.absent}>grey</Chip> = not
                      opened. A claim badge is green when supported, red when refuted.
                    </>
                  }
                  reading={
                    <>
                      The order is the dependency order, which is also the order the steps are
                      worked: the symptoms choose the genes, the reads and the callset are read
                      independently, and only step 6 compares the two iterations.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={q.data?.data}
                >
                  <div className="space-y-3">
                    {data.steps.map((step) => (
                      <StepCard key={step.slug} step={step} />
                    ))}
                  </div>
                </Exhibit>
              </Section>

              <Section title="The blinding">
                <BlindChecklist data={data} />
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
