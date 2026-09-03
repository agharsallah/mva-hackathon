/**
 * PageHeader — the one h1 on a page, with the question it serves above it and the next
 * stop on the journey beside it. Rendered once by the shell (`app/PageFrame.tsx`) from
 * the module manifest, so no page file writes its own title and none can forget one.
 */

import { Link } from 'react-router-dom';

export interface JourneyLink {
  to: string;
  label: string;
  preload?: () => void;
}

export interface PageHeaderProps {
  /** Section word and its question, e.g. "Data · Is the measurement trustworthy?" */
  eyebrow?: string;
  /** "2 of 3" — the page's place in its section. */
  position?: string;
  title: string;
  description?: string;
  prev?: JourneyLink;
  next?: JourneyLink;
}

const STEP =
  'flex flex-col rounded-control border border-line px-3 py-2 leading-tight transition hover:border-line-strong hover:bg-chrome-900/60 focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-600';

export function PageHeader({ eyebrow, position, title, description, prev, next }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 border-b border-line pb-5">
      <div className="max-w-4xl min-w-0">
        {(eyebrow || position) && (
          <p className="flex flex-wrap items-baseline gap-x-3 font-serif text-reading text-chrome-400 italic">
            {eyebrow && <span>{eyebrow}</span>}
            {position && (
              <span className="font-sans text-xs text-chrome-500 not-italic">page {position}</span>
            )}
          </p>
        )}
        <h1 className="mt-1 font-serif text-title leading-tight font-medium tracking-tight text-chrome-50">
          {title}
        </h1>
        {description && (
          <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-chrome-400">{description}</p>
        )}
      </div>
      {(prev || next) && (
        <nav aria-label="Journey" className="flex items-stretch gap-2">
          {prev && (
            <Link
              to={prev.to}
              onPointerEnter={prev.preload}
              onFocus={prev.preload}
              className={STEP}
            >
              <span className="text-micro text-chrome-500">Previous</span>
              <span className="text-sm text-chrome-200">{prev.label}</span>
            </Link>
          )}
          {next && (
            <Link
              to={next.to}
              onPointerEnter={next.preload}
              onFocus={next.preload}
              className={STEP + ' text-right'}
            >
              <span className="text-micro text-chrome-500">Next</span>
              <span className="text-sm text-chrome-200">{next.label}</span>
            </Link>
          )}
        </nav>
      )}
    </div>
  );
}

/**
 * JourneyFooter — the bottom-of-page hand-off: where the reader has been and where the
 * journey goes next, with each page's one-line description so the choice is informed.
 */
export function JourneyFooter({
  prev,
  next,
}: {
  prev?: JourneyLink & { description?: string; eyebrow?: string };
  next?: JourneyLink & { description?: string; eyebrow?: string };
}) {
  if (!prev && !next) return null;
  return (
    <nav
      aria-label="Continue the journey"
      className="grid gap-3 border-t border-line pt-5 sm:grid-cols-2"
    >
      {prev ? <JourneyCard dir="prev" {...prev} /> : <span aria-hidden="true" />}
      {next && <JourneyCard dir="next" {...next} />}
    </nav>
  );
}

function JourneyCard({
  dir,
  to,
  label,
  description,
  eyebrow,
  preload,
}: JourneyLink & { dir: 'prev' | 'next'; description?: string; eyebrow?: string }) {
  return (
    <Link
      to={to}
      onPointerEnter={preload}
      onFocus={preload}
      className={
        'group rounded-card border border-line bg-panel p-4 transition hover:border-line-strong hover:bg-chrome-900/70 focus:outline-none focus-visible:ring-1 focus-visible:ring-machinery-600 ' +
        (dir === 'next' ? 'text-right' : '')
      }
    >
      <div className="text-xs text-chrome-500">
        {dir === 'prev' ? 'Previous' : 'Next'}
        {eyebrow && <span className="text-chrome-600">, in {eyebrow}</span>}
      </div>
      <div className="mt-1 font-serif text-heading font-medium text-chrome-100 group-hover:text-chrome-50">
        {label}
      </div>
      {description && (
        <p className="mt-1 max-w-[60ch] text-xs leading-relaxed text-chrome-500">{description}</p>
      )}
    </Link>
  );
}
