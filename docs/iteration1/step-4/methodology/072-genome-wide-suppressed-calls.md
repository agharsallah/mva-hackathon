# 072 — Is a second allele hiding in a call the filters discarded, genome-wide?

**Step:** step-4   **Hypotheses tested:** H007 (pre-registered 2026-09-05); H006 (retrospective, entry 049)
**Written:** 2026-09-05.

## Question

Step 4 asks whether one of the two alleles sits in a non-PASS call. Entry
[049](../../../step-0/methodology/049-suppressed-calls.md) answered it for the eight-gene
panel (no). The coding layer built in [069](../../step-2/methodology/069-layer-2-coding-scan.md)
keeps every FILTER value, so the same question can be asked of every coding allele in the
genome at no extra cost.

## Hypothesis and prediction — written before the run

**H007:** no gene reaches a biallelic set only by rescuing a non-PASS coding call while also
carrying a ClinVar-pathogenic or LoF allele and a top-30 phenotype rank; BUB1B in particular
carries no rare protein-altering non-PASS coding allele. Predicted: `gene_biallelic` shows
BUB1B `n_nonpass = 0`, and every `biallelic_with_rescue AND NOT biallelic_pass` gene lacks a
P/LP or LoF allele or ranks worse than 30.

**H006 (retrospective):** zero of the 20 panel non-PASS calls are rare and protein-altering
(049). Filed and closed here, labelled retrospective.

## What would refute it

A rare protein-altering non-PASS coding allele in BUB1B; or a rescue-only gene with a
P/LP or LoF allele and a phenotype rank ≤ 30.

## Inputs

`results.coding_alleles` / `coding_candidates` / `gene_biallelic` (069, 070). Non-PASS
means `filter <> 'PASS'`; the values present are `MQ40`, `QD2`, `LowQual` and their
combinations.

## Commands

```bash
uv run mva-warehouse pg-query "SELECT filter, count(*) FROM pg.results.coding_alleles GROUP BY filter ORDER BY 2 DESC"
uv run mva-warehouse pg-query "SELECT gene, n_het_pass, n_nonpass, n_lof_pass, n_plp_pass, phenotype_rank
  FROM pg.results.gene_biallelic WHERE biallelic_with_rescue AND NOT biallelic_pass
   AND (n_plp_pass >= 1 OR n_lof_pass >= 1 OR phenotype_rank <= 30)"
uv run mva-warehouse pg-query "SELECT n_nonpass FROM pg.results.gene_biallelic WHERE gene = 'BUB1B'"
uv run mva-science evidence-add --hypothesis H007 ...     # rows 17, 18
uv run mva-science verdict H007 --commit --status supported --reasoning '...'
uv run mva-science verdict H006 --commit --status supported --reasoning '...'
```

## Observed

| FILTER over the 38,437 coding rows | rows |
|---|---|
| PASS | 36,843 |
| MQ40 | 1,048 |
| QD2 | 245 |
| LowQual;QD2 | 124 |
| MQ40;QD2 | 61 |
| LowQual;MQ40;QD2 | 53 |
| LowQual;MQ40 | 43 |
| LowQual | 13 |

Of the 875 rare protein-altering coding alleles, **129 are non-PASS** (875 − 746).

| Test | Result |
|---|---|
| genes biallelic only with a rescued call | **26** |
| … of which P/LP or LoF or phenotype rank ≤ 30 | **0 rows** |
| BUB1B `n_nonpass` | **0** |

So no gene is one suppressed call away from a credible diagnosis, and the BUB1B pair does
not depend on any filter decision. The 26 rescue-only genes are missense-only carrier
shapes with poor or absent phenotype ranks (`SELECT` above returned nothing).

## Evidence recorded

```
evidence 17  H007 supports 0.7  measurement  methodology/072  — BUB1B n_nonpass 0; 26 rescue-only genes, none P/LP / LoF / top-30
evidence 18  H007 neutral  0.0  absence      methodology/072  — 1,594 non-PASS coding rows; an allele never emitted is not a non-PASS call
evidence 10  H006 supports 0.6  annotation   methodology/049  (filed earlier today)
evidence 11  H006 neutral  0.0  absence      methodology/048  — TRIP13 callability
```

## Verdict

```
H007: prior 0.50  +1.400 supports 0.70 -> 0.802 ; +0.000 neutral -> 0.802 ; suggested 0.80
H006: prior 0.50  +1.200 supports 0.60 -> 0.769 ; +0.000 neutral -> 0.769 ; suggested 0.77
```

**H007 — supported, committed at 0.80** (revision 2). **H006 — supported, committed at
0.77** (revision 2), labelled retrospective.

Both verdicts are bounded by the same fact: a filtered call is a call the caller *made*. An
allele it never emitted — a structural variant, a deep-intronic change, a low-fraction
mosaic — is not in this table at any FILTER level. That is step 5's question, not step 4's.

## Next test

Step 5 (reads), conditional: only if the oracle's reply to submission v1 says one allele is
right and the other is not ([074](../../step-6/methodology/074-submission-v1-design.md)
decode table, row "partial match at rank 1"). Then the k-mer strike over BUB1B ± 50 kb is
the funded route to a partner the caller could not emit.
