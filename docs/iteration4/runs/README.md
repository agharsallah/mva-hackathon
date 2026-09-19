# Iteration 4 — run manifests

**Standing:** written by `mva.zoo.workflow` on every `mva-zoo run`; re-checked 2026-09-19.
Re-verify by re-running.

One JSON per run: run id, config digest, model versions, venues, wall-clock per stage,
dollars, and (from 2026-09-19) a `pairs` block with the genes the pair builder skipped as too
dense to pair. These are the coordinate-free copies — the private copies, with the `build/`
output paths, stay under `build/it4/runs/`.

**A manifest names the config digest that produced it, and a config edit is a new run.** The
run id is `<table_prefix>-<first 12 of the config file's sha256>`, so the same file re-run is
the same run — which is what makes every stage safe to repeat — and any edit starts a different
one. Concretely: the committed manifest here is **`it4-dcda40a4df2c`**, produced by
`src/mva/zoo/zoo.example.toml` *before* the `[case]` block was added; the shipped config now
digests to **`it4-cf39acb4d64c`**. That is the mechanism working, not drift — the R1 results of
entries 114-130 belong to `it4-dcda40a4df2c` and are not restated under the new id, and no
re-run was made. See [`../../notes/zoo-case-config.md`](../../notes/zoo-case-config.md) for why
the case now lives in the config, and [`../reusability.md`](../reusability.md) for running it on
another case.

`it4-dcda40a4df2c.json` predates the `pairs` block and does not carry one; a reader must treat
its absence as *not recorded*, never as *nothing was skipped* (16 genes were — entry 128).

Read with [`../plan.md`](../plan.md) §5 step 4 (the DAG) and the step-4 methodology entry that
files the run.
