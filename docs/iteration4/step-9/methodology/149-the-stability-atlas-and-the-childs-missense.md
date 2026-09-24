# 149 — The BubR1 stability atlas and the child's missense allele

**Step:** iteration 4, [step 9](../README.md) — Track 2, experiment **E1**. **Date:** 2026-09-24.
**Claims:** H083 (`P4-18`), H084 (`P4-19`), filed with `mva-science hypothesis-add` before any run.
**Sources:** genomic (the child's BUB1B `missense_variant` record, step 1's `records.parquet`,
read only by `place`, output in `build/` only) + public protein data + published allele labels.
The clinical HPO terms are not an input; § Conclusion says what the result means for them.

## Question

Is the child's BUB1B missense allele predicted **abundance-lowering** (the substitution
destabilises the folded protein, so the cell degrades it and there is less BubR1) or
**function-impairing** (the protein is made in normal amounts but works worse)? Direction D3
("raise the amount of working BubR1") only makes sense for the first.

Software analogy: two failure modes of a service — it crashes on start (never serves: fix = run
more replicas) vs it runs but returns wrong answers (more replicas do not help). The analogy
breaks down in one way: a destabilised protein may still work when forced to normal amounts,
which is exactly what Suijkerbuijk 2010 showed for two alleles.

## Hypothesis and prediction

Written before the atlas was built (the ThermoMPNN smoke on p53 had run; no BubR1 number existed).

- **H083 / `P4-18`:** over the MVA missense alleles that Suijkerbuijk 2010 (PMID 20516114) and
  other verified papers classify by protein level, a ΔΔG-based score ranks abundance-lowering
  above function-impairing with **AUROC ≥ 0.8**.
- **H084 / `P4-19`:** the child's missense has predicted ΔΔG in the **most destabilising 20 %**
  of all possible BubR1 missense substitutions **and** the E1 classifier calls it
  abundance-lowering.

Pre-set analysis (fixed before the run, not tuned afterwards):
- positive class = `abundance-lowering`; negative class = `stable` (protein level not lowered —
  function-impairing or not). The paper's second class is "stable"; only one stable allele
  has a shown function defect, so "stable" is the honest label.
- **primary** set = MVA alleles only (`primary = yes` in the labels file); **extended** = plus
  non-MVA alleles with a protein-level readout (sensitivity analysis only).
- models: ΔΔG alone (raw score and 1-feature ridge logistic), then ΔΔG + RSA + pLDDT; ridge
  `l2 = 1`, standardised in each fold, leave-one-out; AUROC with a 2,000-draw stratified
  bootstrap (seed 0). Call = abundance-lowering if the full-data fit gives p ≥ 0.5.
- comparator (not a claim): ESM1b LLR (sequence-only), negated so higher = more damaging.

## What would refute it

- H083: AUROC ≤ 0.6, **or** fewer than 4 labelled alleles per class can be recovered — then the
  test has no power and is reported as such.
- H084: ΔΔG in the least destabilising 50 %, or the classifier calls it stable
  (function-impairing).

## Inputs

