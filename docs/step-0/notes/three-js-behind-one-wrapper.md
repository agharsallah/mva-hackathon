# three.js enters behind one wrapper — and only where the third dimension *is* the finding

**Standing:** **built 2026-09-03** — §3 (the module) and the first exhibit of §5 shipped on
that date; the rest of §5 has not. Originally explored the same day by three read-only surveys
of the repo (domain value, app architecture, failure diagnostics). Every number marked
*measured* was observed in this checkout then; nothing was run against the warehouse. What
shipped, and what did not, is in [§5](#5-build-order). Revisit when React 19 lands (§3) or when
an alignment (BAM/CRAM) exists (§1).

What landed:

| Piece | Where | Verified |
|---|---|---|
| the server route + a committed real AlphaFold fixture (§5.1) | `src/mva/viz/proteinstructure.py`, `src/fixtures/data/panel-protein-structure.json` | [methodology 056](../methodology/056-protein-structure-endpoint.md) |
| the `viz3d` module — raw three, one wrapper, lazy, `lib`-only (§3) | [`app/src/viz3d/`](../../../app/src/viz3d/README.md) | that README's Verified line |
| the protein exhibit on `/panel` (§5.3, first half) | [`app/src/pages/panel/protein/`](../../../app/src/pages/panel/protein/ProteinExplorer.tsx) | [methodology 057](../methodology/057-protein-explorer-exhibit.md) |
| the **structure gene set** — `GET /api/panel/structure-genes`, free-form display groups carrying their own label and rank (this case uses `panel` / `mva-sac` / `extended`), per-gene real AlphaFold fixtures — so the exhibit is no longer one gene | `ressources/reference/structure_genes.tsv`, `src/mva/viz/geneset.py`, `app/src/fixtures/data/{protein,gene-structure}/<SYMBOL>.json` | [methodology 060](../methodology/060-structure-gene-set.md) |
| the **side-by-side comparison** — two folds, one colour-by, one camera preset, one confidence toggle, cameras syncable; a two-column fact sheet under them | [`app/src/pages/panel/protein/compare/StructureCompare.tsx`](../../../app/src/pages/panel/protein/compare/StructureCompare.tsx) | `StructureCompare.test.tsx` (picker grouping, URL state, 422, off-panel callout) |
| the **cross-gene metrics table** + its pLDDT bar chart — one row per gene in the set, each row its own request pair and its own loading/error state | [`app/src/pages/panel/protein/compare/StructureMetricsTable.tsx`](../../../app/src/pages/panel/protein/compare/StructureMetricsTable.tsx) | `metrics.test.ts` (17 cases on the reduction) |
| a **controlled camera** in the module: `CameraPose3D`, `Viz3dCanvas.pose` / `onPose`, `Viewer.getPose` / `setPose` — what makes "sync cameras" possible without a page touching three | [`app/src/viz3d/spec/types.ts`](../../../app/src/viz3d/spec/types.ts), `core/viewer.ts` | `Viz3dCanvas.test.tsx` (adopts a pose, never echoes it) + `camera.test.ts` (`poseDistance`) |

The one rule the widening had to carry: **only the eight annotated panel genes may show an
allele.** The callset was annotated over the panel BED, so an off-panel gene's empty candidate
list is a statement about the pipeline's scope, never about the proband — every off-panel
canvas therefore carries a callout saying so, and every off-panel allele cell reads
`n/a — fold only` rather than `0`. A non-coding gene stays in the set as a reference row and
gets no canvas at all (the route answers 422; the client also knows from `StructureGene.coding`
and does not spend the request).

What did **not**: the partner complex (idea #2), the cis/trans phase ribbon (idea #3), and both
2D failure-locator exhibits of §4. None is blocked by the module; each is its own piece of work.

## The question

Can a WebGL 3D view in the React app make a human see *what is wrong* in this genome, and
locate the failure, faster than the Plotly 2D exhibits already there? And can it land as a
reusable module another N-of-1 case picks up unchanged?

## The answer in one line

Yes, for **one** exhibit: the candidate protein in 3D with both alleles painted on residues.
No, for every other idea surveyed. 3D earns its place only when the third dimension *is* the
finding (two residues close in space; two physical chromosome copies), never as a spare
channel for a scalar a 2D chart already shows.

## 1. What the repo itself rules out

| Fact in the repo | Where | Kills |
|---|---|---|
| No aneuploidy signal. Every autosome sits on the 0.5 allele-balance line at mean depth; only Y is flagged, expected for a male sample | `app/src/pages/Genome.tsx` headline callout; [data-findings §2](../../../ideation/data-findings.md) | a 3D karyotype extruding BAF/depth — it renders a flat plate. The only bump would be the fixture's planted fake arm, self-labelled "a deliberate lie" in `app/src/fixtures/shape/baf-bins.ts` |
| No BAM/CRAM in the delivery | [data-findings §1](../../../ideation/data-findings.md) | any 3D read pileup — zero input |
| 99.7 % of the pair grid is *unknown* phase (BUB1B: 1,653 pairs, 3 trans / 2 cis) | [data-findings §2.4](../../../ideation/data-findings.md) | a pair-score *surface* — it manufactures continuity over categorical sparsity on an arbitrary axis order |
| Failure sets are tiny or empty by design: 7 dependency checks, 9 funnel rows, 7 lineage edges, probe ledger 0 of 6, science register not yet created | `docs/current-state.md`; `app/src/pages/status`, `provenance`, `probes`, `science` | every "3D failure locator". A 7-node DAG rotated into a scene loses the hover-an-edge affordance that carries `transform`/`tool` |
| Interaction data for the SAC pathway was left out on purpose | `src/mva/phenotype/__init__.py` | a 3D pathway graph — and a force-directed hairball has no natural embedding anyway. The repo's own rule already prescribes committed Mermaid/SVG for pathway structure |
| Bundle budget headroom is **11.85 kB raw / 3.94 kB gzip** (*measured*: 248.15 / 80.06 kB against 260 / 84 kB in `app/tools/bundle-budget.mjs`) | `app/dist`, build of 2026-09-02 | any *static* import of three — `three.module.min.js` r0.185.1 is 365.6 kB raw / 87.1 kB gzip (*measured*) |

Ranking of everything surveyed, by (judge value + analyst value) / effort:

| # | Idea | Analyst value | Gimmick risk | Verdict |
|---|---|---|---|---|
| 1 | Protein structure, both alleles painted, domains coloured | high — only view answering 3D adjacency and partner interface | low | **build first** |
| 2 | …extended to the partner complex (BUB3 / CDC20 interface) | high | low | phase 2 of #1 |
| 3 | cis/trans phase ribbon explainer beside `PairMatrix` | none; teaching value high | medium | build second, cheaply |
| 4 | SAC pathway | low | low *in 2D* | build as Mermaid/SVG, not 3D |
| 5 | HPO similarity embedding | low — the useful output is a top-10 list, already emitted by `GeneScore.summary` | medium-high | skip |
| 6 | Pair-score surface | negative — implies false continuity | high | skip |
| 7 | 3D karyotype | negative — dresses a null result | high | skip |
| 8 | 3D read pileup | n/a | high | blocked, no BAM |
| 9 | 3D lineage / dependency / probe-ledger "failure locators" | negative — cardinality 4–20 rows | high | skip; 2D alternatives in §5 |

## 2. The exhibit to build: the protein in 3D

**Why 2D cannot do it.** `app/src/pages/panel/DomainLollipop.tsx` puts amino acids on a 1D
axis and answers "which domain". It is blind to the two questions that decide a compound
heterozygote (two different broken copies of one gene, one from each parent):

- are the two alleles' residues *spatially adjacent* — two hits packing into one binding
  pocket versus two hits on opposite faces. Sequence distance is a poor proxy for 3D distance;
- does a residue sit on a *partner interface* — BUBR1's KEN box binds CDC20, its TPR region
  binds BUB3. An interface residue is a mechanism claim usable in Track 2.

**The data is nearly all on the wire.** `GeneStructure` (`app/src/api/types/panel.ts`) already
carries `protein` (the Ensembl translation id), `protein_length`, `domains[start_aa, end_aa]`
and `candidates[].protein_pos` — exactly the residue index a painter needs.

**The unlock is a filter change, not an integration.** `src/mva/viz/genestructure.py:23-26`
documents that Ensembl's `/overlap/translation/<ENSP>` *already returns* the AlphaFold model
reference and the PDB `sifts` cross-references, and the code discards them as "not domains".

**Fetching stays server-side.** AlphaFold DB (`https://alphafold.ebi.ac.uk/api/prediction/{acc}`,
resolve `cifUrl` and version from the reply, never hardcode `model_v4`), RCSB
(`https://files.rcsb.org/download/{id}.cif`) and UniProt REST are public and keyless. The
browser still never calls them: `genestructure.py` gives the three reasons the repo forbids
browser-to-third-party calls, so the route is a new `/api/panel/protein-structure` in
`src/mva/viz/routes_panel.py` that proxies and disk-caches the mmCIF like the existing Ensembl
cache. Fixture mode keeps working for free.

**Perimeter win.** The gene-structure payload is public reference data plus derived protein
offsets — "holds nothing that could not be published". The 3D protein view inherits that, so
it is the one patient-informative figure whose screenshot can go straight into the public
report and the Track 2 video. Locus and pileup views cannot.

**Honesty the exhibit owes.** AlphaFold is a prediction. pLDDT (per-residue confidence) must
be visible; stretches below ~70 are painted `C.unmeasured`, not a domain colour, and support
no spatial claim. The `Legend` line says so.

**Renderer.** Do not hand-write a cartoon renderer on raw three (weeks). Lazy-import a
three-based molecular viewer that parses mmCIF: 3Dmol.js (smallest), NGL (better quality),
Mol* (heaviest). Estimate: 1.5–2 days including the proxy route; +0.5 day for the partner
complex.

### Data contracts

> **Superseded by the shipped code.** The contract that exists is
> [`app/src/api/types/protein.ts`](../../../app/src/api/types/protein.ts) (`ProteinStructure`,
> `ProteinResidue`, `SecondarySegment`, `ProteinPartner`) and it is not the draft below: the
> route serves a **parsed per-residue alpha-carbon trace**, not the raw coordinate file, so the
> browser needs no mmCIF parser and no second structure library. `data`/`format`/`url`/`plddt[]`
> below became `residues[{n, aa, ca, plddt}]` + `model_url` + `protein_length`. `ResiduePaint`
> was never built as a type: the page maps `GeneCandidate` straight into a `viz3d` `Datum3D`
> (see `app/src/pages/panel/protein/buildScene.ts`). Read the draft for the *reasoning*; read
> the types file for the shape.

```ts
/** GET /api/panel/protein-structure?gene=… — server-proxied, disk-cached, publishable. */
export interface ProteinStructure {
  gene: string;
  /** MUST equal GeneStructure.protein, or every painted residue is on the wrong sequence. */
  protein: string;
  uniprot: string | null;
  provenance: 'alphafold' | 'pdb';   // prediction vs experiment — never silently mixed
  url: string;                        // the resolved source, verbatim, for the provenance line
  format: 'mmcif' | 'pdb';
  data: string;                       // coordinate file, unmodified; parsed by the viewer
  version: string | null;             // as resolved from the source API
  plddt: number[] | null;             // index i = residue i+1; null for a PDB entry
  covered: [number, number][];        // residue ranges the model covers; a gap is unmeasured
  partners: { chain: string; uniprot: string | null; label: string }[];
}

/** One residue to highlight. Built in the browser from GeneStructure.candidates. */
export interface ResiduePaint {
  residue: number;                    // GeneCandidate.protein_pos, 1-based
  label: string;                      // GeneCandidate.label
  tone: Tone;                         // impactTone(candidate.impact)
  rare: boolean;                      // false renders hollow, matching the lollipop
  allele: 'left' | 'right' | null;    // which half of the selected pair
}
```

The cis/trans ribbon (#3) needs no endpoint: `PanelHetPair{phase, auto}` from `useHetPairs`,
rendered with `unknown` as a distinct third state — never defaulted to cis or trans.

## 3. How three.js enters the app: raw `three`, one wrapper, lazy

**Decision: raw `three@^0.185`, wrapped by one in-repo component mirroring
`app/src/components/Plot.tsx`. Not `@react-three/fiber`.** The decider is the React 18 pin,
not size (*measured* via `pnpm view`):

| Package | latest | peer |
|---|---|---|
| `three` | 0.185.1 | none |
| `@react-three/fiber` | 9.7.0 | `react >=19 <19.3` — blocked |
| `@react-three/fiber@8` | 8.18.0 | `react >=18 <19` — a terminal release, types authored against three ≤0.16x |
| `@react-three/drei` | 10.7.8 | needs fiber 9 |

Adopting fiber today means adopting 8.18.0 and redoing the integration at React 19. Raw three
needs no peer, ships its own types, and the repo already has the precedent, the lint-rule
shape and the budget gate for "one wrapper owns the heavy lib".

### Module layout — `app/src/viz3d/`, case-agnostic

```
app/src/viz3d/
  README.md            boundary contract + Mermaid diagram with a Legend line
  index.ts             the ONLY entry pages import
  spec/                Scene3D, Datum3D, Axes3D, ColorEncoding, Selection3D; describeScene()
  adapters/            data -> typed geometry buffers. Pure. The real test surface.
  core/                loadThree.ts (the one import('three')), capability.ts (hasWebGL),
                       colorRamp.ts, scene.ts, camera.ts, pick.ts
  hooks/               useSceneSelection.ts  — Selection3D <-> lib/urlstate
  components/          Viz3dCanvas.tsx (<canvas role="img">), SceneFallback.tsx
```

Top-level, not under `components/`, because `components` may import `api` and that coupling
is exactly what makes a module non-transferable. **`viz3d` imports `lib` only, never `api`**:
the page maps this case's API rows into a `Scene3D`; `viz3d` never learns what a
`DensityBinRow` is. Another case adds a `Scene3D` variant and an adapter, nothing else.

### The generic contract

```ts
export type Scene3D =
  | (SceneBase & { kind: 'surface';   grid: SurfaceGrid })
  | (SceneBase & { kind: 'points';    points: readonly Datum3D[]; radius?: number })
  | (SceneBase & { kind: 'karyotype'; chromosomes: readonly ChromosomeBar[] })
  | (SceneBase & { kind: 'protein';   backbone: readonly Vec3[]; residues: readonly Datum3D[] });

interface SceneBase { title: string; axes: Axes3D; color: ColorEncoding }
interface ColorEncoding { scale: Colorscale; domain: [number, number]; lowMeans: string; highMeans: string }
interface Datum3D { id: string; label: string; at: Vec3; value: number; tone?: Tone; meta?: Record<string, string | number | null> }

/** Adapter output — no three import, unit-tested. */
export interface GeometryBuffers {
  positions: Float32Array; colors: Float32Array; indices?: Uint32Array;
  pickTable: readonly { id: string; from: number; to: number }[];   // raycast hit -> datum id
  bounds: { min: Vec3; max: Vec3 };
}
```

Selection is a controlled prop: `highlighted` ids live in the URL via `useUrlState`, so one
URL (`?bins.3d=1&bins.pick=…&bins.view=top`) cites one 3D figure, the property
`lib/urlstate.ts` was written for.

### Colour

`new three.Color(C.grid)` with `renderer.outputColorSpace = SRGBColorSpace`; per-vertex ramps
via a new `colorRamp.ts` that interpolates the *existing* `Colorscale` stops, so a 3D surface
and the 2D heat strip of the same data are the same numbers
([colour is generated](colour-is-generated.md)). It parses hex out of generated stops and
never writes one, so both colour lint rules stay green. Theme is dark only (*measured*:
`index.css` sets `color-scheme: dark`, no light palette exists), so no reactivity.

### AI export and accessibility, one artefact

`describeScene(scene)` returns a structured summary (kind, axes with units, colour encoding
with what low/high mean, object count, top/bottom-k, highlighted ids) plus a deterministic
prose paragraph. It is `Exhibit`'s `data` prop, the canvas's `aria-label`, and the body of
`SceneFallback` — a real `<ul>` of `<button>`s that is the keyboard path and the no-WebGL
rendering. Axes are in bins/Mb/index units, so the no-coordinates rule holds.

### Gates that would fail, and the fix

| Gate | Failure | Fix |
|---|---|---|
| boundaries lint | `src/viz3d/**` matches no element type; `default: 'disallow'` reports `pages -> viz3d` | add the `viz3d` element, its `lib`-only policy, and `'viz3d'` to the pages/components/test `anyOf` lists |
| `no-restricted-imports` | a page importing `three` inlines it into the entry chunk | add `three` to the *same* `paths` array as `plotly.js-dist-min`, ignoring only `src/viz3d/core/loadThree.ts` |
| jsx-a11y under `--max-warnings 0` | `onClick` on `<canvas>` | `role="img"` + `aria-label`; pointer listeners via `ref` in the effect; keyboard through `SceneFallback` |
| `modules.test.tsx` (*measured*) | jsdom `getContext` emits `jsdomError: Not implemented` → `console.error` → gate 2 fails for every page mounting a canvas | one line in `src/test/setup.ts`: `HTMLCanvasElement.prototype.getContext = () => null`, so `hasWebGL()` is false and the fallback renders |
| `a11y.test.tsx` | loops the whole manifest; a nameless canvas fails `role-img-alt` | the `aria-label` above |
| `bundle-budget` | one static import blows the 3.94 kB gzip headroom | dynamic import only; add `/three/i`-not-in-initial and `three`-chunk-exists guards next to the Plotly ones |
| `react-refresh/only-export-components` | a component file exporting a type as a value | types in `spec/types.ts`; component files export the component only, the `Plot.tsx`/`plotLayout.ts` split |

Two rows above were **wrong when the module was actually built**, and the corrections are worth
keeping because both were surveyed rather than run:

- **three ships no types.** `three@0.185.1` contains zero `.d.ts` files (*measured* on install),
  contradicting "needs no peer, ships its own types" in §3. `@types/three` is a required dev
  dependency.
- **the jsdom `getContext` claim did not reproduce.** On jsdom 25.0.1 / vitest 3.2.7 the call
  returns `null` and vitest prints the `jsdomError` to **stderr**; a `console.error` spy recorded
  zero calls, so `modules.test.tsx` would not have failed. The stub is in `src/test/setup.ts`
  anyway — it silences a 12-line stack per mount and makes `hasWebGL()` deterministic.

One gate the survey did not predict: `eslint` `max-lines: 400`. The exhibit is eight files
(`buildScene`, `encodings`, `distances`, `filters`, plus four components) for that reason.

## 4. What "locate failures faster" actually needs — and it is 2D

Nineteen failure signals were inventoried (dependency down, fixture fallback, chunk load
error, job failed, QC filter drop, funnel stage drop, variant vetoed and why, cis-excluded
pair, hash mismatch, fingerprint discrepancy, derivation run, hypothesis refuted, probe
outcome, k-mer verdict…). None has the cardinality where a third axis helps. Two exhibits
would help, both 2D and both cheaper than three:

- **First-failed-stage matrix.** One row per annotated panel allele, one boolean per funnel
  stage, sorted by the stage that removed it; click a cell to land on `/panel?gene=…` or
  `/compare?cmp.gene=…&cmp.a=…`. Needs a table that does not exist: `analysis_funnel.py`
  computes per-allele survival inside a CTE chain and keeps only 9 counts. Owner: a new
  `src/mva/warehouse/analysis_dropout.py` registered in `DERIVATIONS`, allele grain, panel
  scope only, joining on the bare contig per the [chr-prefix bridge](chr-prefix-bridge.md).
  Free cross-check: its `failed_at` counts must reproduce `candidate_funnel`'s deltas.
- **Health overlay on the existing lineage DAG.** A pure client-side join of
  `DependencyCheck.powers[]` with `LineageRow` / `DerivationRow` / `SourceObjectRow`, colouring
  the SVG nodes already drawn in `pages/provenance/LineageGraph.tsx`; a broken node links to
  `/status#<check.id>` where the remedy already lives. No new endpoint.

Three gaps found on the way, independent of any visual: a failed `pg-derive` leaves no row
(`derivation_runs` has no status column); `src/mva/warehouse/integrity.py` has no endpoint and
no exhibit; nothing asserts every `results` table has a lineage edge.

## 5. Build order

Status as of 2026-09-03: 1, 2 and the first half of 3 are **done**; the rest is **not**.

1. **Done.** Server: keep AlphaFold/`sifts` refs in `genestructure.py`; add the proxied, cached
   `/api/panel/protein-structure` route and a committed public AlphaFold fixture for BUB1B
   (public reference data, not synthetic — label it so). It serves a parsed Cα trace rather
   than the mmCIF, which is the one deviation from §2's draft contract.
2. **Done.** App: `src/viz3d/` landed with the boundaries element, the `no-restricted-imports`
   rule, the jsdom canvas stub and both bundle-budget guards.
3. **Half done.** Exhibit: the protein view on `/panel` is built — painted from
   `GeneStructure.candidates`, five colour encodings, pLDDT visible and dimmed below 70,
   per-encoding `Legend` and `reading`, Cα distances between every placed pair, the picked pair
   in the URL. **Not done:** the partner-complex chain (AlphaFold serves single chains; this
   needs an experimental PDB entry and `partners[]` is empty today) and the cis/trans ribbon.
4. **Partly done.** Docs: `app/src/viz3d/README.md` written; `app/README.md`'s stack row split
   2D/3D. Dictionary has **AlphaFold**, **pLDDT**, **mmCIF**, **alpha carbon**, **ångström**,
   **Cα distance**. **Still missing:** **WebGL**, **three.js**, **scene graph**, **raycasting**.

> **Legend:** table rows only — no diagram in this file.
