# 109 — Blind, from the reads and the symptoms, did iteration 2 find the same pair?

**Unblinds:** yes.

**Written:** 2026-09-18. **Step:** `step-6` (iteration 2).
**Hypotheses:** **H041 refuted**, **H044 supported**. Both were filed before
[107](107-the-routes-and-which-of-them-earned-a-rank.md) ran.

**Supersedes nothing.** It is the first entry of iteration 2 permitted to read an
iteration-1 candidate table, and from this entry onwards every later entry may too. The
ranking it compares was frozen and hashed in
[108](108-the-ranking-frozen-before-anyone-looked.md) **before this entry existed**.

## Hypothesis and prediction

* **H041** — the fused ranking places iteration 1's confirmed pair at rank 1, **and** no
  admitted ranking route places that pair below rank 3. *Predicted:* fused rank 1, and each
  of `phenotype`, `likelihood` and `knowledge` ranks it 3 or better.
* **H044** — a second oracle upload is not informative. *Predicted:* expected information
  gain of 0.000 bits for every candidate row layout, so the default of no second upload
  stands.

## What would refute them

* H041: the fused rank 1 is a different pair, **or** any admitted ranking route places the
  pair outside its own top 3.
* H044: any pre-registered decode table shows expected information gain above 0 bits on a
  live hypothesis.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.it2_fusion_scores`, `results.it2_fusion_matrix` — the frozen fused ranking as loaded | [108](108-the-ranking-frozen-before-anyone-looked.md) |
| file | `build/it2/step-6/fused-ranking.tsv`, sha256 `a596abf8…` | [108](108-the-ranking-frozen-before-anyone-looked.md) |
| **iteration 1** | `submissions/track1/iteration-1/spec.selectors.json` — the committed, coordinate-free description of the pair that was uploaded | [074](../../iteration1/step-6/methodology/074-submission-v1-design.md) |
| **iteration 1** | `results.coding_candidates` — resolving those two selectors to their consequence and dbSNP identifier | iteration 1's callset |
| **iteration 1** | [083](../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md) — the oracle's reply: full match at rank 1, F-max 1.000, threshold 0.9963 | the upload of 2026-09-09 |
| derived | `build/it2/step-6/upload-assessment.json` — the expected-information-gain arithmetic | this entry |

**This is the unblinding.** The three iteration-1 rows above are the first ones any
iteration-2 entry has read. `tools/check_blind.py` reported *still blind* before this file
existed and reports *unblinded by* this file after it.

## Commands

```
uv run python tools/assess_it2_upload.py
uv run python tools/unblind_it2.py
uv run python tools/check_blind.py
```

`unblind_it2.py` reads the pair to look for out of the **committed submission spec**, never
by searching the fused ranking for a good answer. The selector has to match exactly one row
or the tool refuses: a spec that no longer describes what was uploaded would make the
comparison be against something else.

## Observed — the comparison

| | Iteration 1 (uploaded, confirmed) | Iteration 2 (blind) |
|---|---|---|
| gene | `BUB1B` | `BUB1B` |
| allele A | `stop_gained`, dbSNP `rs759242053` | `truncating`, dbSNP `rs759242053` |
| allele B | `missense_variant`, **no dbSNP identifier** | `missense`, **no dbSNP identifier** |
| how it was found | the delivered callset, filtered: rare ∧ protein-altering ∧ biallelic ∧ PASS | symptoms alone → genome-wide likelihood ratio with no filter → fused |
| rank | uploaded at row 1; oracle: full match at rank 1, F-max 1.000 | **fused rank 1** of 274, and rank 1 under measured-error-rate weights too |

Same gene, same two allele classes, same identifier on one side and the same absent
identifier on the other. **The blind route rediscovered the uploaded pair.**

This is the **first row of the decision table** fixed in `plan.md` §3 step 6:

> iteration-2 rank 1 = the confirmed pair → replication report; **no upload**.

### What the rediscovery is, and what it is not

* It is **not** a second independent confirmation of causality. The oracle already settled
  that ([083](../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)); what
  this measures is whether a **different method** reaches the same place from the raw inputs.
* It is **not** coverage. The symptom-nominated target set has a held-out recall@300 of
  **0.335** [0.318, 0.350] ([091](../../step-1/methodology/091-recall-at-the-full-population.md)).
  A rediscovery says the route found this pair, never that it would find the next one.
* It is **not** four witnesses. [108](108-the-ranking-frozen-before-anyone-looked.md) already
  measured that: silence the likelihood route and the leader falls to rank 62.

### H041 — refuted, on its second clause

| Route | Rank it gave the confirmed pair | ≤ 3? |
|---|---|---|
| `likelihood` | **1** | yes |
| `phenotype` | **9** | no |
| `knowledge` | **not listed** (rank 51, the absent default) | no |
| `confirmation` | no rank by construction; all three booleans hold | n/a |

The first clause held exactly — fused rank 1. The second failed on **two of the three**
admitted routes, and the refutation clause was pre-registered as a disjunction, so one would
have been enough. What that buys, stated as the claim required:

* **The symptom ranker put the answer at rank 9 of its own list**, not in its top 3. Its
  recall was already measured at 0.335, and this is what that number looks like on the one
  case where the answer is known.
* **The literature never nominated it.** The knowledge route's top 50 does not contain the
  gene, so the independent-evidence count is 3 of 4 rather than 4 of 4 — and a literature
  route that misses a gene with a ClinVar-pathogenic truncating allele in it is a measurement
  of that route, not a footnote about this case.
* The honest summary sentence for the report is therefore **"one route found it, two
  corroborated it at a distance, and one instrument confirmed it in the raw reads"** — not
  "the routes converged".

### H044 — supported

Three questions a second Track 1 upload could still be aimed at, each simulated against the
local replica of the published scorer (`mva.pipeline.probe_design`, `mva.pipeline.scorer`):

| Question | Expected information gain | Why |
|---|---|---|
| the causal pair | **0.000 bits** | the first reply was a full match at rank 1 with F-max 1.000, so the hypothesis space is a single point and its entropy is 0 |
| a second causal pair (dual diagnosis) | **0.000 bits** | **not expressible**: the scorer's answer key holds one or two alleles, so "there is also a second pair" is not a hypothesis this instrument can be asked |
| secondary findings below the pair | **0.000 bits** | simulating the same truth with and without three secondary rows produces the **identical** reply; the rows carry qualitative review value and measure nothing |

The second row is the stronger finding and it is the one that closes the plan's fourth
outcome row. Iteration 2 does nominate a runner-up — `ADAMTS1`, 1.70× behind on the
likelihood ratio ([099](../../step-4/methodology/099-every-gene-ordered-with-nothing-filtered-out.md)),
rank 2 under measured-error-rate weights — so the "second pair with a comparable posterior"
row is live in fact. It cannot be resolved by this oracle at any cost in slots, because the
oracle has no way to say "both". **No second upload. 5 of 6 slots remain, deliberately.**

## Assumptions, limitations and quality checks

* **The comparison is at class-and-identifier grain, not at position grain.** The fused
  ranking is coordinate-free by design, so the match was made on
  `gene | consequence class : dbSNP identifier`. The mapping from iteration 1's consequence
  strings to the fusion's classes is written out in `tools/unblind_it2.py` rather than
  inferred, because a silent mismatch there would report a rediscovery as a miss.
* **Both selectors resolved to exactly one row**, which the tool requires; a spec that had
  drifted would have aborted rather than compared against something else.
* **The hash was recorded first.** [108](108-the-ranking-frozen-before-anyone-looked.md)
  carries `a596abf8…`; `shasum -a 256 build/it2/step-6/fused-ranking.tsv` still returns it,
  and the file has not been rebuilt since.
* **The blind gate was run on both sides of this entry** and changed state exactly once.
* **Phase is still unmeasured.** No read-backed phase block reaches the pair's coding span
  ([092](../../step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md)) and P(trans)
  is undetermined ([101](../../step-4/methodology/101-the-phase-that-cannot-be-measured.md)).
  The pair is *in trans* because the oracle's answer key says so, not because iteration 2
  measured it — the one fact in this entry that comes from the reply rather than from the
  mirror.
* **Decoys reach the fused top 20** ([108](108-the-ranking-frozen-before-anyone-looked.md)),
  so the ranking's resolution below rank 1 is poor and no claim is made about ranks 2–20.

## Conclusion

Starting from 1.07 billion reads, 5.0 million callset records and eight clinical terms, with
no iteration-1 table read until this entry, the fused ranking puts **the same two `BUB1B`
alleles first** — under equal weights and under measured-error-rate weights. Decision-table
row 1 fires: a replication report, and **no upload**, because no live hypothesis gains a bit
and the one question still open — a second causal pair — is one this oracle cannot be asked.

The rediscovery is real and it is carried by one route. Both halves belong in the report.
