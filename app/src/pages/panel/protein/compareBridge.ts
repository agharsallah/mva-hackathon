/**
 * The bridge from the Compare page's staged pair to two residues on this fold.
 *
 * Split out of `ProteinExplorer.tsx` so that file stays wiring: this is the one piece of
 * cross-exhibit reasoning in the protein folder, and it is the piece with a rule worth
 * reading on its own.
 */

import { useMemo } from 'react';

import { useUrlState } from '../../../lib/urlstate';
import { DEFAULT_GENE } from '../LocusExplorer';
import type { PlacedCandidate } from './buildScene';

/**
 * The pair the Compare page is holding, mapped onto residues — when it can be mapped.
 *
 * `cmp.a` / `cmp.b` are **indices into that gene's het-variant list** (verified in
 * `pages/compare/PairComparator.tsx`), not positions, so reading them adds no coordinate to
 * any URL. The bridge to a residue is therefore `hetIndex` — the same index, carried on a
 * `PlacedCandidate` by `buildScene` — and not `rsid`: a candidate keeps its het index even
 * when the annotation payload names no dbSNP accession for it.
 *
 * Two ways the mapping can fail, and they are told apart because they mean different things:
 *
 * - **The staged variant is not on the fold.** It is in Compare's list, but no *placed*
 *   candidate carries that het index — the allele has no modelled residue (or no het index
 *   at all). Nothing is wrong with Compare; the fold cannot show it.
 * - **The staged index is not one of this gene's het variants.** A stale `cmp.a` / `cmp.b`
 *   from another gene's list, or an index past the end of this one's.
 */
export function useComparePair(
  gene: string,
  placed: readonly PlacedCandidate[],
): { pair: readonly [PlacedCandidate, PlacedCandidate] | null; why: string } {
  const [cmpGene] = useUrlState('cmp.gene', DEFAULT_GENE);
  const [cmpA] = useUrlState('cmp.a', '');
  const [cmpB] = useUrlState('cmp.b', '');

  return useMemo(() => {
    if (!cmpA || !cmpB) {
      return { pair: null, why: 'the Compare page is not holding a pair yet' };
    }
    if (cmpGene !== gene) {
      return { pair: null, why: `Compare is on ${cmpGene}, this exhibit is on ${gene}` };
    }
    const find = (key: string) =>
      placed.find((p) => p.hetIndex !== null && String(p.hetIndex) === key);
    const a = find(cmpA);
    const b = find(cmpB);
    const missing = [!a && cmpA, !b && cmpB].filter((key): key is string => key !== false);
    if (missing.length > 0) {
      return {
        pair: null,
        why:
          `het variant ${missing.join(' and ')} of ${gene} ${missing.length > 1 ? 'are' : 'is'} ` +
          'not placed on this fold — no modelled residue carries that het index, so it cannot ' +
          'be drawn without guessing',
      };
    }
    if (!a || !b || a === b) {
      return {
        pair: null,
        why: `Compare is holding one variant twice (het index ${cmpA}), which is not a pair`,
      };
    }
    return { pair: [a, b] as const, why: `place ${a.label} and ${b.label} on the fold` };
  }, [cmpGene, cmpA, cmpB, gene, placed]);
}
