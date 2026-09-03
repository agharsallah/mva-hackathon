# 057 — The protein explorer: the first exhibit where the third dimension is the finding

**A step-0 platform entry, so it carries no hypothesis.** It records what was built on top of
entry [056](056-protein-structure-endpoint.md)'s endpoint and the `viz3d` module, what a real
browser was observed doing with it, and the Cα distances the offline fixture produces — which
are **numbers about invented alleles on a real backbone and mean nothing clinically**.

## Question

Entry [056](056-protein-structure-endpoint.md) put a folded protein on the wire. The 2D domain
lollipop (entry [040](040-locus-gene-track.md)) already answers *which domain* an allele lands
in. So: can the browser draw that fold, paint this proband's protein-altering alleles onto
their own residues, and **measure the distance between any two of them** — with the model's
own confidence visible, with nothing paintable onto the wrong sequence, and inside the
`viz3d` boundary (a page hands in data, never three.js code)?

The three sub-questions that decide whether it is honest rather than decorative:

1. What stops a residue being painted onto the **wrong translation**? Amino-acid offsets are
   only meaningful on the translation they were computed against.
2. How does a **prediction** stay visibly a prediction? AlphaFold's `pLDDT` below 70 supports
   no spatial claim, so those residues must not read as a domain colour.
3. What is the reader allowed to conclude from a short distance? Nothing functional — a
   distance band is geometry.

## Inputs

| Input | Shape as read |
|---|---|
| `GET /api/panel/protein-structure?gene=` | `ProteinStructure` — 1,050 residues, `ca` + `plddt` each, `covered [[1, 1050]]`, 62 secondary segments (entry 056) |
| `GET /api/panel/gene-structure?gene=` | `GeneStructure` — `protein`, `protein_length`, 5 `domains`, 3 `candidates` |
| `GET /api/panel/het-pairs?gene=` | `PanelHetPairs` — used only to look up a pair's phase, never to place a residue |
| Offline fixtures | `app/src/fixtures/data/panel-protein-structure.json` (**real** AlphaFold `AF-O60566-F1` v6) + `panel-gene-structure.json` (**synthetic** alleles and domain offsets) |
| Module | `app/src/viz3d/` (WP2) — `Scene3D` kind `protein`, `useSceneExplorer`, `useSceneSelection`, `Viz3dCanvas`, `describeScene` |
| Design | [three.js behind one wrapper](../notes/three-js-behind-one-wrapper.md) §2 and §5.3 |
| Contract | `app/src/api/types/protein.ts`, `app/src/api/types/panel.ts` |

No warehouse table and no patient coordinate is read. The exhibit's axes are ångström in the
model's own frame and its residue ids are amino-acid indices (`r737`), so the repo's
no-coordinate rule holds by construction.

## What was built

| File | Concern |
|---|---|
| `app/src/pages/panel/protein/buildScene.ts` | `ProteinStructure` + `GeneStructure` (+ optional `PanelHetPairs`) → `Scene3D`, or a typed error. Also `sliceProteinScene` (trim the chain, backbone included) and `emphasise` (grey + shrink, never delete) |
| `.../encodings.ts` | the five colour encodings and the domain→tone palette; every `means` string is read verbatim into the legend, the `aria-label` and the AI export |
| `.../distances.ts` | pairwise Cα distance, the geometric bands, the `confident` / `bothRare` / `sameDomain` flags, the phase lookup, the `viz3d` link |
| `.../filters.ts` | filter state + the pure emphasis predicate |
| `.../ProteinExplorer.tsx` | the wiring: queries, URL keys, pair building, focus |
| `.../ProteinFilters.tsx`, `.../DistanceTable.tsx`, `.../ProteinNotes.tsx` | the control row, the closest-pairs table, and the words (per-encoding legend + reading, provenance, the two failure renderings) |
| `app/src/pages/Panel.tsx` | one new `Section` under the locus/lollipop section |

Three decisions worth recording, because each is a *deviation* from the obvious route:

