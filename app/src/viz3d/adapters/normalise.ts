/**
 * The arithmetic every adapter shares: the data-space box, the transform into the unit box
 * the camera presets are written against, per-datum colour, and the link lines.
 *
 * Pure. No three import — this is the module the adapter tests actually exercise.
 */

import { rampColors, toneRgb } from '../core/colorRamp';
import { fieldValue } from '../spec/datums';
import type {
  Bounds3,
  ColorEncoding,
  Datum3D,
  LinkLines,
  PickRange,
  Scene3D,
  Vec3,
} from '../spec/types';

/** The axis-aligned box containing every point. An empty input gives a zero box. */
export function boundsOf(points: readonly Vec3[]): Bounds3 {
  if (points.length === 0) return { min: [0, 0, 0], max: [0, 0, 0] };
  const min: [number, number, number] = [Infinity, Infinity, Infinity];
  const max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  for (const p of points) {
    for (let i = 0; i < 3; i++) {
      if (p[i] < min[i]) min[i] = p[i];
      if (p[i] > max[i]) max[i] = p[i];
    }
  }
  return { min, max };
}

export interface Normaliser {
  /** Data space -> the unit box, centred on the origin, longest side spanning 2. */
  toUnit(at: Vec3): Vec3;
  /** A data-space length -> the same length in unit space. */
  toUnitLength(length: number): number;
  extent: Bounds3;
  bounds: Bounds3;
}

/**
 * One uniform scale for all three axes — not per-axis — so a scene keeps its real shape.
 * A protein squeezed independently on each axis would misreport spatial adjacency, which is
 * the whole reason the protein view exists.
 */
export function normaliser(extent: Bounds3): Normaliser {
  const centre = [0, 1, 2].map((i) => (extent.min[i] + extent.max[i]) / 2);
  const spans = [0, 1, 2].map((i) => extent.max[i] - extent.min[i]);
  const longest = Math.max(...spans, Number.EPSILON);
  const factor = 2 / longest;
  const toUnit = (at: Vec3): Vec3 => [
    (at[0] - centre[0]) * factor,
    (at[1] - centre[1]) * factor,
    (at[2] - centre[2]) * factor,
  ];
  return {
    toUnit,
    toUnitLength: (length: number) => length * factor,
    extent,
    bounds: { min: toUnit(extent.min), max: toUnit(extent.max) },
  };
}

/** The domain an encoding actually paints: its declared one, or the observed range. */
function encodingDomain(
  datums: readonly Datum3D[],
  encoding: ColorEncoding,
): readonly [number, number] {
  if (encoding.kind === 'categorical') return [0, 1];
  if (encoding.domain) return encoding.domain;
  const values = datums
    .map((d) => fieldValue(d, encoding.field))
    .filter((v): v is number => typeof v === 'number');
  if (values.length === 0) return [0, 1];
  return [Math.min(...values), Math.max(...values)];
}

/**
 * One sRGB triple per datum. Precedence: an explicit `datum.tone` wins (a categorical verdict
 * the page has already decided), then the encoding, then the absent grey.
 */
export function datumColors(datums: readonly Datum3D[], encoding: ColorEncoding): Float32Array {
  const out =
    encoding.kind === 'numeric'
      ? rampColors(
          datums.map((d) => {
            const raw = fieldValue(d, encoding.field);
            return typeof raw === 'number' ? raw : null;
          }),
          encoding.scale,
          encodingDomain(datums, encoding),
        )
      : categoricalColors(datums, encoding);
  datums.forEach((datum, index) => {
    if (!datum.tone) return;
    const rgb = toneRgb(datum.tone);
    out.set(rgb, index * 3);
  });
  return out;
}

function categoricalColors(
  datums: readonly Datum3D[],
  encoding: Extract<ColorEncoding, { kind: 'categorical' }>,
): Float32Array {
  const out = new Float32Array(datums.length * 3);
  datums.forEach((datum, index) => {
    const raw = fieldValue(datum, encoding.field);
    const tone = raw === null ? undefined : encoding.tones[String(raw)];
    out.set(tone ? toneRgb(tone) : toneRgb('neutral'), index * 3);
  });
  return out;
}

/** One `PickRange` per datum over an index space of `stride` slots each. */
export function tilePickTable(
  datums: readonly Datum3D[],
  stride = 1,
  offset = 0,
): readonly PickRange[] {
  return datums.map((datum, index) => ({
    id: datum.id,
    from: offset + index * stride,
    to: offset + (index + 1) * stride,
  }));
}

/** The straight lines a scene's `links` draw, plus where each label sits. */
export function linkLines(
  scene: Scene3D,
  datums: readonly Datum3D[],
  unit: Normaliser,
): LinkLines | undefined {
  const links = (scene.links ?? []).flatMap((link) => {
    const from = datums.find((d) => d.id === link.from);
    const to = datums.find((d) => d.id === link.to);
    return from && to ? [{ link, from, to }] : [];
  });
  if (links.length === 0) return undefined;
  const positions = new Float32Array(links.length * 6);
  const colors = new Float32Array(links.length * 6);
  const labels = links.map(({ link, from, to }, index) => {
    const a = unit.toUnit(from.at);
    const b = unit.toUnit(to.at);
    positions.set(a, index * 6);
    positions.set(b, index * 6 + 3);
    const rgb = toneRgb(link.tone ?? 'decision');
    colors.set(rgb, index * 6);
    colors.set(rgb, index * 6 + 3);
    return {
      at: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2] as Vec3,
      text: link.label ?? `${from.label} ↔ ${to.label}`,
    };
  });
  return { positions, colors, labels };
}
