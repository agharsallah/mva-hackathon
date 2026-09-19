# Step 4 — The workflow DAG

**Standing:** **run 2026-09-19**; a machinery step — it files no hypothesis (see
[`method.md`](../../method.md), *the carve-out*). Marked **done** in
`src/mva/science/step_maps/iteration4.py`. Iteration 4, `step-4`.

**Goal** (from `steps.py`):

> Does a checkpointed DAG run the whole zoo end-to-end, resumably, from one command — and what does it cost in wall-clock and dollars?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 4*. Resume and its kill test (`P4-5`) are opt-A
and are **not** built; the read-only allele pairing substep is opt-A and is not built.

## What happened

`uv run mva-zoo run --config src/mva/zoo/zoo.example.toml` runs eight stages end to end on the
real warehouse in **≈ 15 s warm (113 s on the first full pass), $0**:

| stage | seconds | rows |
|---|---|---|
| normalize | 4.78 | 39,286 records |
| registry_check | 0.01 | 4 lanes |
| fan_out | 6.61 | 58,480 cached scores |
| collect | 0.10 | 4 coverages |
| rank_per_model | 1.49 | 63,347 pairs → 402 rank rows (0 on a repeat: the run id *is* the config digest) |
| report_per_model | 0.43 | 4 reports |
| merge | 1.44 | RRF rank, catalogue-free: **20,639** |
| render | 0.00 | `docs/iteration4/report.md` |

**The confirmed pair is flagged exactly once** — `BUB1B` yields one pair, so the
truncating-plus-missense rule was not needed to disambiguate.

**`skipped_genes` is not empty.** Sixteen genes exceed the 60-heterozygous-call cap and are
skipped whole: AHNAK2, CARMIL1, CELF2, GRM8, HLA-DRB1, LRP1B, LTBP1, MUC16, MUC3A, MUC6, OR8U1,
PDE3A, PDZD2, RYR3, SUGCT, ZNF717 — all high-diversity or repeat-rich loci. `BUB1B` is not among
them, but every "all biallelic pairs" number in this iteration means *all pairs outside these
sixteen genes*.

Per-lane ranking of the confirmed pair: only **SpliceAI** has an opinion (rank 11,980 of 50,696,
23.63 %). AlphaMissense, ESM1b and REVEL each scored at most one half and are recorded as having
**no opinion**, not a bad one.

**Three faults only real data could expose**, each committed before the entry:

| fault | effect | commit |
|---|---|---|
| the result schema and the lineage schema were one argument | the DAG died after `collect` | `91a7156` |
| the DAG read the score cache out of the result schema | **no error** — 0 scores, nothing ranked, RRF `None` | `58c0ae5` |
| `Deps.hpo_row` was never supplied | every report said the 8 HPO terms produced no `BUB1B` row — the table ranks it **#14 of 5,267** | `58c0ae5` |

## Outputs

| Artifact | Where |
|---|---|
| per-lane ranks, 402 rows | `results.it4_model_ranks` |
| the seven-section report JSON, 4 rows | `results.it4_model_reports` |
| the run manifest | `build/it4/runs/it4-dcda40a4df2c.json` |
| its coordinate-free copy | [`../runs/it4-dcda40a4df2c.json`](../runs/it4-dcda40a4df2c.json) |
| four per-model reports, the merged report | [`../reports/`](../reports/), [`../report.md`](../report.md) |

## Limitations

Stated by entry 128, beside the result rather than under it.

- **Sixteen genes are not in the pair set.** `MAX_CALLS_PER_GENE = 60` skips them (60 calls is
  already 1,770 pairs); they are named in the entry, never silently dropped. Every "of N pairs"
  in steps 4-6 means the pairs outside those genes.
- **The manifest's per-stage seconds are for a warm run.** A cold run's cost is step 3's
  6,320 s, and entry 128 says explicitly that the two must not be added.
- **Resume is nominal.** `--from <stage>` skips stages; there is no kill-mid-fan-out test, so
  claim `P4-5` is *not* claimed here.
- **`read_only_percentiles` is unused** — the read-only alleles are ranked like any other.
- **Two earlier manifests were deleted before committing**, so the run folder shows the run
  that completed, not the two that died on the faults the entry records.

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml
```

## Methodology

[`methodology/128`](methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)
— the run, the manifest, the skipped genes, and the three faults.
