/**
 * The course outline: fifteen chapters in the order the dictionary wants them read, with
 * the reader's own progress ticked off. The order is not ours — the markdown is arranged so
 * every word uses only words defined above it, so chapter n is the prerequisite of n+1.
 */

import { Link } from 'react-router-dom';

import type { Chapter } from '../../lib/dictionary';
import { cx } from '../../lib/ui';

export function ChapterRail({
  chapters,
  current,
  read,
  onToggleRead,
}: {
  chapters: Chapter[];
  current: Chapter;
  read: ReadonlySet<string>;
  onToggleRead: (id: string) => void;
}) {
  const done = chapters.filter((c) => read.has(c.id)).length;
  const pct = Math.round((done / chapters.length) * 100);
  return (
    <nav aria-label="Chapters" className="space-y-3">
      <div>
        <div className="flex items-baseline justify-between text-micro text-chrome-500">
          <span>Course progress</span>
          <span className="tabular-nums">
            {done} of {chapters.length}
          </span>
        </div>
        <div
          role="progressbar"
          aria-label="Chapters read"
          aria-valuemin={0}
          aria-valuemax={chapters.length}
          aria-valuenow={done}
          className="mt-1 h-1 overflow-hidden rounded-pill bg-chrome-900"
        >
          <div className="h-full bg-good-500 transition-[width]" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <ol className="space-y-0.5">
        {chapters.map((c) => {
          const isCurrent = c.id === current.id;
          const isRead = read.has(c.id);
          const terms = c.blocks.filter((b) => b.kind === 'entry').length;
          return (
            <li key={c.id} className="flex items-stretch gap-1">
              <button
                type="button"
                onClick={() => onToggleRead(c.id)}
                aria-pressed={isRead}
                aria-label={`${isRead ? 'Unmark' : 'Mark'} chapter ${c.number} as read`}
                className={cx(
                  'w-5 shrink-0 self-center rounded-pill text-center text-micro leading-5 transition',
                  isRead
                    ? 'bg-good-950/60 text-good-400'
                    : 'text-chrome-700 hover:bg-chrome-900 hover:text-chrome-400',
                )}
              >
                {isRead ? '✓' : c.number}
              </button>
              <Link
                to={{ hash: `#${c.id}` }}
                aria-current={isCurrent ? 'page' : undefined}
                className={cx(
                  'flex min-w-0 flex-1 items-baseline justify-between gap-2 rounded-control px-2 py-1 text-xs transition',
                  isCurrent
                    ? 'bg-chrome-800 text-chrome-50'
                    : 'text-chrome-400 hover:bg-chrome-900 hover:text-chrome-200',
                )}
              >
                <span className="truncate">{c.title}</span>
                <span className="shrink-0 tabular-nums text-micro text-chrome-600">{terms}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
