/**
 * The imperative half of the canvas: renderer, camera, controls, the render loop, picking,
 * and teardown. React never enters this file, and this file never enters React — the only
 * things crossing are the `Viewer` methods and the two callbacks.
 *
 * That split is deliberate. Hover fires at pointer rate and the loop at frame rate; routing
 * either through `useState` would re-render the tree ~60×/s. So the loop owns its own state
 * and the link labels are plain DOM nodes inside an overlay element the component hands over.
 *
 * Renderer settings that are not defaults, and why:
 *   - `alpha: true` + `setClearAlpha(0)`: the page background shows through, matching
 *     `plotLayout.ts`'s `paper_bgcolor: 'rgba(0,0,0,0)'`.
 *   - `outputColorSpace = SRGBColorSpace`: makes a palette hex come out on screen as the
 *     number the DOM half of the palette paints.
 *   - `ACESFilmicToneMapping` at a gentle exposure: keeps the key light's highlight from
 *     clipping to white on a saturated ramp colour.
 *   - pixel ratio capped at 2: a 3× phone would otherwise render 9 megapixels of spheres.
 */

import { C } from '../../lib/palette';
import type { CameraPose3D, CameraPreset, GeometryBuffers, Vec3 } from '../spec/types';
import { fitPoints, type PointSet, poseDistance } from './camera';
import type { ThreeBundle } from './loadThree';
import type { PickSource } from './pick';
import { buildSceneGraph, type SceneGraph } from './scene';

export interface PickHit {
  source: PickSource;
  index: number;
}

export interface ViewerOptions {
  canvas: HTMLCanvasElement;
  /** Element the link labels are written into, positioned relative to the canvas. */
  overlay?: HTMLElement | null;
  autoRotate?: boolean;
  onPick?: (hit: PickHit | null) => void;
  /** Hover, in client coordinates so an HTML tooltip can be placed at the pointer. */
  onHover?: (hit: PickHit | null, at: { x: number; y: number }) => void;
  /**
   * The camera moved. Throttled to {@link POSE_REPORT_MS} and gated on
   * {@link POSE_EPSILON}, because OrbitControls damps: the camera keeps creeping for about a
   * second after the reader lets go, and reporting every frame of that would drive a React
   * state update at frame rate — the one thing this file exists to avoid.
   */
  onPoseChange?: (pose: CameraPose3D) => void;
}

/** How `setGeometry` treats the camera. See `Viewer.setGeometry`. */
export interface SetGeometryOptions {
  /**
   * Force (`true`) or forbid (`false`) a camera refit. Default: refit only when the new
   * buffers describe a different data box — see the note on `setGeometry`.
   */
  refit?: boolean;
}

export interface Viewer {
  /**
   * Swap the geometry. **The camera is only refitted when the scene's box changed** (a
   * different residue window, a different gene, a filter that drops datums). A recolour, a
   * highlight or a de-emphasis pass produces the same box, and refitting on those threw away
   * the reader's orbit on every chip toggle. Pass `{ refit: true }` to force one.
   */
  setGeometry(buffers: GeometryBuffers, options?: SetGeometryOptions): void;
  setHighlight(ids: readonly string[]): void;
  setView(preset: CameraPreset): void;
  /** Where the camera is now, in the normalised unit box. */
  getPose(): CameraPose3D;
  /**
   * Put the camera exactly here. Used by the controlled `pose` prop, so two canvases can
   * share one orbit; the pose is *not* echoed back through `onPoseChange`.
   */
  setPose(pose: CameraPose3D): void;
  setAutoRotate(on: boolean): void;
  resize(): void;
  /**
   * Start or stop the render loop.
   *
   * A page may now mount several canvases at once (the side-by-side protein comparison mounts
   * two beside the single-gene explorer), and every one of them holds its own WebGL context
   * and its own `requestAnimationFrame` chain. Pausing the ones nobody is looking at is what
   * keeps that page affordable — measured on headless software WebGL, three simultaneous
   * always-on contexts starved the renderer badly enough that navigating away from the page
   * timed out. Idempotent; a paused viewer still answers `renderOnce()`.
   */
  setRunning(on: boolean): void;
  /** Renders one frame outside the loop — used by the tests, which have no rAF budget. */
  renderOnce(): void;
  dispose(): void;
}

const FOV = 42;
const DRAG_SLOP_PX = 4;
const MAX_PIXEL_RATIO = 2;
/** Smallest camera move worth reporting, in unit-box units. */
const POSE_EPSILON = 1e-4;
/** Floor on the interval between two pose reports, in ms (~11 Hz, not 60). */
const POSE_REPORT_MS = 90;

