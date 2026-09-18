# 100 — How high would the leader have come out by chance, and does the scoring discriminate at all?

**Written:** 2026-09-18. **Step:** `step-4` (iteration 2).
**Hypotheses:** **H033 refuted**, **H034 supported**. Both were filed before
[098](098-the-lanes-and-what-they-were-calibrated-against.md) ran.

**Supersedes nothing.** It is the entry that says how much
[099](099-every-gene-ordered-with-nothing-filtered-out.md)'s ordering is worth, and the
answer is less than the ordering on its own suggests.

## Hypothesis and prediction

* **H033** — under a phenotype-permutation null, fewer than 1 in 1,000 random seven-term sets
  drawn with the child's term-depth profile produce a top ratio at or above the observed one.
  *Predicted:* 0 of 1,000 draws reach it, giving an empirical p < 0.001.
* **H034** — under the identical likelihood ratio, the step-1 target genes separate from
  their matched decoys. *Predicted:* the bootstrap interval of the target-versus-decoy AUC
  on best-pair ratio has a lower bound above 0.5.

## What would refute them

* H033: one or more draws reach the observed top — the lead is not phenotype-specific and is
  reported as a ranking a random symptom set could also produce.
* H034: the interval covers 0.5 — the likelihood ratio has no measured discrimination
  between a symptom-nominated gene and a size-matched control, and the step reports that
  instead of a lead.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `build/it2/step-4/tables/it2_lr_pairs.tsv` — 51,920 hypotheses, one row each | [099](099-every-gene-ordered-with-nothing-filtered-out.md) |
| reference | `build/reference-scratch/hp.obo` + `genes_to_phenotype.txt` — the ontology and corpus step 1 ranked on | entry 067 |
| clinical | the proband's seven terms, for their **depths only** — the draws take the shape, never the terms | `Challenge_Clinical_Phenotype_1.md` |
| derived | `results.it2_targets` (404) and `results.it2_decoys` (396) | [084](../../step-1/methodology/084-the-blind-target-set.md) |

Seed **20260918** for every draw and every bootstrap, so both numbers reproduce exactly.

## Commands

```
uv run python tools/run_it2_lr_nulls.py --draws 1000 --resamples 1000
uv run mva-warehouse pg-load-it2-step4
```

## Why 1,000 whole re-rankings cost 34 minutes and not a week

LIRICAL's degradation is a **power**, so it distributes over the product:
`(C · G · pheno)^f = (C · G)^f · pheno^f`. Substituting the phenotype lane is therefore
exact arithmetic on a number already stored per row (`lr_without_phenotype`, `exponent`),
not an approximation. Each draw costs one phenotype ranking over 5,259 genes — 2.03 s — and
the re-scoring of all 51,920 hypotheses is a multiply. `ScoredPair.rescored` is the function,
and a test asserts it reproduces the original ratio exactly when handed the original lane.

## Observed — the decoy null (H034)

| | |
|---|---|
| target genes with a hypothesis | **256** |
| decoy genes with a hypothesis | **266** |
| **AUC** | **0.706** |
| 95 % bootstrap interval, 1,000 resamples | **[0.655, 0.751]** |
| interval excludes 0.5 | **yes** |

**H034 is supported.** A randomly chosen symptom-nominated gene outscores a randomly chosen
size-matched control about **seven times in ten**.

The comparison is the point. Step 2 measured the two sets' *unfiltered* biallelic rate as
indistinguishable — 10 of 396 each, Fisher one-sided p = 0.589, which is what refuted H020
([090](../../step-2/methodology/090-the-alleles-the-vendor-never-reported.md)). The gene list
was never an instrument. The separation measured here was produced entirely by the scoring,
which is what "the discriminating power lives in the filter" means when it is measured
rather than asserted.

By class, on the best hypothesis per gene:

| Class | Genes | Median ratio | 90th percentile |
|---|---|---|---|
| core target | 38 | **0.333** | 5.775 |
| net target | 180 | 0.052 | 0.964 |
| mechanism-term target | 38 | 0.039 | 0.181 |
| **decoy** | 266 | **0.0098** | 0.142 |
| curated, not nominated | 2,899 | 0.0028 | 0.159 |
| uncurated | 8,044 | 0.0098 | 0.099 |

A core target's median gene sits **34×** above a decoy's. Note also that the median gene of
*every* class is below 1: the ranking's ordinary answer is "this gene argues against itself",
which is the correct behaviour for a scan where one gene in 19,723 is causal.

## Observed — the permutation null (H033)

