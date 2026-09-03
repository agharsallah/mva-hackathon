/**
 * Shared Tailwind class recipes — the strings that were showing up hand-typed, identically,
 * across three or more page files (see `src/components/README.md` for the duplication survey
 * that produced this list).
 *
 * This module never invents a colour. Every utility below names a **semantic family**
 * (`good`, `broken`, `decision`, `machinery`, `raw`, `chrome`) whose `--color-*` custom
 * properties are generated into `src/theme.generated.css` from the same numbers
 * `lib/palette`'s `RAMP` hands to Plotly — so `text-good-400` and `RAMP.good[400]` are one
 * value, checked by `pnpm theme:check`. What lives here is the *recipe* built on that
 * language: "a card is this border, this background, this padding", spelled once by name
 * instead of retyped with a one-character drift between copies.
 *
 * Shade roles, kept consistent across every recipe below so a new tone has an obvious answer:
 *
 * | role       | shade | used for                                  |
 * | ---------- | ----- | ----------------------------------------- |
 * | text       | 300/400 | the label or number itself              |
 * | border     | 800/900 | the box edge                            |
 * | background | 950     | the tint behind it (always at low alpha) |
 *
 * The maps are `Record<Tone, string>` and the class strings are literal on purpose: Tailwind
 * discovers utilities by scanning source text, so a class assembled from a template string
 * would silently never be generated. Typed by `Tone` means adding a tone breaks compilation
 * here until every map answers for it — see `lib/palette/tones.ts`.
 */

import type { Tone } from './palette';

/** Join class fragments, dropping falsy ones. `cx('a', cond && 'b', undefined)` → `'a b'`. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

/** The bordered panel every exhibit, card and console section sits in. */
export const CARD = 'rounded-card border border-line bg-panel p-4';

/** A recessed panel inside a card — a code block, a legend well, a nested list. */
export const WELL = 'rounded-control border border-line-soft bg-well p-3';

/** A small control: button, select, input. Border, radius, type size; no colour. */
export const CONTROL =
  'rounded-control border border-line bg-panel-raised px-2 py-1 text-micro transition hover:border-line-strong focus:outline-none focus-visible:ring-1 focus-visible:ring-focus';

/**
 * The alert/callout box, one entry per tone. `Callout` is the canonical user; anything
 * reaching for its own warning box should reach for `BOX.decision` (or `Callout` itself)
 * rather than retyping the classes.
 */
export const BOX: Record<Tone, string> = {
  neutral: 'border-line bg-panel text-chrome-300',
  good: 'border-good-800/60 bg-good-950/25 text-good-300',
  broken: 'border-broken-900/60 bg-broken-950/25 text-broken-300',
  decision: 'border-decision-800/60 bg-decision-950/25 text-decision-300',
  machinery: 'border-machinery-900/60 bg-machinery-950/25 text-machinery-300',
  raw: 'border-raw-800/60 bg-raw-950/25 text-raw-300',
};

/**
 * The small pill badge: a verdict or a flag rendered as a coloured chip. Deeper background
 * and a harder border than `BOX` — a badge is a mark, not a region.
 */
export const BADGE: Record<Tone, string> = {
  neutral: 'border-line-strong bg-chrome-900 text-chrome-400',
  good: 'border-good-800 bg-good-950/60 text-good-400',
  broken: 'border-broken-900 bg-broken-950/60 text-broken-400',
  decision: 'border-decision-800 bg-decision-950/60 text-decision-400',
  machinery: 'border-machinery-900 bg-machinery-950/60 text-machinery-400',
  raw: 'border-raw-800 bg-raw-950/60 text-raw-400',
};

/**
 * The dashed empty-state box. `neutral` is a plain gap (a filtered table with no matches);
 * `good` is the register/ledger case where nothing recorded is the *expected* state, which
 * is why it is green rather than grey. The other tones exist so the map is total over `Tone`
 * and an empty state can say "nothing here, and that is a problem" if one ever needs to.
 */
export const EMPTY_DASHED: Record<Tone, string> = {
  neutral: 'border-dashed border-line text-chrome-500',
  good: 'border-dashed border-good-900/50 bg-good-950/10',
  broken: 'border-dashed border-broken-900/50 bg-broken-950/10',
  decision: 'border-dashed border-decision-900/50 bg-decision-950/10',
  machinery: 'border-dashed border-machinery-900/50 bg-machinery-950/10',
  raw: 'border-dashed border-raw-900/50 bg-raw-950/10',
};

/**
 * The left rule: a 2px marginal stroke in the tone's colour, for content that annotates the
 * page rather than boxing itself in — a stat tile's figure, a callout's note. The stroke
 * says "this carries a verdict" without a tinted region behind it.
 */
export const RULE: Record<Tone, string> = {
  neutral: 'border-l-chrome-700',
  good: 'border-l-good-600',
  broken: 'border-l-broken-600',
  decision: 'border-l-decision-500',
  machinery: 'border-l-machinery-600',
  raw: 'border-l-raw-600',
};

/** The tint behind a callout, one entry per tone — lighter than `BOX`, no border of its own. */
export const TINT: Record<Tone, string> = {
  neutral: 'bg-panel',
  good: 'bg-good-950/20',
  broken: 'bg-broken-950/20',
  decision: 'bg-decision-950/20',
  machinery: 'bg-machinery-950/20',
  raw: 'bg-raw-950/20',
};

/** Just the text colour for a tone — a tinted number on an untinted card (`StatTile`). */
export const TEXT: Record<Tone, string> = {
  neutral: 'text-chrome-100',
  good: 'text-good-400',
  broken: 'text-broken-400',
  decision: 'text-decision-400',
  machinery: 'text-machinery-400',
  raw: 'text-raw-400',
};
