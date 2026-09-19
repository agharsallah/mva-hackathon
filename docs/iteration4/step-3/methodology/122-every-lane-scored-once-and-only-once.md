# 122 — Every lane scored, once and only once

**Written:** 2026-09-19. **Step:** `step-3` (iteration 4). **Run:** R3 of the wave-2 chain.
**Hypotheses tested:** H062 (plan label `P4-4a`).

Follows [119](../../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md), which
established that all four MVP lanes can be fetched, licensed and joined, and measured what each
one covers. This entry spends them: a cold pass over the whole record set into the append-only
score cache, the no-op re-run that proves the cache key, and the catalogue-aware pass that is the
other half of the plan's report-both rule (D4).

## Question

Can one contract — `Adapter.score(records) → ScoreRow` behind `mva-zoo score --model X` — serve
four lanes of three different kinds (a warehouse column, a downloaded table, a live REST plugin)
over ~39,300 records, cache every score with its provenance, cost nothing, and finish inside an
hour on this laptop? And does a re-run of the same `(model, version, allele_id)` insert nothing?

## Hypothesis and prediction

*Written before the first command ran.* Filed as H062 by
`uv run mva-science hypothesis-add --iteration iteration4 --step step-3 … --by wave2`.

| | |
|---|---|
| **Statement** | `P4-4a`: a cold MVP run — four lanes over the ~39,300 allele records — completes in at most one hour of laptop wall-clock at zero dollars. |
| **Prediction** | Scoring all four enabled lanes from an empty cache takes ≤ 3,600 s of wall-clock on this laptop, spends nothing, and every lane writes exactly one `warehouse.data_lineage` edge named `it4-score:<model>`. |

## What would refute it

*Written before the first command ran, quoted from [`plan.md` §5](../../plan.md).*

> The cold four-lane pass takes more than **4 hours** — then the join is profiled and the fix
> recorded.

Between 1 h and 4 h the claim is neither supported nor refuted by its own terms; the entry says
so and names the lane responsible rather than rounding.

Two correctness conditions that are **not** hypotheses:

* a second `score` of a lane already scored must report **inserted 0** — the cache key is
  `(model, version, allele_id)` and the cache is append-only;
* the two offline lanes must insert **0** rows under `--mode aware`, because neither reads
  `clin_sig`; a lane that inserts rows there is reading a catalogue field it should not.

## Inputs

| input | rows | role |
|---|---|---|
| `results.it4_allele_records` | 39,286 (15,620 `missense_variant`) | what every lane is asked about — [114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) |
| `warehouse.it2_insilico_annotations` | `am_pathogenicity` 10,601, `spliceai_ds_max` 32,534 non-null | the two warehouse lanes |
| `build/it4/tables/esm1b.parquet` | 169,457,840 rows, sha256 `cd1b009b…` | the ESM1b lane — [119](../../step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md) |
| Ensembl VEP REST, `REVEL=1` | live | the catalogue-adjacent lane |

**Starting state.** `warehouse.allele_scores` was **emptied** before the timing, so the "cold"
in the claim is literal. The append-only `data_lineage` list keeps the edges of the runs that
preceded the reset, including a 52-row REVEL edge whose rows no longer exist — the edge list
records attempts, the table records state, and the two are deliberately not the same thing.

## Commands

```bash
# cold, one lane at a time, timed
for m in alphamissense spliceai esm1b revel; do uv run mva-zoo score --model "$m"; done

# the no-op proof — the cache key is (model, version, allele_id)
uv run mva-zoo score --model alphamissense
uv run mva-zoo score --model spliceai
uv run mva-zoo score --model esm1b

# the catalogue-aware pass (plan D4, report-both)
uv run mva-zoo score --model alphamissense --mode aware
uv run mva-zoo score --model spliceai    --mode aware
uv run mva-zoo score --model esm1b       --mode aware
```

## Observed

### The cold pass

| lane | wall-clock | inserted | dollars |
|---|---|---|---|
| AlphaMissense | **15 s** | 10,601 | 0 |
| SpliceAI | **27 s** | 32,534 | 0 |
| ESM1b | **11 s** | 4,562 | 0 |
| REVEL | **6,267 s** (4 attempts) | 10,783 | 0 |
| **total** | **6,320 s = 1 h 45 m 20 s** | **58,480** | **$0** |

The three offline lanes together take **53 seconds** for 47,697 rows. Everything else is one
remote lane.

**REVEL needed four attempts**, because Ensembl's public endpoint failed mid-pass three times:

| attempt | wall-clock | inserted | how it ended |
|---|---|---|---|
| 1 | 4,922 s | 9,462 | `500 server error` — 12,800 of 14,692 alleles answered |
| 2 | 438 s | 420 | `503 server error` — 600 of 1,892 answered |
| 3 | 682 s | 696 | `503 server error` — 1,000 of 1,292 answered |
| 4 | 225 s | 205 | complete |

Realised REVEL coverage: **10,783 of 15,620 missense alleles (69.0 %)** — the lane's true
number, and the one to quote. (`mva-zoo coverage --model revel` prints 100 %; a remote lane
cannot know what the server will answer until it asks. Entry 119 already flagged that.)

### Two fixes this run needed, both from measurement

**1. An interrupted pass threw away everything it had.** The lane wrote its checkpoint once,
after the whole pass returned, so the first 500 discarded **1,238 s of replies** and left the
lane with nothing. It now writes after every batch and stops without discarding: attempts 1–3
above each *kept* what they had, which is why four attempts cost 6,267 s rather than four full
passes. Recorded as `VepRestAdapter.incomplete` and printed by the CLI, so an interrupted pass
reads as interrupted rather than as a lane with poor coverage.

