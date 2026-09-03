import { describe, expect, it } from 'vitest';

import type { Bounds3 } from '../spec/types';
import { boundsCentre, boundsRadius, fitPoints, fitToBounds, poseDistance } from './camera';

const BOX: Bounds3 = { min: [-1, -1, -1], max: [1, 1, 1] };
const OFF_CENTRE: Bounds3 = { min: [2, 4, 6], max: [4, 8, 10] };

describe('bounds arithmetic', () => {
  it('centres on the box, not on the origin', () => {
    expect(boundsCentre(OFF_CENTRE)).toEqual([3, 6, 8]);
  });

  it('reports half the diagonal', () => {
    expect(boundsRadius(BOX)).toBeCloseTo(Math.sqrt(12) / 2, 6);
  });

  it('never reports a zero radius, so a degenerate scene still gets a camera', () => {
    expect(boundsRadius({ min: [0, 0, 0], max: [0, 0, 0] })).toBe(1);
  });
});

describe('fitToBounds', () => {
  it('always looks at the centre of the box', () => {
    for (const preset of ['iso', 'top', 'front', 'side'] as const) {
      expect(fitToBounds(OFF_CENTRE, preset).target).toEqual([3, 6, 8]);
    }
  });

  it('puts top straight above on z, with y up so north reads level', () => {
    const pose = fitToBounds(BOX, 'top');
    expect(pose.position[0]).toBeCloseTo(0, 6);
    expect(pose.position[1]).toBeCloseTo(0, 6);
    expect(pose.position[2]).toBeGreaterThan(0);
    expect(pose.up).toEqual([0, 1, 0]);
  });

  it('puts front on -y and side on +x, both with z up', () => {
    expect(fitToBounds(BOX, 'front').position[1]).toBeLessThan(0);
    expect(fitToBounds(BOX, 'front').up).toEqual([0, 0, 1]);
    expect(fitToBounds(BOX, 'side').position[0]).toBeGreaterThan(0);
  });

  it('places iso off all three axes', () => {
    const pose = fitToBounds(BOX, 'iso');
    expect(pose.position.every((c) => Math.abs(c) > 0.1)).toBe(true);
  });

  it('pulls back further on a narrow canvas, where the horizontal fov is the binding one', () => {
    const wide = fitToBounds(BOX, 'front', 42, 2);
    const narrow = fitToBounds(BOX, 'front', 42, 0.5);
    expect(Math.abs(narrow.position[1])).toBeGreaterThan(Math.abs(wide.position[1]));
  });

  it('leaves the whole radius inside the vertical field of view', () => {
    const pose = fitToBounds(BOX, 'front', 42, 1);
    const distance = Math.hypot(...pose.position.map((c, i) => c - pose.target[i]));
    expect(distance).toBeGreaterThan(boundsRadius(BOX));
  });
});

/**
 * `fitPoints` is the fit that made the fold fill the canvas. The properties worth pinning are
 * exactness (the extreme point lands just inside the frustum, not at a third of it) and that a
 * flat figure is no longer fitted as if it were a cube.
 */
