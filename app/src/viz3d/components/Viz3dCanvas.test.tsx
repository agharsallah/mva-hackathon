/**
 * The canvas smoke test, and the reason `core/capability.ts` and `core/loadThree.ts` are
 * separate one-export files: they are the only two seams a test has to replace to run the
 * whole 3D path — adapter, scene graph, viewer, render loop and teardown — in jsdom, which
 * has no WebGL at all.
 *
 * The fake `ThreeApi` below is the honest cost of the `PlotlyApi` pattern: it is exactly the
 * surface `loadThree.ts` declares, so anything `core/` reaches for that is not listed there
 * fails here loudly instead of silently at runtime.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DENSITY_SCALE } from '../../lib/palette';
import type { NumericEncoding, Scene3D } from '../spec/types';
import { Viz3dCanvas } from './Viz3dCanvas';

const spies = {
  render: vi.fn(),
  rendererDispose: vi.fn(),
  controlsDispose: vi.fn(),
  geometryDispose: vi.fn(),
  materialDispose: vi.fn(),
};
const state = { webgl: true };

class Vec {
  x = 0;
  y = 0;
  z = 0;
  set() {
    return this;
  }
  copy() {
    return this;
  }
  project() {
    return this;
  }
  setScalar() {
    return this;
  }
}
/** A `Vec` that actually stores what `set()` is given — the controlled-pose path reads it back. */
class LiveVec extends Vec {
  set(x = 0, y = 0, z = 0) {
    this.x = x;
    this.y = y;
    this.z = z;
    return this;
  }
}
class Obj {
  children: unknown[] = [];
  position = new LiveVec();
  quaternion = new Vec();
  scale = new Vec();
  add(...kids: unknown[]) {
    this.children.push(...kids);
    return this;
  }
  remove() {
    return this;
  }
  clear() {
    this.children = [];
    return this;
  }
}
class Geometry {
  setAttribute() {}
  setIndex() {}
  computeVertexNormals() {}
  dispose = spies.geometryDispose;
}
class Material {
  dispose = spies.materialDispose;
}
class Instanced extends Obj {
  instanceMatrix = { needsUpdate: false };
  instanceColor = { needsUpdate: false };
  setMatrixAt() {}
  setColorAt() {}
  dispose = spies.geometryDispose;
}
class Renderer {
  outputColorSpace = '';
  toneMapping = 0;
  toneMappingExposure = 1;
  setPixelRatio() {}
  setClearAlpha() {}
  setSize() {}
  render = spies.render;
  dispose = spies.rendererDispose;
}
/** Every camera the fake bundle builds, so a test can read where the viewer put it. */
const cameras: Camera[] = [];

class Camera extends Obj {
  aspect = 1;
  up = new LiveVec();
  constructor() {
    super();
    cameras.push(this);
  }
  updateProjectionMatrix() {}
}

class OrbitControls {
  enableDamping = false;
  dampingFactor = 0;
  autoRotate = false;
  autoRotateSpeed = 0;
  target = new LiveVec();
  update() {}
  dispose = spies.controlsDispose;
}

const fake = {
  Scene: Obj,
  Group: Obj,
  Object3D: Obj,
  PerspectiveCamera: Camera,
  WebGLRenderer: Renderer,
  Color: class {
    setRGB() {
      return this;
    }
  },
  Vector2: Vec,
  Vector3: LiveVec,
  Matrix4: class {
    makeScale() {
      return this;
    }
    setPosition() {
      return this;
    }
  },
  Raycaster: class {
    setFromCamera() {}
    intersectObjects() {
      return [];
    }
  },
  BufferGeometry: Geometry,
  BufferAttribute: class {},
  SphereGeometry: Geometry,
  TorusGeometry: Geometry,
  InstancedMesh: Instanced,
  Mesh: Obj,
  LineSegments: Obj,
  MeshStandardMaterial: Material,
  MeshBasicMaterial: Material,
  LineBasicMaterial: Material,
  HemisphereLight: Obj,
  DirectionalLight: Obj,
  SRGBColorSpace: 'srgb',
  ACESFilmicToneMapping: 1,
  DoubleSide: 2,
};

/**
 * The mock factories are hoisted above this module's body, so they may only *close over*
 * these bindings, never read them at hoist time — `fakeBundle` is a function declaration
 * (hoisted by JavaScript itself) and `state` is read when `hasWebGL()` is actually called.
 */
function fakeBundle() {
  return { three: fake, OrbitControls };
}

vi.mock('../core/capability', () => ({ hasWebGL: () => state.webgl }));
vi.mock('../core/loadThree', () => ({
  loadThreeBundle: () => Promise.resolve(fakeBundle()),
}));

const COLOR: NumericEncoding = {
  id: 'v',
  kind: 'numeric',
  label: 'value',
  field: 'value',
  scale: DENSITY_SCALE,
  lowMeans: 'low',
  highMeans: 'high',
};

