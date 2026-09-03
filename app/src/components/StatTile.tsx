import type { ReactNode } from 'react';

import type { Tone } from '../lib/palette';
import { cx, RULE, TEXT } from '../lib/ui';

export interface StatTileProps {
  label: string;
  value: ReactNode;
  /** The exact figure, or the unit, or the denominator. */
  sub?: ReactNode;
  /** Tint the value. Plain chrome by default — a number with no verdict attached. */
  tone?: Tone;
  hint?: string;
  /**
   * Optional badge on the label row — a `NormChip` verdict, where the metric has a
   * published expectation. Omitted on every tile that has none, which is the default.
   */
  chip?: ReactNode;
}

export function StatTile({ label, value, sub, tone = 'neutral', hint, chip }: StatTileProps) {
  return (
    <div className={cx('border-l-2 py-0.5 pl-3', RULE[tone])} title={hint}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs text-chrome-500">{label}</div>
        {chip}
      </div>
      <div
        className={cx(
          'tabular-nums mt-1 text-figure leading-none font-semibold tracking-tight',
          TEXT[tone],
        )}
      >
        {value}
      </div>
      {sub && <div className="tabular-nums mt-2 text-xs text-chrome-500">{sub}</div>}
    </div>
  );
}
