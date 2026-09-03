/**
 * Card — the bordered panel used for anything that isn't a chart (that's `Exhibit`) but still
 * wants the same visual weight: a console section, a builder step, a results box.
 *
 * Extracted because the exact class string `rounded-card border border-line bg-panel
 * p-4` was hand-typed identically across six-plus page files (Probes console, builder, job
 * monitor, candidate picker, search results). `Exhibit`'s own `<figure>` wrapper uses the same
 * recipe — both now read it from `lib/ui.ts` so the two can never silently drift apart.
 */
import type { ReactNode } from 'react';

import { cx } from '../lib/ui';

export interface CardProps {
  children: ReactNode;
  /** Extra classes — e.g. `space-y-3` for a card whose children need vertical rhythm. */
  className?: string;
  /**
   * `panel` (default) is the bordered card everything else is measured against. `well` is the
   * recessed panel that sits *inside* a card — a legend, a code block, a nested list. `plain`
   * keeps the padding rhythm and drops the border, for a card-sized region on the page itself.
   */
  variant?: 'panel' | 'well' | 'plain';
  /** `md` is the card padding (16px); `sm` (12px) for dense grids; `none` for a table flush to the edge. */
  padding?: 'md' | 'sm' | 'none';
}

const VARIANT = {
  panel: 'rounded-card border border-line bg-panel',
  well: 'rounded-control border border-line-soft bg-well',
  plain: 'rounded-card',
} as const;

const PADDING = { md: 'p-4', sm: 'p-3', none: '' } as const;

export function Card({ children, className, variant = 'panel', padding = 'md' }: CardProps) {
  return <div className={cx(VARIANT[variant], PADDING[padding], className)}>{children}</div>;
}
