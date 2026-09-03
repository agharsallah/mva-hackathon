/**
 * The whole public data contract of `viz3d`.
 *
 * A page supplies **data**, never three.js code: it maps this case's API rows into a
 * `Scene3D` and hands that in. Nothing in this folder knows what a `DensityBinRow` is, which
 * is the property that makes the module transferable to another N-of-1 case — a new case adds
 * a `Scene3D` variant plus an adapter, and nothing else.
 *
 * Layer edge: `viz3d` imports `lib` only (palette, urlstate, format). Never `api`.
 */

import type { Colorscale, Tone } from '../../lib/palette';

/** A point in the scene's own units (bins, megabases, Ångström, index). */
export type Vec3 = readonly [number, number, number];

export interface Bounds3 {
  min: Vec3;
  max: Vec3;
}

export interface AxisSpec {
  /** Axis title in the reader's words ('megabase', 'flowcell tile', 'residue index'). */
  label: string;
  /** Unit, for the legend and the text description. */
  unit?: string;
  /** Tick labels when the axis is ordinal (chromosome names, partitions). */
  categories?: readonly string[];
}

export interface Axes3D {
  x: AxisSpec;
  y: AxisSpec;
  z: AxisSpec;
}

/**
 * Which field a datum's colour comes from, and what the colour *means*.
 *
 * `field` is `'value'` (the datum's own `value`) or a key of `Datum3D.meta`. A scene declares
 * every encoding it is willing to be coloured by in `SceneBase.encodings`, which is what lets
 * a page offer "colour by any field" without knowing anything about three.
 */
export interface NumericEncoding {
  id: string;
  /** Words for the control and the legend ('calls per megabase'). */
  label: string;
  kind: 'numeric';
  field: string;
  /** Omit to let the adapter take the observed min/max of the field. */
  domain?: readonly [number, number];
  scale: Colorscale;
  /** Legend + AI-export prose: what the cold and hot ends of the ramp mean. */
  lowMeans: string;
  highMeans: string;
}

export interface CategoricalEncoding {
  id: string;
  label: string;
  kind: 'categorical';
  field: string;
  /** Category value -> tone. A value not in the map is drawn in `C.unmeasured`. */
  tones: Readonly<Record<string, Tone>>;
  /** Legend words for the whole encoding ('one colour per consequence class'). */
  means: string;
}

export type ColorEncoding = NumericEncoding | CategoricalEncoding;

/** One pickable thing. `id` is what the selection callback reports and the URL holds. */
export interface Datum3D {
  id: string;
  label: string;
  at: Vec3;
  value: number;
  /** Optional categorical override, resolved through `TONE_MARK` — never a hex. */
  tone?: Tone;
  /** Radius multiplier, 1 = the scene default. */
  size?: number;
  /** Which toggleable layer this datum belongs to (see `SceneBase.layers`). */
  layer?: string;
  /** Extra facts for the tooltip, the filters and the AI export. Never a coordinate. */
  meta?: Readonly<Record<string, string | number | null>>;
}

export interface SurfaceGrid {
  x: readonly number[];
  y: readonly (number | string)[];
  /** `z[yIndex][xIndex]`; `null` = not measured (drawn flat in `C.unmeasured`). */
  z: readonly (readonly (number | null)[])[];
}

export interface ChromosomeBar {
  name: string;
  /** In the axis's own unit (Mb/bins) — never a patient position. */
  length: number;
  /** The aneuploidy signal: 1, 2, 3… */
  copies: number;
  bands?: readonly { from: number; to: number; value: number }[];
}

/** A drawn relationship between two datums — e.g. the distance between two picked residues. */
export interface SceneLink {
  from: string;
  to: string;
  /** Words drawn beside the line, in the scene's own unit. */
  label?: string;
  tone?: Tone;
}

/** A toggleable group of datums. `on` is the initial state (default: on). */
export interface SceneLayer {
  id: string;
  label: string;
  on?: boolean;
}

export interface SceneBase {
  title: string;
  axes: Axes3D;
  /** The active encoding. */
  color: ColorEncoding;
  /** Every encoding a page may offer in a "colour by" control. Defaults to `[color]`. */
  encodings?: readonly ColorEncoding[];
  layers?: readonly SceneLayer[];
  links?: readonly SceneLink[];
  /** Unit for a link label and for spatial prose ('Å', 'Mb'). */
  unit?: string;
}

export type Scene3D =
  | (SceneBase & { kind: 'surface'; grid: SurfaceGrid })
  | (SceneBase & { kind: 'points'; points: readonly Datum3D[]; radius?: number })
  | (SceneBase & { kind: 'karyotype'; chromosomes: readonly ChromosomeBar[] })
  | (SceneBase & {
      kind: 'protein';
      backbone: readonly Vec3[];
      residues: readonly Datum3D[];
      /** Tube radius in scene units. */
      radius?: number;
    });

