/**
 * `describeScene` — one artefact, three jobs.
 *
 * A canvas has no serialisable content, so a 3D exhibit's AI export is the *description*, not
 * the picture. The same object is:
 *
 *   1. `Exhibit`'s `data` prop — the AI-export payload;
 *   2. the canvas's `aria-label` (`.text`), which is what axe's `role-img-alt` audits;
 *   3. the body of `SceneFallback`, the keyboard path and the no-WebGL rendering.
 *
 * It is deterministic: same scene in, byte-identical description out, so a blessed export
 * hash does not churn.
 *
 * Numbers are formatted through `lib/format`, which groups thousands with commas. That is not
 * cosmetic: the repo's binding rule is that no genomic coordinate is ever exported, and a
 * grouped number can never present the bare 7–9 digit run a coordinate takes. Axes are
 * declared in bins/Mb/index units by the page for the same reason.
 */

import { compact, dec, int } from '../../lib/format';
import { fieldValue, sceneDatums } from './datums';
import type { Axes3D, Bounds3, ColorEncoding, Datum3D, Scene3D, SceneKind } from './types';

/** Grouped, never a bare long digit run. See the module note above. */
export function num(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  if (Number.isInteger(n)) return int(n);
  if (Math.abs(n) >= 1e5) return compact(n);
  return dec(n, 2);
}

export interface AxisDescription {
  label: string;
  unit: string | null;
  from: string;
  to: string;
  categories: readonly string[] | null;
}

export interface DatumDescription {
  id: string;
  label: string;
  value: string;
  meta: Readonly<Record<string, string>>;
}

export interface SceneDescription {
  kind: SceneKind;
  title: string;
  count: number;
  axes: readonly AxisDescription[];
  color: {
    label: string;
    kind: ColorEncoding['kind'];
    field: string;
    means: string;
  };
  top: readonly DatumDescription[];
  bottom: readonly DatumDescription[];
  highlighted: readonly DatumDescription[];
  links: readonly string[];
  /** The deterministic prose paragraph. */
  text: string;
}

const AXIS_ORDER = ['x', 'y', 'z'] as const;

function describeAxes(axes: Axes3D, extent: Bounds3): AxisDescription[] {
  return AXIS_ORDER.map((key, index) => ({
    label: axes[key].label,
    unit: axes[key].unit ?? null,
    from: num(extent.min[index]),
    to: num(extent.max[index]),
    categories: axes[key].categories ?? null,
  }));
}

function describeDatum(datum: Datum3D): DatumDescription {
  const meta: Record<string, string> = {};
  for (const [key, value] of Object.entries(datum.meta ?? {})) {
    meta[key] = typeof value === 'number' ? num(value) : (value ?? '—');
  }
  return { id: datum.id, label: datum.label, value: num(datum.value), meta };
}

function extentOf(datums: readonly Datum3D[]): Bounds3 {
  if (datums.length === 0) return { min: [0, 0, 0], max: [0, 0, 0] };
  const axis = (i: 0 | 1 | 2) => datums.map((d) => d.at[i]);
  const lo = AXIS_ORDER.map((_, i) => Math.min(...axis(i as 0 | 1 | 2)));
  const hi = AXIS_ORDER.map((_, i) => Math.max(...axis(i as 0 | 1 | 2)));
  return {
    min: [lo[0], lo[1], lo[2]],
    max: [hi[0], hi[1], hi[2]],
  };
}

function colorWords(color: ColorEncoding): string {
  return color.kind === 'numeric'
    ? `low = ${color.lowMeans}, high = ${color.highMeans}`
    : color.means;
}

const KIND_NOUN: Record<SceneKind, string> = {
  surface: 'surface',
  points: 'point cloud',
  karyotype: 'karyotype',
  protein: 'protein backbone',
};

/** How many extremes each end of the description lists. */
const EXTREMES = 3;

export function describeScene(
  scene: Scene3D,
  highlighted: readonly string[] = [],
): SceneDescription {
  const datums = sceneDatums(scene);
  const axes = describeAxes(scene.axes, extentOf(datums));
  const ranked = [...datums].sort(
    (a, b) => b.value - a.value || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
  // "Highest / lowest by value" is only a fact when the values differ. Where every datum
  // carries the same value (an experimental structure has no per-residue confidence, so the
  // scene's `value` is flat), ranking degenerates to an alphabetical id sort and reporting it
  // as an extreme would be an invented finding. Say nothing instead.
  const spread = ranked.length > 1 && ranked[0].value !== ranked[ranked.length - 1].value;
  const top = spread ? ranked.slice(0, EXTREMES).map(describeDatum) : [];
  const bottom = spread ? ranked.slice(-EXTREMES).reverse().map(describeDatum) : [];
  const picked = highlighted
    .map((id) => datums.find((d) => d.id === id))
    .filter((d): d is Datum3D => d !== undefined)
    .map(describeDatum);

  const links = (scene.links ?? []).map((link) => {
    const from = datums.find((d) => d.id === link.from)?.label ?? link.from;
    const to = datums.find((d) => d.id === link.to)?.label ?? link.to;
    return `${from} ↔ ${to}${link.label ? ` (${link.label})` : ''}`;
  });

  const color = {
    label: scene.color.label,
    kind: scene.color.kind,
    field: scene.color.field,
    means: colorWords(scene.color),
  };

  return {
    kind: scene.kind,
    title: scene.title,
    count: datums.length,
    axes,
    color,
    top,
    bottom,
    highlighted: picked,
    links,
    text: prose(scene, { axes, color, count: datums.length, top, picked, links }),
  };
}

function axisPhrase(axis: AxisDescription): string {
  const unit = axis.unit ? ` in ${axis.unit}` : '';
  if (axis.categories) return `${axis.label} (${axis.categories.length} categories)`;
  return `${axis.label}${unit} from ${axis.from} to ${axis.to}`;
}

function prose(
  scene: Scene3D,
  parts: {
    axes: readonly AxisDescription[];
    color: SceneDescription['color'];
    count: number;
    top: readonly DatumDescription[];
    picked: readonly DatumDescription[];
    links: readonly string[];
  },
): string {
  const sentences = [
    `${scene.title}: a 3D ${KIND_NOUN[scene.kind]} of ${num(parts.count)} pickable objects.`,
    `Axes — ${parts.axes.map(axisPhrase).join('; ')}.`,
    `Colour encodes ${parts.color.label} (${parts.color.field}): ${parts.color.means}.`,
  ];
  if (parts.top.length > 0) {
    sentences.push(
      `Highest by value: ${parts.top.map((d) => `${d.label} at ${d.value}`).join(', ')}.`,
    );
  }
  if (parts.picked.length > 0) {
    sentences.push(`Highlighted: ${parts.picked.map((d) => d.label).join(', ')}.`);
  } else {
    sentences.push('Nothing is highlighted.');
  }
  if (parts.links.length > 0) sentences.push(`Linked pairs: ${parts.links.join('; ')}.`);
  return sentences.join(' ');
}

/**
 * The one-line summary a tooltip shows: the datum's label, its value, then its meta fields.
 * Shared by the canvas overlay and `SceneFallback` so both read the same words.
 */
export function describeDatumLine(datum: Datum3D, field = 'value'): string {
  const raw = fieldValue(datum, field);
  const head = `${datum.label} · ${typeof raw === 'number' ? num(raw) : (raw ?? '—')}`;
  const rest = Object.entries(datum.meta ?? {})
    .filter(([key]) => key !== field)
    .map(([key, value]) => `${key} ${typeof value === 'number' ? num(value) : (value ?? '—')}`);
  return [head, ...rest].join(' · ');
}
