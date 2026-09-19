# Iteration 4 — run manifests

**Standing:** written by `mva.zoo.workflow` on every `mva-zoo run`; re-verify by re-running.

One JSON per run: run id, config digest, model versions, venues, wall-clock per stage, and
dollars. These are the coordinate-free copies — the private copies, with the `build/` output
paths, stay under `build/it4/runs/`. The run id is derived from the config digest, so the same
configuration re-run is the same run id, not a new one.

Read with [`../plan.md`](../plan.md) §5 step 4 (the DAG) and the step-4 methodology entry that
files the run.
