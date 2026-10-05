/**
 * Reading a `Scene3D` as a flat list of pickable datums, and reading a field off one.
 *
 * Every kind is ultimately a bag of `Datum3D`s: `points` and `protein` carry them directly,
 * `surface` derives them from its grid. Picking, the keyboard fallback, the filters and the
 * text description all work off this one list, so a new scene kind gets all four by
 * answering this function.
 */

import type { Datum3D, Scene3D } from './types';

/** Cell id for a surface grid — `y` first, matching `z[yIndex][xIndex]`. */
export const cellId = (yIndex: number, xIndex: number): string => `cell-${yIndex}-${xIndex}`;

/** Every pickable datum in the scene, in a stable order. */
export function sceneDatums(scene: Scene3D): readonly Datum3D[] {
  switch (scene.kind) {
    case 'points':
      return scene.points;
    case 'protein':
      return scene.residues;
    case 'surface': {
      const out: Datum3D[] = [];
      scene.grid.z.forEach((row, yIndex) => {
        row.forEach((z, xIndex) => {
          if (z === null) return;
          const y = scene.grid.y[yIndex];
          out.push({
            id: cellId(yIndex, xIndex),
            label: `${typeof y === 'string' ? y : String(y)} · ${scene.grid.x[xIndex]}`,
            at: [scene.grid.x[xIndex], yIndex, z],
            value: z,
          });
        });
      });
      return out;
    }
  }
}

/** `'value'` or a `meta` key, read off one datum. Absent reads as `null`. */
export function fieldValue(datum: Datum3D, field: string): string | number | null {
  if (field === 'value') return datum.value;
  return datum.meta?.[field] ?? null;
}

export interface NumericField {
  name: string;
  kind: 'numeric';
  min: number;
  max: number;
}

export interface CategoricalField {
  name: string;
  kind: 'categorical';
  values: readonly string[];
}

export type SceneField = NumericField | CategoricalField;

/**
 * Every field a page may filter or colour by: `value` plus each `meta` key, classified as
 * numeric (a range slider) or categorical (a set of checkboxes) by what the data holds.
 * A field whose values are all numbers is numeric; anything else is categorical.
 */
export function sceneFields(datums: readonly Datum3D[]): readonly SceneField[] {
  const names = ['value', ...new Set(datums.flatMap((d) => Object.keys(d.meta ?? {})))];
  return names.map((name) => {
    const seen = datums.map((d) => fieldValue(d, name)).filter((v) => v !== null);
    const numeric = seen.length > 0 && seen.every((v) => typeof v === 'number');
    if (numeric) {
      const nums = seen as number[];
      return { name, kind: 'numeric', min: Math.min(...nums), max: Math.max(...nums) };
    }
    return { name, kind: 'categorical', values: [...new Set(seen.map(String))].sort() };
  });
}
