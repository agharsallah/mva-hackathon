/**
 * The distance module is the exhibit's actual *measurement*, so every claim it makes is
 * asserted here: the arithmetic, the ordering, the flags that qualify a number (both ends
 * confident, both alleles rare, one domain), and the phase lookup — which must answer
 * `unknown` wherever the two payloads share no identifier, never guess cis or trans.
 */

import { describe, expect, it } from 'vitest';

import type { PanelHetPairs, PanelHetVariant } from '../../../api/types';
import type { PlacedCandidate } from './buildScene';
import {
  angstromLabel,
  bucketOf,
  candidateDistances,
  distance,
  findPair,
  pairLink,
} from './distances';

function candidate(over: Partial<PlacedCandidate> = {}): PlacedCandidate {
  return {
    id: 'r1',
    label: 'a',
    n: 1,
    aa: 'A',
    at: [0, 0, 0],
    impact: 'HIGH',
    consequence: 'stop_gained',
    rare: true,
    plddt: 95,
    domain: 'head',
    clinSig: null,
    hetIndex: null,
    ...over,
  };
}

const A = candidate({ id: 'r10', label: 'stop · rs1', n: 10, at: [0, 0, 0], hetIndex: 0 });
const B = candidate({
  id: 'r20',
  label: 'missense · rs2',
  n: 20,
  at: [6, 0, 0],
  impact: 'MODERATE',
  rare: false,
  domain: 'head',
  hetIndex: 1,
});
const C = candidate({
  id: 'r30',
  label: 'missense · rs3',
  n: 30,
  at: [0, 40, 0],
  domain: 'tail',
  plddt: 30,
  hetIndex: 2,
});

function hetPairs(over: Partial<PanelHetPairs> = {}): PanelHetPairs {
  const variant = (rsid: string): PanelHetVariant => ({
    gene: 'TESTGENE',
    chrom: '1',
    pos: 1,
    ref: 'A',
    alt: 'T',
    allele_ix: 1,
    gt: '0/1',
    qual: 100,
    dp: 30,
    vaf: 0.5,
    pgt: null,
    pid: null,
    rsid,
    consequence: 'missense_variant',
    impact: 'MODERATE',
    gnomad_af: null,
    gnomad_af_grpmax: null,
    clin_sig: null,
    annotated: true,
    is_rare_recessive: true,
    is_protein_altering: true,
  });
  return {
    gene: 'TESTGENE',
    variants: [variant('rs1'), variant('rs2'), variant('rs3')],
    pairs: [{ i: 0, j: 1, phase: 'trans', auto: false }],
    summary: {
      n_het: 3,
      n_pairs: 3,
      n_trans: 1,
      n_auto_trans: 0,
      n_cis: 0,
      n_unknown: 2,
      pct_unknown: 66.7,
    },
    ...over,
  };
}

describe('distance', () => {
  it('is the straight-line distance in the model’s own unit', () => {
    expect(distance([0, 0, 0], [3, 4, 0])).toBe(5);
    expect(distance([1, 1, 1], [1, 1, 1])).toBe(0);
  });

  it('labels to one decimal, the precision a predicted model earns', () => {
    expect(angstromLabel(8.44)).toBe('8.4 Å');
    expect(angstromLabel(12.35)).toBe('12.3 Å');
  });
});

describe('bucketOf — geometric bands, not verdicts', () => {
  it('splits at 10 Å and 25 Å, on the closed-below side', () => {
    expect(bucketOf(0)).toBe('same neighbourhood');
    expect(bucketOf(9.99)).toBe('same neighbourhood');
    expect(bucketOf(10)).toBe('same lobe');
    expect(bucketOf(24.99)).toBe('same lobe');
    expect(bucketOf(25)).toBe('far apart');
    expect(bucketOf(1000)).toBe('far apart');
  });
});

