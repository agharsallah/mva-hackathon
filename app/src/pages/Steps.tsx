import { useSteps } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { useJourney } from '../components/journeyContext';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { useUrlState } from '../lib/urlstate';
import { BlindChecklist } from './steps/BlindChecklist';
import { IterationBar } from './steps/IterationBar';
import { StepCard } from './steps/StepCard';
import { Submissions } from './steps/Submissions';

/**
 * Steps — the research journey, and what each step actually claimed.
 *
 * Every other page shows a *result*. This one shows the process that produced it: what
 * question each step was asked, what was predicted before the run, what the run did to the
 * prediction, what it wrote and what it drew. A refuted claim is as visible as a supported
 * one — more so, because the refutations are where the plan changed.
 *
 * **Every iteration, not only the current one.** The work ran as four iterations, and this
 * page showed one of them until the switcher below existed: iteration 1 produced the
 * uploaded submission, iteration 2 re-derived its answer blind, iteration 3 was drafted and
 * absorbed, iteration 4 is running. `/api/steps?iteration=` had always served them all.
 *
 * Nothing on this page is hand-written prose about a step. The step map declares the goals
 * and the track each one feeds, the register holds the claims, the blind gate reads the
 * entries, and the figure directory says what was drawn. Add a step — or a whole iteration
 * — and it appears here.
 */

/** A well-formed iteration name, so a hand-edited address degrades instead of 404-ing. */
const ITERATION_NAME = /^iteration\d+$/;

export default function StepsPage() {
  // Which step detail pages exist, read from the manifest the shell already published —
  // the card links to one only if it was built.
  const built = new Set(
    useJourney().flatMap((g) => g.pages.flatMap((p) => (p.children ?? []).map((c) => c.to))),
  );
  const [asked, setAsked] = useUrlState('iteration', '');
  const wanted = ITERATION_NAME.test(asked) ? asked : '';
  const q = useSteps(wanted || undefined);

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            A <strong>step</strong> is one question, asked once, with its answer written down before
            the data could talk back. An <strong>iteration</strong> is a whole set of those
            questions — a route through the case, with its own plan, its own steps and its own
            submission. Pick one below; each card then carries the question, the claims filed
            against it — <em>with their refutation conditions, written before the run</em> — and
            what became of them.
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
            dict: 'blind-protocol',
            plain:
              'A rule that this iteration may not read the earlier one’s answer until the step that exists to compare them.',
          },
          {
            term: 'methodology entry',
            dict: 'methodology-entry',
            plain:
              'One executed test, written down: the question, the exact commands, the output seen, and the conclusion drawn. Append-only — an entry is superseded, never edited.',
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
          const figures = research.reduce((n, s) => n + s.figures.length, 0);

          return (
            <div className="space-y-6">
              <Section title="The iterations">
                <Exhibit
                  title="Four routes through one case, and where each of them got to"
                  legend={
                    <>
                      One card per iteration. <Chip color={C.good}>green</Chip> = every step
                      finished · <Chip color={C.decision}>amber</Chip> = steps still open ·{' '}
                      <Chip color={C.absent}>grey</Chip> = drafted but never declared, so it has no
                      step map to show. The blue ring marks the one being read.
                    </>
                  }
                  reading={
                    <>
                      Iteration 1 produced the uploaded submission; iteration 2 re-derived the same
                      answer by routes that share no code with it; iteration 3 was a draft absorbed
                      into iteration 4, which is tooling and files no submission of its own.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={data.index}
                >
                  <IterationBar
                    index={data.index}
                    selected={data.iteration}
                    onSelect={(next) => setAsked(next === data.current ? '' : next)}
                  />
                </Exhibit>
              </Section>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <StatTile label="iteration" value={data.iteration} hint="the one being read" />
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
                <StatTile
                  label="figures drawn"
                  value={figures}
                  hint="rendered by a committed script, served by the API, shown on the cards below"
                />
              </div>

              <Submissions rows={data.submissions} iteration={data.iteration} />

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
                      opened. A claim badge is green when supported, red when refuted; the second
                      badge on each card is the track that step feeds.
                    </>
                  }
                  reading={
                    <>
                      The order is the dependency order, which is also the order the steps are
                      worked. Open a card&apos;s <em>what this step wrote and drew</em> to read the
                      methodology entries verbatim and to see the figures the step rendered.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={q.data?.data}
                >
                  <div className="space-y-3">
                    {data.steps.map((step) => (
                      <StepCard
                        key={step.slug}
                        step={step}
                        iteration={data.iteration}
                        current={data.current}
                        origin={q.data?.origin}
                        built={built}
                      />
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
