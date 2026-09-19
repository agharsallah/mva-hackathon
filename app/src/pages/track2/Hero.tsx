/**
 * "Track 2 in one screen" — the approach, the suggestion and the output, before anything
 * else on the page.
 *
 * The report below is complete but long: a reader had to scroll past a strategy timeline and
 * a mechanism card before meeting a single drug name. This panel answers the three questions
 * a reviewer actually opens the page with — *how was this done, what is being suggested, and
 * what came out* — and every box, card and bar links down into the section that shows its
 * working. Nothing here is a second source of truth: all of it is derived in `hero/heroModel`
 * from the same `GET /api/track2` payload the sections below render.
 */

import { useMemo } from 'react';

import type { Track2 } from '../../api/types';
import { Section } from '../../components/Controls';
import { ApproachFlow } from './hero/ApproachFlow';
import {
  ANCHOR,
  approachSteps,
  argueByDirection,
  contextOnlyCount,
  funnelStages,
  setAside,
  unmeasuredFacts,
} from './hero/heroModel';
import { type Artefact, Output } from './hero/Output';
import { Suggestion } from './hero/Suggestion';

/** The step-7 entries, named where they live. Append-only, so the list only ever grows. */
const METHODOLOGY = [
  '110-the-card-revised-and-the-claims-filed-before-the-search',
  '111-the-automated-stages-literature-trials-and-labels-per-drug',
  '112-two-decoy-cards-through-the-same-pipeline',
  '113-the-ladder-the-shortlist-and-the-do-not-table',
].map((name) => ({
  label: name.slice(0, 3),
  path: `docs/iteration2/step-7/methodology/${name}.md`,
}));

const TRACK2_ITERATION = 'track2/iteration-1';

function artefacts(data: Track2): Artefact[] {
  const claims = data.register.filter((r) => r.step === 'step-7').map((r) => r.hypothesis_id);
  const span = claims.length > 1 ? `${claims[0]}–${claims.at(-1)}` : (claims[0] ?? 'none yet');

  return [
    {
      label: 'the report',
      hint: `submissions/${TRACK2_ITERATION}/report.md, with its rendered PDF and methods form`,
      href: `/submissions?it=${TRACK2_ITERATION}`,
    },
    {
      label: 'the tables',
      hint: 'ressources/track2/*.tsv — every column, with the provenance manifest behind each file',
      href: `#${ANCHOR.catalog}`,
    },
    {
      label: 'the figures',
      hint: 'figures/track2/*.png — the rendered figures the report embeds',
      href: 'figures/track2',
      repo: true,
    },
    ...METHODOLOGY.map((m) => ({
      label: `methodology ${m.label}`,
      hint: m.path,
      href: m.path,
      repo: true,
    })),
    {
      label: `register ${span}`,
      hint: `${claims.length} claims filed with a prediction and a refutation condition before the search ran`,
      href: `#${ANCHOR.register}`,
    },
  ];
}

export function Hero({ data, source }: { data: Track2; source?: string }) {
  const steps = useMemo(() => approachSteps(data), [data]);
  const groups = useMemo(() => argueByDirection(data), [data]);
  const stages = useMemo(() => funnelStages(data), [data]);
  const aside = useMemo(() => setAside(data), [data]);
  const links = useMemo(() => artefacts(data), [data]);

  const caution = (data.do_not ?? []).filter((r) => r.verdict === 'caution');

  return (
    <Section
      title="Track 2 in one screen"
      id="track-2-in-one-screen"
      subtitle="the approach, the suggestion and the output — each panel links down to the section that shows its working"
    >
      <div className="space-y-4">
        <ApproachFlow steps={steps} source={source} />
        <div className="grid items-start gap-4 xl:grid-cols-2">
          <Suggestion
            groups={groups}
            evidence={data.evidence ?? []}
            caution={caution}
            contextOnly={contextOnlyCount(data)}
            tumourContext={data.summary.card.tumour_context}
            standardOfCare={data.card.case.context_standard_of_care?.drugs ?? []}
            source={source}
          />
          <Output
            stages={stages}
            setAside={aside}
            artefacts={links}
            unmeasured={unmeasuredFacts(data)}
            measured={data.card.measured_facts ?? []}
            source={source}
          />
        </div>
      </div>
    </Section>
  );
}