| input | value |
|---|---|
| structure | AlphaFold DB `AF-O60566-F1-model_v6.pdb` (model 2025-08-01, UniProt seq v3, mean pLDDT 63.59), sha256 `684e4316…cd49f`; CC BY 4.0. Its sequence equals the UniProt canonical (checked by `build`). |
| features | UniProtKB O60566 JSON (entry v234; sha256 `73899b2e…36ec1`); InterPro `entry/all` for O60566 (Pfam, CDD, SMART, PROSITE profile rows kept); a KEN tripeptide scan; one literature span: BUB3-binding (GLEBS) bound 387–483 (Suijkerbuijk 2010: the 386X truncation cannot bind BUB3, 483X can). UniProt and InterPro annotate no GLEBS and no ABBA motif; none is invented. |
| stability model | ThermoMPNN (Dieckhaus 2024, PNAS, PMID 38285937; MIT), repo commit `370f76ec62bd`, `thermoMPNN_default.pt` + ProteinMPNN `v_48_020`; weights digest `d7169ce6…:fdacf4e2…` (sha256 over each weights folder). Sign: + = destabilising. |
| sequence model (comparator) | ESM1b LLR matrix for O60566 (Brandes 2023, PMID 37563329; MIT), from `ALL_hum_isoforms_ESM1b_LLR.zip` sha256 `42b90ce7…7cd0` already in `build/it4/tables/esm1b/` (step 8). Not re-run. |
| RSA | Shrake–Rupley in numpy (probe 1.4 Å, 100 dots, Bondi radii) ÷ Tien 2013 max ASA, capped at 1. Checked against Biopython 1.88 `ShrakeRupley`: Pearson r = 0.997 over 1,050 residues, max |Δ| 0.099. |
| labels | `ressources/track2/bub1b_published_alleles.tsv` (+ provenance): full texts of Suijkerbuijk 2010 (PMC2887387, eutils XML), Sieben 2020 (PMC6934189 HTML), Wei 2026 (PMC13349884), abstracts incl. Hahn 2016 (PMID 27239782). Hanks 2004, Matsuura 2006, Rio Frio 2010 are not in PMC; their missense alleles either are the ones Suijkerbuijk assayed (Hanks, same group) or have no allele-level protein readout in the abstract (Matsuura; full text not accessed). |
| the child's allele | the BUB1B `missense_variant` record's `hgvs_p` in `build/it4/records.parquet`, found via `[case] confirmed_gene` in `src/mva/zoo/zoo.example.toml`; read only by `place`; output `build/it4/track2-e1/child.json` only |
| GPU | Modal T4, app `mva-zoo-thermompnn` (ephemeral `modal run`), `max_containers=1`, no volume (weights ship in the cloned repo) |

Labels recovered:

| class | primary (MVA patients) | extended only |
|---|---|---|
| abundance-lowering | I909T, R727C, R814H, L844F, L1012P (5) | — |
| stable | Y155C (function-impairing: checkpoint lost), R550Q (functional), Q921H (wild-type-like, in cis with L844F) (3) | C945Y (heterozygous colorectal-cancer carrier, not MVA) |
| ambiguous (excluded) | — | W722R, A739S (carrier lymphocytes, qualitative trend, mRNA also lower) |

**The child's allele is not among the labelled alleles** (`place` → `in_labelled_set: false`).

## Commands

```bash
# ThermoMPNN lane: smoke on the repository's own example, then the atlas (T4)
uv run --group zoo-ml python tools/modal_trace.py run thermompnn smoke
uv run --group zoo-ml python tools/modal_trace.py run thermompnn atlas --uniprot O60566 --seconds-estimate 120
uv run --group zoo-ml python tools/modal_trace.py stop thermompnn     # "No App ... found": both runs had already stopped
uv run --group zoo-ml modal app list                                   # both mva-zoo-thermompnn apps: stopped, 0 tasks
uv run --group zoo-ml modal billing report --for today --json

# atlas, evaluation, placement, figures (laptop)
ESM1B=build/it4/tables/esm1b/esm1b-extracted/content/ALL_hum_isoforms_ESM1b_LLR
A=ressources/track2/bub1b_atlas.parquet L=ressources/track2/bub1b_published_alleles.tsv
uv run python tools/variant_atlas.py build --uniprot O60566 \
  --ddg build/it4/track2-e1/thermompnn/O60566.tsv --esm1b "$ESM1B/O60566_LLR.csv" \
  --region "BUB3-binding (GLEBS) bound:387-483:literature PMID 20516114 (386X lacks, 483X keeps BUB3 binding)" \
  --out $A
uv run python tools/variant_atlas.py evaluate --atlas $A --labels $L --out build/it4/track2-e1/evaluate.json
uv run python tools/variant_atlas.py place --atlas $A --labels $L --case src/mva/zoo/zoo.example.toml \
  --records build/it4/records.parquet --out build/it4/track2-e1/child.json
uv run python tools/render_step9_e1.py
```

