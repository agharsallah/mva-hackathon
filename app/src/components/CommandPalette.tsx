/**
 * The jump palette (⌘K / Ctrl+K): every page, every section on the current page, and the
 * few app-wide actions, filtered as you type and run with Enter. It is the fastest route
 * between two places in the app and needs no pointer — the rail beside the content answers
 * "where am I", this answers "take me there".
 *
 * Only the button and the hotkey live in the entry chunk; the dialog (`PaletteDialog`) is
 * fetched the first time it opens.
 */

import { lazy, Suspense, useEffect, useRef, useState } from 'react';

import { CONTROL, cx } from '../lib/ui';

const PaletteDialog = lazy(() => import('./PaletteDialog'));

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);

  const close = () => {
    setOpen(false);
    button.current?.focus();
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <>
      <button
        ref={button}
        type="button"
        onClick={() => setOpen(true)}
        onPointerEnter={() => void import('./PaletteDialog')}
        aria-haspopup="dialog"
        aria-expanded={open}
        title="Jump to a page, a section or an action"
        className={cx(CONTROL, 'flex items-center gap-2 text-chrome-400')}
      >
        Jump to
        <kbd className="rounded-pill border border-line px-1 font-sans text-[10px] text-chrome-400">
          {IS_MAC ? '⌘K' : 'Ctrl K'}
        </kbd>
      </button>
      {open && (
        <Suspense fallback={null}>
          <PaletteDialog close={close} />
        </Suspense>
      )}
    </>
  );
}
