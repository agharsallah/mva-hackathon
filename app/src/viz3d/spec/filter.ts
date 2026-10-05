/**
 * Deriving a scene from a scene: keep the datums a predicate accepts, and swap the active
 * colour encoding. Pure, so "colour by any field / filter by any field" is testable without
 * mounting a canvas.
 *
 * A `surface` cell is not deleted but set to `null` — the grid's shape is the x/y axes, and
 * dropping a row would silently rescale them. `null` is already this module's word for "not
 * measured", and it renders as a hole rather than as a value.
 *
 * A `protein` scene has **two index-aligned arrays** — `residues[i]` is the datum whose Cα is
 * `backbone[i]` — and the adapter derives the tube's colour and its pick ranges from that
 * alignment. Filtering only `residues` left a full-length tube painted from a shorter residue
 * list, so every ring past the first dropped residue was coloured and labelled as its
 * neighbour. `filterScene` therefore trims both, at the same indices. A scene whose two arrays
 * are not the same length cannot be trimmed honestly, so it is returned unchanged (the page
 * that built it owns the mismatch; see `pages/panel/protein/buildScene.ts` for a page that
 * de-emphasises instead of dropping, and why).
 */

import { cellId } from './datums';
import type { ColorEncoding, Datum3D, Scene3D } from './types';

export type DatumPredicate = (datum: Datum3D) => boolean;

export function filterScene(scene: Scene3D, keep: DatumPredicate): Scene3D {
  switch (scene.kind) {
    case 'points':
      return { ...scene, points: scene.points.filter(keep) };
    case 'protein': {
      if (scene.backbone.length !== scene.residues.length) return scene;
      const kept = scene.residues
        .map((datum, index) => ({ datum, index }))
        .filter((k) => keep(k.datum));
      if (kept.length === scene.residues.length) return scene;
      return {
        ...scene,
        residues: kept.map((k) => k.datum),
        backbone: kept.map((k) => scene.backbone[k.index]),
      };
    }
    case 'surface':
      return {
        ...scene,
        grid: {
          ...scene.grid,
          z: scene.grid.z.map((row, yIndex) =>
            row.map((z, xIndex) => {
              if (z === null) return null;
              const y = scene.grid.y[yIndex];
              return keep({
                id: cellId(yIndex, xIndex),
                label: `${typeof y === 'string' ? y : String(y)} · ${scene.grid.x[xIndex]}`,
                at: [scene.grid.x[xIndex], yIndex, z],
                value: z,
              })
                ? z
                : null;
            }),
          ),
        },
      };
  }
}

/** Point the scene at a different declared encoding. Unknown ids leave the scene unchanged. */
export function recolour(scene: Scene3D, encodingId: string): Scene3D {
  const found = (scene.encodings ?? [scene.color]).find((e) => e.id === encodingId);
  return found ? { ...scene, color: found } : scene;
}

/** Every encoding a page may offer, always including the scene's current one. */
export function sceneEncodings(scene: Scene3D): readonly ColorEncoding[] {
  const declared = scene.encodings ?? [];
  return declared.some((e) => e.id === scene.color.id) ? declared : [scene.color, ...declared];
}
