/**
 * Raycast result -> `Datum3D`. The half that has no three in it, and is therefore tested.
 *
 * three answers a raycast with a vertex/face index or an `instanceId`; neither means anything
 * on its own. The adapter already emitted a `pickTable` of half-open ranges over that same
 * index space, so resolving a hit is a lookup, not geometry work — which is what keeps
 * `core/viewer.ts`'s pointer handler down to a few lines.
 */

import { sceneDatums } from '../spec/datums';
import type { Datum3D, GeometryBuffers, PickRange, Scene3D, Selection3D } from '../spec/types';

/** Which buffer the hit came from: the primary mesh/instances, or the secondary instances. */
export type PickSource = 'primary' | 'instances';

/** The datum id owning `index`, or `null` when the index falls outside every range. */
export function idAt(pickTable: readonly PickRange[], index: number): string | null {
  for (const range of pickTable) {
    if (index >= range.from && index < range.to) return range.id;
  }
  return null;
}

export function idAtHit(
  buffers: GeometryBuffers,
  source: PickSource,
  index: number,
): string | null {
  const table = source === 'instances' ? buffers.instances?.pickTable : buffers.pickTable;
  return table ? idAt(table, index) : null;
}

export function datumById(scene: Scene3D, id: string): Datum3D | null {
  return sceneDatums(scene).find((datum) => datum.id === id) ?? null;
}

function toSelection(scene: Scene3D, id: string | null): Selection3D | null {
  if (id === null) return null;
  const datum = datumById(scene, id);
  return datum ? { id: datum.id, label: datum.label, datum } : null;
}

/** The whole path, for a hit three has already resolved to a buffer and an index. */
export function selectionAt(
  scene: Scene3D,
  buffers: GeometryBuffers,
  source: PickSource,
  index: number,
): Selection3D | null {
  return toSelection(scene, idAtHit(buffers, source, index));
}
