/**
 * One gene's fold, fetched and reduced to a single discriminated state.
 *
 * Both the side-by-side comparison and the explorer need the same five-way answer for a
 * gene, and each of the five renders differently:
 *
 *   `loading`     — the two payloads are in flight.
 *   `non-coding`  — the gene has no protein-coding canonical transcript, so there is no
 *                   residue axis and nothing to draw. Known *before* the request from
 *                   `StructureGene.coding`, and confirmed by the API's own 422.
 *   `error`       — upstream (AlphaFold DB / Ensembl) was unreachable, or the API said no.
 *   `mismatch`    — the two payloads name different translations, so painting an allele
 *                   would put it on the wrong sequence. Nothing is drawn.
 *   `ready`       — a scene, the placed/unplaced alleles, and the metric row.
 *
 * A non-coding gene is never *fetched*: `useProteinStructure(null)` disables the query, so
 * the exhibit does not spend a request to be told what the gene set already said. The 422
 * branch still exists because the set can be stale relative to Ensembl, and because it is
 * the answer a hand-edited `?gene=` gets.
 */

import { useMemo } from 'react';

import type { Origin } from '../../../../api/client';
import { useGeneStructure, useProteinStructure } from '../../../../api/hooks';
import type { GeneStructure, ProteinStructure, StructureGene } from '../../../../api/types';
import { buildProteinScene, type ProteinSceneBuild } from '../buildScene';
import { isNonCodingError, type StructureMetrics, structureMetrics } from './metrics';

export type FoldState =
  | { kind: 'loading' }
  | { kind: 'non-coding'; gene: string; message: string }
  | { kind: 'error'; gene: string; error: Error }
  | { kind: 'mismatch'; gene: string; message: string }
  | {
      kind: 'ready';
      gene: string;
      entry?: StructureGene;
      structure: ProteinStructure;
      anatomy: GeneStructure;
      build: ProteinSceneBuild;
      metrics: StructureMetrics;
      /** True only for the annotated panel: the flag that decides whether alleles exist. */
      inPanel: boolean;
      origin?: Origin;
    };

export function useFold(gene: string, entry?: StructureGene): FoldState {
  // `coding === false` is known from the gene set, so the request is never made.
  const coding = entry?.coding ?? true;
  const model = useProteinStructure(coding ? gene : null);
  const anatomy = useGeneStructure(gene);

  return useMemo(() => {
    if (!coding) {
      return {
        kind: 'non-coding',
        gene,
        message: `${gene} has no protein-coding canonical transcript (biotype ${
          entry?.biotype ?? 'unknown'
        }), so it has no residues and no fold to draw.`,
      };
    }
    if (isNonCodingError(model.error)) {
      return { kind: 'non-coding', gene, message: model.error?.message ?? '' };
    }
    const error = model.error ?? anatomy.error;
    if (error) return { kind: 'error', gene, error };
    if (!model.data || !anatomy.data) return { kind: 'loading' };

    const built = buildProteinScene(model.data.data, anatomy.data.data);
    if (!built.ok) return { kind: 'mismatch', gene, message: built.error.message };
    return {
      kind: 'ready',
      gene,
      entry,
      structure: model.data.data,
      anatomy: anatomy.data.data,
      build: built.build,
      metrics: structureMetrics(model.data.data, anatomy.data.data, entry),
      inPanel: entry?.in_panel ?? anatomy.data.data.in_panel,
      origin: model.data.origin,
    };
  }, [coding, gene, entry, model.error, model.data, anatomy.error, anatomy.data]);
}
