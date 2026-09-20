# 136 — The two write verbs, behind a job and behind a token

**Written:** 2026-09-20. **Step:** `step-3` (iteration 4), opt-A substep A3.
**Hypotheses:** **none.**

This entry declares no hypothesis, on the two conditions [`method.md`](../../../method.md) sets
for a machinery entry inside a research step:

1. **Why.** It builds an *instrument* — an HTTP surface over machinery entry
   [122](122-every-lane-scored-once-and-only-once.md) already measured. "`POST /api/zoo/score`
   writes the same cache rows `mva-zoo score` writes" is true or false regardless of what this
   child's genome says; evidence cannot refute it, a re-run can.
2. **Which hypotheses it serves.** None directly. It is the substep plan §5 step 3 labels
   *opt-A: needed only for dashboard-triggered runs*, and the claim it eventually serves
   (`P4-4`, cost and wall-clock of a full zoo) is opt-B and unfiled.

## Question

Can the dashboard start a scoring pass or a whole DAG run without a terminal — and can that be
done without (a) a second job system, (b) a second implementation of "score one lane", or
(c) handing an unauthenticated caller the machine's CPU?

## What was built

`src/mva/viz/api_zoo_jobs.py`, mounted in `app.py` beside the read-only zoo router.

| verb | route | body / result |
|---|---|---|
| POST | `/api/zoo/score` | `{model, allele_ids?, mode?, config?}` → `{job_id}`; the job's summary is `{model, version, mode, run_id, requested, inserted, skipped, coverage, incomplete, wall_clock_seconds}` |
| POST | `/api/zoo/run` | `{config?, from_stage?, force?}` → `{job_id}`; the job's summary is the run manifest's coordinate-free copy |
| GET | `/api/zoo/jobs` | every zoo job, newest first |
| GET | `/api/zoo/jobs/{id}` | one job |
| GET | `/api/zoo/jobs/{id}/wait?timeout=` | long-poll, capped at 290 s |

Three decisions carry the work:

**The job manager is reused, not rebuilt.** `mva.reads.api.jobs.Manager` already runs the k-mer
scans behind `/api/jobs`: a worker pool, a JSON history on disk, `queued → running →
done | failed | cancelled | lost`, and a long-poll that blocks server-side. The zoo routes
submit into it. One lifecycle to reason about, one snapshot shape, one place where "finished
answers survive a restart" is implemented.

**The score job is the CLI's body, in process.** It makes the same four calls `mva-zoo score`
makes — `adapters.build` → `coverage_of` → `cache.write` → `cache.lineage_row` — rather than
shelling out. A subprocess would need its own connection and its own `.env`, and its failure
would arrive as an exit code instead of an exception the job can report. The consequence that
matters: a score written through the API is indistinguishable from one written at the terminal,
cache key and lineage edge included.

**Compute needs a token.** Every `/api/*` route already carries the `X-API-Key` guard, which is
*absent* when `MVA_VIZ_TOKEN` is empty — the correct setting for a loopback read service, and an
indefensible one for a route that spends an hour of CPU and appends to the warehouse. So the two
`POST`s refuse outright, with the reason in the reply, when the token is empty. The `GET`s stay
open, because on such a deployment they can only report on jobs that were never allowed to start.

**Coordinate-free at the boundary.** Rows are inlined only when the caller named the alleles and
there were ≤ 500 of them; a lane's free-form `aux` — the one field on this route that is not
coordinate-free *by construction*, because a model writes it — is filtered against
`FORBIDDEN_AUX` on the way out, in the route as well as in the job body.

## Commands

```bash
uv run pytest tests/test_viz_zoo_jobs.py -q
# live smoke, against the real warehouse:
MVA_VIZ_TOKEN=… uv run mva-viz-api --port 8912
curl -s -X POST localhost:8912/api/zoo/score -d '{"model":"spliceai","allele_ids":[…200…]}'
```

## Observed

### The tests

`tests/test_viz_zoo_jobs.py`, 15 green. The two job bodies are injected
(`api_zoo_jobs.Runners`), so the routes, the manager and the payload shaping are the real ones
and only the warehouse work is replaced. The case is a fabricated one in `tmp_path` (gene
`GENEG`, prefix `demo`), so a route that hard-coded this project's case fails.

