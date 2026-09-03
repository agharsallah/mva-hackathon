/**
 * Dynamic exploration, without the page learning anything about three.
 *
 * A page hands in a `Scene3D` whose datums carry their facts in `meta` and which declares the
 * encodings it is willing to be coloured by. This hook turns that into the state a generic
 * explorer needs — active encoding, a numeric range per numeric field, an excluded set per
 * categorical field, layer visibility — and returns a **derived scene** with those applied.
 * `SceneControls` renders the controls from the same object; a page can also ignore
 * `SceneControls` and build its own UI over this state.
 *
 * The active encoding is URL-held (`?<ns>.by=…`) because it changes what the figure *means*
 * and therefore belongs in a citation. Filters and layers are component state: they are
 * exploratory, high-cardinality, and would make the URL unreadable.
 */

import { useCallback, useMemo, useState } from 'react';

import { useUrlState } from '../../lib/urlstate';
import { fieldValue, sceneDatums, type SceneField, sceneFields } from '../spec/datums';
import { filterScene, recolour, sceneEncodings } from '../spec/filter';
import type { ColorEncoding, Datum3D, Scene3D, SceneLayer } from '../spec/types';

export interface LayerState extends SceneLayer {
  on: boolean;
}

export interface SceneExplorer {
  /** The scene to render: filtered, layer-masked and recoloured. */
  scene: Scene3D;
  encoding: ColorEncoding;
  encodings: readonly ColorEncoding[];
  setEncoding: (id: string) => void;
  /** Every field, classified numeric/categorical from the *unfiltered* data. */
  fields: readonly SceneField[];
  /** field -> the accepted [min, max]; absent means "the whole range". */
  ranges: Readonly<Record<string, readonly [number, number]>>;
  setRange: (field: string, range: readonly [number, number]) => void;
  /** field -> the category values currently hidden. */
  excluded: Readonly<Record<string, readonly string[]>>;
  toggleValue: (field: string, value: string) => void;
  layers: readonly LayerState[];
  toggleLayer: (id: string) => void;
  visible: number;
  total: number;
  /** Back to every datum, every layer, and the scene's own encoding. */
  reset: () => void;
}

export function useSceneExplorer(scene: Scene3D, ns: string): SceneExplorer {
  const encodings = useMemo(() => sceneEncodings(scene), [scene]);
  const encodingIds = useMemo(() => encodings.map((e) => e.id), [encodings]);
  const [encodingId, setEncoding] = useUrlState(`${ns}.by`, scene.color.id, encodingIds);

  const datums = useMemo(() => sceneDatums(scene), [scene]);
  const fields = useMemo(() => sceneFields(datums), [datums]);

  const [ranges, setRanges] = useState<Record<string, readonly [number, number]>>({});
  const [excluded, setExcluded] = useState<Record<string, readonly string[]>>({});
  const [off, setOff] = useState<readonly string[]>(() =>
    (scene.layers ?? []).filter((layer) => layer.on === false).map((layer) => layer.id),
  );

  const keep = useCallback(
    (datum: Datum3D): boolean => {
      if (datum.layer && off.includes(datum.layer)) return false;
      for (const [field, range] of Object.entries(ranges)) {
        const raw = fieldValue(datum, field);
        if (typeof raw !== 'number') continue;
        if (raw < range[0] || raw > range[1]) return false;
      }
      for (const [field, hidden] of Object.entries(excluded)) {
        const raw = fieldValue(datum, field);
        if (hidden.includes(String(raw ?? ''))) return false;
      }
      return true;
    },
    [off, ranges, excluded],
  );

  const derived = useMemo(
    () => recolour(filterScene(scene, keep), encodingId),
    [scene, keep, encodingId],
  );

  const layers = useMemo<LayerState[]>(
    () => (scene.layers ?? []).map((layer) => ({ ...layer, on: !off.includes(layer.id) })),
    [scene.layers, off],
  );

  return {
    scene: derived,
    encoding: encodings.find((e) => e.id === encodingId) ?? scene.color,
    encodings,
    setEncoding,
    fields,
    ranges,
    setRange: useCallback((field, range) => setRanges((prev) => ({ ...prev, [field]: range })), []),
    excluded,
    toggleValue: useCallback((field, value) => {
      setExcluded((prev) => {
        const hidden = prev[field] ?? [];
        return {
          ...prev,
          [field]: hidden.includes(value) ? hidden.filter((v) => v !== value) : [...hidden, value],
        };
      });
    }, []),
    layers,
    toggleLayer: useCallback(
      (id) => setOff((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id])),
      [],
    ),
    visible: datums.filter(keep).length,
    total: datums.length,
    reset: useCallback(() => {
      setRanges({});
      setExcluded({});
      setOff([]);
      setEncoding(scene.color.id);
    }, [setEncoding, scene.color.id]),
  };
}
