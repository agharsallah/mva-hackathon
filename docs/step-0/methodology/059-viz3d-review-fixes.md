# 059 — `viz3d` and the protein exhibit: sixteen review findings, and the camera fit that was wrong

**A step-0 platform entry, so it carries no hypothesis.** It records the app-side half of a
review of the uncommitted protein work — the fixes, the measurements that replace three stale
numbers, and the browser instrument that is now committed rather than described.

**Supersedes two claims in entry [057](057-protein-explorer-exhibit.md)**, and nothing else in
it:

1. 057 line 176 says "the exhibit is ~1,000 lines of page code". Measured on this checkout:
   `app/src/pages/panel/protein/` is **1,581 lines** of non-test code, **2,236** with its three
   test modules. The point 057 was making — zero lines of three.js in the page — stands.
2. 057 line 104 says "Measured **~120 fps**" with no instrument, from a driver (`node final.mjs`)
   that was never committed. The figure reproduces (**120.3 fps**, below) but it is a _scheduling
   throughput_ number from headless Chromium with software WebGL and no vsync cap, not a frame
   budget. The driver is now [`app/tools/verify-protein-explorer.mjs`](../../../app/tools/verify-protein-explorer.mjs),
   whose module note states what each number measures and what it does not.

The `src/mva/viz/*` findings from the same review are entry
[058](058-mmcif-parser-hardening.md)'s; they are not repeated here.

## Question

The review raised sixteen findings against `app/src/viz3d/**`, `app/src/pages/panel/protein/**`
and three comment sites quoting three's bundle size. Two are behaviour a reader would notice
immediately; the rest are correctness, cost, honesty or accessibility. Specifically: **does the
default camera actually frame the figure**, and **does exploring the scene keep the reader's
orbit**?

## Inputs

- `app/` at this checkout — `three` 0.185.1, vite 8.2.2, vitest 3.2.7.
- Dev server in **fixture mode**: `VITE_API_URL=http://127.0.0.1:8999` (a dead port) so every
  API call falls back to the committed fixtures, `pnpm dev --port 5197 --strictPort`.
- Chromium 1228 from the `ms-playwright` cache, headless, software WebGL
  (`--use-angle=swiftshader --enable-unsafe-swiftshader`), viewport 1340 × 1400.
- `playwright` 1.59.1, resolved from the global npm root. Deliberately **not** an app
  dependency: it is a one-machine instrument, not part of the build.

## Commands run

```
cd app
pnpm run check                                  # typecheck · lint · format · theme · test
pnpm run lint:strict                            # --max-warnings 0
pnpm run build && pnpm run bundle-budget --skip-build
VITE_API_URL=http://127.0.0.1:8999 pnpm dev --port 5197 --strictPort
node tools/verify-protein-explorer.mjs --url=http://127.0.0.1:5197
```

## Observation 1 — the camera was fitting the wrong thing

`core/camera.ts`'s `fitToBounds` put the camera at `radius / sin(halfFov) × 1.35`, where
`radius` is **half the diagonal of the data box**. For a globular protein inside a
2 × 1.6 × 1.2 unit box that is a sphere of radius 1.42 — the camera is placed as though the
fold were a cube inscribing it, and then 35 % more room is added on top. The consequence is the
one the review saw in the screenshots: the fold drew at roughly a third of the frame.

The replacement, `fitPoints`, is an exact fit of the **drawn points** on both screen axes. For
each point `p` relative to the target, with screen basis `right` / `screenUp` / `backward`:

```
d = max over p of   p·backward + max( (|p·right| + r) / tanH ,
                                      (|p·screenUp| + r) / tanV )
```

`tanV` from the camera fov, `tanH = tanV × aspect`, `r` the point's own sphere radius. One pass
over the buffers, no allocation; `MARGIN` is now 1.08. `fitToBounds` survives as the fallback
for a caller with no point buffer, and its aspect handling was corrected to `min(tanV, tanH)`.

Two details that only showed up in the browser:

