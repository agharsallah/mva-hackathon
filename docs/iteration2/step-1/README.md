# Step 1 — the blind target set

**Standing:** run 2026-09-10/11; verdicts committed. Iteration 2, `step-1`.

**Goal** (from `src/mva/science/steps.py`):

> Which genes do the child's symptoms alone nominate — a target set chosen with the DNA
> never read?

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H012 | held-out recall@300 ≥ 0.90 | **refuted** — 0.360 [0.295, 0.420] |
| H013 | a recessive chromosome-instability gene is in the set | **supported** — 33 of them |
| H014 | the two rankers agree on ≥ 50 % of the top 300 | **refuted** — 32.3 % |
| H015 | fewer than 20 % of protein-coding genes are uncurated | **refuted** — 73.6 % |

Three of four refuted, and the most consequential is H012: **no cutoff of a
phenotype-only ranker reaches 0.90 recall on this corpus**, so the target set is an
*enrichment*, never coverage. The full reasoning, the numbers and the decision that
follows are in [084](methodology/084-the-blind-target-set.md).

## Outputs

| Artifact | Where |
|---|---|
| target set, 404 rows, tiered | `results.it2_targets` (built under `build/it2/step-1/targets.tsv`) |
| matched decoy set, 396 rows | `results.it2_decoys` |
| gate numbers, tier counts, blind-spot size | `build/it2/step-1/summary.json` |
| inputs, sha256, release, seed, parameters | `build/it2/step-1/provenance.json` |
| four report figures + an interactive page | `figures/track1/iteration2/step-1/` |

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

## Reproduce

```
uv run python tools/build_it2_targets.py
uv run mva-phenotype benchmark --sample 200 --seed 20260910 --out build/it2/step-1/benchmark.json
uv run mva-phenotype agreement --limit 300 --out build/it2/step-1/agreement.json
uv run python tools/render_it2_step1_figures.py
uv run mva-warehouse pg-load-it2
uv run mva-science check --blind iteration2
```
