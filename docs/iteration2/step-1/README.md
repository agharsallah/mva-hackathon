# Step 1 — the blind target set

**Standing:** run 2026-09-10/11, re-tested at the full population 2026-09-12; all four verdicts
committed and the step is marked **done** in `src/mva/science/steps.py`. Iteration 2, `step-1`.

**Goal** (from `src/mva/science/steps.py`):

> Which genes do the child's symptoms alone nominate — a target set chosen with the DNA
> never read?

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H012 | held-out recall@300 ≥ 0.90 | **refuted** — 0.335 [0.318, 0.350] over the full population ([091](methodology/091-recall-at-the-full-population.md)); 0.360 [0.295, 0.420] on the 200-disease sample it was first tested on |
| H013 | a recessive chromosome-instability gene is in the set | **supported** — 33 of them |
| H014 | the two rankers agree on ≥ 50 % of the top 300 | **refuted** — 32.3 % |
| H015 | fewer than 20 % of protein-coding genes are uncurated | **refuted** — 73.6 % |

Three of four refuted, and the most consequential is H012: **no cutoff of a
phenotype-only ranker reaches 0.90 recall on this corpus**, so the target set is an
*enrichment*, never coverage. The full reasoning, the numbers and the decision that
follows are in [084](methodology/084-the-blind-target-set.md).

**[091](methodology/091-recall-at-the-full-population.md) removed the sampling.** 084's first
stated limitation was that the curve came from 200 of 3,240 eligible diseases. The whole
population has now been run on the same seed and release: recall@300 = **0.335
[0.318, 0.350]**, inside the sample's own interval, with an interval 3.9× narrower (theory
predicts 4.0) and 901 of 3,240 genes unrankable at any N. H012's verdict is unchanged and no
revision was filed; what changed is that the number quoted downstream no longer carries a
sampling caveat — and is slightly worse, not better.

## Outputs

| Artifact | Where |
|---|---|
| target set, 404 rows, tiered | `results.it2_targets` (built under `build/it2/step-1/targets.tsv`) |
| matched decoy set, 396 rows | `results.it2_decoys` |
| gate numbers, tier counts, blind-spot size | `build/it2/step-1/summary.json` |
| inputs, sha256, release, seed, parameters | `build/it2/step-1/provenance.json` |
| four report figures + an interactive page | `figures/track1/iteration2/step-1/` |
| full-population recall curve, 3,240 diseases | `build/it2/step-1/benchmark-full.json` |
| all of the above as one JSON surface | `GET /api/steps/step-1`, rendered at `/steps/step-1` and on `/phenotype` |

The tables are derived and stay under `build/`; the warehouse copies carry
`data_lineage` rows naming **both** the public HPO release and the clinical phenotype
document.

## Tools this step needed

| Tool | Why |
|---|---|
| `mva.phenotype.targets` | tiering, the mechanism-term rule, the seeded decoy draw |
| `mva.phenotype.benchmark` + `mva-phenotype benchmark` | H012's recall curve |
| `mva.phenotype.network` | the `uncurated` tier, which H015 made the headline blind spot |
| `mva.pipeline.inheritance` | the mode-of-inheritance prior (consumed by step 4) |
| `mva.science.steps.STEPS_BY_ITERATION` | one step map per iteration — the platform fix step 1 needed first |
| `mva-science check --blind` | the gate that holds every iteration-2 entry to its declared inputs |
| `tools/build_it2_targets.py`, `mva-warehouse pg-load-it2` | build and load, with provenance |
| `mva.viz.steps_it2_step1` (`GET /api/steps/step-1`) | the step's numbers as one JSON surface — counts, fractions and curves, no coordinate and no gene symbol |
| `app/src/pages/Step1.tsx` + `pages/steps/step1/*`, `pages/phenotype/Reach.tsx` | the deep page and the four exhibits `/phenotype` gained |

## Reproduce

```
uv run python tools/build_it2_targets.py
uv run mva-phenotype benchmark --sample 200 --seed 20260910 --out build/it2/step-1/benchmark.json
uv run mva-phenotype benchmark --sample 3240 --seed 20260910 --out build/it2/step-1/benchmark-full.json  # 091, ~2h16m
uv run mva-phenotype agreement --limit 300 --out build/it2/step-1/agreement.json
uv run python tools/render_it2_step1_figures.py
uv run mva-warehouse pg-load-it2
uv run mva-science check --blind iteration2
```
