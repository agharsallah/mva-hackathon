# 088 — Which alleles do the recovered reads carry, and does the target set earn its place?

**Written:** 2026-09-12 before the calls existed; **run:** 2026-09-12. **Step:** `step-2`
(iteration 2). **Hypotheses tested:** H016 (**supported**), H019 (**supported**),
H020 (**supported, weakly**), H022 (**supported**), H023 (**refuted**) — all filed before
the run; H017 and H018 were superseded by H022 and H023 before it
([README](../README.md)).

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | the recovered reads | `build/it2/step-2/baited-reads.parquet`, 15,773,226 reads in 7,886,613 complete pairs, entry [087](087-the-pass-and-what-it-recovered.md) |
| public | GRCh38 no-alt analysis set + hs38d1, bare contigs | sha256 `fb4243eb…`, 195 contigs |
| public | `ressources/reference/coding_regions.tsv` | Ensembl 116 |
| callset | `warehouse.variants_raw` — the delivered callset, layer 1, unfiltered | concordance denominator only (H022) |
| platform | `warehouse.coding_annotations` — VEP consequence, gnomAD frequency, ClinVar | **allowed**: a platform table keyed by allele, saying what a variant *is*, not what iteration 1 concluded |

**No iteration-1 candidate table was read.** `results.gene_biallelic`,
`results.coding_candidates` and the decode table are untouched; the comparison they exist
for is step 6's.

## Hypotheses and predictions — written before the run

- **H016** at least one target gene carries a biallelic candidate set of rare
  protein-altering alleles.
- **H019** for the top candidate pair, read-backed phasing closes a chain between the two
  alleles or reports the exact gap that prevents it.
- **H020** the decoy set yields fewer biallelic candidates per gene than the target set.
- **H022** the read-derived calls agree with the delivered callset at ≥ 99 % of sites where
  both emit a genotype.
- **H023** no SV supported by two callers of different method classes, outside the
  bait-edge zone, removes or duplicates a coding exon of a gene that also carries a rare
  heterozygous protein-altering allele.

## What would refute them

H016: no target gene yields any biallelic candidate. H019: neither a closed chain nor a
named gap — a tooling failure, re-run before concluding anything. H020: the decoys yield as
many or more, and the read route enters step 6 at reduced weight. H022: concordance < 99 %,
every discordant site listed before anything is concluded. H023: a deletion or insertion
does, and that gene becomes a lead; a duplication or inversion does, and the gene is a lead
only once coverage or k-mer copy number confirms the dosage change.

## Commands

```
uv run python tools/run_it2_step2_calling.py --skip-download --skip-fastq --threads 4
uv run python tools/export_it2_step2_tables.py
uv run mva-warehouse pg-load-it2-step2
uv run mva-warehouse pg-derive --only it2_concordance it2_read_pairs it2_scored_pairs \
                                      it2_sv_consensus it2_sv_leads
```

## Observed

### The chain

| Stage | Result |
|---|---|
| align (minimap2 `-ax sr`, split index + merge) | 15,829,813 records, **98.87 % mapped**, 14,390,663 properly paired, 1,944,315 duplicates marked |
| coverage (mosdepth, MAPQ ≥ 20) | 3,020 baited intervals, **median depth 44.08**, 29 below 10× |
| freebayes | 68,767 → 70,847 normalised |
| `bcftools mpileup \| call -m` | 59,797 → 60,683 normalised |
| delly (read-pair + split-read) | 788 |
| dysgu (local assembly + classifier) | 17,398 |
| WhatsHap | 6,823 phase blocks |

**Median depth 44.08 is an independent check, not a summary.** The delivery's stated depth
is 44×; nothing in the bait, the recovery or the alignment was tuned to reproduce it.
Recovering it from the baited alignment says the recovery is not systematically lossy.

**The 29 thin intervals are the genes the bait already predicted.** They are LIMS4,
CNTNAP3, GTF2IRD2, TBC1D3, POTED, GOLGA6, HNRNPCL3, SPDYE10, PWWP4 — plus PMS2, CR1 and
GTF2I — the same segmental-duplication families entry 085's k-mer uniqueness profile
flagged as unreachable. Two measurements sharing no machinery, pointing at one gene list.

### H022 — do the callers agree with the vendor's?

