import { type ComponentType, lazy, type LazyExoticComponent, Suspense } from 'react';
import { useLocation } from 'react-router-dom';

import { useSteps } from '../api/hooksSteps';
import { Badge } from '../components/Badge';
import { Section } from '../components/Controls';
import { EmptyState } from '../components/EmptyState';
import { Exhibit } from '../components/Exhibit';
import { Callout } from '../components/Explainer';
import { FieldList } from '../components/FieldList';
import { Loaded, Skeleton } from '../components/QueryState';
import { STEP_BODIES } from './steps/bodies.generated';
import { ClaimCard } from './steps/ClaimCard';
import { EntryList } from './steps/EntryList';
import { FigureStrip } from './steps/FigureStrip';
import { Narrative } from './steps/Narrative';
import { iterationLabel, parseResearchPath, stepLabel, trackLabel } from './steps/route';
import { statusLabel, stepTone, TRACK_LABEL } from './steps/status';

/**
 * One `lazy()` per body, made once. Made inside the render, a new component type each render
 * remounted the analysis — its state gone, its skeleton back — on every re-render of this page,
 * such as the address change an opened figure writes.
 */
const BODIES = new Map<string, LazyExoticComponent<ComponentType>>();
function bodyFor(key: string): LazyExoticComponent<ComponentType> | null {
  const load = STEP_BODIES[key];
  if (!load) return null;
  let body = BODIES.get(key);
  if (!body) {
    body = lazy(load);
    BODIES.set(key, body);
  }
  return body;
}

/**
 * One step, complete: the question, what was claimed, what was written and what was drawn.
 *
 * Every step of every iteration gets this page, not only the ones whose analysis was built
 * out. That is the point: before it existed, a step with no hand-written page had no surface
 * at all, so iteration 1's eight steps and iteration 4's seven were readable only by cloning
 * the repository. What the page shows is assembled from the step map, the register, the
 * blind gate and the figure directory — the four places the record already lives.
 *
 * **The analysis body.** Seven of iteration 2's steps have a deep page of their own, with
 * their tables, nulls and charts; four of iteration 4's borrow the zoo dashboard's exhibits. Those are rendered *below* the record, from the generated
 * registry, so one address carries both halves. A step without one says so and shows the
 * record alone, which is the whole truth about it.
 */
export default function StepPage() {
  const route = parseResearchPath(useLocation().pathname);
  const q = useSteps(route?.iteration);

  if (!route || !route.slug) {
    return (
      <EmptyState title="Not a step address">
        This page is reached as <span className="font-mono">/track1/iteration2/step-4</span> — a
        track, an iteration and a step the step maps declare.
      </EmptyState>
    );
  }

  const { track, iteration, slug } = route;
  const Body = bodyFor(`${iteration}/${slug}`);

  return (
    <div className="space-y-6">
      <Loaded query={q} height={360}>
        {(data) => {
          const step = data.steps.find((s) => s.slug === slug);
          if (!step) {
            return (
              <EmptyState title={`${iterationLabel(iteration)} declares no ${slug}`}>
                Its steps are {data.steps.map((s) => s.slug).join(', ')}.
              </EmptyState>
            );
          }

          return (
            <div className="space-y-6">
              <Section title="What this step did">
                {step.narrative ? (
                  <Narrative
                    narrative={step.narrative}
                    track={track}
                    iteration={iteration}
                    linkable={
                      new Set(data.steps.filter((s) => s.kind !== 'platform').map((s) => s.slug))
                    }
                  />
                ) : (
                  <Callout tone="neutral" title="Nobody has written this step up yet">
                    Its goal, claims, entries and figures are below — all of them derived. The
                    summary, the reasoning and the hand-off to the next step are judgements a person
                    writes, and this step has none.{' '}
                    <span className="font-mono">tools/check_step_narrative.py</span> names it.
                  </Callout>
                )}
              </Section>

              <Section title="The question">
                <div className="space-y-3 rounded-card border border-line bg-panel p-4">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <Badge tone={stepTone(step)}>{statusLabel(step)}</Badge>
                    <Badge tone={step.track === 'track2' ? 'raw' : 'machinery'}>
                      {TRACK_LABEL[step.track] ?? step.track}
                    </Badge>
                    <span className="text-micro text-chrome-500">
                      {trackLabel(track)} · {iterationLabel(iteration)} · {stepLabel(slug)}
                    </span>
                  </div>
                  <p className="font-serif text-note text-chrome-100 italic">{step.goal}</p>
                  <FieldList
                    fields={[
                      { key: 'record', label: 'record', value: step.docs },
                      {
                        key: 'unblocks',
                        label: 'unblocks',
                        value:
                          step.unblocks.length > 0
                            ? step.unblocks.join(', ')
                            : 'nothing downstream',
                      },
                    ]}
                  />
                </div>
              </Section>

              <Section title="What was claimed">
                {step.hypotheses.length === 0 ? (
                  <Callout tone="machinery" title="No claim is filed under this step">
                    {step.kind === 'platform'
                      ? 'A platform step records decisions, not claims about the patient, so it files no hypotheses.'
                      : 'Nothing has been predicted about this step yet, so nothing can have been refuted. That is its state, not a gap in this page.'}
                  </Callout>
                ) : (
                  <Exhibit
                    title="Every claim filed under this step, with what would have killed it"
                    legend="Green = supported · red = refuted, and kept · blue = still open · grey = superseded by a later revision."
                    reading="A prediction that cannot fail is not a prediction. The two lines that matter are what was predicted and what would have refuted it, both written before the run."
                    source={q.data?.source}
                    cachedAt={q.data?.cachedAt}
                    origin={q.data?.origin}
                    data={step.hypotheses}
                  >
                    <div className="space-y-3">
                      {step.hypotheses.map((claim) => (
                        <ClaimCard key={claim.hypothesis_id} claim={claim} />
                      ))}
                    </div>
                  </Exhibit>
                )}
              </Section>

              <Section title="What was written">
                <Exhibit
                  title={`The methodology entries of ${stepLabel(slug)}`}
                  legend="Each row is one executed test. The badge is its global number; a red badge is an entry the blind gate flagged."
                  reading="Open one to read it verbatim — the question, the inputs with their versions, the exact commands, the observed output and the verdict. The log is quoted here, never summarised."
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={step.entries}
                >
                  <EntryList iteration={iteration} slug={slug} entries={step.entries} />
                </Exhibit>
              </Section>

              <Section title="What was drawn">
                <Exhibit
                  title={`Every figure ${stepLabel(slug)} rendered`}
                  legend="Each image is the file the report embeds, served by the API from the same bytes. A figure with an interactive version opens it in a new tab."
                  reading="Click a figure to open it full size; the open figure is written to the address bar, so one link cites one figure."
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={step.figures}
                >
                  <FigureStrip figures={step.figures} origin={q.data?.origin} />
                </Exhibit>
              </Section>

              {Body ? (
                <Section title="The analysis">
                  <Suspense
                    fallback={
                      // Marked so the test harness waits for the chunk (`testHarness.tsx`).
                      <div data-suspense-fallback>
                        <Skeleton height={320} label="Loading the analysis" />
                      </div>
                    }
                  >
                    <Body />
                  </Suspense>
                </Section>
              ) : (
                <Callout tone="neutral" title="This step has no analysis page of its own">
                  Its tables and charts were never built out into a page. Everything the record
                  holds about it is above; the methodology entries carry the numbers.
                </Callout>
              )}
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
