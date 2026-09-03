/**
 * The two cross-gene exhibits, plus the wiring that makes them one instrument: a click in the
 * metrics table either moves the single-gene explorer above (the shared `?gene=` key) or
 * stages a gene into side A / side B of the comparison.
 *
 * The wiring lives here rather than in `Panel.tsx` so the page file stays a list of sections
 * and the URL keys stay next to the exhibits that own them.
 */

import { useCallback } from 'react';

import { useUrlState } from '../../../../lib/urlstate';
import { DEFAULT_GENE } from '../../LocusExplorer';
import { COMPARE_A, COMPARE_B } from '../geneSet';
import { StructureCompare } from './StructureCompare';
import { StructureMetricsTable } from './StructureMetricsTable';

export function ProteinCompareSection() {
  const [, setGene] = useUrlState('gene', DEFAULT_GENE);
  const [, setA] = useUrlState('prot.cmpA', COMPARE_A);
  const [, setB] = useUrlState('prot.cmpB', COMPARE_B);

  const onCompare = useCallback(
    (gene: string, slot: 'A' | 'B') => (slot === 'A' ? setA(gene) : setB(gene)),
    [setA, setB],
  );

  return (
    <div className="space-y-6">
      <StructureCompare />
      <StructureMetricsTable onPickGene={setGene} onCompare={onCompare} />
    </div>
  );
}
