/**
 * Explainer — the page's intro panel.
 *
 * The audience is a software engineer with no genomics background, so every page opens by
 * naming its concepts in the repo's house pattern: `technical term (plain-English meaning)`.
 * The jargon is never removed, only paired with its translation, because the reader has to
 * recognise the real word in a tool flag or a paper later.
 */

import { useState, type ReactNode } from 'react';
import { BOX, cx } from '../lib/ui';

export interface Term {
  term: string;
  /** The plain-English half. Keep it one sentence. */
  plain: ReactNode;
}

export interface ExplainerProps {
  /** What this page is for, in one or two sentences. */
  intro: ReactNode;
  terms: Term[];
  /** Something the reader should be warned about before believing the charts. */
  caveat?: ReactNode;
}

export function Explainer({ intro, terms, caveat }: ExplainerProps) {
  const [open, setOpen] = useState(true);
  return (
    <section className="rounded-xl border border-blue-900/40 bg-blue-950/20 p-4">
      <div className="flex items-start justify-between gap-4">
        <p className="max-w-4xl text-sm leading-relaxed text-zinc-300">{intro}</p>
        <button
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:bg-zinc-800"
        >
          {open ? 'hide terms' : `show ${terms.length} terms`}
        </button>
      </div>
      {open && (
        <dl className="mt-3 grid gap-x-6 gap-y-2 border-t border-blue-900/40 pt-3 sm:grid-cols-2 xl:grid-cols-3">
          {terms.map((t) => (
            <div key={t.term} className="text-xs leading-relaxed">
              <dt className="inline font-semibold text-zinc-200">{t.term}</dt>
              <dd className="inline text-zinc-400"> — {t.plain}</dd>
            </div>
          ))}
        </dl>
      )}
      {caveat && (
        <p className="mt-3 border-t border-blue-900/40 pt-3 text-xs leading-relaxed text-amber-400/90">
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
  children,
}: {
  tone?: 'good' | 'broken' | 'decision' | 'neutral';
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={cx('rounded-xl border p-4', BOX[tone])}>
      <div className="text-xs font-semibold uppercase tracking-wider">{title}</div>
      <div className="mt-1.5 text-sm leading-relaxed text-zinc-300">{children}</div>
    </div>
  );
}