- **The axes box has to be in the fit.** `core/scene.ts` draws the twelve edges of the data box,
  and for a `protein` scene that box is the _outermost_ thing on screen — the tube's vertices
  all sit inside the residue extent. Fitting only the geometry measured **100.0 % of the shorter
  canvas side**, i.e. the box was being clipped. `core/viewer.ts` now feeds the fit the
  geometry, the instanced spheres with their radii, and the eight box corners.
- **`pose.up` stays the declared preset up.** `OrbitControls` uses `camera.up` as the axis it
  orbits about, so handing it the orthogonalised (tilted) up for `iso` would make a drag rotate
  the scene about a tilted axis. The orthogonalised `screenUp` is used only for the projection —
  which is what three's own `lookAt` does for the view matrix.

Measured, `/panel?gene=BUB1B`, canvas 1266 × 520:

|                                                   | fraction of the shorter canvas side the figure spans            |
| ------------------------------------------------- | --------------------------------------------------------------- |
| before (`fitToBounds`, box diagonal, margin 1.35) | ~30–45 % (the review's reading of the committed screenshots)    |
| points only, no axes box                          | 100.0 % — clipped                                               |
| **`fitPoints` incl. the axes box, margin 1.08**   | **77.8 %** (34.2 % wide × 77.8 % high, 4.7 % of pixels painted) |
| after _focus on selection_                        | 80.8 %                                                          |
| the `/style-guide` point cloud                    | 81.3 %                                                          |

The `/panel` canvas height is left at **520 px**. It was already inside the 520–560 range the
review asked for; with the fit corrected there is no empty box left to shrink.

## Observation 2 — the orbit survives exploration

`viewer.setGeometry` used to call `applyView()` unconditionally, and `Viz3dCanvas` calls it on
every `buffers` change — so _dim_, _rare only_, an impact chip or _colour by_ threw the reader's
orbit away. It now refits only when the scene's data box changed, compared over `extent` and
`bounds` to six decimals; `setGeometry(buffers, { refit: true })` forces one. `viewer.resize()`
no longer refits at all — the `ResizeObserver` fires on every layout reflow.

Measured against a hand-set orbit (a real 140 × 60 px drag, then 2 s for the damping to settle),
as the largest per-edge move of the figure's bounding box, in canvas fractions:

| step                               | figure bounding box (canvas fractions) | distance from the default view |
| ---------------------------------- | -------------------------------------- | ------------------------------ |
| default view, no interaction       | `[0.325, 0.182, 0.662, 0.949]`         | 0                              |
| after a 140 x 60 px drag           | `[0.321, 0.101, 0.654, 0.848]`         | 0.101                          |
| after _colour by_ → pLDDT          | `[0.333, 0.152, 0.654, 0.818]`         | **0.131**                      |
| after toggling _rare alleles only_ | `[0.338, 0.162, 0.658, 0.818]`         | **0.131**                      |

The comparison is against the **default view**, not against the orbited one, because the default
view is deterministic (it is `fitPoints` on the `iso` preset) and a refit lands exactly on it. It
does not: both post-action boxes stay 0.131 away from it. The instrument's own noise floor is
0.03 — two reads with no action at all — because `OrbitControls`' damping asymptotes rather than
stopping, and the 240-px-wide readback quantises each axis to ~0.01.

Independently confirmed by tracing `applyView` from a temporary `console.warn` in
`core/viewer.ts`: **3 calls during mount, 0 on the recolour, 0 on the filter toggle.** (The trace
was removed; it is quoted here because it is the sharper evidence — the pixel comparison above is
what the committed driver can measure without a hook in production code.)

## Observation 3 — three's bundle size, and which number is which

All three comment sites (`core/loadThree.ts`, `tools/bundle-budget.mjs`, `eslint.config.js`)
stated the three chunk was "365.6 kB raw / 87.1 kB gzip (measured)". Both numbers are real; they
measure different artefacts. Measured on this checkout:

| artefact                                       | raw       | gzip      | fetched by this app?       |
| ---------------------------------------------- | --------- | --------- | -------------------------- |
| emitted chunk `dist/assets/three.module-*.js`  | 529.85 kB | 131.78 kB | **yes**, on first 3D mount |
| `node_modules/three/build/three.module.min.js` | 365.55 kB | 87.12 kB  | no                         |

The chunk is the larger because rolldown bundles three's ESM sources (plus what the
`OrbitControls` addon pulls in) and minifies them itself rather than shipping the prebuilt file.
All three comments now quote the emitted-chunk figure and name the other one.

