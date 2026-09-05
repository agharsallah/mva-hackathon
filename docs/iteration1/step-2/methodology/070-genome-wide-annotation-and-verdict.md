# 070 — Does any coding gene outrank the BUB1B pair? The genome-wide annotation and the verdict

**Step:** step-2   **Hypotheses tested:** H004 (pre-registered in [069](069-layer-2-coding-scan.md)); H003 (retrospective, entries 031 + 051)
**Written:** 2026-09-05, from executed runs whose output is quoted below.

## Question

With every coding allele the proband carries annotated, does any protein-coding gene
carry a candidate biallelic set that beats the eight-gene panel's answer?

## Hypothesis and prediction — written before the run (069)

**H004:** BUB1B is the only gene that is biallelic on PASS calls **and** carries a ClinVar
pathogenic allele **and** ranks ≤ 30 in the panel-blind phenotype ranking. Predicted: in
`results.gene_biallelic` BUB1B satisfies all three; no other gene does; other biallelic
genes exist but fail the second or third condition.

**H003 (retrospective):** the panel filter leaves exactly the two BUB1B alleles. Its test
ran in 031 and 051 before the register existed; it is filed and closed here, labelled as
such.

## What would refute it

Another gene with `biallelic_pass`, a pathogenic or LoF allele, and phenotype rank ≤ 30; or
BUB1B missing from the biallelic set.

## Inputs

| Input | Value |
|---|---|
| `results.coding_alleles` | 38,437 rows, 38,087 distinct alleles ([069](069-layer-2-coding-scan.md)) |
| Ensembl VEP REST | release 116, GRCh38, `af_gnomadg=1 af_gnomade=1 canonical=1 hgvs=1`; batches of 200 |
| Rarity cutoff | gnomAD AF absent or < 0.01 (`RARE_RECESSIVE_AF`, recessive threshold) |
| Protein-altering | VEP impact `HIGH` or `MODERATE` |
| ClinVar P/LP | `clin_sig` contains `pathogenic`, contains neither `conflicting` nor any `benign` term |
| Phenotype ranking | `warehouse.hpo_gene_scores`, term set `proband-only` ([067](../../step-3/methodology/067-phenotype-ranking-without-java.md)) |

## Commands

```bash
uv run mva-warehouse annotate-coding --workers 4     # resumed from a 1-worker start
uv run mva-warehouse pg-derive --only coding_candidates gene_biallelic
uv run mva-warehouse pg-query "SELECT ... FROM pg.results.gene_biallelic ORDER BY biallelic_pass DESC, n_plp_pass DESC, n_lof_pass DESC, phenotype_rank NULLS LAST"
uv run mva-science evidence-add --hypothesis H004 ...   # rows 12–14
uv run mva-science verdict H004 --commit --status supported --reasoning '...'
uv run mva-science verdict H003 --commit --status supported --reasoning '...'
```

## Observed

`annotate-coding`, 191 requests in total (11 sequential, then 180 with 4 workers; the first
run was stopped and resumed from its checkpoint — resumption is the feature, and it worked):

```
alleles 38,087  checkpointed 2,200  to ask 35,887
  batch 180/180  answered 38,087
source   ensembl-vep-rest release=116 assembly=GRCh38
wrote    38,087 rows into warehouse.coding_annotations
  with a consequence   38,087
  with a gnomAD AF     37,904
  with a ClinVar call  9,506
  distinct genes       11,313
```

Wall clock: about 33 minutes (14:58 → 15:17 local, of which the first 12 minutes ran one
request at a time; four workers ran at ~6 batches/minute). One VEP POST of 200 alleles
takes ~30 s of server time.

| coding_annotations | Value |
|---|---|
| impact | MODERATE 15,694 · LOW 15,037 · MODIFIER 6,120 · HIGH 1,236 |
| top consequences | missense 15,209 · synonymous 11,948 · intron 5,294 · splice_region 2,401 · frameshift 558 · stop_gained 278 |
| absent from gnomAD | 183 |
| gnomAD AF < 0.01 (seen) | 1,341 |
| with an rsID | 37,931 |
| ClinVar P/LP after the predicate above | **10** alleles (51 before the `benign` clause — the difference is `benign;pathogenic` conflicts at common sites) |

`pg-derive --only coding_candidates gene_biallelic` (24 s): 38,437 and **667** rows.

The funnel, distinct alleles unless stated (`figures/track1/funnel.json`):

