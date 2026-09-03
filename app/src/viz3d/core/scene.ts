/**
 * `GeometryBuffers` + the palette -> a three scene graph. The only file that constructs
 * three objects; everything upstream of it is pure data.
 *
 * Rendering choices, and why:
 *   - **Soft hemisphere + one directional light**, `MeshStandardMaterial`. A physically-lit
 *     surface makes height legible without a colour change, which matters because colour is
 *     already carrying a data channel.
 *   - **`InstancedMesh` for every sphere.** One draw call for thousands of points; a per-point
 *     `Mesh` would not survive a real point cloud.
 *   - **Vertex colours are linearised on the way in.** three parses a `#rrggbb` string as sRGB
 *     and converts to its linear working space; a buffer attribute is assumed to be *already*
 *     linear. Without `linearizeColors` a ramped mesh comes out visibly paler than the
 *     `C.grid` lines drawn beside it.
 *   - **Highlight is a billboarded ring**, not a colour swap: the datum keeps the colour its
 *     encoding gave it, so a selection never lies about the data. The ring geometry is **one
 *     cached unit torus**, scaled per mesh: allocating a `TorusGeometry` per highlighted id
 *     leaked one GPU buffer per pick for the life of the mount, because `Group.clear()`
 *     detaches children without disposing anything.
 */

import { C, TONE_MARK } from '../../lib/palette';
import type { Bounds3, GeometryBuffers, Vec3 } from '../spec/types';
import { linearizeColors } from './colorRamp';
import type { ThreeApi } from './loadThree';
import type { PickSource } from './pick';

type Obj = InstanceType<ThreeApi['Object3D']>;
type Group = InstanceType<ThreeApi['Group']>;
type Camera = InstanceType<ThreeApi['PerspectiveCamera']>;
type Disposable = { dispose(): void };

export interface PickTarget {
  object: Obj;
  source: PickSource;
}

export interface SceneGraph {
  root: Group;
  /** What the raycaster tests, and which pick table each hit resolves against. */
  targets: readonly PickTarget[];
  /** Unit-space centre per datum id — the highlight ring and the link labels sit here. */
  centres: ReadonlyMap<string, Vec3>;
  setHighlight(ids: readonly string[]): void;
  /** Per frame: keeps the highlight rings facing the camera. */
  update(camera: Camera): void;
  dispose(): void;
}

const SPHERE_SEGMENTS = 18;
const SPHERE_RINGS = 12;
/** Highlight ring size relative to the datum it marks. */
const RING_SCALE = 2.6;
/** Tube thickness of the highlight ring, as a fraction of its radius. */
const RING_THICKNESS = 0.14;

