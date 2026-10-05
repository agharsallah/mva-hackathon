/**
 * Explainer — the page's background panel.
 *
 * The audience is a software engineer with no background in the problem domain, so every
 * page opens by naming its concepts in the repo's house pattern:
 * `technical term (plain-English meaning)`.
 * The jargon is never removed, only paired with its translation, because the reader has to
 * recognise the real word in a tool flag or a paper later.
 *
 * Layout rule: the intro is always visible, the terms are always *discoverable* but never
 * cost more than one row by default. Each term is a chip; clicking one reveals just that
 * definition, and "all definitions" opens the full glossary. That choice is remembered
 * across pages, so a reader who wants the glossary open sees it open everywhere.
 */

import { type ReactNode, useState } from 'react';
import { Link } from 'react-router-dom';

import type { Tone } from '../lib/palette';
import { cx, RULE, TEXT, TINT } from '../lib/ui';

export interface Term {
  term: string;
  /** The plain-English half. Keep it one sentence. */
  plain: ReactNode;
  /**
   * The dictionary entry's slug (`/learn#<slug>`), when the word has one. The chip's one
   * sentence stays; this adds "full definition" under it, so the page never restates the
   * dictionary and the dictionary stays the one glossary. `src/test/explainer-dict.test.ts`
   * requires it whenever the term matches an entry by name.
   */
  dict?: string;
}

function FullDefinition({ slug }: { slug?: string }) {
  if (!slug) return null;
  return (
    <Link
      to={`/learn#${slug}`}
      className="ml-2 font-sans text-micro whitespace-nowrap text-machinery-300 hover:text-machinery-200"
    >
      full definition <span aria-hidden="true">→</span>
    </Link>
  );
}

export interface ExplainerProps {
  /** What this page is for, in one or two sentences. */
  intro: ReactNode;
  terms: Term[];
  /** Something the reader should be warned about before believing the charts. */
  caveat?: ReactNode;
}

const PREF_KEY = 'app.explainer.definitions';

function readPref(): boolean {
  try {
    return window.localStorage.getItem(PREF_KEY) === 'open';
  } catch {
    return false;
  }
}

function writePref(open: boolean) {
  try {
    window.localStorage.setItem(PREF_KEY, open ? 'open' : 'closed');
  } catch {
    /* private mode or blocked storage: the toggle still works for this page */
  }
}

export function Explainer({ intro, terms, caveat }: ExplainerProps) {
  const [allOpen, setAllOpen] = useState(readPref);
  const [picked, setPicked] = useState<string | null>(null);
  const shown = picked ? terms.find((t) => t.term === picked) : undefined;

  function toggleAll() {
    setAllOpen((v) => {
      writePref(!v);
      return !v;
    });
    setPicked(null);
  }

  return (
    <section aria-label="Background">
      <div className="flex items-start justify-between gap-6">
        <p className="max-w-[70ch] font-serif text-reading leading-relaxed text-chrome-300">
          {intro}
        </p>
        {terms.length > 0 && (
          <button
            type="button"
            onClick={toggleAll}
            aria-pressed={allOpen}
            className="shrink-0 rounded-control border border-line px-2 py-1 text-micro text-chrome-400 transition hover:border-line-strong hover:text-chrome-200"
          >
            {allOpen ? 'hide definitions' : `all ${terms.length} definitions`}
          </button>
        )}
      </div>

      {terms.length > 0 && !allOpen && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="mr-1 text-xs text-chrome-400">Terms</span>
          {terms.map((t) => {
            const on = picked === t.term;
            return (
              <button
                key={t.term}
                type="button"
                aria-pressed={on}
                onClick={() => setPicked(on ? null : t.term)}
                className={cx(
                  'rounded-control border px-2 py-0.5 text-micro transition',
                  on
                    ? 'border-machinery-700 bg-machinery-950/60 text-machinery-200'
                    : 'border-line bg-panel text-chrome-300 hover:border-line-strong hover:text-chrome-100',
                )}
              >
                {t.term}
              </button>
            );
          })}
        </div>
      )}

      {shown && !allOpen && (
        <dl className="mt-2 max-w-[80ch] border-l-2 border-machinery-600 pl-3 text-note leading-relaxed">
          <dt className="inline font-semibold text-chrome-100">{shown.term}</dt>
          <dd className="inline font-serif text-chrome-300">
            {' '}
            {shown.plain}
            <FullDefinition slug={shown.dict} />
          </dd>
        </dl>
      )}

      {allOpen && (
        <dl className="mt-3 grid gap-x-8 gap-y-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {terms.map((t) => (
            <div key={t.term} className="text-note leading-relaxed">
              <dt className="inline font-semibold text-chrome-200">{t.term}</dt>
              <dd className="inline font-serif text-chrome-400">
                {' '}
                {t.plain}
                <FullDefinition slug={t.dict} />
              </dd>
            </div>
          ))}
        </dl>
      )}

      {caveat && (
        <p className="mt-3 max-w-[90ch] border-l-2 border-decision-500 pl-3 font-serif text-note leading-relaxed text-decision-300">
          {caveat}
        </p>
      )}
    </section>
  );
}

/** A pull-out callout for the one thing on the page that changes the conclusion. */
export function Callout({
  tone = 'decision',
  title,
  action,
  children,
}: {
  tone?: Tone;
  title: string;
  /**
   * A control that acts on *this* callout, pinned to the title row — the Status page's
   * per-dependency "re-probe" button. Optional, so every existing call site is unchanged;
   * it exists because a card that reports one service's state is also the only sensible
   * place to put the button that re-measures that service.
   */
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={cx('rounded-r-card border-l-2 px-4 py-3', RULE[tone], TINT[tone])}>
      <div className="flex items-start justify-between gap-3">
        <div className={cx('text-sm font-semibold', TEXT[tone])}>{title}</div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <div className="mt-1 max-w-[80ch] font-serif text-reading leading-relaxed text-chrome-200">
        {children}
      </div>
    </div>
  );
}