Label extraction: eutils `efetch db=pmc` (XML → text), `efetch db=pubmed rettype=abstract`,
`esearch` for five BUB1B/BUBR1 queries; sentences copied verbatim into the TSV's `evidence`
column (scripts in the session scratchpad; raw texts in `build/it4/track2-e1/papers/`).

## Observed output

**Lane.** Smoke: 3,880 swaps of p53 (PDB 2OCJ chain A) in 4.0 s; max |ΔΔG − published example
output| = 0.0006 kcal/mol over all 3,880 → the container reproduces the authors' numbers. Atlas:
21,000 swaps (1,050 residues × 20, self-swaps dropped later → 19,950 rows), 0 structure gaps,
12.1 s of T4.

**Atlas (protein-generic).** Median ΔΔG 0.21; top-20 % cut 1.02 kcal/mol. Per residue, mean ΔΔG
tracks burial (Spearman ρ = −0.71 vs RSA) and confidence (ρ = 0.63 vs pLDDT): the model scores
the folded TPR and pseudokinase domains high and the disordered middle near zero
([figure a](../../../../figures/it4/step9-e1-atlas.svg)). ΔΔG vs −ESM1b LLR: Pearson r = 0.48.

**Labelled alleles** (public, other people's):

| allele | class | ΔΔG | ΔΔG pct | ESM1b LLR | pLDDT | RSA | region |
|---|---|---:|---:|---:|---:|---:|---|
| L1012P | abundance-lowering | 3.11 | 99.0 | −9.76 | 95.3 | 0.01 | Protein kinase |
| I909T | abundance-lowering | 1.94 | 91.5 | −9.24 | 87.0 | 0.02 | Protein kinase |
| L844F | abundance-lowering | 1.51 | 87.0 | −7.93 | 85.9 | 0.01 | Protein kinase |
| R727C | abundance-lowering | 0.91 | 78.3 | −5.52 | 88.5 | 0.06 | none annotated (near the kinase domain) |
| R814H | abundance-lowering | 0.86 | 77.3 | −9.62 | 90.2 | 0.17 | Protein kinase |
| Y155C | stable | 2.23 | 93.9 | −11.36 | 96.3 | 0.00 | BUB1 N-terminal (TPR) |
| Q921H | stable | 0.98 | 79.3 | −8.56 | 83.2 | 0.03 | Protein kinase |
| R550Q | stable | 0.04 | 27.4 | −2.84 | 35.3 | 0.80 | none annotated |
| C945Y (extended) | stable | −0.07 | 13.3 | −9.27 | 76.9 | 0.17 | Protein kinase |

**Separation** (`evaluate.json`; bootstrap 95 % CI; [figure c](../../../../figures/it4/step9-e1-roc.svg)):

| score | primary, 5 vs 3 | extended, 5 vs 4 |
|---|---|---|
| raw ΔΔG | **0.60** [0.13, 1.00] | 0.70 [0.25, 1.00] |
| raw −ESM1b LLR (comparator) | 0.53 [0.00, 1.00] | 0.50 [0.10, 0.90] |
| ridge logistic ΔΔG, LOO | 0.13 [0.00, 0.40] | 0.40 [0.05, 0.80] |
| ridge logistic ΔΔG+RSA+pLDDT, LOO | 0.00 [0.00, 0.00] | 0.45 [0.00, 0.90] |

LOO AUROC below the raw score's is the known small-n artefact of pooling leave-one-out
probabilities (removing a positive moves the intercept against it); it says the logistic layer
adds nothing, not that ΔΔG is anti-informative.

**The child's missense allele** (values rounded; exact ones in `build/it4/track2-e1/child.json`):

| quantity | value |
|---|---|
| ΔΔG | ≈ 1.5 kcal/mol |
| ΔΔG percentile, all 19,950 substitutions (pre-registered) | **87th** (most destabilising 13 %) |
| post hoc: percentile among folded residues (pLDDT ≥ 70, 9,728 rows) | 74th |
| post hoc: percentile within the UniProt "Protein kinase" domain (5,415 rows) | 72nd |
| ESM1b LLR percentile (damage) | 73rd |
| region | UniProt "Protein kinase" domain (pseudokinase) and CDD cd14029 |
| pLDDT / RSA band | ≥ 90 (very confident) / < 0.2 (buried) |
| call, ΔΔG model (primary fit) | abundance-lowering, p = 0.64 (class base rate 5/8 = 0.625) |
| call, ΔΔG+RSA+pLDDT (primary fit) | abundance-lowering, p = 0.67 |
| calls, extended fit | 0.60 / 0.63 (base rate 5/9 = 0.56) |

**Spend.** Ledger (`e1-thermompnn`): $0.0026 (16.1 GPU-s, 2 calls). Modal billing report,
today, both `mva-zoo-thermompnn` apps: $0.0149 (includes cold start and the 60 s idle window).
No volume created.

## Verdict

- **H083 — refuted as registered, and without power.** The primary set holds 3 stable alleles
  (< 4 → no power), and raw ΔΔG AUROC is 0.60 (≤ 0.6). The extended set's 0.70 [0.25, 1.00] is
  inside the inconclusive band. Why: ThermoMPNN reads fold destabilisation of a domain, and two
  stable alleles sit at buried folded residues — Y155C (TPR, ΔΔG 2.2) and Q921H (pseudokinase,
  1.0) score above two abundance-lowering alleles. Cellular abundance adds chaperone (HSP90)
  dependence, degradation and partner binding, which a single-structure ΔΔG does not see.
- **H084 — prediction met on both counts, weakly.** ΔΔG is at the 87th percentile (≥ 80th) and
  both models call abundance-lowering (p ≥ 0.5); no refutation condition holds. But the
  classifier has no demonstrated skill (LOO AUROC 0.13 / 0.00) and its p is the class base rate
  (0.64 vs 0.625): the call carries no information beyond "most published MVA missense alleles
  are abundance-lowering". Among folded residues alone the allele is at the 74th percentile, and
  one wild-type-like allele (Q921H) and one stable function-impairing allele (Y155C) score as
  high or higher. Only the ΔΔG half is evidence.

The confidences are for `mva-science verdict`; the weighing is a transparent triage heuristic,
not a calibrated posterior.

## Limitations

- n = 8 (primary): the AUROC moves in steps of 1/15 and every CI spans ~0.9.
- One stability predictor on one predicted structure of a protein whose AlphaFold model is
  low-confidence in half its length; no complex (BUB3, CDC20) context; RaSP / a second
  ΔΔG model not run (ThermoMPNN reproduced its published example, but is not ensembled).
- Labels come from overexpression in HeLa/U2OS plus a few patient lines; "stable" mixes
  functional (R550Q, Q921H) and function-impairing (Y155C) alleles; Q921H is a probable passenger.
- The GLEBS span is a bound from truncation mapping, not a motif call.
- Percentiles over "all substitutions" include every disordered residue; the folded-only
  percentile (74th) is post hoc and stated as such.

## Conclusion

A reusable, gene-agnostic tool now builds a stability atlas for any UniProt protein in ~12 GPU
seconds (`tools/variant_atlas.py`, `src/mva/drugs/variant_atlas*.py`, lane
`src/mva/zoo/modal_apps/thermompnn.py`). On BubR1 it **cannot** separate the published
abundance-lowering from stable MVA alleles (H083 refuted, no power), so it cannot by itself
answer "unstable or inactive?". The child's missense is predicted destabilising (87th
percentile, buried, confident region, inside the UniProt pseudokinase domain), which is
consistent with the abundance-lowering class and with Suijkerbuijk's positional rule (5 of 6
MVA missense alleles in or near the kinase domain are abundance-lowering; that rule was drawn
from the same alleles, so it is a prior, not a test). **D3 keeps its standing as a dosage
argument** — strengthened only in wording: "predicted destabilising, class not proven". The
clinical HPO terms are not touched by this result: it bears on which drug direction fits the
genotype, not on whether the genotype explains the phenotype.
