/**
 * The ONLY module in the repo that names `three`.
 *
 * Two things are bought here. First, placement: `import('three')` is a dynamic import, so
 * rolldown emits three as its own chunk and a visitor who never opens a 3D exhibit downloads
 * none of it. Two different numbers get quoted for "how big is three", so both, measured on
 * this checkout (three 0.185.1) on 2026-09-03:
 *
 *   - **the emitted chunk** `dist/assets/three.module-*.js` — 529.85 kB raw / 131.78 kB gzip.
 *     This is what a reader who opens a 3D exhibit actually downloads, and the only number
 *     that describes this file's effect.
 *   - the library's own prebuilt `three/build/three.module.min.js` — 365.55 kB raw / 87.12 kB gzip.
 *     Never fetched by this app; it is the figure three's release notes quote.
 *
 * The chunk is the larger of the two because rolldown bundles three's ESM sources (plus the
 * `OrbitControls` addon's imports) and minifies them itself rather than shipping that prebuilt
 * file. It is the same mechanism
 * `src/components/Plot.tsx` uses for Plotly's ~4 MB chunk, and the reason
 * `tools/bundle-budget.mjs` can assert `/three/i` never appears in the initial payload.
 *
 * Second, a seam. `ThreeApi` is deliberately the *subset* of three this module uses, not
 * `typeof import('three')`: it is the list of constructors `core/scene.ts` and `core/viewer.ts`
 * are allowed to reach for, and it is small enough that a test can hand over a fake with spy
 * constructors — exactly the `PlotlyApi` pattern in `Plot.tsx`. Adding a three feature means
 * adding a line here, which is a visible decision rather than a silent dependency.
 *
 * `import type * as Three` is erased (`verbatimModuleSyntax: true`), so the real types are
 * available at author time at zero runtime cost.
 */

import type * as Three from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export interface ThreeApi {
  Scene: typeof Three.Scene;
  Group: typeof Three.Group;
  Object3D: typeof Three.Object3D;
  PerspectiveCamera: typeof Three.PerspectiveCamera;
  WebGLRenderer: typeof Three.WebGLRenderer;
  Color: typeof Three.Color;
  Vector2: typeof Three.Vector2;
  Vector3: typeof Three.Vector3;
  Matrix4: typeof Three.Matrix4;
  Raycaster: typeof Three.Raycaster;
  BufferGeometry: typeof Three.BufferGeometry;
  BufferAttribute: typeof Three.BufferAttribute;
  SphereGeometry: typeof Three.SphereGeometry;
  TorusGeometry: typeof Three.TorusGeometry;
  InstancedMesh: typeof Three.InstancedMesh;
  Mesh: typeof Three.Mesh;
  LineSegments: typeof Three.LineSegments;
  MeshStandardMaterial: typeof Three.MeshStandardMaterial;
  MeshBasicMaterial: typeof Three.MeshBasicMaterial;
  LineBasicMaterial: typeof Three.LineBasicMaterial;
  HemisphereLight: typeof Three.HemisphereLight;
  DirectionalLight: typeof Three.DirectionalLight;
  SRGBColorSpace: typeof Three.SRGBColorSpace;
  ACESFilmicToneMapping: typeof Three.ACESFilmicToneMapping;
  DoubleSide: typeof Three.DoubleSide;
}

export type OrbitControlsCtor = typeof OrbitControls;

let threePromise: Promise<ThreeApi> | null = null;
let controlsPromise: Promise<OrbitControlsCtor> | null = null;

/** Load three once, on the first 3D mount. Cached, so a second exhibit pays nothing. */
export function loadThree(): Promise<ThreeApi> {
  // The namespace is narrowed to `ThreeApi` field by field rather than passed through, so
  // the object the rest of `core/` sees is exactly the declared subset — a three export used
  // without being declared above is then a type error, not a surprise at runtime.
  threePromise ??= import('three').then((m): ThreeApi => ({
    Scene: m.Scene,
    Group: m.Group,
    Object3D: m.Object3D,
    PerspectiveCamera: m.PerspectiveCamera,
    WebGLRenderer: m.WebGLRenderer,
    Color: m.Color,
    Vector2: m.Vector2,
    Vector3: m.Vector3,
    Matrix4: m.Matrix4,
    Raycaster: m.Raycaster,
    BufferGeometry: m.BufferGeometry,
    BufferAttribute: m.BufferAttribute,
    SphereGeometry: m.SphereGeometry,
    TorusGeometry: m.TorusGeometry,
    InstancedMesh: m.InstancedMesh,
    Mesh: m.Mesh,
    LineSegments: m.LineSegments,
    MeshStandardMaterial: m.MeshStandardMaterial,
    MeshBasicMaterial: m.MeshBasicMaterial,
    LineBasicMaterial: m.LineBasicMaterial,
    HemisphereLight: m.HemisphereLight,
    DirectionalLight: m.DirectionalLight,
    SRGBColorSpace: m.SRGBColorSpace,
    ACESFilmicToneMapping: m.ACESFilmicToneMapping,
    DoubleSide: m.DoubleSide,
  }));
  return threePromise;
}

/**
 * `OrbitControls` ships as an addon, not part of the core bundle, and is cached the same way.
 * It is loaded beside three rather than inside it so a future non-interactive scene (a
 * thumbnail, a print figure) can skip it.
 */
function loadOrbitControls(): Promise<OrbitControlsCtor> {
  controlsPromise ??= import('three/addons/controls/OrbitControls.js').then((m) => m.OrbitControls);
  return controlsPromise;
}

/** Both halves, in one await — what `components/Viz3dCanvas.tsx` actually calls. */
export interface ThreeBundle {
  three: ThreeApi;
  OrbitControls: OrbitControlsCtor;
}

export function loadThreeBundle(): Promise<ThreeBundle> {
  return Promise.all([loadThree(), loadOrbitControls()]).then(([three, controls]) => ({
    three,
    OrbitControls: controls,
  }));
}