| caller | co-called | agreed | concordance | at delivered PASS |
|---|---|---|---|---|
| `bcftools call -m` | 45,512 | 45,316 | **0.995693** | 0.996029 |
| freebayes | 43,639 | 43,322 | **0.992736** | 0.993848 |

**Supported** for both, on a large denominator. Reads selected by k-mer bait rather than
whole-genome alignment, called by two callers of disjoint model class, reproduce the vendor
pipeline's genotypes. **Scope stated:** single-base substitutions only, where normalisation
is a no-op so a disagreement is about the genotype and not the spelling. Indels are
excluded — `variants_raw` is unnormalised and its indels are not comparable without a
left-alignment this query cannot do — which means the claim is untested for exactly the
allele class minimap2's short-read mode is weakest at.

### H016 — is there a biallelic candidate?

Four target genes carry two rare (gnomAD < 1 %) protein-altering heterozygous alleles, or
one homozygous:

| gene | tier | rare het | rare hom | truncating | ClinVar-flagged | bait density | depth |
|---|---|---|---|---|---|---|---|
| **BUB1B** | core | 2 | 0 | **1** | **1** | 0.850 | 43.71 |
| FANCM | mechanism-term | 0 | 1 | 0 | 0 | 0.866 | 45.91 |
| HSPG2 | net | 2 | 0 | 0 | 0 | 0.894 | 45.27 |
| ZFP57 | net | 4 | 0 | 0 | 0 | 0.840 | 48.40 |
| *TXNDC11* | *decoy* | 3 | 0 | 0 | 0 | 0.884 | 44.51 |
| *VPS41* | *decoy* | 3 | 0 | 1 | 0 | 0.955 | 42.77 |

**Supported.** One gene is in the core tier, and it is **the only gene among all 792 that
carries both a truncating and a ClinVar-flagged allele**. Its bait density (0.850) and
depth (43.71×) are ordinary, so neither reachability nor coverage qualifies the finding.

**This is step 2's own ranking, by step 2's own criteria, and it is not an unblinding.** No
iteration-1 table was read; whether this agrees with iteration 1 is step 6's question and
is not asked here.

**The number is a floor, not a census.** Rarity and consequence come from joining
`coding_annotations`, which has no row for an allele the delivered callset never reported —
**32 such alleles sit in core-tier genes** and are uncounted. Those are precisely what a
second caller exists to find, so the biallelic set can only grow when they are annotated.

### H020 — does the target set beat its own null?

| set | genes | biallelic | rate |
|---|---|---|---|
| target | 396 | 4 | **0.0101** |
| decoy | 396 | 2 | **0.0051** |

Restricted to genes above half the median bait density, as entry 085 pre-registered:
4/391 against 2/380 — **unchanged**, so the bait-density imbalance between the two sets did
not create the difference.

**Supported in direction, not in strength.** Four events against two is Fisher one-sided
**p = 0.343**: this design cannot distinguish a twofold effect from none. Recorded at
confidence 0.45 to say so.

**The counterfactual matters more than the verdict.** Run the same enumeration **without**
the rarity and consequence filter and the decoys score *higher* than the targets — 0.573
against 0.509 for core:

| set | biallelic rate, unfiltered | biallelic rate, rare + protein-altering |
|---|---|---|
| core | 0.5085 | 0.0169 |
| mechanism-term | 0.4203 | 0.0145 |
| net | 0.5336 | 0.0075 |
| decoy | **0.5732** | 0.0051 |

Every person carries roughly two heterozygous differences per gene, so "two variants in one
gene" is the normal state of a genome and describes a decoy exactly as well as a target.
**The discriminating power is in the filter, not in the symptom-derived gene list.** Any
later step quoting a target-versus-decoy rate has to say which version it means.

### H019 — can the reads phase the pair?

**Supported as written, and the useful outcome did not happen.** WhatsHap resolved 6,823
blocks and placed **neither** of the lead gene's two alleles in any of them. The gap is
measured rather than guessed:

| | |
|---|---|
| distance between the two alleles | **10,911 bp** |
| heterozygous variants between them | **4** (mean spacing ~2.7 kb) |
| sequencing fragment | ~266 bp |
| phase blocks overlapping the span | **0** |
| mean depth there | 43.7× |

