/**
 * One column of the side-by-side comparison: a gene's fold, or the honest reason there is no
 * picture. The five `FoldState` cases each render once, here, so both columns and the single
 * explorer above them tell a reader the same story about the same failure.
 *
 * The scene is derived, not rebuilt: `useFold` owns the build, and this file applies the two
 * *shared* controls to it — the colour encoding (picked out of the scene's own declared
 * encodings by id, so each gene's domain palette stays its own) and the low-confidence
 * de-emphasis. Neither drops a residue, for the reason `buildScene.ts`'s `emphasise` gives:
 * a dropped residue repaints that stretch of tube in a surviving neighbour's colour.
 */

import { useMemo } from 'react';

import { Callout } from '../../../../components/Explainer';
import { Skeleton } from '../../../../components/QueryState';
import { type CameraPose3D, type CameraPreset, Viz3dCanvas } from '../../../../viz3d';
import { emphasise } from '../buildScene';
import { emphasisPredicate } from '../filters';
import { ProteinError } from '../ProteinNotes';
import type { FoldState } from './useFold';

/** The one sentence an off-panel gene owes the reader, stated the same way everywhere. */
export function OffPanelNote({ gene }: { gene: string }) {
  return (
    <Callout tone="machinery" title="no annotated alleles: fold only">
      {gene} is outside the <strong>annotated panel</strong> — the variant calls were annotated only
      over the eight-gene panel BED, so this gene has no candidate alleles in the callset{' '}
      <em>because nothing was ever annotated there</em>, not because the proband is clean at that
      locus. The fold is shown, and nothing is painted on it.
    </Callout>
  );
}

export function FoldPanel({
  state,
  encodingId,
  dim,
  view,
  pose,
  onPose,
  refitKey,
  height = 380,
}: {
  state: FoldState;
  encodingId: string;
  dim: boolean;
  view: CameraPreset;
  pose?: CameraPose3D | null;
  onPose?: (pose: CameraPose3D) => void;
  /** Bumped by the shared "reset both cameras" control — see `Viz3dCanvasProps.refitKey`. */
  refitKey?: number;
  height?: number;
}) {
  const scene = useMemo(() => {
    if (state.kind !== 'ready') return null;
    const accept = emphasisPredicate({
      dim,
      rareOnly: false,
      onlyCandidates: false,
      hiddenImpacts: [],
      from: 1,
      to: state.metrics.length,
    });
    const painted = emphasise(state.build.scene, accept);
    const color = painted.encodings?.find((e) => e.id === encodingId) ?? painted.color;
    return { ...painted, color };
  }, [state, dim, encodingId]);

  if (state.kind === 'loading') return <Skeleton height={height} />;
  if (state.kind === 'error') return <ProteinError error={state.error} />;
  if (state.kind === 'non-coding') {
    return (
      <Callout tone="broken" title={`${state.gene} is non-coding — there is no protein`}>
        {state.message} A fold needs a translation to have coordinates for; this gene is in the set
        as a reference row, and the exhibit draws no canvas for it rather than drawing something
        that is not a protein.
      </Callout>
    );
  }
  if (state.kind === 'mismatch') {
    return (
      <Callout tone="broken" title={`${state.gene}: nothing painted — the payloads disagree`}>
        {state.message}
      </Callout>
    );
  }
  if (!scene) return <Skeleton height={height} />;

  return (
    <div className="space-y-2">
      <Viz3dCanvas
        scene={scene}
        height={height}
        view={view}
        pose={pose}
        onPose={onPose}
        refitKey={refitKey}
        autoRotate={false}
      />
      {!state.inPanel && <OffPanelNote gene={state.gene} />}
    </div>
  );
}
