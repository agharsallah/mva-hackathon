# Figures — generated report artifacts

**Standing:** generated output, not source. Everything here is regenerable; nothing is
hand-edited. Last checked 2026-09-19 — the two `track1/` rows below were added then
(methodology [126](../docs/step-0/methodology/126-every-iteration-on-the-steps-page.md)); the
rest was last checked 2026-09-03.

Every file here is also served by the API and shown on `/steps`: a step's figures are
`GET /api/steps/<iteration>/<slug>/figure/<name>`, listed on the step's card.

Three self-contained HTML pages, each opening from the filesystem with no server and no
build step. Only Plotly's runtime is fetched from a CDN; every style, behaviour and data
point is inlined. All three come off one renderer, [`src/mva/render/`](../src/mva/render/),
so the palette and the shell are shared.

| File | What it is | Regenerate with |
|---|---|---|
| `explore-report.html` | the full exploration report — twenty exhibits over the committed data profile, each with its caption and legend | `uv run mva-explore report ressources/data-profile` |
| `science-report.html` | the research record — the method, the step goals, the hypothesis board, the evidence ledger, the oracle budget, and the methods form. **Currently renders as empty**, because no hypothesis has been recorded yet; that is the honest state, not a broken page | `uv run mva-science report --from docs/science-register.json` |
| `locus-fixture.html` | the locus browser rendered over the **synthetic** `tests/fixtures/mini.vcf`, so the page can be committed | `uv run mva-explore locus tests/fixtures/mini.vcf --out figures/locus-fixture.html` |
| `track1/*.png` + `track1/funnel.json` | iteration 1's three exhibits — the filtering funnel, every biallelic gene against the phenotype ranking, and the decode table — embedded by `submissions/track1/iteration-1/report.md` and cited by methodology 070, 071 and 074/076 | `uv run python tools/render_track1_figures.py` |
| `track1/<iteration>/step-<n>/*` | the per-step exhibits of one research iteration, PNG for the report and self-contained HTML for the interactive version. This is the convention; `track1/*.png` and `track2/*.png` predate it, and the steps that drew them name their files in the step map so they are still served | the step's own `tools/render_it2_step<n>.py` |
| `track2-report.html` + `track2/*.png` | Track 2's step-7 exhibits — the evidence ladder matrix, the rung funnel, the decoy overlap, the paediatric pointers, the drug × mechanism literature — rendered from `build/track2/analysis.json` and nothing else; every number is the enrichment run's | `uv run python tools/track2_enrich.py && uv run python tools/render_track2_figures.py` |

`locus-fixture.html` is deliberately built from the fixture rather than the real callset:
the locus views are the only ones that read patient records, and a page built from the real
VCF must be written outside the repository. `science-report.html` is committed for the same reason it is safe to: the register holds no
genomic positions, and [`mva-science export`](../docs/method.md) refuses to write one. See
[`docs/step-0/exploration.md`](../docs/step-0/exploration.md),
[`docs/method.md`](../docs/method.md), and the
[data-handling perimeter](../README.md#data-handling--read-this-first).

## `exhibits/` — screenshots of the React app's exhibits

PNGs, captured from a real browser (Chromium headless with software WebGL) against
[`app/`](../app/README.md) in **fixture mode**, so they are safe to commit and safe to put in
the report. One row below states its own exception and why it is still safe. Regenerate by starting the app with its API pointed at a dead port
(`cd app && VITE_API_URL=http://127.0.0.1:8901 pnpm dev`) and driving the page; the run that
produced these, and every number visible in them, is recorded in
[methodology 057](../docs/step-0/methodology/057-protein-explorer-exhibit.md).

> **Fixture:** real AlphaFold backbone, synthetic candidate alleles. The fold in every image
> below is the true `AF-O60566-F1` v6 model of BUBR1 (public reference data, identical for
> every human); the alleles painted on it come from the **synthetic** gene-structure fixture,
> so no distance shown means anything clinically. Genes outside the eight-gene annotated panel
> carry **no allele at all**, real or synthetic — the callset was only annotated over the panel
> BED, so those images are the fold and nothing else, which is what their callouts say.

| File | The view it shows |
|---|---|
| `protein-explorer-domain.png` | the default view — iso camera, colour by domain, low-confidence residues dimmed |
| `protein-explorer-plddt.png` | the same fold coloured by pLDDT (AlphaFold's own per-residue confidence), which is what makes the prediction visibly a prediction |
| `protein-explorer-pair.png` | a candidate pair picked, drawn as a labelled Cα-distance link, with the closest-pairs table under it |
| `protein-explorer-focus.png` | "focus on selection" — the chain trimmed to the picked residues, which is what refits the camera |
| `protein-explorer-no-dim.png` | the same scene with "dim low-confidence" off, for contrast: how much of BUBR1 is below pLDDT 70 |
| `protein-explorer-mismatch.png` | the honest failure — the model and the gene structure naming different translations, so **nothing is painted** |
| `protein-compare.png` | two folds side by side — BUB1B against TRIP13, one colour-by (pLDDT), one camera preset, cameras synced, with the two-column fact sheet under them |
| `protein-compare-offpanel.png` | the same comparison with side B on a **fold-only** gene (CENATAC): the fold is drawn, no allele is painted, and the callout says the annotation never ran there |
| `protein-metrics.png` | the cross-gene metrics table over the whole structure set, plus the pLDDT ≥ 70 % bar chart coloured by group — the two allele columns read `n/a — fold only` outside the annotated panel |
| `viz3d-style-guide.png` | the `viz3d` module's own demo on `/style-guide` (the palette as a point cloud) |
| `provenance-reference.png` | `/provenance` § *The public inputs* — one row per provenance manifest (a lockfile for data: URL + version + hash), expanded to its inputs and outputs tables. Not a 3D exhibit; captured the same way |
| `status-board-masked.png` | `/status` — the whole dependency board, **captured live** (not in fixture mode) with addresses masked, which is the default state: every host and port renders `••••`, and each card carries its own `re-probe`, `latency · budget` and `probed … ago`. Safe to commit for the same reason it is the default: the mask is what the page shows unless a reader presses `show`. Recorded in [methodology 065](../docs/step-0/methodology/065-health-controls.md) |

`.gitignore` excludes `figures/exhibits/*` — the per-page HTML copies are regenerable noise —
with one negation, `!figures/exhibits/*.png`, for exactly these screenshots: a browser is needed
to regenerate them, and they carry nothing that could not be published.

The `exhibits/<page>/*.html` files are a different thing and come from the Python renderer,
not the app: they are the standalone exhibits of `explore-report.html`, one file each.