## Observation 4 — the other thirteen findings

| Finding                                                                                                                                                                     | Fix                                                                                                                                                                                                                               |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `setHighlight` allocated a `TorusGeometry` per highlighted id and `Group.clear()` disposes nothing — one leaked GPU buffer per pick, unbounded per session                  | one cached unit torus, scaled per `Mesh`; ring size is a transform, so a pick allocates no GPU resource                                                                                                                           |
| the residue window was seeded once, so switching gene silently trimmed the new chain                                                                                        | the window is stored with the `protein_length` it was chosen against and reset during render when that changes                                                                                                                    |
| `filterScene`'s `protein` case filtered `residues` and left `backbone` full-length — the tube would be painted and picked from the wrong residues                           | both trimmed at the same indices; a scene whose two arrays are not index-aligned is returned unchanged                                                                                                                            |
| `nearestResidue` was O(samples × residues) — ~6.6 M distance evaluations per scene rebuild for BUB1B, on every recolour                                                     | `backboneOwners`: sample `k` is at curve parameter `k / SAMPLES_PER_SEGMENT`, so its owner is `round(k / perSegment)` in O(1) when the arrays are aligned; the scan is kept for when they are not                                 |
| `SceneFallback` stopped at 60 datums and told the reader to "filter the scene", a control the protein exhibit does not render — 990 of 1,050 residues off the keyboard path | highlighted then tone-bearing (candidate) datums first, then scene order; paged 60 at a time behind _show next_ / _show all_; the note names those                                                                                |
| the "first touch stops auto-rotate" listeners were armed at mount with `{once: true}`, before the viewer existed                                                            | armed on `status === 'ready'`                                                                                                                                                                                                     |
| the module note claimed hover "never touches React state" while `setHover` fired per pointermove                                                                            | state changes only when the hovered id changes; the tooltip's position is a `transform` written to a ref'd DOM node; note corrected                                                                                               |
| `karyotype` is genomics vocabulary in a case-agnostic module                                                                                                                | kept, documented in `src/viz3d/README.md` as the one case-flavoured kind, with why renaming loses more than it gains                                                                                                              |
| the style-guide demo labelled _luma_ as "relative luminance" — WCAG coefficients on gamma-encoded sRGB                                                                      | linearised through `viz3d`'s own `srgbToLinear`, now exported from the barrel; the exhibit's _reading_ line replaced with a measured claim (monotone fall 50→950 in all seven families, steep across 50–400, near-flat below 700) |
| the exhibit footer counted drawn residues against the _translation_ length                                                                                                  | counted against `build.modelled`, with the window and the unmodelled count named separately                                                                                                                                       |
| `value: r.plddt ?? 0` made every residue's value 0 for an experimental structure, so `describeScene`'s extremes degenerated to an id sort                                   | `value: r.plddt ?? r.n`, and `describeScene` reports no extremes at all when every value is equal                                                                                                                                 |
| `src/test/setup.ts` replaced `getContext` globally, so a future 2D-canvas test would silently get `null`                                                                    | `null` for `webgl`/`webgl2`/`experimental-webgl` only; other ids delegate to jsdom inside a `try/catch`                                                                                                                           |
| the frame-rate claim had no committed instrument                                                                                                                            | `tools/verify-protein-explorer.mjs` + `tools/viz3d-measure.mjs`, with the method in their module notes                                                                                                                            |

## Observation 5 — the browser, and the gates

