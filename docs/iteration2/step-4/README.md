# Step 4 — likelihood-ratio ranking over the VCF

**Standing:** opened 2026-09-13 by step 3's handover; **nothing has run.**
Iteration 2, `step-4`.

**Goal** (from `src/mva/science/steps.py`):

> Over every protein-coding gene in the VCF, with no hard filter, which biallelic pair has
> the highest posterior, and what is its P(trans)?

Design: [`plan.md`](../plan.md) §3 step 4, **as expanded by
[§11.5](../plan.md#115-step-4-expanded--the-only-discriminating-and-genome-wide-route)**.
Read that section first: it changes what this step is for.

---

## 1. Why this step now carries the weight

Steps 1–3 have each measured their own limits, and every one of those measurements points
here.

| Finding | Entry | What it means for step 4 |
|---|---|---|
| held-out **recall@300 = 0.360** [0.295, 0.420] | [084](../step-1/methodology/084-the-blind-target-set.md) | the target set is an **enrichment, never coverage** — a gene's absence from it says nothing, and step 4 is the only step that sees every gene |
| **73.6 %** of protein-coding genes carry no HPO curation | [084](../step-1/methodology/084-the-blind-target-set.md) | the human-only ranker cannot score them at all; the network-proximity lane lives here |
| **H020 refuted** — targets and decoys carry a biallelic candidate at exactly the same rate | [090](../step-2/methodology/090-the-alleles-the-vendor-never-reported.md) | the read route has **zero measured ranking power** |
| the lead pair is **unphaseable** | [088](../step-2/methodology/088-the-alleles-the-reads-carry.md) | P(trans) here is the *only* trans evidence that will exist |
| **H027 refuted** — ~1 in 3 vendor-unreported alleles corroborated, ~19 in 20 vendor-reported ones | [096](../step-3/methodology/096-the-alleles-at-their-multiplicity.md) | step 2's biallelic counts are upper bounds; the read route enters step 6 as confirmation, not ranking |

**Step 4 was the safety net. It is now the primary and only discriminating route.**

## 2. What steps 1–3 hand over

| Input | Where | Note |
|---|---|---|
| target set, 404 rows, tiered | `results.it2_targets` | a prior, not a filter — recall 0.36 |
| matched decoy set, 396 rows | `results.it2_decoys` | must go through the identical LR (§11.5) |
| read-derived alleles | `results.it2_read_alleles` | 75,733 distinct |
| **k-mer genotypes** | `results.it2_kmer_genotypes` | 164,044 alleles with a posterior, a probe agreement and a confirmation flag |
| **confirmed-only recount** | `results.it2_kmer_pairs` | which genes still carry two *confirmed* heterozygous alleles |
| reachability per gene | `results.it2_mapq_profile` | no absence claim without it |
| the platform annotation table | `warehouse.coding_annotations` | keyed by allele, allowed by the blind protocol |

## 3. The assumptions this step inherits

1. **The read route confirms, it does not rank.** Its contribution to a pair is a triple —
   *read-confirmed*, *single-copy*, *no CN loss* — and **no rank at all**
   ([plan §11.6](../plan.md#116-step-6-pre-registered-now)).
2. **A step-2 allele is not evidence until step 3 has seen it.** Two thirds of the
   vendor-unreported ones are not corroborated. Any pair built on them carries that.
3. **The decoy set is the null for this step too.** Not only the permutation null: the
   discriminating power lives in the *filter*, and a filter must be measured against a
   matched gene set (F4).
4. **No hard filter anywhere.** That is the whole point of a likelihood ratio: no gene is
   dropped, only down-weighted. Non-PASS calls enter with a down-weight.
5. **Correlated evidence is not counted twice.** CADD's hyperparameters were tuned on
   ClinVar-versus-ExAC, so the two never enter one product at full strength.
6. **A fifth failure category exists: *unphaseable*** ([plan §11.5](../plan.md#115-step-4-expanded--the-only-discriminating-and-genome-wide-route))
   — both alleles real, both single-copy, no fragment spanning them, no parental DNA. It is
   the category the lead pair itself falls into, and step 6's trace must be able to say so.

## 4. Claims to file before it runs

Register ids start at **H030**. The plan's labels (plan H020–H022, H032) map to the claims in
[`plan.md` §3 step 4](../plan.md); file them with `mva-science hypothesis-add` **before** the
first run, as steps 1–3 did.

## 5. What step 3 learned about running things

| Lesson | Consequence for step 4 |
|---|---|
| a CSV sniffer turned every empty field into two quote marks and moved a headline rate from 0.91 to 0.34 | the loaders now pass `quote` explicitly; any new loader must too |
| a fractional count made every genotype class impossible and read as class 0 | a model over counts must be given counts; guard the degenerate row rather than trusting `argmax` |
| genes in the bait's padding were being counted as targets | name the tiers you mean; "not a decoy" is not "a target" |
| the headline figure was wrong twice and looked plausible both times | **render the figure and disbelieve it** — both defects were caught that way and neither by a test |
| a 3 GB reference read once per group instead of once | when a helper streams a whole file, check how many times the caller invokes it |

## 6. How to start

```bash
# 1. read, in order
docs/iteration2/plan.md  §11.5
docs/iteration2/step-3/README.md
docs/iteration2/step-3/methodology/096-the-alleles-at-their-multiplicity.md

# 2. file the claims before running anything
uv run mva-science hypothesis-add --step step-4 --statement … --prediction … --refuted-by …

# 3. the tables are already there
uv run mva-warehouse pg-query "SELECT * FROM pg.results.it2_kmer_pairs LIMIT 5"
```

The next free methodology entry is **098**. Step 4's entries go in `methodology/`.
