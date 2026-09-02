/**
 * Badge — a small coloured pill for a verdict, a warning tag, or a boolean flag.
 *
 * `NormChip` already does exactly this for one specific verdict shape (`within/above/below`);
 * this is the general version, for the other places the same recipe was being hand-typed: the
 * amber "gap" tags on the Catalog tables, the boolean rare/protein-altering flags in the pair
 * comparator, ClinVar assertion tags. The tone vocabulary is `lib/palette`'s `Tone`, shared with
 * `StatTile` and `Callout`, so a badge and the tile it sits on cannot disagree about what a
 * colour means.
 */
import type { ReactNode } from 'react';

import type { Tone } from '../lib/palette';
import { BADGE, cx } from '../lib/ui';

export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Badge({ tone = 'neutral', children, className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cx(
        'inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[10px] font-medium',
        BADGE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** A boolean rendered as a badge: green when true, grey when false, a third "unknown" state
 * for `null` — the shape every ad hoc on/off pill in this app already converges on. */
export function Flag({
  on,
  yes,
  no,
  unknown = 'unknown',
}: {
  on: boolean | null;
  yes: ReactNode;
  no: ReactNode;
  unknown?: ReactNode;
}) {
  if (on === null) return <Badge tone="neutral">{unknown}</Badge>;
  return <Badge tone={on ? 'good' : 'neutral'}>{on ? yes : no}</Badge>;
}
