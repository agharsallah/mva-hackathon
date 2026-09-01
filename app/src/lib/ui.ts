/**
 * Shared Tailwind class tokens — the strings that were showing up hand-typed, identically,
 * across three or more page files (see `src/components/README.md` for the duplication survey
 * that produced this list).
 *
 * This module never invents a colour: every hex value still lives in `lib/palette.ts`. What
 * lives here is the *Tailwind utility recipe* built on top of the design language — "a card
 * is this border, this background, this padding" — so a page or component spells it once by
 * name instead of retyping the class string and risking a one-character drift between copies.
 */

/** Join class fragments, dropping falsy ones. `cx('a', cond && 'b', undefined)` → `'a b'`. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}

/** The bordered panel every exhibit, card and console section sits in. */
export const CARD = 'rounded-xl border border-zinc-800 bg-zinc-900/40 p-4';

/**
 * The four-tone alert/callout box: neutral machinery, good, broken, decision — the same
 * vocabulary as `StatTile`'s `tone` prop and the repo's colour legend (green/red/yellow/blue).
 * `Callout` is the canonical user of this; anything reaching for its own amber warning box
 * should reach for `BOX.decision` (or the `Callout` component itself) instead of retyping it.
 */
export const BOX: Record<'neutral' | 'good' | 'broken' | 'decision', string> = {
  neutral: 'border-zinc-800 bg-zinc-900/40 text-zinc-300',
  good: 'border-emerald-800/60 bg-emerald-950/25 text-emerald-300',
  broken: 'border-red-900/60 bg-red-950/25 text-red-300',
  decision: 'border-amber-800/60 bg-amber-950/25 text-amber-300',
};

/**
 * The small pill badge: a verdict or a flag rendered as a coloured chip. Five tones to match
 * `StatTile`'s tone vocabulary (`neutral/good/broken/decision/raw`) — `raw` marks a value taken
 * straight from delivered input rather than computed.
 */
export const BADGE: Record<'neutral' | 'good' | 'broken' | 'decision' | 'raw', string> = {
  neutral: 'border-zinc-700 bg-zinc-900 text-zinc-400',
  good: 'border-emerald-800 bg-emerald-950/60 text-emerald-400',
  broken: 'border-red-900 bg-red-950/60 text-red-400',
  decision: 'border-amber-800 bg-amber-950/60 text-amber-400',
  raw: 'border-purple-800 bg-purple-950/60 text-purple-400',
};

/** The dashed empty-state box, in the two tones it actually appears in: a plain gap, or the
 * "nothing recorded yet, and that's expected" state (register tables, oracle ledgers). */
export const EMPTY_DASHED: Record<'neutral' | 'good', string> = {
  neutral: 'border-dashed border-zinc-800 text-zinc-500',
  good: 'border-dashed border-emerald-900/50 bg-emerald-950/10',
};
