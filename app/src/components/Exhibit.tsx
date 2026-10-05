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
  /** The endpoint payload behind this figure, for the AI export. */
  data?: unknown;
  /** Controls (toggles, selects) rendered on the title row. */
  controls?: ReactNode;
  className?: string;
  /**
   * The DOM id, so another page can deep-link to this figure with `#id` — the Learn page's
   * "see it in the app" links do. Defaults to a slug of the title; pass one when the title
   * carries a variable the reader can change and the link must survive that change.
   */
  id?: string;
}

/** "Depth by bin — the coverage screen" → "depth-by-bin-the-coverage-screen". */
function exhibitAnchor(title: string): string {
  return title
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
}

export function Exhibit({
  title,
  legend,
  children,
  reading,
  source,
  cachedAt,
  data,
  controls,
  className = '',
  id,
}: ExhibitProps) {
  const { pathname: page, hash } = useLocation();
  const anchor = id ?? exhibitAnchor(title);
  const figureRef = useRef<HTMLElement>(null);
  const legendText = nodeText(legend);
  const readingText = reading === undefined ? undefined : nodeText(reading);
  const record: ExhibitRecord = {
    page,
    title,
    legend: legendText,
    reading: readingText,
    source,
    cachedAt,
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
      data,
    });
    return () => exhibitRegistry.unregister(page, title);
  }, [page, title, legendText, readingText, source, cachedAt, data]);

  // A deep link lands here: the page is a lazy chunk, so the browser's own hash scroll ran
  // before this figure existed. Once it mounts under the URL's hash, it puts itself on screen.
  useEffect(() => {
    if (hash === `#${anchor}`) figureRef.current?.scrollIntoView({ block: 'start' });
  }, [hash, anchor]);

  return (
    <figure ref={figureRef} id={anchor} className={cx(CARD, 'scroll-mt-28', className)}>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold tracking-tight text-chrome-100">{title}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {controls}
          <CopyForAi record={record} />
        </div>
      </div>
      {children}
      <figcaption className="mt-3 space-y-2 border-t border-line pt-3">
        <p className="text-xs leading-relaxed text-chrome-400">
          <span className="mr-2 font-semibold text-chrome-300">Legend</span>
          {legend}
        </p>
        {reading && (
          <p className="max-w-[90ch] font-serif text-note leading-relaxed text-chrome-300">
            <span className="mr-2 font-sans text-xs font-semibold text-chrome-300">Reading</span>
            {reading}
          </p>
        )}
        {source && (
          // The per-reply `source` strings now carry URLs and cache keys, so they must wrap
          // rather than run off the card: `break-words` breaks a long token only when it
          // cannot fit, leaving normal prose alone.
          <p className="font-mono text-micro break-words text-chrome-600">
            {source}
            {cachedAt ? `, cached ${cachedAt.replace('T', ' ').slice(0, 19)}` : ''}
          </p>
        )}
      </figcaption>
    </figure>
  );
}

const AI_HINT =
  'Copy this exhibit as Markdown for an AI chat: its legend and reading, its provenance, and the ' +
  'rows behind it as JSON.';

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
      className={`rounded-control border px-2 py-0.5 text-micro transition focus:outline-none focus-visible:border-machinery-700 ${
        said
          ? 'border-good-800 bg-good-950/40 text-good-300'
          : 'border-line bg-chrome-900 text-chrome-400 hover:border-line-strong hover:text-chrome-300'
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
