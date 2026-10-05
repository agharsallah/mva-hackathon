/**
 * `toGeometry` — the one dispatch from a `Scene3D` to buffers three can upload.
 *
 * Adding a scene kind is: a union member in `spec/types.ts`, a `sceneDatums` case in
 * `spec/datums.ts`, an adapter file here, and one line below. Nothing in `core/` or
 * `components/` changes, because they only ever see `GeometryBuffers`.
 */

import type { GeometryBuffers, Scene3D } from '../spec/types';
import { pointsGeometry } from './points';
import { proteinGeometry } from './protein';
import { surfaceGeometry } from './surface';

export function toGeometry(scene: Scene3D): GeometryBuffers {
  switch (scene.kind) {
    case 'points':
      return pointsGeometry(scene);
    case 'surface':
      return surfaceGeometry(scene);
    case 'protein':
      return proteinGeometry(scene);
  }
}