```
- canvas named: "BUB1B — the fold, with this proband's alleles on it: a 3D protein backbone of 1,050 pickab"…
- no-WebGL note present: false
- canvas fill: 77.8 % of the shorter side (34.2 % wide x 77.8 % high, 4.7 % of pixels painted, drawing buffer 1266x520)
- clicks on the canvas: 2 tried, 2 hit -> ?prot.pick=r92 at (0.5, 0.5), r252 at (0.45, 0.5)
- distance-table row -> ?prot.a=r737 ?prot.b=r1002
- canvas fill after focus: 80.8 %
# style guide — http://127.0.0.1:5197/style-guide
- canvas fill: 81.3 %
- frame rate: 120.3 fps (361 frames in 3002 ms, rAF counter, BUB1B)
# console: 48 message(s) — 36 expected fixture-mode request failure(s), 0 from app code
```

`r737` / `r1002` is the same pair entry 057 recorded, so the fixture's arithmetic is unchanged by
any of this. Screenshots retaken into `figures/exhibits/`:
`protein-explorer-{pick,plddt,domain,no-dim,pair,focus}.png` and `viz3d-style-guide.png`
(`protein-explorer-mismatch.png` is 057's identity-guard Callout and is untouched).

**What "77.8 % of the shorter side" does and does not say.** It is the bounding box of every
painted pixel — the tube, the residue spheres _and_ the twelve edges of the data box. The box's
**corners are virtual**: `(min x, min y, min z)` is a coordinate no atom occupies, so in an iso
projection the box silhouette is strictly larger than the point cloud's. That is why fitting the
points alone measured 100 % (clipped) — the box was outside the frame. The compact core of BUBR1
still looks small inside it, and that is the data, not the camera: 391 of 1,050 residues score
below pLDDT 50, so a large part of what fills the frame is disordered tails.

Two things the driver itself had to learn, recorded because they will bite the next person:

- **`gl.readPixels` is unusable here.** Resolving the multisampled default framebuffer at
  1266 × 520 while the render loop runs blocked for _minutes_ per call on SwiftShader. The
  measurement is a `drawImage` of the WebGL canvas into a 240-px-wide 2D canvas instead, taken
  inside a `requestAnimationFrame` callback so the drawing buffer still holds a rendered frame.
- **Measure cost last.** A 3-second rAF counter competing with three's own loop leaves the
  compositor far enough behind that the next `drawImage` readback never returns. The frame-rate
  probe is therefore the final thing the driver does to a page.

Gate output:

```
$ pnpm run check
$ tsc -b
$ eslint .
$ prettier --check .
All matched files use Prettier code style!
$ node tools/gen-theme.mjs --check
$ vitest run
 Test Files  18 passed (18)
      Tests  290 passed (290)        # 277 before this work + 13 new

$ pnpm run lint:strict               # clean, 0 warnings

$ pnpm run build                     # ✓ built in 1.41s
$ pnpm run bundle-budget --skip-build
Bundle budget OK. First paint downloads 2 JS file(s): 249.50 kB raw / 80.42 kB gzip
  (budget 260.00 kB / 84.00 kB).
```

The 13 new tests are `core/camera.test.ts` (5, `fitPoints`), `adapters/adapters.test.ts` (3,
`backboneOwners`), `spec/describe.test.ts` (2, the protein filter's backbone alignment) and
`pages/panel/protein/filters.test.ts` (3, the residue-window reset). Every touched file is under
the 400-line rule; `tools/verify-protein-explorer.mjs` reached 422 and was split, with the
generic measurement half moved to `tools/viz3d-measure.mjs`.

## Conclusion

1. **The default view was the biggest single defect, and it was invisible to every gate.** No
   test asserts what fraction of the canvas a figure fills, and the description-based a11y tests
   cannot: they audit the text twin. The fix needed a real browser to confirm, and needed it
   twice — the points-only fit clipped the axes box, which only a pixel measurement showed.
2. **A refit is a destructive operation and was being done on every recolour.** The rule is now
   in the type (`SetGeometryOptions.refit`) and in the README, and the browser check for it is a
   bounding-box comparison against a stated noise floor rather than an eyeball.
3. **Three numbers about three's size were repeated in three places and all three were about a
   file the app never fetches.** The pattern that caused it — quoting a number without naming
   the artefact — is what the fix corrects, not just the digits.
