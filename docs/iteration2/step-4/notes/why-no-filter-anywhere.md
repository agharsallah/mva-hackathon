# Why step 4 has no hard filter anywhere

**Standing:** 2026-09-18 — holds for step 4 and for anything that reuses
`mva.pipeline.likelihood`. Written after the run, from what the run measured.

## The result in one sentence

Iteration 1's funnel — rare **and** protein-altering **and** biallelic **and** PASS — would
have deleted the genes that turned out to matter most for reading the answer: the
runner-up, which has no curated phenotype; the 2,670 single-allele hypotheses, which are the
shape a biallelic filter removes by definition; and the 8,252 uncurated genes, which is 72 %
of everything scored.

## Four cuts, and what replaced each

| Iteration 1's cut | What it deleted | Step 4's multiplier |
|---|---|---|
| gnomAD AF < 1e-3 | every allele above the line, including the ones whose frequency lookup simply failed | a ladder: absent or < 1e-4 → ×2.08; ≥ 1e-3 → ×1/4.33; ≥ 5e-3 → ×1/18.7 |
| protein-altering only | synonymous and intronic alleles, including anything a splice predictor might have rescued | consequence class → ×1 for a class with its own tool, ×1/2.08 for a silent allele outside the splice window |
| biallelic only | every gene with one damaging allele and no partner | LIRICAL's degradation: the ratio to the power of the fraction of required alleles seen — one of two keeps the square root |
| FILTER = PASS | every call the caller flagged | ×⅓, measured against a run with the down-weight removed, which moved nothing |

## Three arguments for the design, in the order they carry weight

**1. A filter's error is silent and a multiplier's is visible.** A gene deleted by a cut
leaves no row. A gene divided by 18.7 leaves a row at rank 8,000 with the term that put it
there printed beside it. Every sentence of the form "nothing was found in gene X" becomes
checkable, and [099](../methodology/099-every-gene-ordered-with-nothing-filtered-out.md)'s
lane-coverage table exists only because no allele was ever dropped.

**2. The evidence this case has is exactly the evidence a filter throws away.** 73.6 % of
protein-coding genes carry no HPO curation
([084](../../step-1/methodology/084-the-blind-target-set.md)), and the symptom ranker returns
*nothing* for them — not a low score. Any filter on phenotype evidence removes three quarters
of the genome before the DNA is read. The measured unranked ratio of **×0.379** is the whole
of the difference between "down-weighted 2.6-fold" and "deleted", and the run's second-ranked
gene lives in that bucket.

**3. The nulls are only interpretable without a filter.** A decoy null measures the
*scoring*. If a filter had already removed most decoys, the AUC would measure the filter's
gene list rather than the ranking, which is the mistake step 2 made and
[090](../../step-2/methodology/090-the-alleles-the-vendor-never-reported.md) caught: targets
and decoys carry a biallelic candidate at the same rate, so a gene list is not an instrument.

## What it costs, stated

* **Compute.** 51,920 hypotheses instead of a few dozen. It is seconds on a laptop, so the
  cost is not compute — it is that a table with 51,920 rows needs a page and a set of nulls
  before it means anything, which is most of what this step built.
* **Noise at the top.** Two HLA genes reach ranks 3 and 5 because every human carries many
  rare-looking alleles there. A filter would have removed them and also removed the honest
  statement that the ranking has this failure mode.
* **A pair enumeration cap.** 144 genes carry more than 12 heterozygous alleles; their pairs
  are enumerated over the 12 strongest. This is the one place a cut survives, it is recorded
  on every run, and it affects no gene in the top 200.

## The one thing that is still a filter, and why it is allowed

`results.coding_alleles` restricts to alleles inside a coding interval. That is a *scope*
declared by the step's goal — "every protein-coding gene in the VCF" — rather than a
judgement about a candidate, and it is the boundary iteration 2's other steps share. A
non-coding regulatory variant is out of scope for this step and is not scored badly by it;
the difference is stated so nobody reads a genome-wide ranking as covering the genome.
