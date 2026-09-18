# Step 4 — dictionary terms, draft

**Standing:** drafted 2026-09-18 by the wave-1 *rank + report + merge* agent, against
`fixtures/it4/` only. Not merged: the one dictionary is
[`docs/dictionary.md`](../../dictionary.md) and the wave-3 *docs* agent merges these entries in
dependency order. Nothing here is a result.

Source for every entry: [`docs/iteration4/plan.md`](../plan.md) §5 (step 4),
`src/mva/zoo/workflow.py`, `workflow_types.py`, `workflow_stages.py`, `rank.py`, `pairs.py`,
`src/mva/zoo/zoo.example.toml`.

Insert in the order below — each entry only uses words defined above it.

---

**DAG (directed acyclic graph)** — a set of steps with arrows saying which must finish before
which, and no arrow ever leading back to where it came from. A build graph, not a loop.
*Example: iteration 4's is a straight line of eight — `normalize → registry_check → fan_out →
collect → rank_per_model → report_per_model → merge → render` (`mva.zoo.workflow.STAGES`).*
*Context: the shape of `mva-zoo run`; "acyclic" is the property that lets the runner compute an
order once and never revisit a stage · source: src/mva/zoo/workflow.py · related: idempotent
stage, checkpoint, run manifest · first seen 2026-09-18*

**stage** — one function of the DAG: it takes what the earlier stages left in memory, writes its
own table and its lineage row, and returns one sentence about what it did.
*Example: `rank_per_model` turns the callset's pairs plus four lanes of scores into
`results.it4_model_ranks` and reports `20 pairs, 40 rows`.*
*Context: `mva.zoo.workflow_stages` holds all eight; they share the signature
`(config, state, deps, connection) -> StageResult` so the runner needs no knowledge of any of
them · source: src/mva/zoo/workflow_stages.py · related: DAG, idempotent stage, checkpoint ·
first seen 2026-09-18*

**idempotent stage** — a stage that can be run again without doing its work twice. Re-running
produces the same tables, the same files and no duplicate rows.
*Example: `rank_per_model` checks `SELECT count(*) … WHERE run_id = ?` before inserting; the
second `mva-zoo run` with the same config inserts nothing and the row counts are unchanged
(`tests/test_zoo_workflow.py::test_running_twice_writes_the_warehouse_rows_once`).*
*Context: what makes a pipeline safe to interrupt — the property a resume depends on, tested
here even though resume itself is plan §5 step 4's optional substep · source:
src/mva/zoo/workflow_stages.py · related: stage, checkpoint, run id · first seen 2026-09-18*

**checkpoint** — the line a stage prints (and the file it leaves) saying it finished and what it
produced, so a reader of the log knows exactly how far a run got.
*Example: `[it4-26f9edadfb7b] fan_out  0.002s  200 scores over 4 lanes`.*
*Context: printed by `mva.zoo.workflow.run` after every stage; the same facts are stored per
stage in the run manifest · source: src/mva/zoo/workflow.py · related: stage, run manifest ·
first seen 2026-09-18*

**run id** — the name of one run, derived from the sha256 of its configuration file rather than
from a clock. Two runs of the same configuration share a run id and are therefore the same run.
*Example: `it4-26f9edadfb7b` — `it4-` plus the first 12 hex characters of the digest of
`src/mva/zoo/zoo.example.toml`.*
*Context: `Config.run_id`; it is what every warehouse row of iteration 4 is stamped with, and
what makes "already written" a question the workflow can answer · source:
src/mva/zoo/workflow_types.py · related: idempotent stage, run manifest, config digest ·
first seen 2026-09-18*

**run manifest** — one JSON file per run recording what ran and what it cost: run id, config
digest, each model's version, where each lane ran, wall-clock per stage, and dollars.
*Example: `build/it4/runs/it4-26f9edadfb7b.json`, with a coordinate-free copy at
`docs/iteration4/runs/it4-26f9edadfb7b.json` (the copy drops the `build/` output paths).*
*Context: the measured answer to the methods form's runtime-and-cost question (plan §5 step 4);
written by `mva.zoo.workflow._write_manifest` · source: src/mva/zoo/workflow.py · related: run
id, checkpoint, stage · first seen 2026-09-18*

**dependency injection (the `Deps` bundle)** — passing a stage the functions it should call
instead of letting it import them, so the same stage code runs against the warehouse in
production and against `fixtures/it4/` in a test.
*Example: `Deps.fixtures("fixtures/it4")` reads the synthetic records, score tables and pairs;
`Deps.warehouse(connection)` reaches `mva.zoo.record`, `registry`, `adapters` and `cache`.*
*Context: why `tests/test_zoo_workflow.py` monkey-patches nothing — a failing test is a real
failure, not a patch that drifted · source: src/mva/zoo/workflow_types.py · related: stage,
DAG · first seen 2026-09-18*

**biallelic pair (candidate)** — two heterozygous changes in the same gene proposed as the two
broken copies. The unit iteration 4 ranks; a single allele is never ranked on its own.
*Example: `Pair(gene="GENEG", left_id="2b8ad1d8610e11e6", right_id="975e7ef6fd24556f",
phase="trans", is_confirmed=True)` — the flagged pair of `fixtures/it4/pairs.tsv`.*
*Context: built by `mva.zoo.pairs.pairs_from_alleles`, which delegates the pairing and the
phase verdict to the existing `mva.pipeline.compound_het` rather than re-implementing either ·
source: src/mva/zoo/pairs.py · related: compound heterozygote, phase, allele id ·
first seen 2026-09-18*

**pair score (the bottleneck rule)** — a pair's score under one model is `(min, max)` of its two
allele scores, sorted by `min` first: a pair is only as damaging as its weaker half, because a
gene with one intact copy usually still works.
*Example: alleles at 0.95 and 0.62 give `(0.62, 0.95)`; that pair loses to one scored
`(0.71, 0.74)` even though the first contains the more damaging single allele.*
*Context: `mva.zoo.rank.pair_score`; deliberately parameter-free so the ranking carries nothing
a reviewer has to take on trust · source: src/mva/zoo/rank.py · related: biallelic pair,
unscored pair, percentile · first seen 2026-09-18*

**unscored pair** — a pair one model could not score because it had no number for one of the two
alleles. It is **excluded** from that model's ranking and counted, never scored zero.
*Example: on the fixtures, `esm1b` excludes all 20 pairs (`unscored_pairs = 20`) and is recorded
as having no opinion, which is a different statement from ranking them last.*
*Context: `RankTable.unscored_pairs`, printed in every per-model report and in the merged
report's lane table · source: src/mva/zoo/rank.py · related: pair score, coverage ·
first seen 2026-09-18*

**percentile (this repo's convention)** — a position counted **from the top**, in percent.
Rank 1 of 20 is `5.0`; rank 20 of 20 is `100.0`. Smaller is better, and "top decile" means
`percentile <= 10`.
*Example: the confirmed pair at rank 3 of 1,200 pairs is `0.25 %`.*
*Context: used for pairs (`ConfirmedRank.percentile`) and for single alleles among a lane's
scored alleles (`left_percentile`, `right_percentile`); stated on every table that prints one,
because the opposite convention is equally common in the literature · source:
src/mva/zoo/rank.py · related: pair score, unscored pair · first seen 2026-09-18*
