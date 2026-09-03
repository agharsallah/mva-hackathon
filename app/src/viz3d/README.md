# `viz3d` — 3D exhibits behind one wrapper

**Verified:** 2026-09-03 — `pnpm run check`, `lint:strict --max-warnings 0` (290 tests),
`build` and `bundle-budget --skip-build` all green with this module, its live demo on
`/style-guide` and the protein exhibit on `/panel` mounted. Browser-verified with
[`app/tools/verify-protein-explorer.mjs`](../../tools/verify-protein-explorer.mjs); the numbers
it produced are in
[`docs/step-0/methodology/059`](../../../docs/step-0/methodology/059-viz3d-review-fixes.md).

A case-agnostic WebGL module. A page hands in **data** — a `Scene3D` it built from this case's
API rows — and gets back a canvas, a text twin of the same figure, and generic controls. It is
the second deliverable in `CLAUDE.md` (a reusable toolkit, not a one-off): another N-of-1 case
copies this folder wholesale and adds a scene kind.

Design rationale, including why raw `three` and not `@react-three/fiber`, lives in
[`docs/step-0/notes/three-js-behind-one-wrapper.md`](../../../docs/step-0/notes/three-js-behind-one-wrapper.md).
Read that before changing the library choice; read this before writing an exhibit.

## The layer edge — the one rule that makes it reusable

**`viz3d` imports `lib` only.** Never `api`, never `components`, never `pages`. Enforced by
`eslint-plugin-boundaries` (element `viz3d` in [`eslint.config.js`](../../eslint.config.js)),
so it is a failed build, not a review note.

The consequence is the contract: `viz3d` never learns what a `DensityBinRow` or a
`GeneStructure` is. The page does the mapping. That is also why the small `<select>`/`<button>`
controls in `components/SceneControls.tsx` are re-implemented instead of imported from
`src/components/Controls.tsx` — importing `components` would give this module the transitive
right to reach `api`.

```mermaid
flowchart LR
    Rows["API rows<br/>(this case only)"]:::input
    Map["the page:<br/>rows → Scene3D"]:::decision
    Spec["spec/<br/>types · describe · filter"]:::machinery
    Adapt["adapters/<br/>pure → GeometryBuffers"]:::machinery
    Core["core/<br/>loadThree · scene · viewer · pick"]:::machinery
    Canvas["Viz3dCanvas<br/>&lt;canvas role=img&gt;"]:::goal
    Fallback["SceneFallback<br/>list of buttons"]:::goal
    NoGL["no WebGL /<br/>three failed"]:::broken

    Rows --> Map --> Spec --> Adapt --> Core --> Canvas
    Spec -->|describeScene| Fallback
    Core -.->|hasWebGL false| NoGL --> Fallback
    Canvas -->|keyboard path| Fallback
```

> **Legend:** purple = the raw input (this case's API rows), yellow = the decision point (the
> page choosing how its rows become a scene — the only case-specific code), blue = neutral
> machinery inside this module, green = the two things a reader ends up with, red = the
> degraded path (no WebGL, or the three chunk failed to load).

## Files

