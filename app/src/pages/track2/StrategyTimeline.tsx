/**
 * The Track 2 strategy, as a timeline of phases with their state.
 *
 * The colour convention does the work: **green = done**, **blue = open** (machinery that
 * can run today), **yellow = waiting on the oracle** — a decision point nobody here can
 * take, because the mechanism rests on a pair that only an oracle reply confirms. The
 * ordering is the payload's; nothing here is typed in.
 */

import type { PhaseStatus, StrategyPhase, Track2Strategy } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { C, type Tone } from '../../lib/palette';
import { cx, RULE, TINT } from '../../lib/ui';

const TONE: Record<PhaseStatus, Tone> = {
  done: 'good',
  open: 'machinery',
  waiting: 'decision',
};

const MEANING: Record<PhaseStatus, string> = {
  done: 'run, and its output is on this page',
  open: 'can run today; not started',
  waiting: 'blocked on an oracle reply',
};

const toneOf = (s: string): Tone => TONE[s as PhaseStatus] ?? 'neutral';

export function StrategyTimeline({
  strategy,
  source,
}: {
  strategy: Track2Strategy;
  source?: string;
}) {
  const phases = strategy;
  const done = phases.filter((p) => p.status === 'done').length;
  const waiting = phases.filter((p) => p.status === 'waiting').length;

  return (
    <Exhibit
      title="Strategy — the path to one final suggestion"
      legend={
        <>
          One box per phase, left to right in dependency order.{' '}
          <Chip color={C.good}>green = done</Chip> — {MEANING.done}.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — {MEANING.open}.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — {MEANING.waiting}, so no
          amount of work here moves it. The connector between two boxes is a dependency, not a date.
        </>
      }
      reading={`${done} of ${phases.length} phases have run; ${waiting} are yellow, and both of those wait on the same thing — an oracle reply that confirms the pair the mechanism is argued from.`}
      data={strategy}
      source={source}
    >
      <div className="space-y-3">
        <Callout tone="decision" title="The final suggestion is produced once, at the end">
          Track 2 does not emit a running best guess. Every Track 1 iteration revises the mechanism
          card — a new version with a history entry, never an edit — and the snapshot is re-run
          against it. The ranking is only re-run, and the single Track 2 submission only written,{' '}
          <strong>after all Track 1 iterations are merged</strong>: their evidence and the register
          combined, on a confirmed pair. Everything below this line is the material that merge will
          read, not the answer.
        </Callout>

        <ol className="grid gap-2 md:grid-cols-3 xl:grid-cols-6" data-testid="strategy-phases">
          {phases.map((phase, i) => (
            <Phase key={phase.id} phase={phase} index={i} />
          ))}
        </ol>
      </div>
    </Exhibit>
  );
}

function Phase({ phase, index }: { phase: StrategyPhase; index: number }) {
  const tone = toneOf(phase.status);
  return (
    <li
      data-phase={phase.id}
      data-status={phase.status}
      className={cx('rounded-card border-l-2 p-3', RULE[tone], TINT[tone])}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-mono text-micro text-chrome-500">{index + 1}</span>
        <Badge tone={tone}>{phase.status}</Badge>
      </div>
      <h4 className="mt-1 text-sm font-semibold text-chrome-100">{phase.title}</h4>
      <p className="mt-1 text-micro leading-relaxed text-chrome-400">{phase.detail}</p>
      {phase.depends_on.length > 0 && (
        <p className="mt-2 font-mono text-micro text-chrome-600">
          after {phase.depends_on.join(' + ')}
        </p>
      )}
    </li>
  );
}
