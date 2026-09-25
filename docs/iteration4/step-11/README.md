# Step 11 — Track 2: the same chain, a second case

**Standing:** **opened 2026-09-25**; claim H096 filed before any run; entry 156 reserved.
Iteration 4, `step-11`, track 2. Marked **open** in `src/mva/science/step_maps/iteration4.py`.
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
| T1 | the whole chain on Bloom syndrome, configuration only | H096 `P4-31` | 156 | planned |
