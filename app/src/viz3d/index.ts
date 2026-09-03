/**
 * `viz3d` — the only entry a page imports from. See `./README.md` for the contract.
 *
 * The rule this barrel exists to keep: a page hands in **data** (a `Scene3D` it built from
 * this case's API rows) and gets back a canvas, a text twin of the same figure, and controls.
 * It never imports three, never imports anything under `core/`, and never learns a scene kind
 * it did not build itself.
 */

export { SceneControls } from './components/SceneControls';
// The one piece of `core/` a page may need: sRGB is gamma-encoded, so any *photometric*
// quantity a page computes from a palette hex (relative luminance, contrast) has to linearise
// first. `src/pages/styleguide/Viz3dDemo.tsx` is the caller.
export { Viz3dCanvas } from './components/Viz3dCanvas';
export { srgbToLinear } from './core/colorRamp';
export { type SceneExplorer, useSceneExplorer } from './hooks/useSceneExplorer';
export { type SceneSelection, useSceneSelection } from './hooks/useSceneSelection';
export { describeScene, type SceneDescription } from './spec/describe';
export type {
  Axes3D,
  AxisSpec,
  CameraPose3D,
  CameraPreset,
  CategoricalEncoding,
  ColorEncoding,
  Datum3D,
  NumericEncoding,
  Scene3D,
  SceneKind,
  SceneLayer,
  SceneLink,
  Selection3D,
  Vec3,
  Viz3dCanvasProps,
} from './spec/types';
// The camera vocabulary as a value, not only a type: a page that owns its own view control
// (the side-by-side comparison shares one preset across two canvases) needs the option list.
export { CAMERA_PRESETS } from './spec/types';