- **Filters de-emphasise, they do not drop.** `viz3d`'s generic filter panel is switched off
  (`filters={false}`). The protein adapter colours the backbone tube from the *nearest
  surviving residue*, so dropping a stretch of residues repaints that stretch of chain in a
  neighbour's colour — a picture that asserts something false. Greying (tone `neutral`) and
  shrinking keeps the chain continuous and is also exactly the treatment the design note asks
  for below the pLDDT floor.
- **"Focus on selection" trims the chain rather than moving the camera.** `viz3d` fits the
  camera to the scene's bounds, and the bounds come from the backbone, so narrowing the
  residue window *is* the zoom. No camera API was added to the module.
- **A candidate sphere keeps its impact colour under every ramp** (`Datum3D.tone` wins over the
  encoding). Switching to pLDDT must not make the verdict disappear.

## Commands run

```
cd app
pnpm run check                      # typecheck · lint · format:check · theme:check · test
pnpm run lint:strict                # --max-warnings 0
pnpm run build && pnpm run bundle-budget --skip-build
pnpm dev --port 5197                # VITE_API_URL pointed at a dead port -> fixture mode
node final.mjs                      # playwright over the real page (see below)
```

## Observation 1 — the gates

```
$ pnpm run check
 Test Files  18 passed (18)
      Tests  277 passed (277)      # 233 before this work + 44 new
$ pnpm run lint:strict             # clean, 0 warnings
$ pnpm run build                   # ✓ built in 1.19s
$ pnpm run bundle-budget --skip-build
Bundle budget OK. First paint downloads 2 JS file(s): 249.50 kB raw / 80.42 kB gzip
  (budget 260.00 kB / 84.00 kB).
```

The 44 new tests are `buildScene.test.ts` (21), `distances.test.ts` (17) and
`filters.test.ts` (6) — all pure, no canvas. The initial payload is unchanged by the exhibit:
three still arrives only through `viz3d`'s single dynamic import, and the `three` chunk stays
at 529.85 kB raw / 131.78 kB gzip, fetched on first 3D mount.

`src/test/modules.test.tsx` (no `console.error` on any page) and `src/test/a11y.test.tsx`
(axe, every page) both cover `/panel` with this exhibit mounted; in jsdom `hasWebGL()` is
false, so what they audit is the keyboard-reachable fallback list.

## Observation 2 — a real browser

Chromium 1228 headless with software WebGL (`--use-angle=swiftshader`), against the dev server
in fixture mode. Measured **~120 fps** on the 1,050-residue scene, so the figure is not heavy.

Driven with Playwright against `/panel?gene=BUB1B` (`figures/exhibits/protein-explorer-*.png`
are the frames it captured):

