/**
 * Exhibit — the only way a chart enters this app.
 *
 * The repo's visualization rule is that every figure carries a Legend line decoding its
 * own colours and symbols. Making `legend` a required prop is how that rule is enforced
 * in code rather than in a review checklist.
 *
 * Being the single wrapper also makes it the single place the AI export can hook: each
 * exhibit registers its own narrative, provenance and payload while it is mounted, so the
 * page-level and case-level exports need nothing from the call sites.
 */

import { type ReactNode, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';

import { copyExport } from '../lib/aiExport/download';
import { exhibitBundle } from '../lib/aiExport/markdown';
import { exhibitRegistry } from '../lib/aiExport/registry';
import type { ExhibitRecord } from '../lib/aiExport/types';
import { nodeText } from '../lib/nodeText';
import { CARD, cx } from '../lib/ui';

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
  /**
   * The endpoint payload behind this figure, for the AI export. Omitted where the payload
   * carries a patient genomic coordinate — see `lib/aiExport/redact.ts`.
   */
  data?: unknown;
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
  data,
  controls,
  className = '',
}: ExhibitProps) {
  const page = useLocation().pathname;
  const legendText = nodeText(legend);
  const readingText = reading === undefined ? undefined : nodeText(reading);
  const record: ExhibitRecord = {
    page,
    title,
    legend: legendText,
    reading: readingText,
    source,
    cachedAt,
    origin,
    data,
  };

  useEffect(() => {
    exhibitRegistry.register({
      page,
      title,
      legend: legendText,
      reading: readingText,
      source,
      cachedAt,
      origin,
      data,
    });
    return () => exhibitRegistry.unregister(page, title);
  }, [page, title, legendText, readingText, source, cachedAt, origin, data]);

  return (
    <figure className={cx(CARD, className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-tight text-zinc-100">{title}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {controls}
          <CopyForAi record={record} />
        </div>
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
              <span className="mr-1.5 rounded bg-amber-500/15 px-1 py-px text-amber-400">
                fixture
              </span>
            )}
            {source}
            {cachedAt ? ` · cached ${cachedAt.replace('T', ' ').slice(0, 19)}` : ''}
          </p>
        )}
      </figcaption>
    </figure>
  );
}

const AI_HINT =
  'Copy this exhibit as Markdown for an AI chat: its legend and reading, its provenance, and the ' +
  'rows behind it as JSON. No genomic coordinate is ever exported.';

function CopyForAi({ record }: { record: ExhibitRecord }) {
  const [said, setSaid] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => () => window.clearTimeout(timer.current ?? undefined), []);

  async function run() {
    const outcome = await copyExport(exhibitBundle(`one exhibit — ${record.title}`, [record]));
    setSaid(outcome);
    window.clearTimeout(timer.current ?? undefined);
    timer.current = window.setTimeout(() => setSaid(null), 3500);
  }

  return (
    <button
      type="button"
      onClick={run}
      title={AI_HINT}
      className={`rounded-md border px-2 py-0.5 text-[11px] transition focus:outline-none focus-visible:border-blue-700 ${
        said
          ? 'border-emerald-800 bg-emerald-950/40 text-emerald-400'
          : 'border-zinc-800 bg-zinc-900 text-zinc-500 hover:border-zinc-700 hover:text-zinc-300'
      }`}
    >
      {said ?? 'copy for AI'}
    </button>
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