describe('candidateDistances', () => {
  it('returns every unordered pair once, closest first', () => {
    const rows = candidateDistances([A, B, C]);
    expect(rows).toHaveLength(3);
    expect(rows.map((r) => r.key)).toEqual(['r10|r20', 'r10|r30', 'r20|r30']);
    expect(rows[0].angstrom).toBe(6);
    expect(rows.map((r) => r.angstrom)).toEqual(
      [...rows.map((r) => r.angstrom)].sort((x, y) => x - y),
    );
  });

  it('is empty below two placed candidates, so a lone allele reports no pair', () => {
    expect(candidateDistances([])).toEqual([]);
    expect(candidateDistances([A])).toEqual([]);
  });

  it('caps at k when asked', () => {
    expect(candidateDistances([A, B, C], undefined, 2)).toHaveLength(2);
  });

  it('carries the sequence gap beside the spatial one — the contrast is the point', () => {
    const [row] = candidateDistances([A, B]);
    expect(row.sequenceGap).toBe(10);
    expect(row.angstrom).toBe(6);
    expect(row.bucket).toBe('same neighbourhood');
  });

  it('flags both-rare only when both halves are rare', () => {
    const rows = candidateDistances([A, B, C]);
    expect(rows.find((r) => r.key === 'r10|r20')?.bothRare).toBe(false);
    expect(rows.find((r) => r.key === 'r10|r30')?.bothRare).toBe(true);
  });

  it('flags same-domain only for a real annotated domain', () => {
    const rows = candidateDistances([A, B, C]);
    expect(rows.find((r) => r.key === 'r10|r20')?.sameDomain).toBe(true);
    expect(rows.find((r) => r.key === 'r10|r30')?.sameDomain).toBe(false);
    const none = candidateDistances([
      candidate({ id: 'r1', n: 1, domain: 'none' }),
      candidate({ id: 'r2', n: 2, at: [1, 0, 0], domain: 'none' }),
    ]);
    expect(none[0].sameDomain).toBe(false);
  });

  it('withholds `confident` unless both ends clear the pLDDT floor', () => {
    const rows = candidateDistances([A, B, C]);
    expect(rows.find((r) => r.key === 'r10|r20')?.confident).toBe(true);
    // C sits at pLDDT 30, so any pair touching it is not quotable.
    expect(rows.find((r) => r.key === 'r10|r30')?.confident).toBe(false);
  });

  it('reads phase out of het-pairs, and answers unknown when it cannot', () => {
    const rows = candidateDistances([A, B, C], hetPairs());
    expect(rows.find((r) => r.key === 'r10|r20')?.phase).toBe('trans');
    expect(rows.find((r) => r.key === 'r10|r30')?.phase).toBe('unknown');
    expect(candidateDistances([A, B])[0].phase).toBe('unknown');
  });

  it('names a genotype-proven trans pair distinctly from a phased one', () => {
    const rows = candidateDistances(
      [A, B],
      hetPairs({ pairs: [{ i: 0, j: 1, phase: 'trans', auto: true }] }),
    );
    expect(rows[0].phase).toBe('auto-trans');
  });

  it('reports a resolved cis pair as cis — the verdict that kills a pair', () => {
    const rows = candidateDistances(
      [A, B],
      hetPairs({ pairs: [{ i: 1, j: 0, phase: 'cis', auto: false }] }),
    );
    expect(rows[0].phase).toBe('cis');
  });

  it('never guesses a phase for a candidate with no rsid match', () => {
    const rows = candidateDistances(
      [A, candidate({ id: 'r99', n: 99, at: [1, 0, 0] })],
      hetPairs(),
    );
    expect(rows[0].phase).toBe('unknown');
  });
});

describe('pairLink', () => {
  it('labels the line in ångström and draws it as a decision', () => {
    const [row] = candidateDistances([A, B]);
    expect(pairLink(row)).toEqual({ from: 'r10', to: 'r20', label: '6.0 Å', tone: 'decision' });
  });

  it('greys the line and says so when either end is below the floor', () => {
    const rows = candidateDistances([A, C]);
    const link = pairLink(rows[0]);
    expect(link.tone).toBe('neutral');
    expect(link.label).toContain('low pLDDT');
  });
});

describe('findPair', () => {
  it('finds a pair in either order and misses cleanly', () => {
    const rows = candidateDistances([A, B, C]);
    expect(findPair(rows, 'r10', 'r20')?.key).toBe('r10|r20');
    expect(findPair(rows, 'r20', 'r10')?.key).toBe('r10|r20');
    expect(findPair(rows, 'r10', 'nope')).toBeUndefined();
  });
});
