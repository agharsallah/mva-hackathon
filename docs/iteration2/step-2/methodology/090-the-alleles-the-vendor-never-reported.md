# 090 — What happens to H016 and H020 once the alleles only our callers saw are scored?

**Written:** 2026-09-12. **Step:** `step-2` (iteration 2). **Hypotheses:** H016, H020 —
**re-tested**, on the input the plan always specified.

**Supersedes [088](088-the-alleles-the-reads-carry.md) for the H016 and H020 verdicts
only.** 088's concordance (H022), phasing (H019), recall (H021) and structural-variant
(H023) results are untouched. 088 is not edited; this entry is the later record.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.it2_read_alleles` — 131,530 read-derived calls, 75,733 distinct alleles | entry 088 |
| public | `warehouse.coding_regions` — exon intervals | Ensembl 116 |
| platform | `warehouse.coding_annotations` — VEP consequence, gnomAD, ClinVar, keyed by allele | built from the delivered callset |
| api | Ensembl VEP REST, release 116, assembly GRCh38 | 6 requests, 1,199 alleles |
| derived | `results.it2_bait_density`, `results.it2_exon_depth` | entry 087 |

The blind protocol holds. VEP and ClinVar say what a variant *is*; neither knows anything
about this child. No candidate table of any earlier iteration was opened, and the ranking
below is left in the order its own SQL produced.

## The defect this entry fixes

`it2_scored_pairs` scored an allele by joining `warehouse.coding_annotations`. That table
is built from **the delivered callset**. So an allele that only the read-derived callers
saw had no consequence, no frequency and no ClinVar row, failed the
`impact IN (HIGH, MODERATE)` predicate for want of an impact, and vanished before any
filter ran.

That is a circle, and it is the worst kind: a route built to find **what the vendor missed**
could only ever score **what the vendor found**. It did not look like a bug — it looked
like a smaller number. 088 recorded the blind spot and gave it a size (a per-gene
`unannotated_alleles` column) but did not close it.

`plan.md` §5 **stage 11** said to close it — *"Annotate — reuse `mva.pipeline.annotate_vep`
… every allele annotated, or explicitly listed as failed"* — and it was skipped.

## Hypotheses and predictions — unchanged, as filed before any of step 2 ran

- **H016** at least one target gene carries a biallelic candidate set of rare
  protein-altering alleles. *Refuted by:* none does.
- **H020** the matched decoy set yields **fewer** biallelic candidates per gene than the
  target set. *Refuted by:* **as many or more per gene** — in which case the read route has
  no discriminating power of its own and enters the step-6 fusion at reduced weight.

Nothing here was rewritten after seeing the result. The refutation condition for H020 is
quoted verbatim from the register, revision 1.

## What would refute this entry's own procedure

If annotating the missing alleles changed the numbers only because VEP was asked about
alleles it should not have been (intergenic noise dressed as coding), the comparison would
be an artefact. The scope is therefore fixed in code and not per gene: every read-derived
allele within **10 bp of a coding exon** (`mva.warehouse.annotate_reads.EXON_PAD`) — wide
enough to include the whole splice region, which VEP annotates out to 8 bp, and narrow
enough to exclude the ±50 kb of intron and flank the bait also carried.

## Commands

```
uv run mva-warehouse annotate-it2-reads --dry-run
uv run mva-warehouse annotate-it2-reads --workers 3
uv run mva-warehouse pg-derive --only it2_scored_pairs
uv run python tools/export_it2_step2_analysis.py
uv run python tools/render_it2_step2_results.py
```

## Observed

**1,199 alleles asked, 1,199 answered**, into `warehouse.it2_read_annotations` — a separate
table from `coding_annotations` on purpose, so "the vendor reported this" stays
distinguishable from "only the read route saw this".

| Impact | Alleles | | Top consequences | |
|---|---|---|---|---|
| HIGH | **49** | | missense | 411 |
| MODERATE | 419 | | splice polypyrimidine tract | 246 |
| LOW | 420 | | intron | 196 |
| MODIFIER | 311 | | splice region | 54 |

643 carry a gnomAD frequency, 275 a ClinVar assertion, **3** a pathogenic one. They fall in
521 distinct genes.

### The effect on the gene counts

| Tier | Genes | Biallelic **before** | Biallelic **after** | Qualifying alleles the vendor never reported |
|---|---|---|---|---|
| core | 59 | 1 | **3** | 20 |
| mechanism-term | 69 | 1 | **1** | 16 |
| net | 268 | 2 | **6** | 119 |
| **targets, all tiers** | **396** | **4** | **10** | 155 |
| decoy | 396 | 2 | **10** | 189 |

### H020, on both views

| View | Targets | Decoys | Fisher one-sided p |
|---|---|---|---|
| all genes | 10/396 = 0.0253 | 10/396 = 0.0253 | 0.589 |
| genes the bait reached (pre-registered in 085) | 9/391 = 0.0230 | **9/380 = 0.0237** | 0.618 |

## Verdict

**H016 — supported, and more strongly than in 088.** Ten target genes carry a biallelic
candidate set of rare protein-altering alleles, up from four; three of them are core tier.

**H020 — refuted.** The pre-registered refutation condition is "as many or more per gene".
On all genes the two sets are **exactly equal**; on the pre-registered reachable-gene view
the decoys are marginally **ahead**. The twofold difference 088 reported was an artefact of
scoring only the alleles the vendor had already found: the target set benefited from that
restriction more than the decoy set did, and removing it removed the difference.

The consequence was written into the claim before it was tested and is not negotiable now:
**the read route has no discriminating power of its own and enters the step-6 fusion at
reduced weight.**

### Why this is a completion, not a re-run until the answer changed

The direction matters. Stage 11 was in the plan before any of step 2 ran; running it moved
a verdict **against** the hypothesis, and against the more flattering of the two available
results. The rule this iteration is being held to — a threshold that moves after seeing its
own result is not a threshold ([086](086-can-the-off-target-gate-be-reached.md)) — is not
violated by completing a pre-registered stage whose omission had inflated a claim.

### What did not change

The counterfactual 088 reported is unaffected, because it never used annotation: with **no**
rarity or consequence filter, targets score 202/396 = 0.510 and decoys 227/396 = 0.573.
**The decoys still win without the filter.** So the step's central finding stands and is now
sharper: the discriminating power was never in the symptom-derived gene list, and with the
scoring input completed it is not measurably in the read route either — it is in the filter.

### One observation about the leads, stated without interpretation

Twenty genes survive the filter, ten targets and ten decoys. Ordered by the table's own
key (truncating, then ClinVar, then heterozygote count) the first is a **decoy**,
`TPD52L2`, carrying two truncating alleles. Exactly one gene of the twenty carries an
allele with a ClinVar pathogenic assertion. That single flag is the only feature separating
it from the rest, and it comes from a public catalogue rather than from the reads — which
is the honest description of how much the read route alone achieved. Which gene that is,
and whether it is the right one, is step 6's comparison to make, not this entry's.

## Assumptions and limitations

- **These 1,199 alleles are unvalidated.** They are calls two read-derived callers made
  that the vendor's pipeline did not report, on a baited alignment whose coverage is
  islands. Some fraction are false positives and this entry does not know which. That is
  precisely step 3's job — an alignment-free genotype check confirms or drops them — and
  until it runs, every count above is an **upper** bound.
- The comparison is one-sided by construction: no equivalent set of "alleles the vendor
  reported that our callers missed" was added, because those already carry annotation and
  were always scored.
- gnomAD frequency is absent for 556 of the 1,199, and an allele with no frequency passes
  the rarity filter by default (`gnomad_af IS NULL OR gnomad_af < …`). Novel alleles are
  systematically more likely to lack a frequency, so the filter is **more permissive**
  toward them than toward vendor-reported alleles. This works against the target set only
  if targets carry fewer novel alleles than decoys, and they do: 155 against 189.
- Two genes in the leads, `PWWP4` (mean depth 4.6x) and `GTF2IRD2` (5.3x), sit far below
  the 44x median. Both were already flagged as k-mer-repetitive in [086](086-can-the-off-target-gate-be-reached.md);
  their calls should be read as unreliable rather than as findings.
