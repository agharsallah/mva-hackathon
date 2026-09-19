# Step 3 — The inference API

**Standing:** **run 2026-09-19**; `P4-4a` (H062) tested and **undecided by its own terms** — the
step is marked **open** in `src/mva/science/step_maps/iteration4.py` because the claim is owed a
revision, not because anything is unrun. Iteration 4, `step-3`.

**Goal** (from `steps.py`):

> Can one batch inference API serve every model through the same contract, cache every score with provenance, and dispatch GPU work without sending more than a sequence window?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 3*. The MVP is the adapter protocol, the cache and
the in-process CLI; HTTP routes and Modal are opt-A / opt-B and are not built.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H062 (`P4-4a`) | a cold four-lane pass finishes in ≤ 1 h at $0 | **testing** — measured **1 h 45 m 20 s at $0**: 1.76× the prediction, 0.44× the 4 h that refutes ([122](methodology/122-every-lane-scored-once-and-only-once.md)) |

**58,480 scores cached** across four `(model, version)` pairs, every row carrying its model,
version, digest, licence, venue and run id, and every lane one `it4-score:<model>` lineage edge.

| lane | wall-clock | rows |
|---|---|---|
| AlphaMissense | 15 s | 10,601 |
| SpliceAI | 27 s | 32,534 |
| ESM1b | 11 s | 4,562 |
| REVEL (4 attempts, 3 server failures) | 6,267 s | 10,783 |

**The three local lanes score 47,697 alleles in 53 seconds.** Everything else is one remote
service — so the claim's fate rests on parallelism, not on a join. Two fixes already took REVEL
from ≈ 4.6 h to 1 h 45 m (per-batch checkpointing so an interrupted pass keeps what answered;
asking only about the consequence classes the card's `input_class` names). The third — three
workers, as iteration 2 already runs on the same service — would put the pass near 35 minutes.

**The cache key holds.** A second run of each offline lane inserted 0 and skipped all of them,
and `--mode aware` likewise inserted 0. What that proves and what it does not is spelled out in
the entry: the key is `(model, version, allele_id)` and does not include the mode, so the
mode-independence of these three lanes is structural (none of them is handed `clin_sig`), not
demonstrated by the zero.

**The confirmed pair, every lane:**

| allele | AlphaMissense | ESM1b | REVEL | SpliceAI |
|---|---|---|---|---|
| missense `93e077ae83ac2642` | 0.9229 | 11.537 | 0.472 | 0.00 |
| `stop_gained` `addc19de8fa29228` | — | — | — | **0.03** |

Only SpliceAI has a number for both halves, and both of its numbers are essentially zero. This
was predicted in [step 2's entry](../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md)
before steps 4–6 ran.

## Outputs

| Artifact | Where |
|---|---|
| 58,480 scores, append-only, with provenance | `warehouse.allele_scores` |
| one edge per lane per invocation (14) | `warehouse.data_lineage`, `transform LIKE 'it4-score:%'` |
| REVEL's answers, resumable, ids and numbers only | `build/it4/vep-REVEL/answers.jsonl` (gitignored) |

## Limitations

Stated by entry 122, beside the result rather than under it.

- **Serial by construction.** One worker, one request at a time. Entry 122: adding parallelism
  is "~15 lines plus a lock, and it is the single change that decides `P4-4a`" — three workers
  would put the cold pass near 35 minutes.
- **The timing includes three server-side failures.** 6,320 s is what a free public endpoint
  gave on 2026-09-19, not a property of the method.
- **REVEL's 69.0 % is a realised coverage**, not the published table's: the 4,837 missense
  alleles with no REVEL score are ones the server answered *without* the field.
- **`--mode aware` proves the cache key, not the absence of a leak.** It shows the two modes
  are stored apart; it does not show a model never saw a catalogue.
- **The cache was emptied to make "cold" literal**, so the lineage edge list contains edges for
  rows that no longer exist. Append-only means nothing is deleted to tidy that up.

## Reproduce

```bash
for m in alphamissense spliceai esm1b revel; do uv run mva-zoo score --model "$m"; done
uv run mva-zoo score --model alphamissense              # the no-op proof
uv run mva-zoo score --model alphamissense --mode aware  # the ablation
```

## Methodology

[`methodology/122`](methodology/122-every-lane-scored-once-and-only-once.md) — the cold timing,
the two fixes it forced, the no-op and aware passes, and the verdict.
