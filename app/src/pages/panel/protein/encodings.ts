/**
 * What a residue's colour is allowed to mean — the five encodings this exhibit offers, and
 * the domain palette one of them needs.
 *
 * Split out of `buildScene.ts` because it is the part a reader argues with: every `means` /
 * `lowMeans` / `highMeans` string below is read verbatim into the `Legend` line, the canvas
 * `aria-label` and the AI export by `viz3d`'s `describeScene`, so the words *are* the
 * contract. Pure data plus one pure function; no React, no three.
 */

import type { ProteinDomain } from '../../../api/types';
import { impactTone, QUALITY_SCALE, type Tone } from '../../../lib/palette';
import type { ColorEncoding } from '../../../viz3d';

/**
 * Domain colours. Four tones, assigned by the domain's first appearance along the chain, so
 * the same gene always colours the same way; a fifth domain onward falls to `neutral` grey
 * and the legend says so.
 *
 * `broken` is deliberately *not* in the list: red is reserved for a HIGH-impact candidate
 * sphere, and a domain is not a verdict.
 */
const DOMAIN_TONES: readonly Tone[] = ['machinery', 'raw', 'decision', 'good'];

/** The word used where a residue lies in no annotated domain. Not "unknown": measured absence. */
export const NO_DOMAIN = 'none';

/** Smallest annotated domain covering a residue, or {@link NO_DOMAIN}. */
export function domainAt(domains: readonly ProteinDomain[], n: number): string {
  let best: ProteinDomain | null = null;
  for (const d of domains) {
    if (n < d.start_aa || n > d.end_aa) continue;
    if (!best || d.end_aa - d.start_aa < best.end_aa - best.start_aa) best = d;
  }
  return best?.name ?? NO_DOMAIN;
}

/** Domain name -> tone, ordered by where the domain starts on the chain. */
export function domainToneMap(domains: readonly ProteinDomain[]): Record<string, Tone> {
  const firstStart = new Map<string, number>();
  for (const d of domains) {
    const seen = firstStart.get(d.name);
    if (seen === undefined || d.start_aa < seen) firstStart.set(d.name, d.start_aa);
  }
  const ordered = [...firstStart.entries()].sort((a, b) => a[1] - b[1]).map(([name]) => name);
  const out: Record<string, Tone> = { [NO_DOMAIN]: 'neutral' };
  ordered.forEach((name, i) => {
    out[name] = DOMAIN_TONES[i] ?? 'neutral';
  });
  return out;
}

export function proteinEncodings(domainTones: Readonly<Record<string, Tone>>): ColorEncoding[] {
  return [
    {
      id: 'domain',
      kind: 'categorical',
      label: 'domain',
      field: 'domain',
      tones: domainTones,
      means:
        'one colour per annotated protein domain (a semi-independent working part of the fold); ' +
        'grey = in no annotated domain',
    },
    {
      id: 'plddt',
      kind: 'numeric',
      label: 'pLDDT (model confidence)',
      field: 'plddt',
      domain: [0, 100],
      scale: QUALITY_SCALE,
      lowMeans: 'pLDDT near 0 — the model is guessing; below 50 the region is likely disordered',
      highMeans: 'pLDDT near 100 — the atom positions are as trustworthy as an experiment',
    },
    {
      id: 'impact',
      kind: 'categorical',
      label: 'variant impact',
      field: 'impact',
      tones: {
        HIGH: impactTone('HIGH'),
        MODERATE: impactTone('MODERATE'),
        LOW: impactTone('LOW'),
        MODIFIER: impactTone('MODIFIER'),
        none: 'neutral',
      },
      means: "VEP's severity bucket for the allele on this residue; grey = no allele here",
    },
    {
      id: 'secondary',
      kind: 'categorical',
      label: 'secondary structure',
      field: 'secondary',
      tones: { helix: 'raw', strand: 'machinery', coil: 'neutral' },
      means: 'the local shape of the chain: purple = helix, blue = strand, grey = coil/loop',
    },
    {
      id: 'rarity',
      kind: 'categorical',
      label: 'rarity of the allele',
      field: 'rare',
      tones: { rare: 'good', common: 'broken' },
      means:
        'green = rare in gnomAD, the only kind of allele a recessive candidate can be; ' +
        'red = common, so a poor candidate; grey = no allele on this residue',
    },
  ];
}
