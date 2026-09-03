/**
 * EmptyState — the dashed box for "nothing here", in the two tones it actually appears in.
 *
 * `neutral` is a plain gap: a filtered table with no matches, a search not yet run. `good` is
 * the register/ledger case — nothing recorded is the *expected* state, not a problem — which
 * is why it is green rather than grey. Both tones were being hand-typed at each call site
 * (`DataTable`'s two empty branches, `science/register.tsx`'s `EmptyRegister`, and a duplicate
 * of that same markup in `probes/ProbeLedger.tsx`); this is the one place the class strings
 * live now.
 */
import type { ReactNode } from 'react';

import type { Tone } from '../lib/palette';
import { cx, EMPTY_DASHED, TEXT } from '../lib/ui';

export interface EmptyStateProps {
  tone?: Tone;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function EmptyState({ tone = 'neutral', title, children, className }: EmptyStateProps) {
  return (
    <div className={cx('rounded-card border p-6 text-center', EMPTY_DASHED[tone], className)}>
      {title && (
        <div className={cx('text-sm font-medium', tone !== 'neutral' && TEXT[tone])}>{title}</div>
      )}
      {children && (
        <div
          className={cx(
            title ? 'mx-auto mt-2 max-w-2xl text-xs leading-relaxed text-chrome-400' : 'text-sm',
          )}
        >
          {children}
        </div>
      )}
    </div>
  );
}
