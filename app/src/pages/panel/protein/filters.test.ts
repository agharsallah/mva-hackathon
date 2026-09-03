/**
 * The filter predicate decides what the reader is looking at, so its edge cases are the ones
 * worth pinning: a candidate is never dimmed for low confidence (its verdict colour is the
 * point of the exhibit), and "rare only" must not quietly emphasise the whole chain.
 */

import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Datum3D } from '../../../viz3d';
import { emphasisPredicate, type ProteinFilterValues, useProteinFilters } from './filters';

const OFF: ProteinFilterValues = {
  dim: false,
  rareOnly: false,
  onlyCandidates: false,
  hiddenImpacts: [],
  from: 1,
  to: 100,
};

function residue(meta: Datum3D['meta']): Datum3D {
  return { id: 'r1', label: 'r1', at: [0, 0, 0], value: 0, meta };
}

const plain = residue({ n: 1, plddt: 95, candidate: null, rare: null, impact: 'none' });
const lowPlain = residue({ n: 2, plddt: 40, candidate: null, rare: null, impact: 'none' });
const rareHigh = residue({ n: 3, plddt: 95, candidate: 'stop', rare: 'rare', impact: 'HIGH' });
const commonLowConf = residue({
  n: 4,
  plddt: 30,
  candidate: 'missense',
  rare: 'common',
  impact: 'MODERATE',
});

describe('emphasisPredicate', () => {
  it('emphasises everything when nothing is filtered', () => {
    const accept = emphasisPredicate(OFF);
    expect([plain, lowPlain, rareHigh, commonLowConf].every(accept)).toBe(true);
  });

  it('dims a low-confidence residue but never a candidate', () => {
    const accept = emphasisPredicate({ ...OFF, dim: true });
    expect(accept(plain)).toBe(true);
    expect(accept(lowPlain)).toBe(false);
    expect(accept(commonLowConf)).toBe(true);
  });

  it('keeps only candidates when asked', () => {
    const accept = emphasisPredicate({ ...OFF, onlyCandidates: true });
    expect(accept(plain)).toBe(false);
    expect(accept(rareHigh)).toBe(true);
  });

  it('reads rare-only off the annotation, so an unannotated residue is not "rare"', () => {
    const accept = emphasisPredicate({ ...OFF, rareOnly: true });
    expect(accept(rareHigh)).toBe(true);
    expect(accept(commonLowConf)).toBe(false);
    expect(accept(plain)).toBe(false);
  });

  it('hides an impact bucket for candidates only', () => {
    const accept = emphasisPredicate({ ...OFF, hiddenImpacts: ['HIGH'] });
    expect(accept(rareHigh)).toBe(false);
    expect(accept(commonLowConf)).toBe(true);
    expect(accept(plain)).toBe(true);
  });

  it('applies every filter at once', () => {
    const accept = emphasisPredicate({
      ...OFF,
      dim: true,
      rareOnly: true,
      hiddenImpacts: ['MODERATE'],
    });
    expect(accept(rareHigh)).toBe(true);
    expect(accept(commonLowConf)).toBe(false);
    expect(accept(lowPlain)).toBe(false);
  });
});

/**
 * The window is the one filter that changes what the camera sees, so carrying one protein's
 * window onto the next gene silently trims the new chain. `Explorer` is not remounted on a
 * gene change, so the hook has to notice the new length itself.
 */
describe('useProteinFilters — the residue window', () => {
  it('opens on the whole chain', () => {
    const { result } = renderHook(() => useProteinFilters(1050));
    expect([result.current.from, result.current.to]).toEqual([1, 1050]);
  });

  it('keeps a window the reader set', () => {
    const { result } = renderHook(() => useProteinFilters(1050));
    act(() => result.current.setWindow(600, 700));
    expect([result.current.from, result.current.to]).toEqual([600, 700]);
  });

  it('resets to the whole chain when the protein length changes', () => {
    const { result, rerender } = renderHook(({ length }) => useProteinFilters(length), {
      initialProps: { length: 1050 },
    });
    act(() => result.current.setWindow(600, 700));
    rerender({ length: 300 });
    expect([result.current.from, result.current.to]).toEqual([1, 300]);
  });
});
