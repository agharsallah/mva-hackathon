import type { SubmissionIteration } from '../../api/types';
import { Badge } from '../../components/Badge';
import { cx } from '../../lib/ui';
import { isPanelJudged, iterationKey, STATE_MEANING, STATE_TONE } from './iteration';

/**
 * The dossier's picker: one chip row per track, each chip carrying its folder's state badge,
 * so "which folders exist, and which one is uploaded" reads at a glance instead of from a
 * dropdown. The selection is the `?it=` parameter, unchanged — the chips only draw it.
 */
export function IterationPicker({
  iterations,
  picked,
  onPick,
}: {
  iterations: SubmissionIteration[];
  picked: string;
  onPick: (key: string) => void;
}) {
  const tracks = [...new Set(iterations.map((i) => i.track))].sort();

  return (
    <div className="space-y-2">
      {tracks.map((track) => {
        const mine = iterations
          .filter((i) => i.track === track)
          .sort((a, b) => a.number - b.number);
        const judged = mine.some(isPanelJudged) ? 'panel-judged' : 'oracle-scored';
        return (
          <div
            key={track}
            role="group"
            aria-label={`${track} submission folders`}
            className="flex flex-wrap items-center gap-2"
          >
            <span className="w-40 shrink-0 text-micro text-chrome-400">
              <span className="font-mono text-chrome-200">{track}</span> · {judged}
            </span>
            {mine.map((i) => {
              const key = iterationKey(i);
              const on = key === picked;
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={on}
                  onClick={() => onPick(key)}
                  title={`${key} — ${STATE_MEANING[i.state]}`}
                  className={cx(
                    'inline-flex items-center gap-2 rounded-control border px-2 py-1 text-micro transition',
                    on
                      ? 'border-machinery-700 bg-machinery-950/60 text-machinery-200'
                      : 'border-line-strong bg-chrome-900 text-chrome-300 hover:bg-chrome-800',
                  )}
                >
                  <span className="font-mono">iteration-{i.number}</span>
                  <Badge tone={STATE_TONE[i.state]}>{i.state}</Badge>
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