export function createViewer(
  { three, OrbitControls }: ThreeBundle,
  options: ViewerOptions,
): Viewer {
  const { canvas } = options;
  const renderer = new three.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio ?? 1, MAX_PIXEL_RATIO));
  renderer.setClearAlpha(0);
  renderer.outputColorSpace = three.SRGBColorSpace;
  renderer.toneMapping = three.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new three.Scene();
  const camera = new three.PerspectiveCamera(FOV, 1, 0.01, 200);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotateSpeed = 0.55;
  controls.autoRotate = options.autoRotate ?? false;

  const raycaster = new three.Raycaster();
  const pointer = new three.Vector2();
  const projected = new three.Vector3();

  let graph: SceneGraph | null = null;
  let buffers: GeometryBuffers | null = null;
  let fitted: string | null = null;
  let preset: CameraPreset = 'iso';
  let frame = 0;
  let disposed = false;
  let downAt: { x: number; y: number } | null = null;
  let running = true;
  let reported: CameraPose3D | null = null;
  let reportedAt = 0;
  const labels: HTMLElement[] = [];

  function aspect(): number {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    return w / h;
  }

  /**
   * Everything the fit has to keep on screen: the drawn geometry, the instanced spheres (with
   * their radii), and the eight corners of the axes box — `core/scene.ts` draws that box, and
   * for a `protein` scene it is the *outermost* thing in the picture (the tube's vertices all
   * sit inside the residue extent, the box is on it), so leaving it out clipped the frame.
   */
  function pointSets(next: GeometryBuffers): PointSet[] {
    const sets: PointSet[] = [
      { positions: next.positions, radii: next.radii },
      { positions: boxCorners(next.bounds) },
    ];
    if (next.instances) {
      sets.push({ positions: next.instances.positions, radii: next.instances.radii });
    }
    return sets;
  }

  function applyView(): void {
    if (!buffers) return;
    const pose = fitPoints(pointSets(buffers), buffers.bounds, preset, FOV, aspect());
    camera.up.set(pose.up[0], pose.up[1], pose.up[2]);
    camera.position.set(pose.position[0], pose.position[1], pose.position[2]);
    controls.target.set(pose.target[0], pose.target[1], pose.target[2]);
    controls.update();
  }

  function resize(): void {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function hitAt(event: PointerEvent | MouseEvent): PickHit | null {
    if (!graph || graph.targets.length === 0) return null;
    const box = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - box.left) / box.width) * 2 - 1;
    pointer.y = -((event.clientY - box.top) / box.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(
      graph.targets.map((t) => t.object),
      false,
    );
    for (const hit of hits) {
      const target = graph.targets.find((t) => t.object === hit.object);
      if (!target) continue;
      const index = hit.instanceId ?? hit.face?.a;
      if (index !== undefined) return { source: target.source, index };
    }
    return null;
  }

  function positionLabels(): void {
    if (!options.overlay || !buffers?.links) return;
    buffers.links.labels.forEach((label, index) => {
      const node = labels[index];
      if (!node) return;
      const at = toScreen(label.at);
      node.style.transform = `translate(-50%, -50%) translate(${at.x}px, ${at.y}px)`;
      node.style.opacity = at.behind ? '0' : '1';
    });
  }

  function toScreen(point: Vec3): { x: number; y: number; behind: boolean } {
    projected.set(point[0], point[1], point[2]).project(camera);
    return {
      x: ((projected.x + 1) / 2) * (canvas.clientWidth || 1),
      y: ((1 - projected.y) / 2) * (canvas.clientHeight || 1),
      behind: projected.z > 1,
    };
  }

  function currentPose(): CameraPose3D {
    return {
      position: [camera.position.x, camera.position.y, camera.position.z],
      target: [controls.target.x, controls.target.y, controls.target.z],
      up: [camera.up.x, camera.up.y, camera.up.z],
    };
  }

  /** Report the camera at most every {@link POSE_REPORT_MS}, and only if it actually moved. */
  function reportPose(): void {
    if (!options.onPoseChange) return;
    const now = Date.now();
    if (now - reportedAt < POSE_REPORT_MS) return;
    const pose = currentPose();
    if (reported && poseDistance(pose, reported) < POSE_EPSILON) return;
    reported = pose;
    reportedAt = now;
    options.onPoseChange(pose);
  }

  function renderOnce(): void {
    if (disposed) return;
    controls.update();
    if (graph) graph.update(camera);
    positionLabels();
    renderer.render(scene, camera);
    reportPose();
  }

  function loop(): void {
    if (disposed || !running) return;
    renderOnce();
    frame = requestAnimationFrame(loop);
  }

  const onPointerDown = (event: PointerEvent): void => {
    downAt = { x: event.clientX, y: event.clientY };
  };
  const onPointerUp = (event: PointerEvent): void => {
    const start = downAt;
    downAt = null;
    if (!start) return;
    const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
    if (moved > DRAG_SLOP_PX) return;
    options.onPick?.(hitAt(event));
  };
  const onPointerMove = (event: PointerEvent): void => {
    options.onHover?.(hitAt(event), { x: event.clientX, y: event.clientY });
  };
  const onPointerLeave = (): void => options.onHover?.(null, { x: 0, y: 0 });

  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerleave', onPointerLeave);

  resize();
  frame = requestAnimationFrame(loop);

  return {
    setGeometry(next, geometryOptions) {
      graph?.dispose();
      if (graph) scene.remove(graph.root);
      buffers = next;
      graph = buildSceneGraph(three, next);
      scene.add(graph.root);
      rebuildLabels(options.overlay ?? null, labels, next);
      const box = boxKey(next);
      const changed = box !== fitted;
      fitted = box;
      if (geometryOptions?.refit ?? changed) applyView();
    },
    setHighlight(ids) {
      graph?.setHighlight(ids);
    },
    setView(next) {
      preset = next;
      applyView();
    },
    getPose: currentPose,
    setPose(pose) {
      camera.up.set(pose.up[0], pose.up[1], pose.up[2]);
      camera.position.set(pose.position[0], pose.position[1], pose.position[2]);
      controls.target.set(pose.target[0], pose.target[1], pose.target[2]);
      controls.update();
      // Adopt it as the last reported pose: a pose that came *in* must not go straight back
      // out, or two synced canvases would trade updates forever.
      reported = pose;
    },
    setAutoRotate(on) {
      controls.autoRotate = on;
    },
    setRunning(on) {
      if (on === running) return;
      running = on;
      if (on) frame = requestAnimationFrame(loop);
      else cancelAnimationFrame(frame);
    },
    resize() {
      // Renderer size + projection matrix only. A refit here would snap the camera back to
      // the preset every time the layout reflowed (the `ResizeObserver` fires on mount and on
      // every panel resize), which is the same orbit-destroying bug as refitting on recolour.
      resize();
    },
    renderOnce,
    dispose() {
      disposed = true;
      running = false;
      cancelAnimationFrame(frame);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerleave', onPointerLeave);
      for (const node of labels.splice(0)) node.remove();
      controls.dispose();
      graph?.dispose();
      graph = null;
      scene.clear();
      renderer.dispose();
    },
  };
}

