/**
 * `Selection3D` <-> the URL, per `lib/urlstate.ts`'s four rules (default = absence, replace
 * not push, namespaced keys, junk falls back silently).
 *
 * The point of holding a pick and a camera preset in the query string rather than in the
 * canvas: one URL then cites one 3D figure exactly — `?res.pick=R727&res.view=top` — which is
 * what makes a 3D exhibit referenceable from the report at all.
 */

import { useCallback } from 'react';

import { useUrlEnum, useUrlState } from '../../lib/urlstate';
import { CAMERA_PRESETS, type CameraPreset, type Selection3D } from '../spec/types';

export interface SceneSelection {
  /** Controlled prop for `Viz3dCanvas`. Empty when nothing is picked. */
  highlighted: readonly string[];
  picked: string;
  view: CameraPreset;
  setView: (view: CameraPreset) => void;
  /** Hand straight to `Viz3dCanvas.onSelect` and to `SceneFallback`. */
  onSelect: (selection: Selection3D | null) => void;
  clear: () => void;
}

/**
 * @param ns  exhibit namespace — `'res'` gives `?res.pick=…&res.view=…`.
 * @param ids the pickable ids; an id not in this list reads as "nothing picked", so a stale
 *            or hand-edited URL degrades to the default view instead of a broken one.
 */
export function useSceneSelection(ns: string, ids: readonly string[]): SceneSelection {
  const [picked, setPicked] = useUrlState(`${ns}.pick`, '', ids);
  const [view, setView] = useUrlEnum<CameraPreset>(`${ns}.view`, 'iso', CAMERA_PRESETS);

  const onSelect = useCallback(
    (selection: Selection3D | null) => setPicked(selection?.id ?? ''),
    [setPicked],
  );

  return {
    highlighted: picked ? [picked] : [],
    picked,
    view,
    setView,
    onSelect,
    clear: useCallback(() => setPicked(''), [setPicked]),
  };
}