| What was checked | Observed |
|---|---|
| the canvas exists and is named | one `<canvas role="img">`; `aria-label` is `describeScene(...).text`, no "no WebGL" note |
| provenance line | `model: AlphaFold — a prediction · version 6 · UniProt O60566 · translation ENSP00000000000 · coordinate file` (a link to the real `AF-O60566-F1-model_v6.cif`) |
| coverage line | `1,050 residues modelled · 48.8 % of them at pLDDT ≥ 70 (512 residues)` |
| fixture badge | names the split in words: *real AlphaFold backbone + synthetic candidate alleles* |
| **a click on a sphere picks a residue** | `?prot.pick=r622` after one click at the canvas centre, `?prot.pick=r92` after another — the raycast path works against real WebGL, not only against the test double |
| a click in the closest-pairs table picks the pair | `?gene=BUB1B&prot.a=r737&prot.b=r1002&prot.pick=r737` |
| the link is really drawn | `aria-label` gains `Linked pairs: L737 — stop gained · rs000000001 ↔ N1002 — missense (37.9 Å)` and `Highlighted: …, …` |
| colour-by changes the legend **and** the reading | switching to pLDDT rewrites both paragraphs and writes `?prot.by=plddt`; switching back restores them |
| the distance table sorts | the `Cα distance` header cycles `aria-sort` unsorted → `ascending` → `descending` |
| the keyboard twin | 60 residue buttons (`SceneFallback`'s cap), each firing the same `onSelect` a sphere click does |
| "use pair from Compare" | correctly **disabled**, `title="the Compare page is not holding a pair yet"` |
| console | only the expected fixture-mode fetch failures (`ERR_CONNECTION_REFUSED` against the dead API port) plus two WebGL *performance* warnings from SwiftShader. **No page error, no React warning, no `console.error` from app code.** |
| `/style-guide` | the `viz3d` demo still renders its canvas; console clean apart from the same fixture-mode fetch failures |

## Observation 3 — the honest failure, found by running it

The first browser open did **not** draw the fold. It drew the Callout instead:

> the 3D model is for translation `ENSP00000000000` but the gene structure places its alleles
> on `ENSP00000287598` … nothing is painted: a residue drawn on the wrong sequence is worse
> than no figure.

The cause is a real integration seam, not a typo. A **stale API process** was running: it
serves `/api/panel/gene-structure` (real Ensembl, `ENSP00000287598`) but predates
`/api/panel/protein-structure` and answers 404 for it, so the client fell back to the offline
fixture for that one endpoint — and `fixtures/shape/protein-structure.ts` deliberately takes
its `protein` from the *gene-structure fixture*, whose placeholder is `ENSP00000000000`. The
two payloads therefore can never agree across an api/fixture split.

The guard behaved exactly as designed (nothing painted). What was missing was the *fix*, so
the Callout now also reports when the two payloads came from different origins and names the
remedy (`uv run mva-viz-api`). Screenshot: `figures/exhibits/protein-explorer-mismatch.png`.

## Observation 4 — the Cα distances in the offline fixture

> **These numbers are geometry over invented alleles.** The backbone is the true AlphaFold
> model of BUBR1; the two placeable alleles come from the **synthetic** gene-structure
> fixture. Nothing below is a finding about this or any proband.

Measured directly off `app/src/fixtures/data/panel-protein-structure.json`, and reproduced by
the exhibit to the same tenth:

| Pair | Cα distance | Band | aa apart on the chain | both rare | same domain | pLDDT both ends | phase |
|---|---|---|---|---|---|---|---|
| `L737` (stop gained · rs000000001) ↔ `N1002` (missense) | **37.9 Å** | far apart (> 25 Å) | 265 | yes | no — 737 is in no annotated domain, 1002 is in the kinase domain | 73.6 and 91.1, both ≥ 70, so the distance is quotable | unknown |

The third fixture candidate (`splice region`) has no `protein_pos` and is **listed with its
reason** rather than dropped, which is the same rule the 2D lollipop follows.

Two properties of the fixture worth recording because they shape what the exhibit looks like:

- **Only two of the three candidates are placeable**, so the closest-pairs table has exactly
  one row offline. The table is generic (every unordered pair, sorted, capped at `k`); the
  thinness is the fixture's, not the code's.
- **BUBR1 is a low-confidence protein.** 391 of 1,050 residues score below pLDDT 50 and the
  model's mean is 63.61, so with "dim low-confidence" on (the default) **just under half** the
  chain is drawn in grey. That is the correct picture of an AlphaFold model of a protein with
  large disordered stretches, and `protein-explorer-no-dim.png` is the same scene with the
  toggle off, for contrast.

## Conclusion

The exhibit is built, browser-verified and gated. Three things it establishes beyond the
picture:

1. **`viz3d`'s boundary held.** The exhibit is ~1,000 lines of page code and zero lines of
   three.js: it hands in a `Scene3D` and gets back a canvas, a text twin, a tooltip, camera
   presets and a URL-held pick. The module needed **no change** — the one deviation was to
   stop using its generic filter panel (which drops datums) in favour of de-emphasising, for
   the reason given above. That is the "another N-of-1 case adds a scene kind and nothing
   else" claim of `app/src/viz3d/README.md` surviving its first real consumer.
2. **The identity guard earns its place immediately.** It fired on the very first browser
   open, on a real deployment split, before any human looked at the picture.
3. **A distance is not a claim.** Every surface that shows one — the link label, the table's
   `geometric band` column, the provenance line, the dictionary entry — says what it is:
   geometry on a prediction, with the confidence at both ends printed next to it.

What is **not** built, and is not blocked: the partner-complex view (idea #2 of the design
note — AlphaFold serves single chains, so this needs an experimental PDB entry and
`ProteinStructure.partners` is empty today) and the cis/trans phase ribbon (idea #3).
