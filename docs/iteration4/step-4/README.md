# Step 4 — The workflow DAG

**Standing:** **run 2026-09-20** (resume; the DAG itself 2026-09-19); a machinery step — it files no hypothesis (see
[`method.md`](../../method.md), *the carve-out*). Marked **done** in
`src/mva/science/step_maps/iteration4.py`. Iteration 4, `step-4`.

**Goal** (from `steps.py`):

> Does a checkpointed DAG run the whole zoo end-to-end, resumably, from one command — and what does it cost in wall-clock and dollars?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 4*. Resume and its kill test (`P4-5`) are opt-A
and are **built** (entry [135](methodology/135-a-resume-that-is-tested-by-killing-the-run.md));
the read-only allele pairing substep is opt-A and is not built.

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


## The resume (opt-A, 2026-09-20)

Every stage writes a checkpoint marker under `<out_dir>/checkpoints/<run_id>/<stage>.json` after
its table and lineage write, and a stage whose marker matches the inputs it would read is
*restored* rather than run. Matching is by **content**: a chain seeded with the effective config
and advanced by each stage's own content digest, plus a cheap `Deps.fingerprint` of the source
that stage reads from outside the process.

| | run 1 (no checkpoints) | run 2 |
|---|---:|---:|
| eight stages | **541.21 s** | **0.73 s** (741×) |
| stages restored | 0 | 7 of 8 |

The eighth, `registry_check`, re-ran because a parallel session had added
`src/mva/zoo/models.d/esm2.toml` between the two runs — the roster's bytes moved. Its *content*
for the four lanes this config selects did not, so nothing downstream re-ran. Claim **H067 /
`P4-5`** — supported at 0.90. `--from <stage>` now re-runs that stage onwards (restoring what
came before); `--force` drops the markers.

A third run through `--from render` (entry
[139](methodology/139-the-render-stage-keeps-every-narrative-and-the-manifest-says-which.md))
restored seven stages in 0.69 s and re-rendered the merged report **byte for byte**, both
section-5 versions intact — the stage used to delete the LLM-synthesised one. The manifest now
records the method the page realised (`fusion+synthesis` only when a synthesis is on it), and
that value survives a resume through the render checkpoint.

Limitations, stated by entry 135: a source the bundle cannot fingerprint is trusted until
`--force`; the two fingerprints are coarse (a row count will not notice rows that changed without
changing in number); `rank_per_model`'s restore re-derives its ranking arithmetic; the kill in
the test is a cooperative hook in a thread, not a signal to a subprocess.

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
- **Resume is real since entry 135**, and carries its own limits: a source the bundle cannot
  fingerprint is trusted until `--force`; the two fingerprints are row counts and file bytes;
  `rank_per_model`'s restore re-derives its ranking; the kill test's kill is cooperative.
- **`read_only_percentiles` is unused** — the read-only alleles are ranked like any other.
- **Two earlier manifests were deleted before committing**, so the run folder shows the run
  that completed, not the two that died on the faults the entry records.

## Reproduce

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml   # again: every stage restored
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml --force   # recompute everything
uv run pytest tests/test_zoo_resume.py -q                  # the kill test
```

## Methodology

[`methodology/128`](methodology/128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md)
— the run, the manifest, the skipped genes, and the three faults.
[`methodology/135`](methodology/135-a-resume-that-is-tested-by-killing-the-run.md)
— the checkpoints, the kill test, and the two real-data runs that bracket them.
[`methodology/139`](methodology/139-the-render-stage-keeps-every-narrative-and-the-manifest-says-which.md)
— the render stage's two faults, and the run that proves the fix.
