# 105 — Does the knowledge route order anything a publication count does not, and can it tell a candidate from a control?

**Written:** 2026-09-18. **Step:** `step-5` (iteration 2). **Hypotheses:** H038, H039.
Instruments: [102](102-the-sources-and-what-they-could-be-asked.md). The anchor pass these
read: [104](104-the-papers-the-script-found.md). Why the two conditions are conjunctive:
[`../notes/why-the-baseline-is-the-test.md`](../notes/why-the-baseline-is-the-test.md).

## Hypotheses and predictions

**H038** — *The knowledge score separates the 404 symptom-nominated target genes from the
396 matched decoy genes.*
**Prediction.** The target-versus-decoy AUC, with a bootstrap interval computed the way
step 4 computed its own, has an interval that **excludes 0.5**.

**H039** — *The knowledge ranking reorders the leading genes against a baseline that ranks
them by PubMed hit count alone.*
**Prediction.** Spearman ρ below 0.9, **or** the two top-5 sets differ by at least one gene.

## What would refute them

**H038** — the interval covers 0.5. The knowledge route would then have no measured
discriminating power and would enter step 6 as a confirmation route at weight zero, exactly
as the read route did when H020 was refuted.
**H039** — ρ ≥ 0.9 **and** identical top 5. The route would then be citation volume under
another name, reported as a negative result and dropped from the step-6 fusion.

## Inputs

| Source | What was read |
|---|---|
| `results.it2_anchors`, `it2_anchor_terms` | per gene, the best paper's matched-term count and the terms it co-occurs with at all |
| `results.it2_pub_alleles` | per gene, how many of this child's alleles anyone has published about |
| `results.it2_targets` / `it2_decoys` | the two sets the separation is measured between |
| `results.it2_lr_top_pairs` | step 4's rank per gene, carried for comparison and **not** an input to the score |
| PubMed E-utilities | `GENE[Title/Abstract]`, one count per gene, through `mva.drugs.sources.pubmed` |

## The score, as pre-registered

Lexicographic, per gene: **(best paper's matched-term count, published alleles this child
carries)**, flattened as `100 × terms + min(described, 99)` so the term count cannot be
crossed by the tie-break. **Citation volume is not in it and is not its tie-break** — ties
break on the gene symbol, which carries nothing. That is what keeps H039 answerable.

## Commands

```bash
uv run python tools/run_it2_knowledge_baselines.py
uv run mva-warehouse pg-load-it2-step5
uv run mva-warehouse pg-derive --only it2_knowledge_separation
uv run mva-warehouse pg-derive --only it2_knowledge_vs_citations
```

## Observed — H038, the decoy null

**AUC 0.634 [0.593, 0.672]** over 404 targets and 396 decoys, 1,000 bootstrap resamples,
seed 20260918. The interval excludes 0.5. **Supported.**

| group | genes | mean score | median | genes with a ≥5-term paper | genes with a published allele | median PubMed count |
|---|---|---|---|---|---|---|
| **target** | 404 | 306.7 | 301 | **38** | 250 | 410 |
| **decoy** | 396 | 250.1 | 204 | **16** | 254 | 43.5 |
| curated-other | 11 | 229.1 | 219 | 0 | 11 | 1,635 |
| uncurated-other | 4 | 233.3 | 211 | 0 | 4 | 219.5 |

The `genes with a published allele` column is the control that shows where the separation is
*not* coming from: 250 targets against 254 decoys — **no difference at all**. All of the
separation is in the matched-term count, and none of it in the saturated
published-allele column ([103](103-the-alleles-somebody-already-published.md)).

**0.634 is a modest separation and is quoted as one.** Step 4's likelihood ratio reached
0.706 [0.655, 0.751] on the same two gene sets.

## Observed — H039, the citation baseline

**ρ = 0.024. Top-5 overlap 0 of 5. Supported**, and not marginally.

| | top 5 |
|---|---|
| by knowledge score | `DDX11`, `TTLL5`, `F13B`, `VIPAS39`, `ADAT3` |
| by PubMed hit count | `REST`, `AR`, `NODAL`, `BAX`, `FAS` |

