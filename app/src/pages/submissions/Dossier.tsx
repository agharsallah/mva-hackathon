import type { Result } from '../../api/client';
import type { Submissions } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Section } from '../../components/Controls';
import { EmptyState } from '../../components/EmptyState';
import { cx, RULE, WELL } from '../../lib/ui';
import { useUrlState } from '../../lib/urlstate';
import { CatalogPanel } from '../iterations/CatalogPanel';
import { Artifacts } from './Artifacts';
import { AuditTrail } from './AuditTrail';
import { BeginnerGuide } from './BeginnerGuide';
import { Contributions } from './Contributions';
import { DecodeExhibit } from './DecodeExhibit';
import { DerivationExhibit } from './DerivationExhibit';
import { DossierLinks } from './DossierLinks';
import { EpcrLadder } from './EpcrLadder';
import { isPanelJudged, iterationKey, newestFirst, PANEL_DELIVERABLES } from './iteration';
import { IterationHeader } from './IterationHeader';
import { IterationPicker } from './IterationPicker';
import { LineageView } from './LineageView';
import { PanelGuide } from './PanelGuide';
import { Paperwork } from './Paperwork';
import { ReplyOdds } from './ReplyOdds';
import { SelectorsExhibit } from './SelectorsExhibit';
import { TwoInputs } from './TwoInputs';

/**
 * One iteration, opened.
 *
 * Cumulative by design: the picker lists every folder the endpoint returns, one chip row per
 * track, opening on the newest, because a frozen folder is never edited — iteration 2 exists *because* of what
 * iteration 1's reply said, and comparing them is the point. The selection lives in the
 * URL, so one address is a complete citation of one dossier.
 */
export function Dossier({ result }: { result: Result<Submissions> }) {
  const iterations = newestFirst(result.data.iterations);
  const keys = iterations.map(iterationKey);
  const [picked, setPicked] = useUrlState('it', keys[0] ?? '', keys);
  const iteration = iterations.find((i) => iterationKey(i) === picked) ?? iterations[0];
  const source = result.source;
  // A panel-judged track has no scorer, so the decode table, the epcr ladder and the
  // selectors have nothing to describe — see `isPanelJudged`.
  const panel = iteration ? isPanelJudged(iteration) : false;

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
      <div className="space-y-2">
        <IterationPicker iterations={iterations} picked={picked} onPick={setPicked} />
        <p className="text-micro text-chrome-400">
          {iterations.filter((i) => !isPanelJudged(i)).length} of 6 oracle uploads planned or spent
          {iterations.some(isPanelJudged) ? ' (a panel-judged folder uses none)' : ''} · a frozen
          folder is never edited
        </p>
      </div>

      <DossierLinks iteration={iteration} />

      <p className="text-micro text-chrome-400">
        New iterations appear here automatically once their folder exists — recipe in{' '}
        <span className="font-mono">submissions/README.md</span>.
      </p>

      <IterationHeader iteration={iteration} panelJudged={panel} />

      {panel ? <PanelGuide iteration={iteration} /> : <BeginnerGuide iteration={iteration} />}

      <Section
        title="Two inputs, one answer"
        subtitle="the clinical dataset beside the raw dataset — every conclusion is cross-referenced against both"
      >
        <TwoInputs iteration={iteration} source={source} />
      </Section>

      {panel ? (
        <Section
          title="What the panel receives"
          subtitle="a panel-judged track: no predictions file, no decode table, no selectors — people read it"
        >
          <PanelHandover />
        </Section>
      ) : (
        <>
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
              <DerivationExhibit selectors={iteration.selectors} source={source} />
            </div>
          </Section>
        </>
      )}

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
        title="What data it rests on"
        subtitle="every dataset the contributing entries name, and the edge or manifest that explains it"
      >
        <CatalogPanel
          catalog={iteration.catalog}
          title={`The data catalogue of ${iterationKey(iteration)}`}
          source={source}
        />
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

/**
 * What a panel-judged iteration hands over, in place of the three scored-submission
 * sections. Stated rather than left blank: an absent decode table is a rule of the track,
 * not a gap in the work.
 */
function PanelHandover() {
  return (
    <div className={cx(WELL, 'space-y-2 border-l-2', RULE.machinery)} data-testid="panel-handover">
      <p className="max-w-[90ch] font-serif text-note leading-relaxed text-chrome-300">
        This track is <strong className="text-chrome-100">panel-judged</strong>: there is no scorer
        to upload to, so this folder carries no predictions CSV, no decode table and no
        coordinate-free selectors. Four things are handed over instead, and all four are in the
        repository.
      </p>
      <ul className="flex flex-wrap gap-2">
        {PANEL_DELIVERABLES.map((d) => (
          <li key={d}>
            <Badge tone="machinery">{d}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}
