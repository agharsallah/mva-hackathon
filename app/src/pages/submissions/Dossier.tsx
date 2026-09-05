import type { Result } from '../../api/client';
import type { Submissions } from '../../api/types';
import { Section, Select } from '../../components/Controls';
import { EmptyState } from '../../components/EmptyState';
import { useUrlState } from '../../lib/urlstate';
import { Artifacts } from './Artifacts';
import { AuditTrail } from './AuditTrail';
import { BeginnerGuide } from './BeginnerGuide';
import { Contributions } from './Contributions';
import { DecodeExhibit } from './DecodeExhibit';
import { EpcrLadder } from './EpcrLadder';
import { iterationKey, newestFirst } from './iteration';
import { IterationHeader } from './IterationHeader';
import { LineageView } from './LineageView';
import { Paperwork } from './Paperwork';
import { ReplyOdds } from './ReplyOdds';
import { SelectorsExhibit } from './SelectorsExhibit';
import { TwoInputs } from './TwoInputs';

/**
 * One iteration, opened.
 *
 * Cumulative by design: the picker lists every iteration the endpoint returns, newest
 * first, because a frozen folder is never edited — iteration 2 exists *because* of what
 * iteration 1's reply said, and comparing them is the point. The selection lives in the
 * URL, so one address is a complete citation of one dossier.
 */
export function Dossier({ result }: { result: Result<Submissions> }) {
  const iterations = newestFirst(result.data.iterations);
  const keys = iterations.map(iterationKey);
  const [picked, setPicked] = useUrlState('it', keys[0] ?? '', keys);
  const iteration = iterations.find((i) => iterationKey(i) === picked) ?? iterations[0];
  const source = result.source;

  if (!iteration) {
    return (
      <EmptyState title="No iteration folder yet">
        The endpoint found no{' '}
        <span className="font-mono">submissions/&lt;track&gt;/iteration-n/</span> folder. One is
        created when a submission is first designed; until then there is nothing to upload and
        nothing to freeze.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Select
          label="iteration"
          value={picked}
          options={iterations.map((i) => ({
            value: iterationKey(i),
            label: `${iterationKey(i)} — ${i.state}`,
          }))}
          onChange={setPicked}
        />
        <span className="text-micro text-chrome-500">
          {iterations.length} of 6 oracle uploads planned or spent · newest first · a frozen folder
          is never edited
        </span>
      </div>

      <p className="text-micro text-chrome-500">
        New iterations appear here automatically once their folder exists — recipe in{' '}
        <span className="font-mono">submissions/README.md</span>.
      </p>

      <IterationHeader iteration={iteration} />

      <BeginnerGuide iteration={iteration} />

      <Section
        title="Two inputs, one answer"
        subtitle="the clinical dataset beside the raw dataset — every conclusion is cross-referenced against both"
      >
        <TwoInputs iteration={iteration} source={source} />
      </Section>

      <Section
        title="What every possible reply would mean"
        subtitle="the submission read as a measurement, before it is spent"
      >
        <div className="space-y-6">
          <DecodeExhibit table={iteration.decode_table} source={source} />
          <ReplyOdds table={iteration.decode_table} source={source} />
        </div>
      </Section>

      <Section
        title="What is being claimed"
        subtitle="the submitted rows and the alleles behind them, with no coordinate anywhere"
      >
        <div className="space-y-6">
          <EpcrLadder selectors={iteration.selectors} source={source} />
          <SelectorsExhibit selectors={iteration.selectors} source={source} />
        </div>
      </Section>

      <Section
        title="Which steps contributed"
        subtitle="one row per roadmap step, linked to the append-only entry that produced it"
      >
        <Contributions iteration={iteration} source={source} />
      </Section>

      <Section
        title="Where this submission came from"
        subtitle="the roots it rests on and the derivations the warehouse recorded"
      >
        <LineageView lineage={iteration.lineage} source={source} />
      </Section>

      <Section
        title="What it has cost, and what it moved"
        subtitle="the oracle ledger and the register revisions behind this iteration"
      >
        <AuditTrail audit={iteration.audit} source={source} />
      </Section>

      <Section
        title="The folder itself"
        subtitle="every file, the rendered figures, the methods form and the report source"
      >
        <div className="space-y-6">
          <Artifacts iteration={iteration} source={source} />
          <Paperwork iteration={iteration} source={source} />
        </div>
      </Section>
    </div>
  );
}