describe('fitPoints', () => {
  const FOV = 42;
  const tanV = Math.tan((FOV * Math.PI) / 360);
  /**
   * How much of the frame a point uses on the binding screen axis, from the `front` preset
   * (which looks along +y with z screen-up, so depth is the y gap, x is across, z is up).
   * 1 = exactly on the frustum edge.
   */
  const frameUse = (
    pose: ReturnType<typeof fitPoints>,
    point: readonly number[],
    aspect: number,
  ) => {
    const depth = Math.abs(pose.position[1] - point[1]);
    const up = Math.abs(point[2] - pose.target[2]) / (depth * tanV);
    const across = Math.abs(point[0] - pose.target[0]) / (depth * tanV * aspect);
    return Math.max(up, across);
  };

  it('puts the extreme point just inside the frustum, not a third of the way in', () => {
    // A flat, wide figure: the case a box-diagonal radius gets most wrong.
    const flat: Bounds3 = { min: [-1, -1, -0.25], max: [1, 1, 0.25] };
    const positions = new Float32Array([-1, -1, -0.25, 1, 1, 0.25, 0, 0, 0.25]);
    const corners = [
      [-1, -1, -0.25],
      [1, 1, 0.25],
      [0, 0, 0.25],
    ];
    const worst = (pose: ReturnType<typeof fitPoints>) =>
      Math.max(...corners.map((point) => frameUse(pose, point, 1)));
    // Every point inside the frame, and the outermost one right at its edge.
    expect(worst(fitPoints([{ positions }], flat, 'front', FOV, 1))).toBeGreaterThan(0.85);
    expect(worst(fitPoints([{ positions }], flat, 'front', FOV, 1))).toBeLessThanOrEqual(1);
    // And it sits closer than the box-diagonal fit, which pads for a depth the figure has not
    // got — that padding is what left the fold at a third of the canvas.
    expect(Math.abs(fitPoints([{ positions }], flat, 'front', FOV, 1).position[1])).toBeLessThan(
      Math.abs(fitToBounds(flat, 'front', FOV, 1).position[1]),
    );
  });

  it('accounts for a point radius, so a sphere is not clipped at its edge', () => {
    const bounds: Bounds3 = { min: [-1, -1, -1], max: [1, 1, 1] };
    const positions = new Float32Array([0, 0, 1]);
    const bare = fitPoints([{ positions }], bounds, 'front', FOV, 1);
    const fat = fitPoints([{ positions, radii: new Float32Array([0.5]) }], bounds, 'front', FOV, 1);
    expect(Math.abs(fat.position[1])).toBeGreaterThan(Math.abs(bare.position[1]));
  });

  it('pulls back further on a narrow canvas, where the horizontal fov is the binding one', () => {
    const bounds: Bounds3 = { min: [-1, -1, -1], max: [1, 1, 1] };
    const positions = new Float32Array([-1, 0, 0, 1, 0, 0]);
    const wide = fitPoints([{ positions }], bounds, 'front', FOV, 2);
    const narrow = fitPoints([{ positions }], bounds, 'front', FOV, 0.5);
    expect(Math.abs(narrow.position[1])).toBeGreaterThan(Math.abs(wide.position[1]));
  });

  it('keeps the preset up vector, so OrbitControls still orbits about the declared axis', () => {
    const bounds: Bounds3 = { min: [-1, -1, -1], max: [1, 1, 1] };
    const positions = new Float32Array([1, 1, 1]);
    expect(fitPoints([{ positions }], bounds, 'iso', FOV, 1).up).toEqual([0, 0, 1]);
    expect(fitPoints([{ positions }], bounds, 'top', FOV, 1).up).toEqual([0, 1, 0]);
  });

  it('falls back to the box fit when there are no points', () => {
    const bounds: Bounds3 = { min: [-1, -1, -1], max: [1, 1, 1] };
    expect(fitPoints([{ positions: new Float32Array(0) }], bounds, 'front', FOV, 1)).toEqual(
      fitToBounds(bounds, 'front', FOV, 1),
    );
  });
});

describe('poseDistance', () => {
  const at = (x: number): Parameters<typeof poseDistance>[0] => ({
    position: [x, 0, 4],
    target: [0, 0, 0],
    up: [0, 0, 1],
  });

  it('is zero for the same pose, so an echoed pose is never re-applied', () => {
    expect(poseDistance(at(1), at(1))).toBe(0);
  });

  it('is the largest single-component difference across all nine numbers', () => {
    expect(poseDistance(at(0), at(0.25))).toBeCloseTo(0.25);
    expect(
      poseDistance(
        { position: [0, 0, 0], target: [0, 0, 0], up: [0, 0, 1] },
        { position: [0, 0, 0], target: [0, 3, 0], up: [0, 0, 1] },
      ),
    ).toBeCloseTo(3);
  });

  it('sees a change in `up` alone — a preset switch that keeps the distance', () => {
    expect(
      poseDistance(
        { position: [0, 0, 4], target: [0, 0, 0], up: [0, 0, 1] },
        { position: [0, 0, 4], target: [0, 0, 0], up: [0, 1, 0] },
      ),
    ).toBeCloseTo(1);
  });
});
