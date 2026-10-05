/**
 * Live specimens of the two heavy renderers, so the Style page proves they work rather than
 * describing them.
 *
 * Both are deliberately fed synthetic data generated here: the point is the rendering
 * contract (a Plotly trace drawn in the app's own template; a `Scene3D` turned into a canvas
 * plus its text twin), not any particular dataset. Both libraries are dynamically imported
 * by their wrappers, so this page's chunk stays small and they arrive only when it is opened.
 */

import { Exhibit, Plot } from '../../components';
import { C, DENSITY_SCALE } from '../../lib/palette';
import type { Scene3D, Vec3 } from '../../viz3d';
import { Viz3dCanvas } from '../../viz3d';

const N = 48;

/** A smooth synthetic series — enough to show the axes, the grid and the mark colour. */
const X = Array.from({ length: N }, (_, i) => i);
const Y = X.map((x) => 50 + 30 * Math.sin(x / 5) + 8 * Math.cos(x / 1.7));

/** A helix: three.js needs a real 3D path, and a helix reads as one from every camera. */
const BACKBONE: Vec3[] = Array.from({ length: 60 }, (_, i) => {
  const t = i / 4;
  return [Math.cos(t) * 6, Math.sin(t) * 6, i * 0.6] as Vec3;
});

const SCENE: Scene3D = {
  kind: 'protein',
  title: 'A synthetic backbone',
  axes: {
    x: { label: 'x', unit: 'arbitrary' },
    y: { label: 'y', unit: 'arbitrary' },
    z: { label: 'z', unit: 'arbitrary' },
  },
  color: {
    id: 'score',
    kind: 'numeric',
    label: 'per-residue score',
    field: 'value',
    scale: DENSITY_SCALE,
    domain: [0, 1],
    lowMeans: 'a low score',
    highMeans: 'a high score',
  },
  backbone: BACKBONE,
  residues: BACKBONE.map((at, i) => ({
    id: `r${i + 1}`,
    label: `residue ${i + 1}`,
    at,
    value: (Math.sin(i / 7) + 1) / 2,
  })),
  unit: 'arbitrary',
};

export function PlotSpecimen() {
  return (
    <Exhibit
      title="A chart, in the app's template"
      legend={
        <>
          Blue line = the synthetic series; the grid, fonts and background come from{' '}
          <code className="font-mono">plotLayout.baseLayout()</code>, never from Plotly&rsquo;s
          defaults.
        </>
      }
      reading="Every chart in the app enters through Exhibit, which is why this one has a legend at all."
      source="generated in src/pages/styleguide/Specimens.tsx"
    >
      <Plot
        height={260}
        data={[
          {
            x: X,
            y: Y,
            type: 'scatter',
            mode: 'lines',
            line: { color: C.machinery, width: 2 },
            hovertemplate: '%{x}: %{y:.1f}<extra></extra>',
          },
        ]}
        layout={{ xaxis: { title: { text: 'index' } }, yaxis: { title: { text: 'value' } } }}
      />
    </Exhibit>
  );
}

export function ScenesSpecimen() {
  return (
    <Exhibit
      title="A 3D scene, and its text twin"
      legend="Colour runs cold to hot with the per-residue score. Where WebGL is unavailable the same scene renders as a keyboard-reachable list — that list is the accessible path, not a fallback for failure."
      reading="A page hands viz3d data (a Scene3D), never three.js code; the module knows nothing about the domain the data came from."
      source="generated in src/pages/styleguide/Specimens.tsx"
    >
      <Viz3dCanvas scene={SCENE} height={320} view="iso" />
    </Exhibit>
  );
}