/** The eight corners of a box, as one position buffer. */
function boxCorners(bounds: GeometryBuffers['bounds']): Float32Array {
  const out = new Float32Array(24);
  let at = 0;
  for (const x of [bounds.min[0], bounds.max[0]]) {
    for (const y of [bounds.min[1], bounds.max[1]]) {
      for (const z of [bounds.min[2], bounds.max[2]]) {
        out.set([x, y, z], at);
        at += 3;
      }
    }
  }
  return out;
}

/**
 * The identity of a scene's data box, to six decimals — what "the extent changed" means. Both
 * boxes are compared, because a `protein` scene's unit box is derived from its data extent and
 * a recolour leaves both untouched while a residue-window change moves both.
 */
function boxKey(buffers: GeometryBuffers): string {
  return [buffers.extent, buffers.bounds]
    .flatMap((box) => [...box.min, ...box.max])
    .map((n) => n.toFixed(6))
    .join(',');
}

/**
 * Link labels as plain DOM. They are re-created only when the geometry changes; the render
 * loop moves them with a transform, which never touches layout.
 */
function rebuildLabels(
  overlay: HTMLElement | null,
  labels: HTMLElement[],
  buffers: GeometryBuffers,
): void {
  for (const node of labels.splice(0)) node.remove();
  if (!overlay) return;
  for (const label of buffers.links?.labels ?? []) {
    const node = document.createElement('span');
    node.textContent = label.text;
    node.className = 'pointer-events-none absolute top-0 left-0 whitespace-nowrap text-micro';
    node.style.color = C.inkDim;
    overlay.appendChild(node);
    labels.push(node);
  }
}