| | |
|---|---|
| draws | **1,000** |
| draws reaching or exceeding the observed top | **55** |
| empirical p | **0.0559** |
| median top ratio across draws | 201,028 |
| observed top ratio | 341,019 |
| expected count of genes at or above the observed leader, per draw | **0.055** |
| wall clock | 2,037 s |

**H033 is refuted.** The claim required fewer than 1 in 1,000; 55 in 1,000 is what happened.
The lead is not phenotype-specific at the level the claim asserted, and it is reported that
way.

### The null is nearly degenerate, and that is the finding

A thousand draws produced **four distinct top values**:

| Top ratio reached | Draws | What is producing it |
|---|---|---|
| 201,028 | **945** | `ADAMTS1` — **unchanged by every draw** |
| 531,378 | 47 | `HLA-DRB1`, promoted into the rank-51–300 band |
| 1,142,890 | 7 | `HLA-DRB1`, promoted into the rank-11–50 band |
| 1,533,820 | 1 | `HLA-DRB1`, promoted into the rank-2–10 band |

Two mechanisms, both checkable by arithmetic rather than by inspection:

1. **The null's floor is a gene the permutation cannot touch.** `ADAMTS1` has no curated
   phenotype, so *every* term set — the child's and all 1,000 random ones — puts it in the
   unranked bucket at ×0.379. Its top value is fixed at 529,850 × 0.379 = 201,028, which is
   below the observed 341,019 and above almost everything else. The null therefore spends
   945 of its draws reporting a constant.
2. **Only four genes in the entire callset *can* exceed the observed value under any term
   set at all**, because the phenotype lane's ceiling is ×66.96:

   | Gene | Curated? | Genotype-only ratio | Best reachable |
   |---|---|---|---|
   | ADAMTS1 | no | 529,850 | 201,028 — the cap does not apply, it can never be ranked |
   | HLA-DRB1 | yes | 29,451 | 1,972,055 |
   | HLA-DQA1 | yes | 6,548 | 438,454 |
   | **BUB1B** | yes | 6,548 | 438,454 |

   One of the four is the observed leader itself, and one can never be promoted. So the
   whole null reduces to *"how often does a random seven-term set rank HLA-DRB1 or HLA-DQA1
   highly?"*, and the answer is 55 times in 1,000.

**The honest reading is therefore narrower and more useful than the p-value alone.** The
observed leader is not beaten by chance in 94.5 % of draws, and when it is, the gene that
beats it is one of the two most polymorphic loci in the human genome — the same two that sit
at ranks 3 and 5 in the real ordering. The null is measuring an artefact of HLA
hyperpolymorphism as much as it is measuring phenotype specificity, and a step that reported
`p = 0.056` without that sentence would be reporting the wrong thing.

### What would have made the null stronger, recorded rather than retrofitted

* **Permuting the genotype side as well.** A null that resamples only the phenotype cannot
  move a gene whose evidence is genotype-only, which is exactly the gene that dominated it.
* **Recording the winning gene per draw**, rather than only the top ratio. The attribution
  above is arithmetic over four distinct values and is certain, but it is a reconstruction; a
  column would have been a measurement. `tools/run_it2_lr_nulls.py` writes `top_lr` and
  `genes_above_observed` per draw, and a future run should add `top_gene`.

Neither is changed now: modifying a null after seeing its result is choosing the answer.

## Observed — the genotype-only ablation

Not a null, a control: the same table with the phenotype lane set to 1 for every gene.

| # | Gene | DNA alone | Both routes |
|---|---|---|---|
| 1 | ADAMTS1 | 529,850 | 201,029 |
| 2 | HLA-DRB1 | 29,451 | 143,934 |
| 3 | **BUB1B** | **6,548** | **341,019** |
| 3= | HLA-DQA1 | 6,548 | 6,474 |
| 5 | PEX5 | 728 | 13,134 |

**The DNA alone does not nominate `BUB1B` first — it puts it joint third.** The child's
symptoms move it from joint third to first, and `ADAMTS1` from first to second. H030's
support is for the two routes *combined*, which is stated in
[099](099-every-gene-ordered-with-nothing-filtered-out.md) and recorded as an evidence row
against the claim.

## Conclusion

The scoring discriminates: targets separate from matched decoys at AUC 0.706 [0.655, 0.751],
and that separation is produced by the ranking rather than by the gene list (H034 supported).
The leader is not phenotype-specific at the pre-registered level: 55 of 1,000 random symptom
sets reach it (H033 refuted), and the null is dominated by two HLA loci and by one uncurated
gene that no term permutation can move.

Next: [101](101-the-phase-that-cannot-be-measured.md).
