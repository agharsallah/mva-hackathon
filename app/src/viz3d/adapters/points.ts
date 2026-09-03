/** `points` -> one instanced sphere per datum. The simplest kind, and the reference one. */

import type { Adapter, GeometryBuffers, Scene3D } from '../spec/types';
import { boundsOf, datumColors, linkLines, normaliser, tilePickTable } from './normalise';

type PointsScene = Extract<Scene3D, { kind: 'points' }>;

/** Sphere radius in unit-box units when the scene does not state one. */
const DEFAULT_POINT_RADIUS = 0.035;

export const pointsGeometry: Adapter<PointsScene> = (scene): GeometryBuffers => {
  const datums = scene.points;
  const unit = normaliser(boundsOf(datums.map((d) => d.at)));
  const positions = new Float32Array(datums.length * 3);
  const radii = new Float32Array(datums.length);
  const base = scene.radius === undefined ? DEFAULT_POINT_RADIUS : unit.toUnitLength(scene.radius);
  datums.forEach((datum, index) => {
    positions.set(unit.toUnit(datum.at), index * 3);
    radii[index] = base * (datum.size ?? 1);
  });
  return {
    kind: 'points',
    draw: 'instances',
    positions,
    colors: datumColors(datums, scene.color),
    radii,
    pickTable: tilePickTable(datums),
    links: linkLines(scene, datums, unit),
    bounds: unit.bounds,
    extent: unit.extent,
  };
};
