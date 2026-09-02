/**
 * The repo's visual language, in one place.
 *
 * green  = good / safe / the goal
 * red    = broken / dangerous / lost points
 * yellow = a decision point
 * blue   = neutral machinery
 * purple = the raw input
 * grey   = absent / not measured
 *
 * Every exhibit in the app decodes its own use of these in a Legend line, per the
 * repo's visualization rules.
 */
export const C = {
  good: '#22c55e',
  goodDim: '#166534',
  broken: '#ef4444',
  brokenDim: '#7f1d1d',
  decision: '#eab308',
  machinery: '#3b82f6',
  machineryDim: '#1e3a8a',
  raw: '#a855f7',
  absent: '#6b7280',
  ink: '#e5e7eb',
  inkDim: '#9ca3af',
  grid: '#27272a',
  paper: '#0a0a0a',
  panel: '#18181b',
  /** A bin/cell that was measured but sits below the confidence floor — distinct from
   * `absent`, which marks a value that was never computed at all. Flat grey, on purpose:
   * it must not be mistakable for a point on any of this file's colour scales. */
  unmeasured: '#3f3f46',
  /** The blue stop inside `DENSITY_SCALE` — reused verbatim wherever legend prose spells out
   * the "dark → blue → purple" ramp inline (BAF karyogram, density bins, karyotype, flowcell). */
  densityBlue: '#1d4ed8',
  /** Off-white label text drawn directly on a coloured mark (e.g. a treemap tile fill), where
   * `ink`'s grey doesn't read against a saturated background. */
  onFill: '#f5f5f5',
  /** `machineryDim`'s RGB at ~33% alpha — a translucent blue fill behind a "neutral machinery"
   * station box, as opposed to `machineryDim`'s own opaque use as a stroke/line colour. */
  machineryFill: '#1e3a8a55',
  /** Tailwind amber-900 at ~33% alpha — a translucent fill behind a "decision point" station
   * box, matching `BOX.decision`'s amber theme at the same opacity family. */
  decisionFill: '#78350f55',
} as const;

/** Extra severity tone between `C.broken` and `C.decision`: orange, used where a ramp needs
 * more steps than the three core colours (suppression-reason ranking, base-quality bins). */
export const SEVERITY_ORANGE = '#f97316';

/** Categorical ramp for "one line per lane/read" style series. Blue family = machinery. */
export const SERIES = [
  '#60a5fa',
  '#3b82f6',
  '#2563eb',
  '#1d4ed8',
  '#a78bfa',
  '#8b5cf6',
  '#7c3aed',
  '#6d28d9',
];

/** Sequential ramp for density: dark neutral → blue → purple (raw input at the hot end). */
export const DENSITY_SCALE: [number, string][] = [
  [0, '#0a0a0a'],
  [0.15, '#12263f'],
  [0.4, C.densityBlue],
  [0.7, '#7c3aed'],
  [1, '#e9d5ff'],
];

/** Diverging ramp for quality: red (bad) → yellow → green (good). */
export const QUALITY_SCALE: [number, string][] = [
  [0, '#7f1d1d'],
  [0.35, '#ef4444'],
  [0.6, '#eab308'],
  [1, '#22c55e'],
];

/**
 * Diverging ramp for a signed deviation from a neutral midpoint, e.g. BAF away from 0.5.
 *
 * Green sits at the **centre**, not at an end: for allele balance the goal is the middle
 * of the range, and both directions away from it are the abnormal outcome. Red marks a
 * deficit (fewer variant reads than expected) and purple a surplus, so the sign of the
 * shift is readable and neither direction is quietly privileged.
 */
export const DIVERGING_SCALE: [number, string][] = [
  [0, '#7f1d1d'],
  [0.25, '#ef4444'],
  [0.42, '#166534'],
  [0.5, '#22c55e'],
  [0.58, '#166534'],
  [0.75, '#a855f7'],
  [1, '#e9d5ff'],
];

/** Sequential ramp for read depth: dark → blue → white-hot. Neutral machinery. */
export const DEPTH_SCALE: [number, string][] = [
  [0, '#0a0a0a'],
  [0.3, '#1e3a8a'],
  [0.65, '#3b82f6'],
  [1, '#dbeafe'],
];

/**
 * Suppression-reason ramp for `SuppressedCalls`: reds and yellows, heaviest reason first
 * (`PASS` is drawn separately, in `C.good`). Assigned by rank rather than by reason name so
 * the ordering stays stable if the caller's FILTER vocabulary changes.
 */
export const REASON_RAMP = [
  C.broken,
  SEVERITY_ORANGE,
  C.decision,
  '#b91c1c',
  '#fbbf24',
  C.brokenDim,
];

/**
 * Unknown-pair shading for `PairMatrix`'s compound-het grid: dark neutral (common pair) →
 * machinery blue → pale (rare × rare — the region a causal pair has to live in).
 */
export const RARITY_SCALE: [number, string][] = [
  [0, '#161b22'],
  [0.45, C.machineryDim],
  [0.75, C.machinery],
  [1, '#bfdbfe'],
];

export function balanceColor(call: string): string {
  return call === 'balanced' ? C.good : C.broken;
}

/** Colour a probe verdict: present is what we want, error-level is noise, absent is nothing. */
export function verdictColor(verdict: string): string {
  const v = verdict.toLowerCase();
  if (v.includes('present')) return C.good;
  if (v.includes('lane')) return C.decision;
  if (v.includes('error')) return C.broken;
  return C.absent;
}

/**
 * VEP severity bucket → colour. HIGH truncates the protein (broken), MODERATE changes an
 * amino acid (a decision to make), LOW/MODIFIER are silent or non-coding (machinery).
 */
export function impactColor(impact: string): string {
  switch (impact) {
    case 'HIGH':
      return C.broken;
    case 'MODERATE':
      return C.decision;
    case 'LOW':
    case 'MODIFIER':
      return C.machinery;
    default:
      return C.absent;
  }
}

/** Observed-vs-expected verdict → colour. Agreement is the good outcome. */
export function oeVerdictColor(verdict: string): string {
  switch (verdict) {
    case 'within':
      return C.good;
    case 'above':
    case 'below':
      return C.broken;
    default:
      return C.absent;
  }
}

export function jobStateColor(state: string): string {
  switch (state) {
    case 'done':
      return C.good;
    case 'failed':
    case 'lost':
      return C.broken;
    case 'cancelled':
      return C.absent;
    default:
      return C.machinery;
  }
}
