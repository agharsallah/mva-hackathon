/**
 * FigureLightbox — one rendered figure, opened large and citable.
 *
 * A figure on this app is evidence: it appears in the uploaded report, so a reviewer has to
 * be able to point at *one* of them. That makes the open figure a **view selection**, and
 * this app's rule for a view selection is that it lives in the URL — the caller owns a
 * `?figure=<slug>` parameter and hands the slug in, so loading that address opens this
 * dialog directly and "copy link" produces a complete citation.
 *
 * Everything else here is the modal contract the DOM asks for and nothing more: a labelled
 * `role="dialog"` with `aria-modal`, Escape and backdrop to close, Tab cycling inside the
 * panel, and focus returned to whatever opened it.
 */

import { type ReactNode, useCallback, useEffect, useRef, useState } from 'react';

import { API_URL } from '../api/client';
import type { SubmissionFigure } from '../api/types';
import { cx } from '../lib/ui';

/** The API serves the PNG; a relative route is prefixed, an absolute URL is left alone. */
function figureSrc(url: string): string {
  return url.startsWith('/') ? `${API_URL}${url}` : url;
}

const BTN =
  'rounded-control border border-line bg-panel-raised px-2 py-1 text-micro text-chrome-300 transition hover:border-line-strong hover:text-chrome-50 focus:outline-none focus-visible:ring-1 focus-visible:ring-focus disabled:opacity-40';

function useReturnFocus(open: boolean): void {
  const opener = useRef<Element | null>(null);
  useEffect(() => {
    if (!open) return;
    opener.current = document.activeElement;
    return () => {
      const back = opener.current;
      if (back instanceof HTMLElement) back.focus();
    };
  }, [open]);
}

/** Tab and Shift+Tab cycle inside the panel; Escape closes; ← / → walk the set. */
function useDialogKeys(
  panel: React.RefObject<HTMLDivElement | null>,
  onClose: () => void,
  onStep: (delta: number) => void,
): void {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key === 'ArrowRight') return onStep(1);
      if (event.key === 'ArrowLeft') return onStep(-1);
      if (event.key !== 'Tab') return;
      const focusable = [
        ...(panel.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])') ?? []),
      ];
      if (focusable.length === 0) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !panel.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [panel, onClose, onStep]);
}

export interface FigureLightboxProps {
  figures: SubmissionFigure[];
  /** The slug of the open figure, or null when the dialog is closed. Comes from the URL. */
  slug: string | null;
  /** Write a new slug (or null) back to the URL. */
  onSelect: (slug: string | null) => void;
  /** What "copy link" should copy — the caller knows the address of its own page. */
  linkFor: (slug: string) => string;
}

export function FigureLightbox({ figures, slug, onSelect, linkFor }: FigureLightboxProps) {
  const index = figures.findIndex((f) => f.slug === slug);
  const open = index >= 0;
  const figure = open ? figures[index]! : null;
  const panel = useRef<HTMLDivElement>(null);
  const [actual, setActual] = useState(false);
  const [copied, setCopied] = useState(false);

  const close = useCallback(() => onSelect(null), [onSelect]);
  const step = useCallback(
    (delta: number) => {
      if (figures.length === 0) return;
      const at = figures.findIndex((f) => f.slug === slug);
      if (at < 0) return;
      const next = (at + delta + figures.length) % figures.length;
      onSelect(figures[next]!.slug);
    },
    [figures, slug, onSelect],
  );

  useReturnFocus(open);
  useDialogKeys(panel, close, step);
  useEffect(() => {
    setActual(false);
    setCopied(false);
  }, [slug]);
  useEffect(() => {
    if (open) panel.current?.querySelector('button')?.focus();
  }, [open]);

  if (!figure) return null;

  async function copy() {
    try {
      await navigator.clipboard?.writeText(linkFor(figure!.slug));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-chrome-950/85 p-4"
      data-testid="figure-lightbox-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
      role="presentation"
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={`figure ${figure.slug}`}
        className="flex max-h-full w-full max-w-5xl flex-col gap-2 rounded-card border border-line bg-panel p-3"
      >
        <Bar
          left={
            <span className="font-mono text-micro text-chrome-400">
              figure {index + 1} of {figures.length} · {figure.slug}
            </span>
          }
        >
          <button type="button" className={BTN} onClick={() => setActual(!actual)}>
            {actual ? 'fit to window' : 'zoom 1:1'}
          </button>
          <button type="button" className={BTN} onClick={() => step(-1)}>
            ← prev
          </button>
          <button type="button" className={BTN} onClick={() => step(1)}>
            next →
          </button>
          <button type="button" className={BTN} onClick={copy}>
            {copied ? 'link copied' : 'copy link'}
          </button>
          <a className={BTN} href={figureSrc(figure.url)} target="_blank" rel="noreferrer">
            open PNG in new tab
          </a>
          <button type="button" className={BTN} onClick={close} aria-label="close figure">
            close ✕
          </button>
        </Bar>

        <div
          className={cx(
            'min-h-0 flex-1 rounded-control border border-line-soft bg-well p-2',
            actual ? 'overflow-auto' : 'overflow-hidden',
          )}
        >
          <img
            src={figureSrc(figure.url)}
            alt={figure.slug.replace(/[-_]/g, ' ')}
            className={actual ? 'max-w-none' : 'mx-auto max-h-[70vh] w-auto object-contain'}
          />
        </div>

        <p className="font-mono text-micro break-all text-chrome-400">
          {figure.path} · <span className="text-chrome-400">?figure={figure.slug}</span>
        </p>
      </div>
    </div>
  );
}

function Bar({ left, children }: { left: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      {left}
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}
