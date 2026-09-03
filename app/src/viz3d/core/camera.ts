/**
 * Camera presets and fit-to-bounds. Pure arithmetic — no three, so it is unit-tested.
 *
 * **z is up in this module.** Every adapter puts the *measured* quantity on z (calls per bin,
 * copy number, quality), and the whole point of a 3D view here is that the reader sees that
 * quantity as height. three's own default up is +y, so `core/viewer.ts` sets `camera.up` from
 * `pose.up` rather than relying on the default.
 *
 * Two fits live here, and the difference is why the fold used to sit in the middle of a mostly
 * empty canvas:
 *
 *   - `fitToBounds` fits the *bounding sphere of the data box*. Its radius is half the box
 *     diagonal, so a globular protein inside a 2 × 1.6 × 1.2 box is fitted as if it were a
 *     sphere of radius 1.42 — the fold then drew at ~30–45 % of the shorter canvas side.
 *     It is the fallback for a caller that has no point buffer.
 *   - `fitPoints` fits the **projected extent of the actual drawn points**. It solves, in one
 *     pass, the smallest camera distance at which every point (plus its sphere radius) is
 *     inside both the vertical and the horizontal field of view. The extreme point then lands
 *     at `1 / MARGIN` of the binding half-side, so the figure fills the canvas.
 */

import type { Bounds3, CameraPose3D, CameraPreset, Vec3 } from '../spec/types';

/**
 * The pose a fit produces, and the pose a page hands back in — one type, declared in
 * `spec/types.ts` because it is part of the module's public contract (`Viz3dCanvas.pose`).
 */
export type CameraPose = CameraPose3D;

/** One point buffer, with an optional per-point radius in the same (unit-box) space. */
export interface PointSet {
  positions: Float32Array;
  radii?: Float32Array;
}

const Z_UP: Vec3 = [0, 0, 1];
const Y_UP: Vec3 = [0, 1, 0];

/** Unit direction the camera sits along, per preset, and the up vector that reads level. */
const DIRECTIONS: Record<CameraPreset, { from: Vec3; up: Vec3 }> = {
  iso: { from: [0.72, -0.72, 0.55], up: Z_UP },
  top: { from: [0, 0, 1], up: Y_UP },
  front: { from: [0, -1, 0], up: Z_UP },
  side: { from: [1, 0, 0], up: Z_UP },
};

/**
 * Empty room left around the fitted figure, as a fraction of the fitted distance. 1.08 leaves
 * ~7 % of the shorter side as breathing room — enough for a highlight ring and a link label,
 * where the old 1.35 (on top of a box-diagonal radius) left the figure at a third of the frame.
 */
const MARGIN = 1.08;

export const boundsCentre = (bounds: Bounds3): Vec3 => [
  (bounds.min[0] + bounds.max[0]) / 2,
  (bounds.min[1] + bounds.max[1]) / 2,
  (bounds.min[2] + bounds.max[2]) / 2,
];

/** Half the diagonal of the box — the radius of the sphere the camera has to contain. */
export function boundsRadius(bounds: Bounds3): number {
  const span = [0, 1, 2].map((i) => bounds.max[i] - bounds.min[i]);
  const radius = Math.hypot(span[0], span[1], span[2]) / 2;
  return radius > 1e-6 ? radius : 1;
}

const cross = (a: Vec3, b: Vec3): Vec3 => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];

function unit(a: Vec3, fallback: Vec3): Vec3 {
  const length = Math.hypot(a[0], a[1], a[2]);
  return length < 1e-9 ? fallback : [a[0] / length, a[1] / length, a[2] / length];
}

/** The half-angles of the frustum: vertical from the fov, horizontal from the canvas aspect. */
function halfAngles(fovDegrees: number, aspect: number): { tanV: number; tanH: number } {
  const tanV = Math.tan((fovDegrees * Math.PI) / 360);
  return { tanV, tanH: tanV * (aspect > 1e-6 ? aspect : 1) };
}

/**
 * The camera basis for a preset. `backward` points from the target to the camera; `right` and
 * `screenUp` are the screen axes the fit projects onto — right-handed, so `right = up × backward`
 * and `screenUp = backward × right`.
 *
 * `up` stays the **declared** preset up, not `screenUp`: `OrbitControls` uses `camera.up` as the
 * polar axis it orbits around, so handing it the orthogonalised (tilted) up for `iso` would make
 * a drag rotate the scene about a tilted axis. three's own `lookAt` orthogonalises it for the
 * view matrix, which is exactly what `screenUp` reproduces here.
 */
