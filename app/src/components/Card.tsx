/**
 * Card — the bordered panel used for anything that isn't a chart (that's `Exhibit`) but still
 * wants the same visual weight: a console section, a builder step, a results box.
 *
 * Extracted because the exact class string `rounded-xl border border-zinc-800 bg-zinc-900/40
 * p-4` was hand-typed identically across six-plus page files (Probes console, builder, job
 * monitor, candidate picker, search results). `Exhibit`'s own `<figure>` wrapper uses the same
 * recipe — both now read it from `lib/ui.ts` so the two can never silently drift apart.
 */
import type { ReactNode } from 'react';
import { CARD, cx } from '../lib/ui';

export interface CardProps {
  children: ReactNode;
  /** Extra classes — e.g. `space-y-3` for a card whose children need vertical rhythm. */
  className?: string;
}

export function Card({ children, className }: CardProps) {
  return <div className={cx(CARD, className)}>{children}</div>;
}
