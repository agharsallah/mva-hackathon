/**
 * The exhibit's filter state, and the pure predicate it turns into.
 *
 * Filters stay component state rather than URL state on purpose: `lib/urlstate.ts`'s point is
 * that one URL cites one figure, and what a citation needs is the pick, the pair, the camera
 * and the colour ramp — not which of four impact chips a reader happened to toggle while
 * exploring. The residue window is state for the same reason, even though it changes the
 * camera: "focus on selection" is a gesture, not a claim.
 *
 * `emphasisPredicate` is exported separately from the hook so the filtering logic can be
 * unit-tested without React.
 */

import { useCallback, useMemo, useState } from 'react';

import type { VariantImpact } from '../../../api/types';
import type { Datum3D } from '../../../viz3d';
import { isCandidate, isLowConfidence } from './buildScene';

/** The impact buckets the filter chips offer, most severe first. */
export const IMPACTS: readonly VariantImpact[] = ['HIGH', 'MODERATE', 'LOW', 'MODIFIER'];

export interface ProteinFilterValues {
  /** Grey out every low-confidence residue (pLDDT < 70). On by default. */
  dim: boolean;
  rareOnly: boolean;
  onlyCandidates: boolean;
  /** Impact buckets whose candidate spheres are de-emphasised. */
  hiddenImpacts: readonly string[];
  /** The residue window the chain is trimmed to, inclusive. */
  from: number;
  to: number;
}

/**
 * Which residues the current filters *emphasise*. A residue this rejects is greyed and
 * shrunk, never deleted — see `emphasise` in `buildScene.ts` for why deleting one would
 * repaint the tube in a neighbour's colour.
 *
 * A candidate residue is never dimmed by the confidence filter: its impact colour is the
 * verdict the exhibit exists to show, and its confidence is reported in the tooltip and in
 * the distance table's `pLDDT ≥ 70 both ends` column instead.
 */
export function emphasisPredicate(values: ProteinFilterValues): (datum: Datum3D) => boolean {
  return (datum) => {
    const candidate = isCandidate(datum);
    if (values.dim && isLowConfidence(datum) && !candidate) return false;
    if (values.onlyCandidates && !candidate) return false;
    if (values.rareOnly && datum.meta?.rare !== 'rare') return false;
    if (candidate && values.hiddenImpacts.includes(String(datum.meta?.impact ?? 'none'))) {
      return false;
    }
    return true;
  };
}

export interface ProteinFilters extends ProteinFilterValues {
  length: number;
  setDim: (on: boolean) => void;
  setRareOnly: (on: boolean) => void;
  setOnlyCandidates: (on: boolean) => void;
  toggleImpact: (impact: string) => void;
  setWindow: (from: number, to: number) => void;
  accept: (datum: Datum3D) => boolean;
}

/**
 * The window is stored **with the translation length it was chosen against**. Switching gene
 * re-renders this hook with a new `length` while the component stays mounted, and a window
 * seeded once from the first protein would then silently trim the new chain (clamped only at
 * the top). Comparing the stored length is the reset.
 *
 * The reset happens *during render*, not in an effect: React re-runs the component immediately
 * on a set-state during render, so no child ever sees the previous protein's window. An effect
 * would let one frame paint the wrong trim.
 */
interface WindowState {
  /** The `protein_length` this window was chosen against. */
  length: number;
  range: readonly [number, number];
}

export function useProteinFilters(length: number): ProteinFilters {
  const [dim, setDim] = useState(true);
  const [rareOnly, setRareOnly] = useState(false);
  const [onlyCandidates, setOnlyCandidates] = useState(false);
  const [hiddenImpacts, setHiddenImpacts] = useState<readonly string[]>([]);
  const [stored, setStored] = useState<WindowState>(() => ({ length, range: [1, length] }));
  if (stored.length !== length) setStored({ length, range: [1, length] });

  const values = useMemo<ProteinFilterValues>(() => {
    // The stale render between the set-state above and the re-render it schedules reads the
    // whole chain, not the previous protein's window.
    const [a, b] = stored.length === length ? stored.range : [1, length];
    return {
      dim,
      rareOnly,
      onlyCandidates,
      hiddenImpacts,
      from: Math.max(1, Math.min(a, b)),
      to: Math.min(length, Math.max(a, b)),
    };
  }, [dim, rareOnly, onlyCandidates, hiddenImpacts, stored, length]);

  return {
    ...values,
    length,
    setDim,
    setRareOnly,
    setOnlyCandidates,
    toggleImpact: useCallback(
      (impact) =>
        setHiddenImpacts((prev) =>
          prev.includes(impact) ? prev.filter((v) => v !== impact) : [...prev, impact],
        ),
      [],
    ),
    setWindow: useCallback((from, to) => setStored({ length, range: [from, to] }), [length]),
    accept: useMemo(() => emphasisPredicate(values), [values]),
  };
}
