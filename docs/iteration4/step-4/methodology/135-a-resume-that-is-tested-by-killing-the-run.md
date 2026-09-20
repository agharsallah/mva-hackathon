# 135 — A resume that is tested by killing the run

**Written:** 2026-09-20. **Step:** `step-4` (iteration 4), opt-A substep A4.
**Hypothesis:** **H067 / `P4-5`** (filed 2026-09-20, *before* the test's assertions were written).
**Supersedes nothing.** It answers the "Resume is nominal" limitation entry
[128](128-one-command-eight-stages-and-three-things-a-fixture-could-not-catch.md) left open.

## Question

Does the DAG resume — that is, does a run killed part-way through pick up where it stopped
rather than redo what it already finished — and can that be *asserted* rather than asserted-at?

Before this entry, `--from <stage>` skipped two stages by name. Nothing on disk recorded what a
stage had finished, so the skip could only ever be a claim about the command line, never about
the work.

## Hypothesis and prediction

> **H067 / `P4-5`** — the zoo DAG resumes from any stage without recomputing a finished stage or
> a finished fan-out lane; a run killed mid-fan-out and restarted with the same config reproduces
> the uninterrupted run's outputs.

**Prediction.** With counting `Deps` injected, a workflow killed inside `fan_out` after the first
lanes and restarted makes exactly one `load_records`, one `load_registry`, one `load_pairs` and
one `score` call per lane in total across both attempts; the restarted run's `merged.json`,
per-model report JSON and merged report are identical (generation timestamps aside) to an
uninterrupted run of the same config, and exactly one manifest exists for the run id. On real
data, a second `mva-zoo run` of the same config restores all eight stages and finishes in a
fraction of the first run's wall-clock.

## What would refute it

Any deps call counter above one for a stage or lane finished before the kill; any output
byte-differing from the uninterrupted run beyond its generation timestamps; more than one
manifest for the run id; or a second real-data run that recomputes a stage whose inputs did not
change.

## What was built

A **checkpoint marker** (`src/mva/zoo/checkpoint.py`) per stage, under
`<out_dir>/checkpoints/<run_id>/<stage>.json`, written after that stage's table and lineage
write. It holds four things: the digest of everything the stage consumed, its row count, its
one-sentence note, and the slice of `RunState` it produced. The last field is what makes a skip
possible at all — a stage that is skipped must still hand the next stage what it would have
produced.

`src/mva/zoo/checkpoint_state.py` holds the per-stage capture/restore pair (split from
`checkpoint.py` at the 400-line rule: markers-and-digests is one concern, what-each-stage-holds
is another).

**Matching is by content, not by name.** The runner keeps a rolling digest:

```
chain₀    = seed(config)                        # the effective config, overrides included
inputsₖ   = H(chainₖ, deps.fingerprint(config, stageₖ))
chainₖ₊₁  = H(chainₖ, H(stateₖ))
```

A stage is restored only when its marker's `inputs_digest` equals `inputsₖ`. Three consequences,
each one a test:

| change | what stops matching | what re-runs |
|---|---|---|
| a different `--case-gene` | `seed(config)` — `config.digest` is the TOML's bytes and does **not** move for an override, so the run id and the checkpoint folder are shared | everything |
| one fewer allele in the record set | `deps.fingerprint(config, "normalize")` | everything |
| one lane's version bumped in `models.toml` | `fingerprint(config, "registry_check")`, then the lane key | that lane only |

**`Deps.fingerprint(config, stage)` is new** and is the honest part. A source stage's input is
the outside world, and a checkpoint of it would otherwise mask a source that changed underneath.
The hook is a *cheap* look at that source — the production bundle answers with
`count(*) FROM <results>.coding_alleles` for `normalize` and `rank_per_model`, and with the bytes
of `models.toml` + `models.d/*.toml` for `registry_check`. A bundle that returns `""` is saying
"I cannot tell"; the marker is then trusted, and only `--force` or `--from` re-reads that source.
That limitation is pinned by its own test rather than left to be discovered.

**Fan-out resumes per lane.** Each lane writes
`checkpoints/<run_id>/fan_out/<model>.json` — its scores, its venue, and the key
`H(seed(config), record ids, model, version)` — the moment it comes back. The stage-level marker
keeps only each lane's *digest*, so the scores live in exactly one file and a changed score still
moves the chain. Deliberately **not** keyed on the stage's chain digest: that carries every card
in the roster, so adding a fifth lane would re-score the four that did not change.

**`--from` and `--force` changed meaning.** `--from collect` now means "collect onwards is
stale"; the stages before it are restored from their markers (or run, when they have none). The
old reading — skip `fan_out` and `report_per_model` whatever came before — could produce a run
with no scores at all and a merged report whose rank was `None`. `--force` drops the markers and
recomputes.

## Commands

```bash
uv run pytest tests/test_zoo_resume.py -q                       # the kill test
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml        # run 1: cold checkpoints
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml        # run 2: every stage restored
```

## Observed — the kill test

`tests/test_zoo_resume.py`, 11 tests, green. The workflow runs in a thread; the cooperative kill
hook is injected through `Deps` (the third lane's `score` raises), so nothing is monkey-patched
and the call counters are the bundle's own.

| assertion | result |
|---|---|
| the kill leaves `normalize` + `registry_check` markers and **two** lane markers, no `fan_out.json` | ✓ |
| `load_records`, `load_registry`, `load_pairs` — 1 call each across both attempts | ✓ |
| the two lanes that *finished* before the kill — 1 `score` call each across both attempts | ✓ |
| the restart's whole call set is `{score: lane 3, score: lane 4, load_pairs}` | ✓ |
| `merged.json`, the four report JSONs and the merged report equal an uninterrupted run's | ✓ |
| exactly one manifest, private and public, named for the run id | ✓ |
| a changed record set re-scores every lane; a changed lane version re-scores that lane only | ✓ |
| a truncated marker reads as "not done" instead of raising | ✓ |
| a `--case-gene` override is not the same run | ✓ |

**One boundary the prediction stated too simply.** The lane the kill lands *inside* is scored
twice — once interrupted, once completed — because its work never came back. "One call per lane"
holds for every lane that **finished**; unfinished work is always redone. The test asserts both
halves (`total["score:revel"] == 2`, `killed.returned == lanes[:2]`,
`restart.returned == lanes[2:]`) rather than quietly weakening the claim.

## Observed — real data

Two consecutive `mva-zoo run` calls on the real warehouse, same config
(`it4-2962e3117b5c`), logs `build/it4/a4-run1.log` and `build/it4/a4-run2.log`.

| stage | run 1 (no checkpoints) | run 2 | run 2's note |
|---|---:|---:|---|
| normalize | 85.337 s | **0.171 s** | restored (39,286 records) |
| registry_check | 0.007 s | 0.005 s | **ran** — see below |
| fan_out | 107.982 s | **0.040 s** | restored (58,480 scores, 4 lanes) |
| collect | 0.106 s | **0.001 s** | restored (4 coverages) |
| rank_per_model | 336.693 s | **0.507 s** | restored (63,347 pairs, 402 rows, 16 genes skipped) |
| report_per_model | 9.271 s | **0.004 s** | restored (4 reports) |
| merge | 1.813 s | **0.001 s** | restored (RRF rank, catalogue-free: 20,639) |
| render | 0.004 s | **0.000 s** | restored (`docs/iteration4/report.md`) |
| **eight stages** | **541.21 s** | **0.73 s** | **741× — every stage but one restored** |

**The one stage that re-ran is the finding.** Between the two runs a parallel session added
`src/mva/zoo/models.d/esm2.toml` (01:01 local; run 1 ended 01:02, run 2 started 01:07). The
roster's *bytes* therefore changed, `registry_check`'s fingerprint moved, and the stage re-read
the roster — correctly. The four lanes this config selects were unchanged, so the stage's
**content** digest was unchanged, the chain did not move, and all six stages after it still
restored. Name-addressed invalidation would have re-run the whole DAG for a file that changed
nothing this run reads. This was not staged; it happened.

**One manifest per run id.** `build/it4/runs/` and `docs/iteration4/runs/` each hold
`it4-2962e3117b5c.json` (this config) and `it4-dcda40a4df2c.json` (the config before a parallel
session edited the TOML). Run 2 overwrote run 1's, as the run id demands.

**Checkpoint cost.** 29 MB under `build/it4/checkpoints/<run_id>/` — 17 MB of records, 11 MB of
pairs, 1.7 MB of lane scores, the rest under 100 KB. Gitignored, like everything else the case
writes. Restoring the two large ones is the 0.171 s and 0.507 s above (the second includes
re-deriving the ranking arithmetic from the restored pairs and scores).

### Three numbers that are **not** properties of the method

- **Run 1's 541 s is a contended machine**, not the DAG. Entry 128 measured the same eight
  stages at ≈ 15 s warm / 113 s on the first full pass. During run 1 two parallel sessions were
  hammering the same hosted Postgres (a GPN-MSA fetch and a Track-2 refresh). The comparison
  between run 1 and run 2 is still sound — they are minutes apart on the same machine — but
  541 s must not be quoted as the DAG's cost.
- **`rank_per_model`'s 336 s is a per-row `INSERT`.** `rank.write_ranks` issues one statement per
  row (402 rows), each a round trip to a remote database — the same shape entry 114 measured at
  ≈ 2,900 s for 39,286 rows. Batching it is a small change in `src/mva/zoo/rank.py`, which this
  group does not own; recorded here for whoever does.
- **Process wall-clock is not stage wall-clock.** `/usr/bin/time` reports 554.89 s for run 1 and
  317.38 s for run 2, of which run 2 used 4.79 s of CPU: `uv run` spent the rest blocked on the
  shared environment while a parallel session installed a dependency group. The stage numbers
  above come from the manifest and are the ones that mean anything.

## Verdict

**H067 / `P4-5` — supported**, with one refinement the prediction did not state precisely.

| prediction | observed |
|---|---|
| one `load_records` / `load_registry` / `load_pairs` across the killed attempt and the restart | ✓ (kill test) |
| one `score` call per lane | ✓ **for every lane that finished**; the lane the kill landed inside is scored twice, because its work never returned. The test asserts both halves |
| outputs identical to an uninterrupted run, timestamps aside | ✓ (kill test) |
| exactly one manifest for the run id | ✓ (kill test, and on real data) |
| a second real-data run restores every stage and finishes in a fraction of the first | ✓ 0.73 s against 541.21 s, seven of eight stages restored; the eighth re-ran because its source really had changed |

Nothing in the refutation list was observed. The refinement is recorded rather than smoothed
over: `mva-science hypothesis-revise` can change a status and a confidence but not a prediction's
wording, so the wording stands and this entry is where it is made precise.

## Limitations

- **A source the bundle cannot fingerprint is trusted.** `Deps.fingerprint` answers for
  `normalize`, `registry_check` and `rank_per_model`; anything else returns `""`, and a marker
  for such a stage is believed even if its source moved. `--force` is the escape hatch.
  `test_a_source_the_bundle_cannot_fingerprint_is_restored_and_the_docs_say_so` pins the
  behaviour so it cannot quietly become a surprise.
- **The two fingerprints are coarse.** A row count plus the mode will not notice a table whose
  rows changed without changing in number. A content hash of the source table would, at the cost
  of the scan the resume exists to avoid.
- **`normalize` restores records as dicts, not `AlleleRecord`s.** Every downstream reader goes
  through `_field` / `consequence_map`, which accept either; a future stage that reaches for an
  attribute would need the codec to rebuild the dataclass.
- **`rank_per_model`'s restore re-derives the ranking** from the restored pairs and scores rather
  than storing a nested dataclass tree. It is pure arithmetic over data the checkpoint already
  holds (0.507 s here), but it is a recomputation, and this is where it is declared.
- **The kill is cooperative**, injected through `Deps` in a thread, not a `SIGKILL` of a
  subprocess. It reproduces the state a signal between two lanes would leave — markers for what
  finished, nothing for what did not — and it is what makes the call counters observable. A
  signal arriving *during* a marker write is covered by the atomic write (temp file + rename),
  not by this test.
- **Checkpoints are per `(case, config, record set)` and live under `build/`.** They are a local
  cache, never an artifact: deleting the folder costs a re-run and nothing else.

## Next test

None owed by this claim. The open follow-ups are named above: batch `write_ranks`, and widen
`Deps.fingerprint` if a source is ever rebuilt without changing its row count.
