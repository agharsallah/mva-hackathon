import { useState } from 'react';

import { useStepEntry } from '../../api/hooksSteps';
import type { StepEntry } from '../../api/types';
import { Badge } from '../../components/Badge';
import { cx } from '../../lib/ui';

/**
 * The methodology entries of one step — the audit log, readable on the page.
 *
 * An entry is the unit of evidence in this repository: a question, the exact commands, the
 * observed output, and the verdict drawn. The step card used to print their filenames, so
 * the reader's only way to check a verdict was to clone the repository. Here the number and
 * the entry's own heading are the label, and opening one fetches it verbatim — quoted,
 * never summarised, because an append-only log that gets paraphrased on the way to a reader
 * is no longer an audit trail.
 *
 * The gate's own flags stay visible: an entry that declares no inputs, or that read
 * something the blind protocol forbade, is marked here and not only in the checklist.
 */

function EntryBody({ iteration, slug, entry }: { iteration: string; slug: string; entry: string }) {
  const q = useStepEntry(iteration, slug, entry);
  if (q.isPending) return <p className="p-3 text-micro text-chrome-500">loading the entry…</p>;
  if (q.isError || !q.data)
    return (
      <p className="p-3 text-micro text-chrome-400">
        The entry is served by the API and could not be read — either this session is on fixture
        data, or the API is down. The file itself is at the path above.
      </p>
    );
  return (
    <pre className="max-h-[28rem] overflow-auto p-3 font-mono text-micro leading-relaxed whitespace-pre-wrap text-chrome-300">
      {q.data.data.markdown}
    </pre>
  );
}

export function EntryList({
  iteration,
  slug,
  entries,
}: {
  iteration: string;
  slug: string;
  entries: StepEntry[];
}) {
  const [open, setOpen] = useState<string | null>(null);

  if (entries.length === 0) {
    return (
      <p className="text-micro text-chrome-500">
        No methodology entry is filed under this step yet, so nothing has been executed under it.
      </p>
    );
  }

  return (
    <ul className="space-y-1">
      {entries.map((e) => {
        const isOpen = open === e.entry;
        return (
          <li key={e.entry} className="rounded-control border border-line-soft bg-well">
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : e.entry)}
              aria-expanded={isOpen}
              className={cx(
                'flex w-full flex-wrap items-baseline gap-2 px-2 py-1.5 text-left',
                'focus:outline-none focus-visible:ring-1 focus-visible:ring-focus',
              )}
            >
              <Badge tone={e.violations.length > 0 ? 'broken' : 'machinery'}>
                {e.number || 'entry'}
              </Badge>
              <span className="flex-1 text-xs text-chrome-200">{e.title || e.entry}</span>
              {e.unblinds && <Badge tone="decision">unblinds</Badge>}
              {!e.declares_inputs && <Badge tone="broken">no inputs declared</Badge>}
              <span className="text-micro text-chrome-500">{isOpen ? 'close' : 'read'}</span>
            </button>
            {isOpen && (
              <div className="border-t border-line-soft">
                <p className="px-3 pt-2 font-mono text-micro break-all text-chrome-500">{e.path}</p>
                <EntryBody iteration={iteration} slug={slug} entry={e.entry} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
