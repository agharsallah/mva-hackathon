# Step 2 — discover the alleles from the reads

**Standing:** opened 2026-09-11 by step 1's handover; **nothing has run**. Iteration 2,
`step-2`.

**Goal** (from `src/mva/science/steps.py`):

> Which alleles do the raw reads carry in the target set, discovered without the vendor
> caller — small variants, structural variants, per-exon coverage, and read-backed phase?

The design — bait, align, call, annotate, enumerate, phase — is
[`plan.md`](../plan.md) §3 step 2; the tools, what is adopted and what must be built, are
[`execution.md`](../execution.md) §3.

## What step 1 hands over

| Input | Where | Note |
|---|---|---|
| target set, 404 rows, tiered | `results.it2_targets` | bait input |
| matched decoy set, 396 rows | `results.it2_decoys` | the read route's null (H020) |
| padding, fixed in advance | core ±50 kb, net ±2 kb | plan §3 step 2 |
| the assumption step 2 inherits | **the target set is an enrichment with measured recall ≈ 0.36, not coverage** | [084](../step-1/methodology/084-the-blind-target-set.md) |

That last row is load-bearing. A gene absent from the target set is **not** excluded by
step 2; it is simply not baited. The genome-wide safety net is step 4.

## Claims filed before anything runs

| Id | Plan label | Claim |
|---|---|---|
| H016 | H014 | at least one target gene carries a biallelic candidate in the read-derived calls |
| H017 | H015 | DeepVariant PASS calls agree with the delivered VCF at ≥ 99 % of co-called sites |
| H018 | H016 | no SV called by ≥ 2 callers of different method classes, outside the bait-edge zone, overlaps a coding exon of a gene that also carries a rare heterozygous protein-altering allele |
| H019 | H031 | for the top candidate pair, WhatsHap either closes a phase chain between the two alleles or reports the exact gap that prevents it |
| H020 | H036 | the decoy set yields fewer biallelic candidates per gene than the target set |

## The two tools this step needs first — not built yet

1. **`tools/check_coordinates.py` gains the candidate 31-mers** as patterns. The k-mer
   sequences are patient sequence and must stay under `build/` (plan §5). A step-0
   platform fix, named to this step.
2. **The engine scaling test** — 10³, 10⁴, 10⁵ and 10⁶ patterns on the 6 M-read sample —
   decides whether the Aho-Corasick strike carries the bait or a hashed canonical-k-mer
   filter does (plan §3 step 2, gap S2). It runs *before* the full pass, and its result is
   the first entry filed here.

## Where it runs

The laptop is arm64 with 16 GiB and no Docker; the read store, the aligner, DeepVariant
and the SV callers are Linux/amd64. Alignment, calling and k-mer counting run on the
server or a cloud VM by default ([`execution.md`](../execution.md) §2); the laptop keeps
SQL, fits and figures.
