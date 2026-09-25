# Step 11 — Track 2: the same chain, a second case

**Standing:** **opened 2026-09-25**; claim H096 filed before any run; T1 run and entry 156 written 2026-09-25 (verified that day).
Iteration 4, `step-11`, track 2. Marked **done** in `src/mva/science/step_maps/iteration4.py`: H096 refuted (0.15).
Every number this page will quote is owned by an entry under [`methodology/`](methodology/).

**Goal** (from `steps.py`):

> Does iteration 4's Track 2 chain (phenotype twin, PrimeKG walk, screen sweep, signature
> reversal, convergence, checks) run on a second rare disease, Bloom syndrome (BLM), by
> configuration alone, and does it propose a different drug set?

**Feeds:** the scalability section of
[`submissions/track2/iteration-4/`](../../../submissions/track2/iteration-4/README.md). The panel
weighs scalability at 15 %.

## Why Bloom syndrome

| property | why it makes a fair test |
|---|---|
| a different gene (`BLM`, a DNA helicase) and a different pathway (homologous recombination, not the mitotic checkpoint) | the chain must not carry MVA's biology in its code |
| a chromosomal-instability syndrome with growth restriction and cancer predisposition | the same *kind* of question, so every stage has something to find |
| well-studied Blm mouse alleles in MGI | the twin stage can be checked against a known answer |
| its own HPO annotation in `phenotype.hpoa` | the clinical input comes from a public file, not a hand-typed list |

## The claim

H096 (`P4-31`), filed 2026-09-25: zero source lines changed; every stage writes its table with
provenance; the Blm twin in the top 5 % of MGI genotypes; the two cases' generator unions share
at most 20 % of drugs (Jaccard ≤ 0.20). Refuted by any code change, a stage that fails, a Blm twin
outside the top 25 %, or Jaccard > 0.50.

**Retrospective limb.** Entry 150 already ran Bloom → Blm as E2's positive control, so clause (b)
partly re-observes a known result. It is reported as `retrospective:` and does not count as a
prediction; clauses (a) and (c) are the test.

## What does not transfer

- **K2's genome half.** There is no patient VCF for this case; K2 runs its label half (OnSIDES
  against the case's HPO terms) and says so.
- **The confirmed variant.** Bloom's chain starts from the gene, not from a patient's alleles.

## Experiments

| id | what | claim | entry | status |
|---|---|---|---|---|
| T1 | the whole chain on Bloom syndrome, configuration only | H096 `P4-31` | [156](methodology/156-the-chain-on-bloom-syndrome.md) | done 2026-09-25 — H096 refuted (clause a); (c) met, Jaccard 0.095 |

## What happened

**T1 — the chain on Bloom syndrome** ([156](methodology/156-the-chain-on-bloom-syndrome.md),
note [T1](submission-notes/T1.md)). All seven stages ran on Bloom syndrome and wrote their tables
with manifests, in 53 min for $0 — but **not by configuration alone**, so **H096 is refuted as
registered**.

- **What it took.** A survey of the tools before the run found four stages whose case lives in
  Python constants (the twin's output directory, the sweep's lineage, the reversal's gene, K1's
  rule) and seven that write MVA text (BUB1B, "the child") into outputs. One new driver,
  `tools/transfer_it4.py` (378 lines, no existing line edited), filled the four; its `relabel`
  step made 136 recorded corrections and re-hashed 7 manifest digests.
- **The twin** (`retrospective:`, entry 150's control): best *Blm* genotype at 1.15 % / 1.08 % of
  76,699 (p 0.037 / 0.021) — but *Recql4* ranks higher (0.82 %).
- **The generators.** Walk 50 (driven by PrimeKG's KIT edge, not BLM); twin **0** (no drug has
  been tried in a *Blm* mouse); PRISM 2 of only 14 eligible drugs (PRISM's primary screen measures
  no haematological line); LINCS 1 (mepivacaine), its positive control failed again.
- **Nothing converges** (p 1.0), no survivor. K1 fails cisplatin (alkylating, GeneReviews);
  K2 cannot fail anything without a genome.
- **A different drug set:** 10 of 105 drugs shared, **Jaccard 0.095** (clause c met); dasatinib
  is the one drug both cases reach by different evidence.

![T1 stages](../../../figures/it4/step11-t1-stages.svg)

> **Legend** — blue = the MVA run, built for that case; Bloom column: green = configuration
> alone, yellow = ran from flags but wrote MVA-case text that `tools/transfer_it4.py relabel` had
> to correct, red = needed new code (`tools/transfer_it4.py`), grey = not written; "gap" = entry
> 156's static-survey row; seconds = wall time from the log.

![T1 overlap](../../../figures/it4/step11-t1-overlap.svg)

> **Legend** — blue = MVA's lists, yellow = Bloom's lists; the shared bar is green when the
> Jaccard index is ≤ 0.20 (clause c met), red above 0.50 (refuted), yellow between.

![T1 twin](../../../figures/it4/step11-t1-twin.svg)

> **Legend** — blue bars = the best-genotype percentile for 1,000 IC-matched random term sets;
> solid line = the real query's best genotype, green when ≤ 5 %; dashed yellow = the 5 % bar;
> right: yellow = *Blm*, grey = the case's within-pathway genes (context).
