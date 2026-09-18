/**
 * The Track 2 report, in the order a reader needs it: what is being attempted and how far
 * it has got, what it is linked to, then the argument, then the evidence, then the audit
 * trail that lets someone check all of it.
 *
 * Nothing here is a conclusion. The page is deliberately a *report in progress* — the one
 * suggestion Track 2 ends with is produced after every Track 1 iteration is merged, and
 * saying so at the top is more useful than a ranked list nobody could defend yet.
 */

import { useMemo } from 'react';

import type { Result } from '../../api/client';
import type { Track2 } from '../../api/types';
import { Section } from '../../components/Controls';
import { StatTile } from '../../components/StatTile';
import { int } from '../../lib/format';
import { cx, WELL } from '../../lib/ui';
import { BeginnerGuide } from './BeginnerGuide';
import { approvedPerDirection } from './candidateFilters';
import { Candidates } from './Candidates';
import { Catalog } from './Catalog';
import { Directions } from './Directions';
import { Grading } from './Grading';
import { Track2LineageView } from './LineageView';
import { LinkedIterations } from './LinkedIterations';
import { MechanismCardExhibit } from './MechanismCard';
import { Register } from './Register';
import { StrategyTimeline } from './StrategyTimeline';
import { TargetSet } from './TargetSet';
import { Literature, Trials } from './TrialsLiterature';

export function Report({ result }: { result: Result<Track2> }) {
  const data = result.data;
  const source = result.source;
  const perDirection = useMemo(() => approvedPerDirection(data.candidates), [data.candidates]);

  return (
    <div className="space-y-6">
      <Header data={data} />

      <Section
        title="Strategy"
        subtitle="what has run, what can run today, and what is blocked on an oracle reply"
      >
        <StrategyTimeline strategy={data.strategy} source={source} />
      </Section>

      <Section
        title="Linked Track 1 iterations"
        subtitle="the submissions whose hypotheses this mechanism argument cites"
      >
        <LinkedIterations iterations={data.linked_iterations} />
      </Section>

      <BeginnerGuide data={data} />

      <Section
        title="The mechanism argument"
        subtitle="the hand-off from Track 1, and the therapeutic angles it allows"
      >
        <div className="space-y-6">
          <MechanismCardExhibit card={data.card} source={source} />
          <Directions
            directions={data.card.repurposing_directions}
            summary={data.summary}
            candidatesPerDirection={perDirection}
            source={source}
          />
        </div>
      </Section>

      <Grading data={data} source={source} />

      <Section
        title="What a drug could aim at"
        subtitle="the seed genes, and the pathway expansion that widened them into a search space"
      >
        <TargetSet pathways={data.pathways} summary={data.summary} source={source} />
      </Section>

      <Section
        title="The candidates"
        subtitle="every drug-target interaction the public sources reported, market-approved first"
      >
        <Candidates candidates={data.candidates} summary={data.summary} source={source} />
      </Section>

      <Section
        title="What has been tried, and what has been written"
        subtitle="registered studies in the child's tumour context, and the literature behind the directions"
      >
        <div className="space-y-6">
          <Trials
            trials={data.trials}
            trialQueries={data.summary.trial_queries}
            tumourContext={data.summary.card.tumour_context}
            source={source}
          />
          <Literature
            literature={data.literature}
            queries={data.summary.literature_queries}
            source={source}
          />
        </div>
      </Section>

      <Section
        title="What Track 2 claimed, before it searched"
        subtitle="the register: every claim filed before its test ran, with the observation that would kill it"
      >
        <Register register={data.register} source={source} />
      </Section>

      <Section
        title="The tables themselves"
        subtitle="every column in plain English, with the manifest facts behind each file"
      >
        <Catalog catalog={data.catalog} source={source} />
      </Section>

      <Section
        title="Where all of this came from"
        subtitle="the roots the snapshot rests on and the derivations the warehouse recorded"
      >
        <Track2LineageView lineage={data.lineage} source={source} />
      </Section>
    </div>
  );
}

function Header({ data }: { data: Track2 }) {
  const s = data.summary;
  const done = data.strategy.filter((p) => p.status === 'done').length;
  const argued = (data.shortlist ?? []).filter((r) => r.verdict === 'argue').length;
  return (
    <div className={cx(WELL, 'grid grid-cols-2 gap-4 md:grid-cols-6')}>
      <StatTile
        label="mechanism card"
        tone="raw"
        value={`v${data.card.version}`}
        sub={`${s.card.gene} · ${s.card.disease}`}
      />
      <StatTile
        label="targets searched"
        tone="machinery"
        value={int(s.targets.total)}
        sub={`${s.targets.seed} named by the card, ${int(s.targets.pathway)} by pathway`}
      />
      <StatTile
        label="approved candidates"
        tone="good"
        value={int(s.candidates.distinct_approved_drugs)}
        sub={`distinct molecules, from ${int(s.candidates.approved)} rows`}
      />
      <StatTile
        label="evidence rows"
        value={int(data.trials.length + data.literature.length)}
        sub={`${int(data.trials.length)} trials · ${int(data.literature.length)} articles`}
      />
      <StatTile
        label="shortlist"
        tone="good"
        value={int(argued)}
        sub={`rows the report may argue, of ${int((data.shortlist ?? []).length)} graded`}
      />
      <StatTile
        label="strategy"
        tone="decision"
        value={`${done} / ${data.strategy.length}`}
        sub="phases done — the final suggestion waits for every Track 1 iteration"
      />
    </div>
  );
}
