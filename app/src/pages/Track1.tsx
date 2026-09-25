import { useSteps } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { HubLinks } from './iterations/HubLinks';
import { iterationHubLinks } from './iterations/model';
import { IterationBar } from './steps/IterationBar';
import { TrackMap } from './steps/ResearchMap';

/**
 * Track 1 — the whole research journey, as the iterations that walked it.
 *
 * Track 1 is answered four times over, not once: iteration 1 filtered the vendor callset
 * top-down and produced the submission the oracle answered; iteration 2 re-derived the same
 * answer blind, from the raw reads, by routes that share no code with it; iteration 3 was
 * drafted and absorbed; iteration 4 runs every published model over the same alleles. This
 * page is the map of that, and each card opens the iteration's own steps.
 *
 * Nothing here is hand-written prose about an iteration: the strip is `GET /api/steps`'s
 * `index`, counted from the same declarations the step cards are built from, so the map and
 * the pages under it cannot disagree.
 */
export default function Track1Page() {
  const q = useSteps();

  return (
    <div className="space-y-6">
      <HubLinks links={iterationHubLinks()} />

      <Explainer
        intro={
          <>
            <strong>Track 1</strong> asks one question — which two broken copies of which gene cause
            this child&apos;s disease — and the repository answers it more than once, on purpose.
            Each <strong>iteration</strong> is a complete route to that answer with its own plan,
            steps and claims; agreement between two routes that share no code is worth more than one
            route&apos;s confidence in itself.
          </>
        }
        terms={[
          {
            term: 'iteration',
            dict: 'research-iteration',
            plain:
              'One whole route through the case: its own plan, its own numbered steps, its own claims, and usually its own submission folder. Not a retry of the previous one.',
          },
          {
            term: 'step map',
            dict: 'step-map',
            plain:
              'The declared list of steps of one iteration, held in code: each step’s question, status, the track it feeds and what it unblocks.',
          },
          {
            term: 'blind protocol',
            dict: 'blind-protocol',
            plain:
              'A rule that this iteration may not read the earlier one’s answer until the step that exists to compare them.',
          },
        ]}
      />

      <Callout tone="machinery" title="Why the refutations matter more than the confirmations">
        A prediction that cannot fail is not a prediction. Iteration 2 filed four claims about the
        symptom ranker before running it; three were refuted, and the largest of them — that a
        300-gene target set would recall 90% of causal genes — changed the plan rather than being
        explained away. Measured recall is 0.36, so the target set is an{' '}
        <strong>enrichment, never coverage</strong>, and the genome-wide ranking of step 4 is the
        safety net. Every iteration below keeps its refutations.
      </Callout>

      <Loaded query={q} height={320}>
        {(data) => {
          const declared = data.index.filter((row) => row.declared);
          const claims = declared.reduce((n, row) => n + row.claims, 0);
          const done = declared.reduce((n, row) => n + row.done, 0);
          const total = declared.reduce((n, row) => n + row.steps, 0);

          return (
            <div className="space-y-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="iterations declared"
                  value={declared.length}
                  hint="each with its own step map; one more was drafted and absorbed rather than run"
                />
                <StatTile
                  label="steps finished"
                  value={`${done} / ${total}`}
                  hint="across every declared iteration, research steps only"
                />
                <StatTile
                  label="claims filed"
                  value={claims}
                  tone={claims > 0 ? 'good' : 'neutral'}
                  hint="each with a prediction and a refutation condition, filed before its run"
                />
                <StatTile
                  label="current iteration"
                  value={data.current}
                  hint="what `mva.science.steps.ITERATION` names; the others run beside it or are frozen"
                />
              </div>

              <Section title="The iterations">
                <Exhibit
                  title="Four routes through one case, and where each of them got to"
                  legend={
                    <>
                      One card per iteration. <Chip color={C.good}>green</Chip> = every step
                      finished · <Chip color={C.decision}>amber</Chip> = steps still open ·{' '}
                      <Chip color={C.absent}>grey</Chip> = drafted but never declared, so it has no
                      step map to open.
                    </>
                  }
                  reading={
                    <>
                      Iteration 1 produced the uploaded submission; iteration 2 re-derived the same
                      answer by routes that share no code with it; iteration 3 was a draft absorbed
                      into iteration 4, which is tooling and files no submission of its own. Open a
                      card to read that iteration&apos;s steps.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={data.index}
                >
                  <IterationBar index={data.index} track="track1" />
                </Exhibit>
              </Section>

              <Section
                title="The research map"
                subtitle="Every step of every iteration on one screen — the tree the header opens one branch of at a time."
              >
                <TrackMap track="track1" />
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
