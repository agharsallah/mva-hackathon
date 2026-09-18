# 101 — What is the leading pair's P(trans), when phase cannot be measured at all?

**Written:** 2026-09-18. **Step:** `step-4` (iteration 2).
**Hypotheses:** **H035 supported**, and supported in the way that makes it a limitation
rather than a result.

**Supersedes nothing.** It answers the second half of the step's goal.

## Hypothesis and prediction

**H035** — P(trans) for the leading pair is `undetermined`: at least one of its two alleles
is absent from gnomAD v2's exome co-occurrence dataset, so no observed compound-heterozygosity
probability exists for it.

*Predicted:* resolving both alleles to gnomAD v2 identifiers and querying
`variant_cooccurrence` returns no record; the pair is reported at the published base rate
with the state `undetermined`.

*Refuted by:* gnomAD returns a `p_compound_heterozygous` for the pair — an observed
population estimate exists and is quoted with its caveat instead of a prior.

## Why a population statistic is all that is left

A recessive disease needs both copies of a gene disabled, so two heterozygous variants in one
gene only count if they sit on **opposite** copies — *in trans*. Phase is normally settled two
ways, and this case has neither:

* **read-backed phasing** needs one sequencing fragment covering both variants. Step 2
  measured the lead pair **10,911 bases apart** against ~266-base fragments
  ([088](../../step-2/methodology/088-the-alleles-the-reads-carry.md)). No fragment can span
  it, and none does: `results.it2_phase_blocks` has 6,823 blocks and not one covers `BUB1B`.
* **parental genotypes** need parental DNA. None exists for this case.

Guo 2024 (PMID 38057443) showed that if a pair of variants is seen together in enough people,
the counts of the genotype combinations reveal how often the two travel on the same
chromosome, and gnomAD serves the resulting probability per pair. That is the only
parent-free, BAM-free estimate published, and it is what this entry fetches.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `build/it2/step-4/tables/it2_lr_pairs.tsv` — the top 25 compound hypotheses | [099](099-every-gene-ordered-with-nothing-filtered-out.md) |
| api | gnomAD GraphQL `variant_cooccurrence`, dataset `gnomad_r2_1` | every reply cached under `build/it2/step-4/ptrans/` with its query |
| api | gnomAD GraphQL `variant(rsid:)` — the GRCh38 → GRCh37 bridge | same cache |

## Commands

```
uv run python tools/lookup_it2_ptrans.py --top 25
```

## Observed

| | |
|---|---|
| pairs asked about | **25** (the top 25 genes by ratio, compound hypotheses only) |
| alleles in those pairs | 50 |
| alleles carrying a dbSNP identifier at all | **49** |
| alleles that resolve to a gnomAD v2 variant | **5** |
| pairs with an **observed** `p_compound_heterozygous` | **0** |
| pairs reported `undetermined` | **25** |
| empirical base rate from resolvable pairs | **none — nothing resolved** |
| requests made | 49 |

The leading pair:

| | |
|---|---|
| gene | `BUB1B` |
| shape | compound |
| phase from the caller | unknown |
| left allele | has an rsID, and resolves in gnomAD v2 |
| right allele | **no rsID at all** |
| state | **undetermined** |
| P(trans) reported | 0.5 — the uninformative prior |

**H035 is supported.** The pair's second allele is not a dbSNP record, so no bridge to the
GRCh37 dataset exists, and no co-occurrence estimate can be fetched for it at any confidence.

## Why the coverage is 5 of 50, and what that costs

The co-occurrence dataset exists **only** for gnomAD v2.1.1 exomes, which are called against
**GRCh37**. This callset is GRCh38. There is no coordinate bridge that is safe to build here —
a lifted position is a new assumption in a step whose whole point is that its assumptions are
written down — so the join is by dbSNP identifier, which is assembly-free.

That bridge is the bottleneck twice over:

1. 49 of 50 alleles carry an rsID, so the identifier is almost always *present*;
2. only 5 of them are **in gnomAD v2** at all, because an ultra-rare disease allele in an
   exome cohort of 125,748 people usually is not.

The second number is the real one and it is not a defect of the method: an allele common
enough to be co-observed is, by construction, not the allele a disease with fewer than 50
known patients worldwide is caused by. **The method is least available exactly where it is
most wanted.**

## Two things this entry deliberately does not do

* **It does not report zero.** An absent pair gets 0.5 — two heterozygous variants in one
  gene are, with no information at all, equally likely to be cis as trans — and the state
  `undetermined` travels with the number everywhere it is quoted. Reporting 0 would turn a
  missing measurement into evidence against the pair; reporting 1 would manufacture a
  diagnosis.
* **It does not substitute Guo 2024's rare-pair base rate.** The plan named that number; it
  could not be read from the paper during this step
  ([098](098-the-lanes-and-what-they-were-calibrated-against.md)), and inventing a citation
  is worse than using a prior whose derivation is one sentence long. `base_rate()` exists to
  measure an empirical rate from whatever pairs do resolve, and in this run it returns
  `None`, because none did.

A third state exists and fired once during development: `error`, when the lookup itself
failed. It is kept distinct from `undetermined` on purpose — a network outage recorded as
"gnomAD has never seen this pair" would be a finding rather than a failure. The final run has
zero `error` rows.

## What step 6 receives

* **P(trans) for the lead pair is undetermined**, and that is the strongest statement
  available. Step 3's dosage result — both alleles at one copy each, posterior 1.0, three
  probes agreeing ([096](../../step-3/methodology/096-the-alleles-at-their-multiplicity.md))
  — is consistent with trans and is **not** evidence of it.
* The lead pair therefore falls into failure category **(v) unphaseable**, added by
  [plan §11.5](../../plan.md#115-step-4-expanded--the-only-discriminating-and-genome-wide-route):
  both alleles real, both single-copy, no fragment spanning them, no parental DNA.
* The runner-up's pair is a different case entirely: `ADAMTS1` is phased **cis** by the
  caller, which is positive evidence *against* it being a compound heterozygote
  ([099](099-every-gene-ordered-with-nothing-filtered-out.md)).

## Conclusion

The step's goal asks "what is its P(trans)?" and the answer is that it cannot be measured,
stated with the coverage number that makes that answer checkable: 5 of 50 alleles reach the
only dataset that could have answered. The value reported is a prior, labelled as one.