Two genes tie on the score that decides entry to the knowledge top 5, so that overlap is
**not** an artefact of alphabetical tie-breaking (`tied_at_k = 2`). A rank correlation of
0.024 across 815 genes is as close to orthogonal as this measurement gets: whatever the
knowledge score is tracking, it is not how much has been written about a gene.

## Observed — the result neither claim asked for, and the one step 6 must act on

**The knowledge ordering and the genome-wide DNA ordering are close to orthogonal too, and
the knowledge ordering does not point at the causal gene.**

| step-4 rank | gene | knowledge rank (of 815) | best paper | PubMed count |
|---|---|---|---|---|
| 1 | `BUB1B` | **293** | 3 terms | 526 |
| 2 | `ADAMTS1` | 470 | 2 terms | 683 |
| 3 | `HLA-DRB1` | 445 | 2 terms | 7,505 |
| 4 | `PEX5` | 408 | 3 terms | 410 |
| 6 | `RAI1` | 201 | 3 terms | 272 |

And the other direction is worse: **the knowledge route's own top two genes are decoys**
(`DDX11`, `TTLL5`), and **10 of its top 25 are decoys**.

So the route is, by its own pre-registered tests, a *ranking* route — it separates from its
controls and it is not citation volume — and its ranking is nonetheless **wrong at the top**
and **uninformative about the confirmed lead**. Both statements are true at once, and step 6
has to carry both: a measured AUC of 0.634 is a weight, not a licence to outvote a route
that measured 0.706 and put the causal gene first.

## Evidence recorded

| Hypothesis | Direction | Strength | Claim |
|---|---|---|---|
| H038 | supports | 0.80 | AUC 0.634 [0.593, 0.672] over 404 targets and 396 decoys; the interval excludes 0.5 |
| H038 | neutral | 0.55 | the published-allele column is 250 targets vs 254 decoys — none of the separation comes from it |
| H038 | neutral | 0.45 | 0.634 is below step 4's 0.706 on the same two sets |
| H039 | supports | 0.85 | ρ = 0.024 and top-5 overlap 0 of 5, with only 2 genes tied at the boundary |
| H039 | neutral | 0.50 | the knowledge route's own top two genes are decoys, and the step-4 leader sits at knowledge rank 293 of 815 |

## Limitations, stated beside the result

* **The score's first term is the one [104](104-the-papers-the-script-found.md) showed to be
  a breadth measure**, so the separation is partly "targets appear in more broad clinical
  surveys than matched controls do" — which is true, interesting, and not the same as
  "targets have case reports".
* **AUC 0.634 is modest.** It says a randomly chosen target outscores a randomly chosen
  decoy 63 % of the time. It is a weight for step 6, not a diagnosis.
* **Length-matched decoys are load-bearing here.** A longer gene carries more alleles and
  attracts more papers; an unmatched control set would have measured gene size.
* **`GENE[Title/Abstract]` is a string query**, so a gene with an ambiguous symbol collects
  papers that are not about it. It is a baseline, and the direction of that error inflates
  the baseline rather than the route.
* **Ties.** The knowledge score takes few values, so many genes share a rank. The mid-rank
  Spearman is unaffected; the printed `knowledge_rank` breaks ties on the gene symbol, and
  `tied_at_k` says how wide the tie at the top-5 boundary was.

## Verdict

**H038 — supported, confidence 0.78.** The interval excludes 0.5 and the separation is
produced by the matched-term count, not by the saturated published-allele column.

**H039 — supported, confidence 0.85.** ρ = 0.024 with a top-5 overlap of zero. The route is
measuring something, and that something is not publication volume.

**What step 6 is handed.** A ranking route with a measured weight of AUC 0.634 whose own
leaders include ten decoys in twenty-five and which places the confirmed gene at rank 293.
The two conditions the route passed license it to contribute a rank; nothing in them
licenses that rank to outrank step 4's.

Next: [106](106-where-the-missense-sits-in-the-protein.md), then step 6's fusion.