### The live smoke, against the real warehouse

Two servers: one with `MVA_VIZ_TOKEN` set (port 8912), one without (8913).

| request | reply |
|---|---|
| `POST :8913/api/zoo/score` (open API) | **403** — *"…is disabled: MVA_VIZ_TOKEN is empty, so this API is open. A route that spends the machine's CPU and appends to the warehouse needs the shared token set (the read routes do not)."* |
| `POST :8913/api/zoo/run` (open API) | **403** |
| `GET :8913/api/zoo/jobs` (open API) | **200**, `[]` |
| `POST :8912/api/zoo/score` with no `X-API-Key` | **401** |
| `POST :8912/api/zoo/score`, `{model: spliceai, allele_ids: […200…]}` | **200** `{"job_id":"f88cb662fa02","verb":"zoo-score","state":"running","params":{"model":"spliceai","alleles":200,"mode":"catalogue-free"}}` |
| `GET :8912/api/zoo/jobs/f88cb662fa02/wait?timeout=120` | **200**, `state: done` |

The job's summary:

```json
{"model": "spliceai", "version": "SpliceAI via VEP plugin (iteration 2 annotation pass)",
 "mode": "catalogue-free", "run_id": "20260920T080817Z-64e2",
 "requested": 200, "inserted": 0, "skipped": 171,
 "coverage": {"scored": 171, "total": 200, "fraction": 0.855},
 "incomplete": "", "wall_clock_seconds": 5.935}
```

**`inserted: 0` is the point.** These 200 alleles were already in `warehouse.allele_scores` from
entry [122](122-every-lane-scored-once-and-only-once.md)'s cold pass, and the cache key
`(model, version, allele_id)` skipped every one of them. A second identical submission returned
the same numbers. The API cannot double-write the cache because it does not own the rule — the
cache does.

**171 rows came back inline** (≤ 500 asked for), each `{allele_id, model, version, score, aux,
venue, ts}`. `aux` held exactly `{"mode", "spliceai"}` — the mode the job stamped and the lane's
own four-delta string. No coordinate-shaped key in any reply; `_coordinates()` walks the whole
payload in the test and the smoke's replies were checked the same way.

**The 29 alleles with no row are the lane's blind spot, not a failure:** SpliceAI's realised
coverage over this slice is 85.5 %, which is a measurement, and the summary reports it beside
`requested` rather than implying 200 scores.

### The DAG verb

`POST :8912/api/zoo/run {}` → job `0789153f39f9` → `done`, and its summary is the manifest:
run `it4-2962e3117b5c`, wall-clock **0.754 s**, `dollars 0.0`, **all eight stages `skipped: true`**
— the resume built in entry [135](../../step-4/methodology/135-a-resume-that-is-tested-by-killing-the-run.md)
seen through HTTP. `outputs` carries no `build/` path, because the job returns
`Manifest.public()`, not `Manifest.to_json()`.

## Limitations

- **`ts` is `null`.** The contract names it, but `mva.zoo.cache.read` does not select the column,
  so the route returns `null` rather than an empty string that would read as "the epoch". Filling
  it is a one-column change in `cache.py`, which this group does not own.
- **One worker.** The manager runs a single zoo worker, so two submitted scoring jobs queue
  rather than run together. That is deliberate while every lane writes the same cache table from
  one laptop; it is a constructor argument when it stops being right.
- **No cancel route.** `/api/jobs/{id}/cancel` exists for the reads API because a k-mer scan hands
  the manager a DuckDB `interrupt`. A zoo job has no equivalent handle yet, so offering cancel
  would be offering a button that does nothing.
- **The refusal is about the token, not about authorisation.** Any holder of `MVA_VIZ_TOKEN` may
  spend the machine. There is one shared secret in this deployment, not per-caller identity.
- **The smoke used 200 of 39,286 alleles** — enough to prove the path and the idempotence, not a
  load test. A whole-callset submission through this route has not been run.
- **`config` in the request body names a file on the server.** It is parsed by the same
  `Config.load` the CLI uses and a bad path is a 400, but a caller who holds the token can point
  the server at any TOML it can read.

## Next test

None owed. The dashboard page that calls these routes is the dashboard agent's work; this entry
is the contract it can build against.