const SCENE: Scene3D = {
  kind: 'points',
  title: 'Two bins',
  axes: {
    x: { label: 'megabase', unit: 'Mb' },
    y: { label: 'chromosome' },
    z: { label: 'calls', unit: 'count' },
  },
  color: COLOR,
  points: [
    { id: 'a', label: 'bin a', at: [0, 0, 1], value: 1 },
    { id: 'b', label: 'bin b', at: [1, 0, 9], value: 9 },
  ],
  links: [{ from: 'a', to: 'b', label: '1 Mb apart' }],
};

beforeEach(() => {
  state.webgl = true;
  for (const spy of Object.values(spies)) spy.mockClear();
});

afterEach(() => vi.clearAllMocks());

describe('with WebGL', () => {
  it('renders a named canvas and drives the render loop', async () => {
    render(<Viz3dCanvas scene={SCENE} />);
    const canvas = screen.getByRole('img');
    expect(canvas.tagName).toBe('CANVAS');
    expect(canvas.getAttribute('aria-label')).toContain('Two bins');
    await waitFor(() => expect(spies.render).toHaveBeenCalled());
  });

  it('disposes the renderer, the controls and every geometry on unmount', async () => {
    const view = render(<Viz3dCanvas scene={SCENE} />);
    await waitFor(() => expect(spies.render).toHaveBeenCalled());
    view.unmount();
    expect(spies.rendererDispose).toHaveBeenCalledTimes(1);
    expect(spies.controlsDispose).toHaveBeenCalledTimes(1);
    expect(spies.geometryDispose).toHaveBeenCalled();
    expect(spies.materialDispose).toHaveBeenCalled();
  });

  /**
   * The controlled camera. Two canvases in the side-by-side protein comparison share one
   * `CameraPose3D`, so both directions have to work — and the echo guard is what keeps them
   * from trading updates forever: a pose a canvas was *told* to adopt is never reported back.
   */
  it('reports the camera it fitted when nothing controls it', async () => {
    const onPose = vi.fn();
    render(<Viz3dCanvas scene={SCENE} onPose={onPose} />);
    await waitFor(() => expect(onPose).toHaveBeenCalled());
    const reported = onPose.mock.calls[0][0];
    expect(reported.position).toHaveLength(3);
    // `fitPoints` puts the iso camera off the origin; a zero vector would mean it never ran.
    expect(Math.hypot(...reported.position)).toBeGreaterThan(0);
  });

  it('adopts a controlled pose, and never echoes it back through onPose', async () => {
    const onPose = vi.fn();
    const pose = {
      position: [1, 2, 3] as const,
      target: [0.5, 0, 0] as const,
      up: [0, 0, 1] as const,
    };
    cameras.length = 0;
    const view = render(<Viz3dCanvas scene={SCENE} pose={pose} onPose={onPose} />);
    await waitFor(() => expect(spies.render).toHaveBeenCalled());

    // The pose reached three: the camera sits exactly where the page said, not on the preset.
    await waitFor(() => expect(cameras[0]?.position.x).toBe(1));
    expect([cameras[0].position.x, cameras[0].position.y, cameras[0].position.z]).toEqual([
      1, 2, 3,
    ]);
    expect(onPose).not.toHaveBeenCalled();

    // The same value arriving again is a no-op, not a second apply.
    view.rerender(<Viz3dCanvas scene={SCENE} pose={{ ...pose }} onPose={onPose} />);
    expect(onPose).not.toHaveBeenCalled();
  });

  it('still offers the keyboard list beside the canvas', async () => {
    const onSelect = vi.fn();
    render(<Viz3dCanvas scene={SCENE} onSelect={onSelect} />);
    await waitFor(() => expect(spies.render).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /bin b/ }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 'b' }));
  });
});

describe('without WebGL', () => {
  beforeEach(() => {
    state.webgl = false;
  });

  it('renders the fallback list instead of a canvas, and never loads three', () => {
    render(<Viz3dCanvas scene={SCENE} />);
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByText(/no WebGL/)).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(2);
    expect(spies.render).not.toHaveBeenCalled();
  });

  it('reports the same selection a click on a sphere would', async () => {
    const onSelect = vi.fn();
    render(<Viz3dCanvas scene={SCENE} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', { name: /bin a/ }));
    expect(onSelect).toHaveBeenCalledWith({
      id: 'a',
      label: 'bin a',
      datum: expect.objectContaining({ id: 'a' }),
    });
  });

  it('shows the highlighted datum as pressed', () => {
    render(<Viz3dCanvas scene={SCENE} highlighted={['b']} />);
    expect(screen.getByRole('button', { name: /bin b/ })).toHaveAttribute('aria-pressed', 'true');
  });
});
