import type { ReactNode } from 'react';

export interface StatTileProps {
  label: string;
  value: ReactNode;
  /** The exact figure, or the unit, or the denominator. */
  sub?: ReactNode;
  /** Tint the value: neutral machinery by default. */
  tone?: 'neutral' | 'good' | 'broken' | 'decision' | 'raw';
  hint?: string;
  /**
   * Optional badge on the label row — a `NormChip` verdict, where the metric has a
   * published expectation. Omitted on every tile that has none, which is the default.
   */
  chip?: ReactNode;
}

const TONE: Record<NonNullable<StatTileProps['tone']>, string> = {
  neutral: 'text-zinc-100',
  good: 'text-emerald-400',
  broken: 'text-red-400',
  decision: 'text-amber-400',
  raw: 'text-purple-400',
};

export function StatTile({ label, value, sub, tone = 'neutral', hint, chip }: StatTileProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3.5" title={hint}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-zinc-500">{label}</div>
        {chip}
      </div>
      <div className={`mt-1 font-mono text-2xl leading-none ${TONE[tone]}`}>{value}</div>
      {sub && <div className="mt-1.5 font-mono text-[11px] text-zinc-500">{sub}</div>}
    </div>
  );
}