**2. The lane asked about alleles it cannot score.** REVEL is missense-only, yet the pass asked
about all 39,286 records — three of every four requests bought a guaranteed null. At the
measured **~85 s per 200-allele batch**, the unrestricted pass was on course for **≈ 4.6 h**.
The lane now asks only about the consequence classes its card's `input_class` names
(`missense` → 15,620 alleles). Both fixes are in `d553034`, committed before this run's result.

### The no-op, and the catalogue-aware pass

| lane | second run | `--mode aware` |
|---|---|---|
| AlphaMissense | inserted **0**, skipped 10,601 | inserted **0**, skipped 10,601 |
| SpliceAI | inserted **0**, skipped 32,534 | inserted **0**, skipped 32,534 |
| ESM1b | inserted **0**, skipped 4,562 | inserted **0**, skipped 4,562 |

Both correctness conditions hold. **What each one does and does not prove**, stated because the
two are easy to conflate: the cache key is `(model, version, allele_id)` and does *not* include
the mode, so `inserted 0` under `--mode aware` shows the key is honoured, not by itself that the
lane ignores `clin_sig`. The reason these three lanes cannot read a catalogue field is
structural — AlphaMissense and SpliceAI read one numeric column of
`it2_insilico_annotations`, ESM1b reads a static published table, and none of the three is
handed `clin_sig` at all. The masking is still applied before the adapter sees a record
(`--mode catalogue-free` nulls `CATALOGUE_FIELDS`), so the ablation is real for a lane that
*would* read it. REVEL, the one lane that could leak, is not run in `aware` mode here: it is
catalogue-adjacent by training, which is a property of the model, not of this record set.

### Lineage and the confirmed pair

Fourteen `it4-score:%` edges — one per lane per invocation, including the no-op runs (target
rows 0) and the pre-reset REVEL sample. The cache holds **58,480** rows across four
`(model, version)` pairs.

| allele | AlphaMissense | ESM1b | REVEL | SpliceAI |
|---|---|---|---|---|
| `93e077ae83ac2642` (missense) | **0.9229** | **11.537** | **0.472** | 0.00 |
| `addc19de8fa29228` (`stop_gained`) | — | — | — | **0.03** |

Entry 119's prediction lands exactly: **only SpliceAI has a number for both halves of the
confirmed pair, and both of its numbers are essentially zero.** The three lanes that rate the
missense allele highly (AlphaMissense 0.92 of 1; ESM1b 11.5 on a scale whose observed range here
is −13.6 to 17.9) have nothing at all to say about its partner.

## Evidence recorded

| evidence | direction | claim |
|---|---|---|
| cold four-lane pass = 6,320 s (1 h 45 m 20 s) at $0 — above the hour predicted, below the four hours that refute | neutral | H062 |
| the three offline lanes score 47,697 alleles in 53 s; 6,267 s of the total is one remote lane over four attempts | neutral | H062 |
| every lane wrote its `it4-score:<model>` lineage edge; a second run of each inserted 0 | supports | H062 |

## Verdict

**H062 (`P4-4a`) — `testing`: the prediction failed, the refutation threshold was not reached.**
The claim predicted ≤ 3,600 s and pre-registered > 4 h as refuting. The measurement is
**6,320 s — 1.76× the prediction and 0.44× the refutation line**, so neither clause fires and
the honest verdict is that the claim is *undecided by its own terms*. Confidence 0.15: the
number is 76 % over, and nothing about the run suggests it was unlucky.

**The lane responsible is named, as the refutation clause asks.** It is not a join —
the three lanes that *are* joins finish 47,697 alleles in **53 seconds**. It is one remote
service: 6,267 s of the 6,320 is REVEL, over four attempts, on a public endpoint that failed
three times. Two fixes already took it from ≈ 4.6 h to 1 h 45 m. The remaining and obvious third
is **parallelism**: this pass is strictly serial, and iteration 2's own VEP pass runs three
workers (`tools/annotate_it2_insilico.py --workers 3`). Three workers would put the cold pass
near 35 minutes and inside the claim. That is a named, costed fix, not a widened threshold, and
it is the revision this claim is owed.

**The $0 half of the claim is unambiguous.** Nothing was spent: three lanes are local, one is a
free public endpoint, no GPU was touched.

## Limitations

- **Serial by construction.** `hgvs_pass` and this lane both write one checkpoint file, so
  neither has a `workers` argument. Adding one is ~15 lines plus a lock, and it is the single
  change that decides `P4-4a`.
- **The timing includes three server-side failures.** A run on a healthier endpoint would be
  faster and a run on a worse one slower; 6,320 s is what this endpoint gave on 2026-09-19, not
  a property of the code alone.
- **REVEL's 69.0 %** is a realised coverage over the alleles it was asked about; the 4,837
  missense alleles with no REVEL score are ones the server answered without the field.
- **`--mode aware` proves the cache key, not the absence of a leak** — see above.
- **The cache was emptied to make "cold" literal**, so the lineage edge list contains edges for
  rows that no longer exist. That is the intended asymmetry, but a reader counting edges will
  not get the row count.

## Next test

Step 4 (R4): `mva-zoo run --config src/mva/zoo/zoo.example.toml` — the eight stages end to end,
`results.it4_model_ranks`, the run manifest, and the check that `PairBuild.skipped_genes` is
empty and the confirmed pair is flagged exactly once.
