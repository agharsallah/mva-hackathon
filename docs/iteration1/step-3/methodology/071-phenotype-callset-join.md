# 071 — Do the symptoms and the DNA point at the same gene? The ranking joined to the callset

**Step:** step-3   **Hypotheses tested:** H005 (pre-registered 2026-09-05, before the join ran); H002 (verdict committed)
**Written:** 2026-09-05.

## Question

Step 3's goal is whether an unbiased, symptom-driven gene ranking agrees with the panel-first
candidate list. Entry [067](067-phenotype-ranking-without-java.md) built the ranking and
saw BUB1B 6th of 5,267 — but against the *panel*, which is a list someone chose. The
honest cross-check is against the **genome-wide** set of genes the DNA itself nominates:
every gene carrying a candidate biallelic set, from [070](../../step-2/methodology/070-genome-wide-annotation-and-verdict.md).

## Hypothesis and prediction — written before the run

**H005:** among all genes with a candidate biallelic set of rare protein-altering PASS
alleles, BUB1B is the best-ranked in the panel-blind phenotype ranking. Predicted:
ordering `gene_biallelic` rows with `biallelic_pass` by `phenotype_rank` puts BUB1B first,
and the runner-up ranks worse.

## What would refute it

A different `biallelic_pass` gene with a smaller phenotype rank than BUB1B's.

## Inputs

`results.gene_biallelic` (070) joined in its own SQL to `warehouse.hpo_gene_scores`,
term set `proband-only` — the seven terms describing the child, without the parental
miscarriage term (H002). Neither table reads the other's inputs: the ranking reads two
public ontology files; the scan reads the callset.

## Commands

```bash
uv run mva-warehouse pg-query "SELECT gene, phenotype_rank, n_het_pass, n_hom_pass, n_lof_pass, n_plp_pass
  FROM pg.results.gene_biallelic WHERE biallelic_pass ORDER BY phenotype_rank NULLS LAST"
uv run mva-science evidence-add --hypothesis H005 ...     # rows 15, 16
uv run mva-science verdict H005 --commit --status supported --reasoning '...'
uv run mva-science verdict H002 --commit --status supported --reasoning '...'
```

## Observed

65 genes are biallelic on PASS calls. By phenotype rank:

| rank | gene | what the DNA holds |
|---|---|---|
| **6** | **BUB1B** | stop_gained (ClinVar P/LP) + novel missense |
| 150 | HSPG2 | two rare missense |
| 220 | PEX5 | homozygous splice_donor, gnomAD-absent |
| 400 | POU6F2 | two frameshifts + two missense |
| 503 | ZFP57 | four missense |
| 523 | HLA-DRB1 | HLA — hypervariable |
| … | | |
| — (no curation) | 41 genes | |

Exactly one biallelic gene ranks ≤ 30; it is BUB1B. The figure
`figures/track1/track1-gene-scatter.png` plots every biallelic gene by rank and allele
count (rendered by `tools/render_track1_figures.py`).

## Evidence recorded

```
evidence 15  H005 supports 0.7  measurement  methodology/071  — BUB1B first at 6; next HSPG2 150, PEX5 220; 41 of 65 uncurated
evidence 16  H005 neutral  0.0  absence      methodology/071  — the panel and the HPO curation draw on the same literature
```

## Verdict

```
prior 0.50  (log-odds +0.000)
  +1.400  supports 0.70 — …BUB1B first at rank 6; the next curated biallelic gene is HSPG2 at rank 150…   -> 0.802
  +0.000  neutral  0.00 — …convergence is strong corroboration, not fully independent confirmation…        -> 0.802
suggested confidence 0.80 (1 supporting, 0 refuting, 1 neutral)
```

**H005 — supported, committed at 0.80** (revision 2). The two instruments share no data,
but they are not fully independent: the panel that motivated the scan and the HPO
annotations that drive the ranking both summarise the same MVA literature. Corroboration,
not proof.

**H002 — supported, committed at 0.86** (revision 2). Its evidence (rows 5, 6) was
measured in 067 §5 the same day the claim was filed, so it is retrospective in spirit; the
verdict records that. Applied downstream: `gene_biallelic` reads the proband-only set.

**H001 stays `proposed`.** Its prediction is conditioned on the oracle confirming the gene;
it is the claim the final submission tests, and it is not settled by re-reading the same
ranking.

## Next test

The oracle reply (step 6) settles H001 and H005 together: a confirmed BUB1B pair makes both
predictions observed; a confirmed pair in a gene ranked outside the top 200 refutes both.