function basis(preset: CameraPreset): { right: Vec3; up: Vec3; screenUp: Vec3; backward: Vec3 } {
  const declared = DIRECTIONS[preset];
  const backward = unit(declared.from, [0, 0, 1]);
  const right = unit(cross(declared.up, backward), [1, 0, 0]);
  return { right, up: declared.up, screenUp: cross(backward, right), backward };
}

const pose = (target: Vec3, backward: Vec3, distance: number, up: Vec3): CameraPose => ({
  position: [
    target[0] + backward[0] * distance,
    target[1] + backward[1] * distance,
    target[2] + backward[2] * distance,
  ],
  target,
  up,
});

/**
 * Where to put the camera so the whole data box fits the field of view. The fallback fit: it
 * only knows the box, so it fits the box's bounding sphere and is necessarily loose for any
 * figure that is not a cube. Prefer `fitPoints` when the point buffers are to hand.
 */
export function fitToBounds(
  bounds: Bounds3,
  preset: CameraPreset,
  fovDegrees = 42,
  aspect = 1,
): CameraPose {
  const target = boundsCentre(bounds);
  const radius = boundsRadius(bounds);
  const { tanV, tanH } = halfAngles(fovDegrees, aspect);
  const distance = (radius / Math.min(tanV, tanH)) * MARGIN;
  const { up, backward } = basis(preset);
  return pose(target, backward, distance, up);
}

/**
 * Fit the *drawn points*. For each point `p` (relative to the target) the perspective
 * constraint is `|p·right| ≤ (d − p·backward)·tanH` and `|p·up| ≤ (d − p·backward)·tanV`, so
 * the smallest admissible distance is
 *
 *     d = max over p of  p·backward + max(|p·right| / tanH, |p·up| / tanV)
 *
 * with the point's own sphere radius added to both numerators. One pass, no allocation. An
 * empty point set falls back to `fitToBounds`.
 */
export function fitPoints(
  sets: readonly PointSet[],
  bounds: Bounds3,
  preset: CameraPreset,
  fovDegrees = 42,
  aspect = 1,
): CameraPose {
  const target = boundsCentre(bounds);
  const { tanV, tanH } = halfAngles(fovDegrees, aspect);
  const { right, up, screenUp, backward } = basis(preset);
  let needed = 0;
  let seen = 0;
  for (const set of sets) {
    const count = Math.floor(set.positions.length / 3);
    for (let i = 0; i < count; i++) {
      const x = set.positions[i * 3] - target[0];
      const y = set.positions[i * 3 + 1] - target[1];
      const z = set.positions[i * 3 + 2] - target[2];
      const radius = set.radii?.[i] ?? 0;
      const depth = x * backward[0] + y * backward[1] + z * backward[2];
      const across = Math.abs(x * right[0] + y * right[1] + z * right[2]) + radius;
      const high = Math.abs(x * screenUp[0] + y * screenUp[1] + z * screenUp[2]) + radius;
      const want = depth + Math.max(across / tanH, high / tanV);
      if (want > needed) needed = want;
      seen++;
    }
  }
  if (seen === 0 || needed <= 1e-6) return fitToBounds(bounds, preset, fovDegrees, aspect);
  return pose(target, backward, needed * MARGIN, up);
}

/**
 * How far apart two poses are, as the largest absolute difference across all nine numbers.
 *
 * Used for two things that both need a tolerance rather than equality: deciding whether an
 * orbit is worth reporting (OrbitControls damps, so the camera keeps creeping for ~a second
 * after the reader lets go), and deciding whether an incoming controlled pose is the echo of
 * the one this canvas just reported.
 */
export function poseDistance(a: CameraPose, b: CameraPose): number {
  const keys: readonly (keyof CameraPose)[] = ['position', 'target', 'up'];
  let worst = 0;
  for (const key of keys) {
    for (let i = 0; i < 3; i++) worst = Math.max(worst, Math.abs(a[key][i] - b[key][i]));
  }
  return worst;
}
