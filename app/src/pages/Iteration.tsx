import { useLocation } from 'react-router-dom';

import { useSteps } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { EmptyState } from '../components/EmptyState';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { BlindChecklist } from './steps/BlindChecklist';
import { iterationLabel, parseResearchPath, trackLabel, tracksShownOn } from './steps/route';
import { StepCard } from './steps/StepCard';
import { Submissions } from './steps/Submissions';

/**
 * One iteration of one track: every step that argues this track's answer, in order.
 *
 * The same component serves every node of the tree — `/track1/iteration2`,
 * `/track2/iteration1` and any iteration declared later — because the address carries the
 * identity and `GET /api/steps?iteration=` carries everything else. Declaring an iteration
 * in `mva.science.steps` is therefore the whole job: the generator adds the route, and this
 * page fills it.
 *
 * **Which steps appear.** A step declares the track it feeds. Track 1's pages collect the
 * steps that argue an allele (`track1`) and the ones whose result both submissions quote
 * (`both`); Track 2's collect the steps that argue a drug. A step is never shown twice, and
 * its card names the other track when it serves both.
 *
 * Track 2's iterations have a single step each, so its cards are opened by default: there is
 * nothing to scan past, and the step's entries and figures are the page's real content.
 */
export default function IterationPage() {
  const route = parseResearchPath(useLocation().pathname);
  const q = useSteps(route?.iteration);

  if (!route) {
    return (
      <EmptyState title="Not a research address">
        This page is reached as <span className="font-mono">/track1/iteration2</span> — a track and
        an iteration the step maps declare.
      </EmptyState>
    );
  }

  const { track, iteration } = route;
  const wanted = tracksShownOn(track);

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            An <strong>iteration</strong> is one whole route through the case — its own plan, its
            own steps, its own claims, and usually its own submission folder. A{' '}
            <strong>step</strong> inside it is one question, asked once, with its answer written
            down before the data could talk back. Every card below carries that question, the claims
            filed against it <em>with the refutation condition written before the run</em>, the
            methodology entries the run was written in, and the figures it drew.
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
            term: 'methodology entry',
            dict: 'methodology-entry',
            plain:
              'One executed test, written down: the question, the exact commands, the output seen, and the conclusion drawn. Append-only — an entry is superseded, never edited.',
          },
          {
            term: 'blind protocol',
            dict: 'blind-protocol',
            plain:
              'A rule that this iteration may not read the earlier one’s answer until the step that exists to compare them.',
          },
        ]}
      />

      <Loaded query={q} height={420}>
        {(data) => {
          const mine = data.steps.filter(
            (s) => s.kind === 'platform' || wanted.includes(String(s.track)),
          );
          const research = mine.filter((s) => s.kind !== 'platform');
          const settled = research.filter((s) =>
            s.hypotheses.some((h) => h.status === 'supported' || h.status === 'refuted'),
          );
          const claims = research.flatMap((s) => s.hypotheses);
          const refuted = claims.filter((h) => h.status === 'refuted');
          const figures = research.reduce((n, s) => n + s.figures.length, 0);
          const entries = research.reduce((n, s) => n + s.entries.length, 0);
          const submissions = data.submissions.filter((s) => s.track === track);

          return (
            <div className="space-y-6">
              <Callout
                tone="machinery"
                title={`${trackLabel(track)}, ${iterationLabel(iteration)}`}
              >
                {data.index.find((row) => row.iteration === iteration)?.summary ??
                  'No summary is declared for this iteration.'}{' '}
                {iteration === data.current
                  ? 'This is the iteration being worked now.'
                  : 'This iteration is not the one being worked now.'}
              </Callout>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <StatTile
                  label="steps on this track"
                  value={`${settled.length} / ${research.length}`}
                  hint="with a verdict — a step is finished when its claims are settled, not when its code runs"
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
                  label="entries written"
                  value={entries}
                  hint="methodology entries: one executed test each, readable in full on this page"
                />
                <StatTile
                  label="figures drawn"
                  value={figures}
                  hint="rendered by a committed script and served by the API, shown on the cards below"
                />
              </div>

              <Submissions rows={submissions} iteration={iteration} />

              <Section title="The steps">
                <Exhibit
                  title={`Every ${trackLabel(track)} step of ${iterationLabel(iteration)}, in dependency order`}
                  legend={
                    <>
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
                      Open a card&apos;s <em>what this step wrote and drew</em> to read its
                      methodology entries verbatim and to see the figures it rendered. A step with a
                      page of its own links to it.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={mine}
                >
                  <div className="space-y-3">
                    {mine.map((step) => (
                      <StepCard
                        key={step.slug}
                        step={step}
                        iteration={iteration}
                        track={track}
                        origin={q.data?.origin}
                        open={track === 'track2'}
                      />
                    ))}
                  </div>
                </Exhibit>
              </Section>

              <Section title="The blinding">
                <BlindChecklist data={data} steps={mine} />
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
