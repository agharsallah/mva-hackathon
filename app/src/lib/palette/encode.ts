/**
 * Verdict encoders — the domain's own words mapped onto a `Tone`, once.
 *
 * Each function answers "what does this string *mean*", never "what hue is it": the tone is
 * turned into a colour by `TONE_MARK` (charts) or by a `lib/ui.ts` recipe (DOM), so the same
 * verdict is the same colour in a Plotly trace, a badge and a table cell. Adding a vocabulary
 * means adding a function here, not a colour anywhere.
 */

import { type Tone, TONE_MARK } from './tones';

/** Allele-balance call: `balanced` is the expected outcome, anything else is a problem.
 * Not exported: nothing renders this vocabulary in the DOM, only `balanceColor` below. */
function balanceTone(call: string): Tone {
  return call === 'balanced' ? 'good' : 'broken';
}

/**
 * Probe verdict: `present` is what we want, a lane-level qualifier is a judgement call,
 * an error is noise, and anything else is nothing observed at all.
 */
export function verdictTone(verdict: string): Tone {
  const v = verdict.toLowerCase();
  if (v.includes('present')) return 'good';
  if (v.includes('lane')) return 'decision';
  if (v.includes('error')) return 'broken';
  return 'neutral';
}

/**
 * VEP severity bucket (how badly a variant hits the protein). HIGH truncates the protein
 * (broken), MODERATE swaps one amino acid (a decision to make), LOW/MODIFIER are silent or
 * non-coding (machinery).
 */
export function impactTone(impact: string): Tone {
  switch (impact) {
    case 'HIGH':
      return 'broken';
    case 'MODERATE':
      return 'decision';
    case 'LOW':
    case 'MODIFIER':
      return 'machinery';
    default:
      return 'neutral';
  }
}

/** Observed-vs-expected verdict: agreement with the published expectation is the good one. */
export function oeVerdictTone(verdict: string): Tone {
  switch (verdict) {
    case 'within':
      return 'good';
    case 'above':
    case 'below':
      return 'broken';
    default:
      return 'neutral';
  }
}

/** Job lifecycle state: done is good, failed/lost is broken, cancelled is nothing, else running. */
export function jobStateTone(state: string): Tone {
  switch (state) {
    case 'done':
      return 'good';
    case 'failed':
    case 'lost':
      return 'broken';
    case 'cancelled':
      return 'neutral';
    default:
      return 'machinery';
  }
}

/**
 * Chart-side shorthands: the same verdicts resolved straight to the mark colour, for a Plotly
 * trace or an SVG attribute. A DOM element takes the tone instead and tints itself with a
 * `lib/ui.ts` recipe, so a vocabulary gets a `*Color` twin only once something actually draws
 * it on a canvas — job state, for one, is only ever a badge.
 */
export const balanceColor = (call: string) => TONE_MARK[balanceTone(call)];
export const verdictColor = (verdict: string) => TONE_MARK[verdictTone(verdict)];
export const impactColor = (impact: string) => TONE_MARK[impactTone(impact)];
export const oeVerdictColor = (verdict: string) => TONE_MARK[oeVerdictTone(verdict)];
