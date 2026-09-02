import type { ReactNode } from 'react';

import type { Tone } from '../lib/palette';
import { cx, TEXT } from '../lib/ui';

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
    <div className="rounded-xl border border-chrome-800 bg-chrome-900/40 p-3.5" title={hint}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-chrome-500">
          {label}
        </div>
        {chip}
      </div>
      <div className={cx('mt-1 font-mono text-2xl leading-none', TEXT[tone])}>{value}</div>
      {sub && <div className="mt-1.5 font-mono text-[11px] text-chrome-500">{sub}</div>}
    </div>
  );
}