| Path                           | Role                                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `index.ts`                     | the barrel — the only path a page imports                                                                                                  |
| `spec/types.ts`                | the whole data contract: `Scene3D`, `Datum3D`, `Axes3D`, `ColorEncoding`, `Selection3D`, `CameraPreset`, `CameraPose3D`, `GeometryBuffers` |
| `spec/datums.ts`               | a scene read as a flat list of pickable datums, and field classification                                                                   |
| `spec/describe.ts`             | `describeScene` — the AI export, the `aria-label` and the fallback body, in one object                                                     |
| `spec/filter.ts`               | pure filter/recolour, so "colour by any field" is testable                                                                                 |
| `adapters/*.ts`                | `Scene3D → GeometryBuffers`, one file per kind. Pure, no three. The real test surface                                                      |
| `core/loadThree.ts`            | the **only** `import('three')`, plus the `OrbitControls` addon. Both cached                                                                |
| `core/capability.ts`           | `hasWebGL()` — the seam a test stubs                                                                                                       |
| `core/colorRamp.ts`            | samples the app's generated `Colorscale`s per vertex; parses hex, never writes one                                                         |
| `core/scene.ts`                | `GeometryBuffers` + palette → meshes, materials, lights, highlight rings                                                                   |
| `core/camera.ts`               | the four presets and fit-to-bounds. Pure                                                                                                   |
| `core/pick.ts`                 | raycast index → `pickTable` → `Datum3D`. Pure                                                                                              |
| `core/viewer.ts`               | renderer, controls, render loop, pointer handling, dispose                                                                                 |
| `hooks/useSceneSelection.ts`   | `Selection3D` + camera preset ↔ the URL                                                                                                    |
| `hooks/useSceneExplorer.ts`    | active encoding, per-field filters, layers → a derived scene                                                                               |
| `components/Viz3dCanvas.tsx`   | the canvas, the hover tooltip, the resize/dispose lifecycle                                                                                |
| `components/SceneFallback.tsx` | the `<ul>` of `<button>`s: keyboard path, no-WebGL path, text twin                                                                         |
| `components/SceneControls.tsx` | the generic explorer row: view, colour-by, layers, filters, reset                                                                          |

Live example: [`src/pages/styleguide/Viz3dDemo.tsx`](../pages/styleguide/Viz3dDemo.tsx),
rendered at `/style-guide`.

## How a page maps rows → `Scene3D`

```tsx
const scene: Scene3D = {
  kind: 'points',
  title: 'Calls per megabase',
  axes: {
    x: { label: 'megabase', unit: 'Mb' },
    y: { label: 'chromosome', categories: contigs },
    z: { label: 'calls', unit: 'count' },
  },
  color: BY_DENSITY, // a ColorEncoding naming a generated Colorscale
  encodings: [BY_DENSITY, BY_FILTER_CLASS],
  points: rows.map((row) => ({
    id: `${row.contig}-${row.bin}`,
    label: `${row.contig} bin ${row.bin}`,
    at: [row.bin, contigs.indexOf(row.contig), row.calls],
    value: row.calls,
    meta: { pass: row.pass, suppressed: row.suppressed }, // fields, for colour + filters
  })),
};

const explorer = useSceneExplorer(scene, 'bins');
const selection = useSceneSelection('bins', ids);

<Exhibit
  title="…"
  legend={<>…</>}
  data={describeScene(explorer.scene, selection.highlighted)}
  controls={
    <SceneControls explorer={explorer} view={selection.view} onViewChange={selection.setView} />
  }
>
  <Viz3dCanvas
    scene={explorer.scene}
    highlighted={selection.highlighted}
    onSelect={selection.onSelect}
    view={selection.view}
  />
</Exhibit>;
```

Three properties fall out of that shape:

- **Axes are declared in the reader's units** — bins, Mb, residue index. Never a patient
  genomic position: the repo's binding rule holds by construction, and `describeScene`'s own
  test asserts no bare 7-digit run can reach an export.
- **Dynamic exploration is free.** Every fact a page puts in `Datum3D.meta` becomes a
  colour-by option (when the scene declares an encoding for it) and a filter — numeric fields
  get a range, categorical ones a set of chips.
- **One URL cites one figure.** `?bins.pick=…&bins.view=top&bins.by=class` — pick, camera and
  encoding are URL-held; filters stay component state because they are exploratory.

## Accessibility and AI export are one artefact

`describeScene(scene, highlighted)` returns a structured summary (kind, axes with units,
colour encoding with what low and high _mean_, object count, top/bottom-k, highlighted ids,
links) plus a deterministic prose paragraph. That one object is:

1. `Exhibit`'s `data` prop — a canvas has no serialisable content, so the export is the
   description, not the picture;
