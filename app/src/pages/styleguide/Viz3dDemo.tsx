/**
 * The `viz3d` module, proven end to end on data this page already owns: every generated ramp
 * stop as one sphere, placed at (shade, family, measured luminance).
 *
 * Nothing is hand-listed — the scene is built by iterating `RAMP`, so a colour that changes
 * changes this figure. It is also the module's live contract test: canvas, no-WebGL fallback,
 * generic controls (colour-by, layer toggles, filters) and a pick held in the URL.
 */

import { Exhibit } from '../../components';
import { DENSITY_SCALE, RAMP, type Tone } from '../../lib/palette';
import {
  type ColorEncoding,
  type Datum3D,
  describeScene,
  type Scene3D,
  SceneControls,
  srgbToLinear,
  useSceneExplorer,
  useSceneSelection,
  Viz3dCanvas,
} from '../../viz3d';

/**
 * WCAG **relative luminance** of a generated stop — the measured quantity the z axis carries.
 *
 * The 0.2126/0.7152/0.0722 coefficients are defined over *linear* light. Applying them to the
 * gamma-encoded sRGB bytes straight out of the hex gives *luma*, a different (and much
 * flatter) number, so each channel is linearised first with the module's own `srgbToLinear`.
 */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => srgbToLinear(parseInt(hex.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

const TONE_OF: Record<string, Tone> = {
  good: 'good',
  broken: 'broken',
  decision: 'decision',
  machinery: 'machinery',
  raw: 'raw',
  chrome: 'neutral',
  severity: 'broken',
};
const CORE = new Set(['good', 'broken', 'decision', 'machinery', 'raw']);

const points: Datum3D[] = Object.entries(RAMP).flatMap(([family, ramp], familyIndex) =>
  Object.entries(ramp).map(([shade, hex], shadeIndex): Datum3D => ({
    id: `${family}-${shade}`,
    label: `${family}-${shade}`,
    at: [shadeIndex, familyIndex, luminance(hex) * 10],
    value: luminance(hex),
    layer: CORE.has(family) ? 'tone' : 'chart',
    meta: { family, shade: Number(shade), luminance: Number(luminance(hex).toFixed(3)) },
  })),
);

const ENCODINGS: ColorEncoding[] = [
  {
    id: 'luminance',
    kind: 'numeric',
    label: 'luminance',
    field: 'luminance',
    scale: DENSITY_SCALE,
    lowMeans: 'a deep shade',
    highMeans: 'a pale shade',
  },
  {
    id: 'family',
    kind: 'categorical',
    label: 'family',
    field: 'family',
    tones: TONE_OF,
    means: 'each stop drawn in its own semantic tone',
  },
];

const SCENE: Scene3D = {
  kind: 'points',
  title: 'The palette as a point cloud',
  axes: {
    x: { label: 'shade', unit: 'step, 50 palest to 950 deepest' },
    y: { label: 'family', categories: Object.keys(RAMP) },
    z: { label: 'relative luminance', unit: '×10' },
  },
  points,
  color: ENCODINGS[0],
  encodings: ENCODINGS,
  layers: [
    { id: 'tone', label: 'tone families' },
    { id: 'chart', label: 'chrome + severity' },
  ],
  links: [{ from: 'good-50', to: 'good-950', label: 'the full green ramp', tone: 'good' }],
  unit: 'luminance',
  radius: 0.4,
};

export function Viz3dDemo() {
  const explorer = useSceneExplorer(SCENE, 'palette3d');
  const selection = useSceneSelection(
    'palette3d',
    points.map((p) => p.id),
  );
  return (
    <Exhibit
      title="3D primitives"
      legend={
        <>
          One sphere per generated ramp stop: x = shade step, y = colour family, z = measured
          relative luminance. Colour is whatever the <code>colour by</code> control selects — the
          ramp itself (deep to pale) or each stop&apos;s semantic tone. The yellow ring marks the
          picked stop, held in the URL as <code>?palette3d.pick=</code>; the yellow line links the
          two ends of the green ramp.
        </>
      }
      reading="Relative luminance falls monotonically from 50 to 950 in every one of the seven families (measured, not asserted), but the fall is far from even: it is steep across 50-400 and nearly flat below 700. That is why 300/400 carries text on a dark ground and 950 works as a tinted background — the deep end of a ramp is almost all the same amount of light."
      source="src/lib/palette/ramps.generated.ts via src/viz3d"
      data={describeScene(explorer.scene, selection.highlighted)}
      controls={
        <SceneControls explorer={explorer} view={selection.view} onViewChange={selection.setView} />
      }
    >
      <Viz3dCanvas
        scene={explorer.scene}
        height={420}
        highlighted={selection.highlighted}
        onSelect={selection.onSelect}
        view={selection.view}
      />
    </Exhibit>
  );
}
