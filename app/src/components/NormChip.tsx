import { Link } from 'react-router-dom';

import type { ObservedExpectedRow } from '../api/types';
import { BADGE, cx } from '../lib/ui';

/**
 * The verdict from `results.qc_observed_expected`, rendered small enough to sit on a
 * `StatTile`.
 *
 * The Overview page states raw figures; the Compare page states whether those figures are
 * *normal*. That is one click too far for the number a reader looks at first, so the
 * verdict is mirrored onto the tile and the chip links back to the full comparison — the
 * band, the citation, and the dumbbell — rather than restating any of it here.
 *
 * A tile whose metric has no published norm gets **nothing**: `pickNorm` (in `./pickNorm`)
 * returns `undefined`, `NormChip` renders `null`, and the tile is byte-identical to before.
 * No caller is obliged to pass a chip.
 */

const TEXT: Record<string, string> = {
  within: 'within norm',
  above: 'above norm',
  below: 'below norm',
  unknown: 'not measured',
};

/** Tailwind classes rather than palette hex, because a tile chip is a background, not a mark.
 * Shares its tone recipes with `Badge` via `lib/ui.ts`'s `BADGE` map. */
const STYLE: Record<string, string> = {
  within: BADGE.good,
  above: BADGE.broken,
  below: BADGE.broken,
  unknown: BADGE.neutral,
};

export function NormChip({ row }: { row?: ObservedExpectedRow }) {
  if (!row) return null;
  const band =
    row.expected_low === row.expected_high
      ? `${fmt(row.expected_low)} ${row.unit} (point estimate)`
      : `${fmt(row.expected_low)}–${fmt(row.expected_high)} ${row.unit}`;
  return (
    <Link
      to="/compare"
      title={`published expectation ${band} — ${row.source}. Full comparison on the Compare page.`}
      className={cx(
        'inline-flex shrink-0 items-center rounded-pill border px-2 py-0.5 text-micro font-medium transition-opacity hover:opacity-75',
        STYLE[row.verdict] ?? STYLE.unknown,
      )}
    >
      {TEXT[row.verdict] ?? row.verdict}
    </Link>
  );
}

/** Compact enough for a tooltip: millions get an `M`, ratios keep two decimals. */
function fmt(v: number): string {
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (Math.abs(v) >= 1000) return v.toLocaleString('en-US');
  return String(v);
}