2. the canvas's `aria-label` (what axe's `role-img-alt` audits);
3. the body of `SceneFallback`.

`SceneFallback` is a real `<ul>` of `<button>`s firing the same `onSelect` a click on a sphere
does, so nothing in a 3D exhibit is mouse-only. It renders three times over: when there is no
WebGL, when the three chunk fails to load, and inside a `<details>` beside a working canvas.

Two properties make that claim true for a scene with thousands of datums:

- **Order is by relevance, not by index** — highlighted datums first, then the ones carrying an
  explicit `Datum3D.tone` (a verdict the page has already decided: a candidate allele), then the
  rest in scene order. The datums a reader came for are on the first page whatever their index.
- **Every datum is reachable.** The list renders 60 at a time behind _show next 60_ / _show all_
  buttons. It used to stop dead at 60 and tell the reader to "filter the scene to reach them" —
  a control the protein exhibit deliberately does not render (`filters={false}`), which left 990
  of BUB1B's 1,050 residues off the keyboard path entirely.

## Cost

three is loaded by exactly one dynamic `import()`, so a visitor who never opens a 3D exhibit
downloads **zero** bytes of it. Measured 2026-09-03 on a clean `pnpm run build`:

| chunk                                      | raw       | gzip      |
| ------------------------------------------ | --------- | --------- |
| `three.module-*.js` (lazy)                 | 529.85 kB | 131.78 kB |
| `OrbitControls-*.js` (lazy)                | 19.66 kB  | 4.38 kB   |
| `viz3d-*.js` (lazy, this module)           | 31.93 kB  | 11.24 kB  |
| initial payload (unchanged by this module) | 249.50 kB | 80.42 kB  |

Every number in that table is the **emitted chunk** as measured by
`node tools/bundle-budget.mjs --skip-build`. three's own release notes quote a different
figure — 365.55 kB raw / 87.12 kB gzip — which is the prebuilt `three/build/three.module.min.js`
this app never fetches; rolldown bundles and minifies three's ESM sources itself.

`core/loadThree.ts` narrows the module namespace to the declared `ThreeApi` field by field,
which is what lets rolldown drop the rest: passing the namespace through measured 724.23 kB
raw / 184.67 kB gzip for the same chunk. Two gates hold the placement:
`no-restricted-imports` (only `core/loadThree.ts` may name `three`) and
[`tools/bundle-budget.mjs`](../../tools/bundle-budget.mjs), which fails if `/three/i` appears
in the initial set, or if a page imports `src/viz3d` and no `three` chunk exists at all.

## Recipe: add a new scene kind

1. **`spec/types.ts`** — add the variant to the `Scene3D` union with the data it needs.
2. **`spec/datums.ts`** — add a `sceneDatums` case. Picking, the keyboard fallback, the
   filters and the description all come from that one function, so this is the step that makes
   the new kind a first-class citizen.
3. **`spec/filter.ts`** — add a `filterScene` case (what "hide this datum" means for the kind).
4. **`adapters/<kind>.ts`** — the pure `Scene3D → GeometryBuffers` function. Use
   `adapters/normalise.ts` for the unit box, `datumColors` for colour and `tilePickTable` for
   the pick ranges. Its contract: `colors.length === positions.length`, and the `pickTable`
   ranges tile the primary index space with **no gap and no overlap**.
5. **`adapters/index.ts`** — one line in `toGeometry`.
6. **`adapters/adapters.test.ts`** — add the scene to the `describe.each` table. The shared
   cases (kind, buffer lengths, tiling, unit box, extent, links) then apply for free; add the
   kind-specific assertions beside them.

Nothing in `core/` or `components/` changes: they only ever see `GeometryBuffers`.

### `karyotype` is the one case-flavoured kind

Every other kind is neutral geometry — `points`, `surface`, `protein` (a tube through an
ordered chain of 3D positions). `karyotype` is not: the variant is named after a genomics
figure, and `ChromosomeBar.copies` is documented as "the aneuploidy signal". A different N-of-1
case inherits a scene kind whose vocabulary it cannot use.