export type SceneKind = Scene3D['kind'];

/** Half-open range over an index space -> the datum a raycast hit resolves to. */
export interface PickRange {
  id: string;
  from: number;
  to: number;
}

/** An instanced set of spheres: points, or a protein's residues beside its tube. */
export interface InstanceBuffers {
  /** xyz triples, normalised. */
  positions: Float32Array;
  /** rgb triples, sRGB 0..1. */
  colors: Float32Array;
  /** One radius per instance, in normalised units. */
  radii: Float32Array;
  /** Ranges over the *instance* index space. */
  pickTable: readonly PickRange[];
}

/** Straight lines between two datums, already normalised. */
export interface LinkLines {
  /** Two xyz triples per link (from, to). */
  positions: Float32Array;
  /** rgb triples, one per vertex. */
  colors: Float32Array;
  labels: readonly { at: Vec3; text: string }[];
}

/**
 * Adapter output. Pure data — no three import, fully unit-testable.
 *
 * Positions are normalised into a unit box centred on the origin so the camera presets work
 * for every scene; `extent` keeps the data-space box for axis labels and the description.
 */
export interface GeometryBuffers {
  kind: SceneKind;
  /** How the primary buffer is drawn: a triangle mesh, or one sphere per position. */
  draw: 'mesh' | 'instances';
  positions: Float32Array;
  colors: Float32Array;
  /** Mesh only. */
  indices?: Uint32Array;
  /** Mesh only; absent means three computes them. */
  normals?: Float32Array;
  /** Instances only. */
  radii?: Float32Array;
  /** Ranges over the primary index space (vertex index for a mesh, instance index else). */
  pickTable: readonly PickRange[];
  /** A second, instanced set drawn alongside the primary mesh (protein residues). */
  instances?: InstanceBuffers;
  links?: LinkLines;
  /** Normalised bounds — what the camera fits to. */
  bounds: Bounds3;
  /** Data-space bounds, in the axes' own units. */
  extent: Bounds3;
}

export type Adapter<S extends Scene3D> = (scene: S) => GeometryBuffers;

/** What a pick reports. The *page* decides what to do with it (usually: write the URL). */
export interface Selection3D {
  id: string;
  label: string;
  datum: Datum3D;
}

export type CameraPreset = 'iso' | 'top' | 'front' | 'side';

/**
 * A camera, as three vectors — the *whole* reader-visible view state.
 *
 * A `CameraPreset` names a canned viewpoint; this is where the camera actually is after the
 * reader has orbited it by hand. It exists so two canvases can be driven from one pose ("sync
 * cameras" in a side-by-side comparison): the pose is data, so it crosses the module edge as
 * a plain value and neither the page nor this module needs a three object to express it.
 *
 * Units are the **normalised unit box** every adapter maps its scene into, not the scene's own
 * units — which is exactly what makes one pose meaningful on two different scenes.
 */
export interface CameraPose3D {
  position: Vec3;
  target: Vec3;
  up: Vec3;
}

export const CAMERA_PRESETS: readonly CameraPreset[] = ['iso', 'top', 'front', 'side'];

export interface Viz3dCanvasProps {
  scene: Scene3D;
  height?: number;
  /** Highlighted ids — a controlled prop, held in the URL, never in canvas state. */
  highlighted?: readonly string[];
  /** Click pick; `null` when the background was clicked. */
  onSelect?: (selection: Selection3D | null) => void;
  view?: CameraPreset;
  /** Idle auto-rotate. Ignored when the visitor asked for reduced motion. */
  autoRotate?: boolean;
  /** Overrides the generated `aria-label` (which is `describeScene(scene).text`). */
  label?: string;
  /**
   * Controlled camera pose. Supply it (with `onPose`) to drive two canvases from one orbit;
   * omit it and the canvas owns its own camera, which is the default and unchanged behaviour.
   * A pose equal to the one this canvas last reported is ignored, so the two directions cannot
   * feed each other.
   */
  pose?: CameraPose3D | null;
  /** Fires while the reader moves the camera, throttled — never at frame rate. */
  onPose?: (pose: CameraPose3D) => void;
  /**
   * Bump to re-apply `view` even though the preset itself did not change.
   *
   * A camera preset is normally applied once, when it changes. "Reset the camera" is a
   * different gesture with the same destination: the reader has orbited away from the preset
   * and wants it back, and `view` is still the value it always was. A monotonic counter is
   * the smallest thing that expresses "apply it again" without making the preset itself lie.
   */
  refitKey?: number;
}
