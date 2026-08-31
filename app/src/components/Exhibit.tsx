/**
 * Exhibit — the only way a chart enters this app.
 *
 * The repo's visualization rule is that every figure carries a Legend line decoding its
 * own colours and symbols. Making `legend` a required prop is how that rule is enforced
 * in code rather than in a review checklist.
 */

import type { ReactNode } from 'react';

export interface ExhibitProps {
  title: string;
  /** REQUIRED. Decode every colour and symbol the figure uses. */
  legend: ReactNode;
  children: ReactNode;
  /** One sentence on what the reader should take away. */
  reading?: ReactNode;
  /** The API's provenance string for these rows. */
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
  /** Controls (toggles, selects) rendered on the title row. */
  controls?: ReactNode;
  className?: string;
}

export function Exhibit({
  title,
  legend,
  children,
  reading,
  source,
  cachedAt,
  origin,
  controls,
  className = '',
}: ExhibitProps) {
  return (
    <figure
      className={`rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 ${className}`}
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-tight text-zinc-100">{title}</h3>
        {controls && <div className="flex flex-wrap items-center gap-2">{controls}</div>}
      </div>
      {children}
      <figcaption className="mt-3 space-y-1.5 border-t border-zinc-800 pt-3">
        <p className="text-xs leading-relaxed text-zinc-400">
          <span className="font-semibold text-zinc-300">Legend</span> — {legend}
        </p>
        {reading && (
          <p className="text-xs leading-relaxed text-zinc-400">
            <span className="font-semibold text-zinc-300">Reading</span> — {reading}
          </p>
        )}
        {(source || origin) && (
          <p className="font-mono text-[11px] text-zinc-600">
            {origin === 'fixture' && (
              <span className="mr-1.5 rounded bg-amber-500/15 px-1 py-px text-amber-400">fixture</span>
            )}
            {source}
            {cachedAt ? ` · cached ${cachedAt.replace('T', ' ').slice(0, 19)}` : ''}
          </p>
        )}
      </figcaption>
    </figure>
  );
}

/** A small coloured chip, used inside legends so the words and the colours agree. */
export function Chip({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} />
      {children}
    </span>
  );
}