No fragment bridges consecutive links, so the chain cannot start. Depth rules out coverage
as the cause: this is how densely this child happens to be heterozygous in this gene.
**Step 2 therefore cannot show the two alleles sit on different copies.** The trans
configuration rests on step 4's population estimate, which the plan itself calls poorly
calibrated for ultra-rare pairs. That is a limitation handed forward, not a result.

### H023 — does a structural variant remove an exon?

**Refuted**, and both leads are weak.

| type | gene | tier | rare het | consensus calls | size |
|---|---|---|---|---|---|
| DEL | NLRP7 | net | 1 | 3 | 139–1,296 bp |
| DEL | OBSCN | **decoy** | 1 | 3 | 163–878 bp |

The pre-registered response is that such a gene becomes a lead, so it is recorded as one.
Why it is weak: **one of the two is a decoy**, a gene no symptom nominated, so the signal
is not specific to the target set; both are among the most structurally polymorphic genes
in the human genome, where a common benign deletion is the likelier reading; and at
139–1,296 bp neither removes a gene.

**The refutation needed the artefact control fixed before it meant anything.** The first
consensus run returned a **13 Mb deletion** and a **40 Mb inversion** in a living child. The
pre-registered bait-edge flag tests *proximity* to a boundary; these calls **span** the
unbaited gaps between baited islands — a read-pair caller sees two coverage islands with
emptiness between and reports the emptiness as one enormous event. Adding a span-coverage
rule (at least half of a call's extent must be baited territory) removes them:

| | consensus calls | median length | longest |
|---|---|---|---|
| credible (span mostly baited, not at an edge) | DEL 134, DUP 16, INV 14 | 302 bp | 9.7 kb |
| spanning unbaited gaps | DEL 12, DUP 46, INV 102 | 893 kb | 40.1 Mb |

**This is a widened implementation of a control the plan named before the run, not a new
threshold chosen after seeing the data**, and the distinction is the entry's to defend
rather than assume. A second floor was added for the same reason: anything under 50 bp is
an indel the small-variant callers already counted, and without that floor the "consensus
deletions" had a median length of **1 bp**.

## Assumptions and limitations

1. **Rarity and consequence are a join, not an annotation run.** Alleles absent from the
   delivered callset carry no annotation and are not counted — 32 in core-tier genes. The
   biallelic set is a floor.
2. **Concordance is substitutions only** (above), so the allele class with the weakest
   support is the one left untested.
3. **Phase is unresolved for the lead pair.** Step 2 contributes no direct evidence of
   trans.
4. **The target set is an enrichment at recall ≈ 0.36** (entry 084) and 8.79 % of bait
   k-mers were dropped as repeated (085). A gene absent here is not excluded; it may be
   unbaited or unreachable, and its bait density is in `results.it2_bait_density` for
   exactly that reading.
5. **SV precision priors are Kosugi 2019's**, measured on GRCh37 with 2019 tool versions —
   a prior printed beside each call, not our measurement. No HG002 positive control ran, so
   the SV consensus is reported and unvalidated.
6. **H020's comparison has almost no power** (p = 0.343). The direction is all it supports.

## Verdicts

| Claim | Verdict | Confidence |
|---|---|---|
| H016 a target gene carries a biallelic candidate | **supported** | 0.85 |
| H019 phasing closes the chain or names the gap | **supported** | 0.70 |
| H020 decoys yield fewer candidates per gene | **supported, weakly** | 0.45 |
| H022 ≥ 99 % concordance with the delivered callset | **supported** | 0.88 |
| H023 no two-class SV over an exon of a rare-allele gene | **refuted** | 0.25 |

Confidence is the register's transparent triage heuristic, not a calibrated posterior, and
three of the five were overridden away from the heuristic's suggestion with the reason
stored beside them.

## What this hands to step 3

`results.it2_read_alleles` (131,530 rows), `it2_scored_pairs` (792 genes with their rare
protein-altering counts, bait density and depth), `it2_sv_calls` and `it2_sv_consensus`,
`it2_exon_depth`, `it2_phase_blocks`, and one lead gene with a truncating and a
ClinVar-flagged allele that **the reads could not phase**. Step 3 genotypes those alleles
without an aligner or a caller, which is the independent reading the phase failure makes
more valuable, not less.