It is kept rather than renamed because the name is what makes the _existing_ exhibit readable,
and a neutral rename (`bars`, `extruded categories`) would leave this repo with a kind whose
name says less than the data it holds. Treat it as the exception: a new case either ignores it
or copies `adapters/karyotype.ts` under its own name. Nothing else in the module knows the word.

## Two rules the camera obeys

1. **The camera fits the drawn points, not the data box.** `core/camera.ts` exports two fits.
   `fitToBounds` fits the bounding sphere of the box, whose radius is half the box _diagonal_ —
   for a globular protein in a 2 × 1.6 × 1.2 unit box that is a sphere of radius 1.42, and the
   fold drew at ~30–45 % of the shorter canvas side. `fitPoints` solves, in one pass over the
   point buffers, the smallest distance at which every point (plus its sphere radius) is inside
   both the vertical and the horizontal frustum, so the extreme point lands at `1 / 1.08` of the
   binding half-side. `core/viewer.ts` uses `fitPoints`; `fitToBounds` is the fallback for an
   empty point set.
2. **A refit throws away the reader's orbit, so it happens only when the scene's box changed.**
   `viewer.setGeometry(buffers)` compares the new `extent`/`bounds` against the fitted ones: a
   different residue window or a different gene refits, a recolour or a de-emphasis pass does
   not. `setGeometry(buffers, { refit: true })` forces one; `viewer.resize()` never refits (it
   only resizes the renderer and updates the projection matrix), because the `ResizeObserver`
   fires on every layout reflow.
3. **The camera can be _controlled_, and a controlled pose never echoes.** `Viz3dCanvas` takes
   an optional `pose: CameraPose3D` plus `onPose`, over `Viewer.getPose()` / `setPose()`. The
   pose is three vectors in the **normalised unit box** — not the scene's own units — which is
   exactly what makes one pose meaningful on two different scenes, and therefore what makes
   "sync cameras" in the side-by-side protein comparison possible without a page ever touching
   three. Two guards keep it from oscillating: the viewer reports at most every 90 ms and only
   past a 1e-4 threshold (OrbitControls damps, so the camera creeps for ~a second after the
   reader lets go), and both the viewer and the component remember the last pose they emitted
   or adopted, so a value arriving back is a no-op. `pose` is applied by an effect declared
   _after_ the `view` effect, so a shared orbit wins over a preset fit.

## Testing

| Layer                             | What it covers                                                                                                                                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `adapters/adapters.test.ts`       | buffer lengths, pick-table tiling, bounds and extent, per-kind geometry, protein backbone sampling and per-residue colour                                                                                                         |
| `core/colorRamp.test.ts`          | `sampleScale` against the generated ramp stops, null → absent grey, sRGB→linear                                                                                                                                                   |
| `core/camera.test.ts`             | the four presets, fit-to-bounds, the narrow-canvas case                                                                                                                                                                           |
| `spec/describe.test.ts`           | determinism, axes/units, extremes, links, no coordinate-shaped digit run; plus filter/recolour and picking                                                                                                                        |
| `components/Viz3dCanvas.test.tsx` | mounts the real adapter → scene → viewer path against a fake `ThreeApi`: render called, full dispose on unmount, the controlled `pose` reaching the camera without being echoed back, and the no-WebGL fallback firing `onSelect` |

jsdom has no WebGL. `src/test/setup.ts` stubs `HTMLCanvasElement.prototype.getContext` to
`null` **for the `webgl`/`webgl2` ids only** (other ids delegate to jsdom; the measured jsdom
behaviour is recorded there), so `hasWebGL()` is deterministically
false in every page test and the fallback — the part axe can actually audit — is what renders.
A test that wants the canvas path mocks `core/capability` and `core/loadThree`, which is why
those are separate one-export files.