export function buildSceneGraph(three: ThreeApi, buffers: GeometryBuffers): SceneGraph {
  const root = new three.Group();
  const junk: Disposable[] = [];
  const targets: PickTarget[] = [];
  const rings: Obj[] = [];

  const keep = <T extends Disposable>(thing: T): T => {
    junk.push(thing);
    return thing;
  };

  root.add(...lights(three));
  root.add(keepAll(junk, axesHelper(three, buffers.bounds)));

  if (buffers.draw === 'mesh') {
    const mesh = solidMesh(three, buffers, keep);
    root.add(mesh);
    targets.push({ object: mesh, source: 'primary' });
  } else {
    const spheres = instanced(
      three,
      { positions: buffers.positions, colors: buffers.colors, radii: buffers.radii },
      keep,
    );
    if (spheres) {
      root.add(spheres);
      targets.push({ object: spheres, source: 'primary' });
    }
  }

  if (buffers.instances) {
    const spheres = instanced(three, buffers.instances, keep);
    if (spheres) {
      root.add(spheres);
      targets.push({ object: spheres, source: 'instances' });
    }
  }

  if (buffers.links) {
    const geometry = keep(new three.BufferGeometry());
    geometry.setAttribute('position', new three.BufferAttribute(buffers.links.positions, 3));
    geometry.setAttribute(
      'color',
      new three.BufferAttribute(linearizeColors(Float32Array.from(buffers.links.colors)), 3),
    );
    const material = keep(new three.LineBasicMaterial({ vertexColors: true, transparent: true }));
    root.add(new three.LineSegments(geometry, material));
  }

  const centres = datumCentres(buffers);
  const highlightGroup = new three.Group();
  root.add(highlightGroup);
  const ringMaterial = keep(
    new three.MeshBasicMaterial({
      color: new three.Color(TONE_MARK.decision),
      transparent: true,
      opacity: 0.9,
    }),
  );
  // One geometry for every ring the graph will ever draw, at radius 1. A per-id size becomes a
  // uniform `scale`, so a pick allocates a `Mesh` (a plain JS object with no GPU buffer) and
  // nothing needs disposing when the highlight changes.
  const ringGeometry = keep(new three.TorusGeometry(1, RING_THICKNESS, 10, 40));

  function setHighlight(ids: readonly string[]): void {
    highlightGroup.clear();
    rings.length = 0;
    for (const id of ids) {
      const centre = centres.get(id);
      if (!centre) continue;
      const radius = radiusFor(buffers, id) * RING_SCALE;
      const ring = new three.Mesh(ringGeometry, ringMaterial);
      ring.scale.setScalar(radius);
      ring.position.set(centre[0], centre[1], centre[2]);
      highlightGroup.add(ring);
      rings.push(ring);
    }
  }

  return {
    root,
    targets,
    centres,
    setHighlight,
    update(camera) {
      for (const ring of rings) ring.quaternion.copy(camera.quaternion);
    },
    dispose() {
      // The rings share `ringGeometry`/`ringMaterial`, both in `junk`, so clearing the group
      // is enough: there is no per-ring resource left to free.
      highlightGroup.clear();
      rings.length = 0;
      for (const thing of junk) thing.dispose();
      junk.length = 0;
      root.clear();
    },
  };
}

function keepAll(junk: Disposable[], parts: { object: Obj; junk: Disposable[] }): Obj {
  junk.push(...parts.junk);
  return parts.object;
}

/** Soft sky/ground fill plus one shaping key light. Both neutral — colour is data here. */
function lights(three: ThreeApi): Obj[] {
  const hemisphere = new three.HemisphereLight(
    new three.Color(C.ink),
    new three.Color(C.paper),
    1.15,
  );
  const key = new three.DirectionalLight(new three.Color(C.onFill), 1.5);
  key.position.set(2.5, -3, 4);
  const rim = new three.DirectionalLight(new three.Color(C.machinery), 0.35);
  rim.position.set(-3, 2, -1.5);
  return [hemisphere, key, rim];
}

function solidMesh(
  three: ThreeApi,
  buffers: GeometryBuffers,
  keep: <T extends Disposable>(t: T) => T,
): Obj {
  const geometry = keep(new three.BufferGeometry());
  geometry.setAttribute('position', new three.BufferAttribute(buffers.positions, 3));
  geometry.setAttribute(
    'color',
    new three.BufferAttribute(linearizeColors(Float32Array.from(buffers.colors)), 3),
  );
  if (buffers.normals) {
    geometry.setAttribute('normal', new three.BufferAttribute(buffers.normals, 3));
  }
  if (buffers.indices) geometry.setIndex(new three.BufferAttribute(buffers.indices, 1));
  if (!buffers.normals) geometry.computeVertexNormals();
  const material = keep(
    new three.MeshStandardMaterial({
      vertexColors: true,
      roughness: 0.55,
      metalness: 0.08,
      side: three.DoubleSide,
    }),
  );
  return new three.Mesh(geometry, material);
}