| Stage | Survivors |
|---|---|
| variant records | 5,012,204 |
| inside a coding interval (gene × allele rows) | 38,437 |
| distinct coding alleles, all annotated | 38,087 |
| rare | 1,524 |
| rare and protein-altering | 875 |
| … on PASS calls | 746 |
| genes carrying any such allele | 667 |
| genes biallelic on PASS calls | **65** |
| … with a ClinVar pathogenic allele | **1** |
| … and phenotype rank ≤ 30 | **1 — BUB1B** |

Head of `gene_biallelic` (the table's own order; positions never selected):

| gene | het | multi | hom | non-PASS | LoF | P/LP | novel | phenotype rank | consequences |
|---|---|---|---|---|---|---|---|---|---|
| **BUB1B** | 2 | 0 | 0 | 0 | 1 | 1 | 1 | **6** | stop_gained; missense_variant |
| SERPINA1 | 16 | 0 | 0 | 1 | 6 | 0 | 1 | 1,482 | 16 rare alleles in one gene — paralogous or hypervariable mapping |
| HLA-DRB1 | 11 | 1 | 0 | 3 | 4 | 0 | 1 | 523 | HLA: hypervariable by construction |
| HLA-DQA1 | 13 | 2 | 3 | 0 | 4 | 0 | 0 | 1,547 | idem |
| POU6F2 | 4 | 0 | 0 | 0 | 2 | 0 | 0 | 400 | two frameshifts, AF up to 1e-3 |
| PEX5 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 220 | homozygous splice_donor, gnomAD-absent |
| … | | | | | | | | | 65 biallelic genes in all; 41 of them with no HPO curation |

Counts across the 65: LoF-carrying 15; phenotype rank ≤ 30 exactly 1 (BUB1B); next
curated biallelic gene by rank HSPG2 at 150, then PEX5 at 220.

Panel genes in the coding scan: BUB1B 2 alleles, CENPE 6, CEP192 7, SMC5 1, TP53 1;
**CEP57, TRIP13, DICER1 carry no coding allele at any FILTER level**. TRIP13's absence is
consistent with its callability deficit ([048](../../../step-0/methodology/048-gene-background.md)).

## Evidence recorded

```
evidence 12  H004 supports 0.8  measurement  methodology/070  — 667 / 65 / 1 / 1, BUB1B rank 6
evidence 13  H004 supports 0.5  measurement  methodology/070  — the 15 LoF-carrying biallelic genes: no P/LP, ranks ≥ 220 or absent; HLA/SERPINA1 shape
evidence 14  H004 neutral  0.0  absence      methodology/070  — coding-only scope, 1.4 % of the genome
evidence  7  H003 supports 0.7  annotation   methodology/031  (filed earlier today)
evidence  8  H003 supports 0.6  annotation   methodology/051
evidence  9  H003 neutral  0.0  absence      methodology/031  — phase unresolved
```

## Verdict

`mva-science verdict H004`:

```
prior 0.50  (log-odds +0.000)
  +1.600  supports 0.80 — …667 genes… 65 biallelic… exactly one… BUB1B… rank 6   -> 0.832
  +1.000  supports 0.50 — …15 biallelic genes with a LoF allele… none… P/LP…      -> 0.931
  +0.000  neutral  0.00 — …coding intervals plus an 8 bp splice flank only…        -> 0.931
suggested confidence 0.93 (2 supporting, 0 refuting, 1 neutral)
```

**H004 — supported, committed at 0.93** (revision 2). Reasoning as committed: all three
conditions hold for BUB1B and for no other gene among 65; the verdict is about the coding
fraction — a non-coding or structural second allele elsewhere is outside this test.

**H003 — supported, committed at 0.93** (revision 2), labelled retrospective in the
reasoning: two independent routes agree on the same two alleles; phase unresolved.

The weighing is the register's transparent heuristic, not a calibrated posterior.

## Next test

- Step 3 ([071](../../step-3/methodology/071-phenotype-callset-join.md)): the join to the
  phenotype ranking as its own claim, H005.
- Step 4 ([072](../../step-4/methodology/072-genome-wide-suppressed-calls.md)): the
  non-PASS coding alleles, H007.
- Step 6 ([074](../../step-6/methodology/074-submission-v1-design.md)): the submission the
  verdict licenses.
- Open: the same scan over deep-intronic positions would need SpliceAI genome-wide — the
  one blind spot this entry names and does not close.