function instanced(
  three: ThreeApi,
  set: { positions: Float32Array; colors: Float32Array; radii?: Float32Array },
  keep: <T extends Disposable>(t: T) => T,
): Obj | null {
  const count = Math.floor(set.positions.length / 3);
  if (count === 0) return null;
  const geometry = keep(new three.SphereGeometry(1, SPHERE_SEGMENTS, SPHERE_RINGS));
  const material = keep(new three.MeshStandardMaterial({ roughness: 0.4, metalness: 0.1 }));
  const mesh = new three.InstancedMesh(geometry, material, count);
  const matrix = new three.Matrix4();
  const color = new three.Color();
  for (let i = 0; i < count; i++) {
    const radius = set.radii?.[i] ?? 0.03;
    matrix.makeScale(radius, radius, radius);
    matrix.setPosition(set.positions[i * 3], set.positions[i * 3 + 1], set.positions[i * 3 + 2]);
    mesh.setMatrixAt(i, matrix);
    // setRGB with SRGBColorSpace does the sRGB -> linear conversion three applies to a hex
    // string, so an instance colour and a `new Color(C.grid)` line agree on screen.
    color.setRGB(
      set.colors[i * 3],
      set.colors[i * 3 + 1],
      set.colors[i * 3 + 2],
      three.SRGBColorSpace,
    );
    mesh.setColorAt(i, color);
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  keep(mesh);
  return mesh;
}

/** The twelve edges of the data box, in the app's gridline grey. Subtle on purpose. */
function axesHelper(three: ThreeApi, bounds: Bounds3): { object: Obj; junk: Disposable[] } {
  const [x0, y0, z0] = bounds.min;
  const [x1, y1, z1] = bounds.max;
  const corners: Vec3[] = [
    [x0, y0, z0],
    [x1, y0, z0],
    [x1, y1, z0],
    [x0, y1, z0],
    [x0, y0, z1],
    [x1, y0, z1],
    [x1, y1, z1],
    [x0, y1, z1],
  ];
  const edges = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 0],
    [4, 5],
    [5, 6],
    [6, 7],
    [7, 4],
    [0, 4],
    [1, 5],
    [2, 6],
    [3, 7],
  ];
  const positions = new Float32Array(edges.length * 6);
  edges.forEach(([a, b], index) => {
    positions.set(corners[a], index * 6);
    positions.set(corners[b], index * 6 + 3);
  });
  const geometry = new three.BufferGeometry();
  geometry.setAttribute('position', new three.BufferAttribute(positions, 3));
  const material = new three.LineBasicMaterial({
    color: new three.Color(C.grid),
    transparent: true,
    opacity: 0.55,
  });
  return { object: new three.LineSegments(geometry, material), junk: [geometry, material] };
}

/**
 * Unit-space centre per datum id. Instance positions are exact; a mesh datum's centre is the
 * mean of the vertices its `pickTable` range owns, which works for any future kind without
 * the adapter having to report centres separately.
 */
function datumCentres(buffers: GeometryBuffers): Map<string, Vec3> {
  const out = new Map<string, Vec3>();
  const primary = buffers.draw === 'instances' ? buffers.positions : null;
  for (const range of buffers.pickTable) {
    out.set(range.id, primary ? readVec(primary, range.from) : mean(buffers.positions, range));
  }
  if (buffers.instances) {
    for (const range of buffers.instances.pickTable) {
      out.set(range.id, readVec(buffers.instances.positions, range.from));
    }
  }
  return out;
}

const readVec = (buffer: Float32Array, index: number): Vec3 => [
  buffer[index * 3],
  buffer[index * 3 + 1],
  buffer[index * 3 + 2],
];

function mean(buffer: Float32Array, range: { from: number; to: number }): Vec3 {
  const sum: [number, number, number] = [0, 0, 0];
  const count = Math.max(range.to - range.from, 1);
  for (let i = range.from; i < range.to; i++) {
    sum[0] += buffer[i * 3];
    sum[1] += buffer[i * 3 + 1];
    sum[2] += buffer[i * 3 + 2];
  }
  return [sum[0] / count, sum[1] / count, sum[2] / count];
}

/** Ring size: the datum's own sphere radius where it has one, else a fraction of the box. */
function radiusFor(buffers: GeometryBuffers, id: string): number {
  const instances = buffers.instances;
  if (instances) {
    const index = instances.pickTable.find((range) => range.id === id)?.from;
    if (index !== undefined) return instances.radii[index] || 0.04;
  }
  if (buffers.draw === 'instances' && buffers.radii) {
    const index = buffers.pickTable.find((range) => range.id === id)?.from;
    if (index !== undefined) return buffers.radii[index] || 0.04;
  }
  return 0.05;
}
