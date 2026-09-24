# 152 — Is each candidate safe *for this child*? His pharmacogenome and his own phenotypes

**Step:** iteration 4, [step 9](../README.md), experiments E5 and E6, run together.
**Date:** 2026-09-24. **Claims:** H090 (`P4-25`), H091 (`P4-26`). **Sources:** **both, and
this entry is the clearest case of the standing two-source rule** — E5 reads only the
genome (the WGS callset, through PharmCAT), E6 reads only the clinical dataset (the
proband's own HPO terms, through drug labels), and the deliverable is the join. No genomic
position, diplotype, allele string or read appears in any tracked file; what crosses the
boundary is an *actionability word* ("Poor Metabolizer", "no call") and a count.

**Clinical framing.** This is a research exercise. Nothing here advises for or against
giving any drug to this child. Every row is a **question for a treating team**, with the
evidence and the uncertainty attached.

## Question

For every Track 2 candidate — the eleven mechanism drugs, the fifty RMS-context drugs, the
do-not table and the new D5 drugs — does the child's *own* genome change how it would be
prescribed, and does his *own* phenotype list collide with what its label says it does?

## Hypothesis and prediction

Filed in the register before this entry:

| id | claim | prediction | refuted if |
|---|---|---|---|
| H090 `P4-25` | the child's genome carries ≥ 1 pharmacogenomic result that changes how a shortlisted candidate would be prescribed | PharmCAT + CPIC return ≥ 1 non-normal phenotype among SLCO1B1, ABCG2, CYP2C9 (statins), CYP3A5 (vincristine), CYP2C9 (valproate), G6PD (chloroquine/HCQ) | every relevant gene is normal, **or** too few positions are callable to make any diplotype |
| H091 `P4-26` | label-derived adverse effects flag a conflict between ≥ 1 shortlisted candidate and one of the child's own phenotypes | in OnSIDES ≥ 1 shortlisted approved drug carries a labelled adverse effect matching nephrocalcinosis, growth failure or myopathy, **above the rate in a matched set of approved drugs not on the shortlist** | none carries any, or the shortlist rate is no higher than the comparison set |

Analysis plan, fixed before the runs:

| choice | fixed value | why |
|---|---|---|
| PGx caller | PharmCAT 3.4.0, allele/guideline data `2026-07-13-11-40`, Java 21 | the published bridge from a VCF to CPIC (PMID 31306493, 36350094) |
| callset preparation | subset to PharmCAT's 23 regions (± 200 bp), `bcftools annotate --rename-chrs` to `chr`, then PharmCAT's own preprocessor (which normalises and left-aligns) | the delivered VCF is no-`chr` (`ideation/data-findings.md` §2.1) |
| the no-call problem | run PharmCAT **twice** — as delivered, and with `--absent-to-ref` — and report the difference as the uncertainty | a variant-only callset makes every unlisted PGx position a no-call; `--absent-to-ref` invents reference calls and PharmCAT itself labels it DANGEROUS |
| what is a "result" | only the strict run's phenotypes are **observed**; anything that appears only under `--absent-to-ref` is an **assumption** and is labelled as one everywhere | see Verdict |
| callability proxy | per gene: PASS variants the callset holds inside the gene's region ÷ region kb, over the genome-wide density (4,740,790 PASS ÷ 3,099,922,541 bp = **1.529 per kb**). ≥ 0.5× "region normally callable"; 0.2–0.5× "weakly supported"; < 0.2× "not supported" | distinguishes "absent because it matches the reference" from "absent because the region is a hole", which the position itself cannot |
| label source | OnSIDES v3.1.1 (data CC BY 4.0), all four label jurisdictions (US/EU/UK/JP) | US-only loses vincristine and irinotecan entirely (UK labels only) |
| HPO → label terms | [`ressources/track2/hpo_to_adverse_terms.tsv`](../../../../ressources/track2/hpo_to_adverse_terms.tsv), 16 active MedDRA ids over 5 proband phenotypes, each row with a tier and a written rationale | no standard HPO↔MedDRA mapping exists; it is a judgement call, so it is inspectable |
| unit of the rate | one **ingredient** (does any of its labels carry a mapped effect?) | a drug with 400 labels would otherwise swamp one with 3 |
| comparison set | the 5 nearest approved ingredients per candidate on *number of distinct labelled adverse effects*, candidates excluded, ties broken by name | label verbosity / depth of study is the main confounder of "does this label mention muscle injury"; ATC class was rejected because nicotinamide, bortezomib and dasatinib have no class-mate on the shortlist |
| interval | Wilson 95 % | several candidates have single-digit label counts |
| paediatric view | openFDA FAERS, `patientonsetage` 0–17 years, exact MedDRA PT | OnSIDES v3.1.1 ships **no** paediatric ADE table (its paediatric file is a 200-label annotation gold standard) |
| positive controls | furosemide (published nephrocalcinosis association in preterm infants, PMID 35348900) and calcitriol (top FAERS paediatric nephrocalcinosis drug) must be matched by the mapping | otherwise a null result on nephrocalcinosis is uninterpretable |

**The 8th clinical term is excluded.** HP:0200067 (recurrent spontaneous abortion) is the
*parents'* reproductive history, not a phenotype of the proband. A drug given to the child
cannot act on it, and including it would inflate the match rate with an event belonging to a
different person. It is recorded in the mapping table with `used_for_flag = no` and the
reason, rather than silently dropped. HP:0001622 (premature birth) and HP:0001518 (small for
gestational age) are the proband's own but are **already realised perinatal events**: they
are mapped for inspection and excluded from the post-natal drug flag, again with the reason
written in the row.

## What would refute it

- H090: no gene among SLCO1B1/ABCG2/CYP2C9/CYP3A5/G6PD returns a non-normal phenotype from
  **observed** positions, or no gene is callable at all.
- H091: no shortlisted ingredient carries a mapped effect, or the shortlist's flagged share
  is at or below the comparison set's (CIs overlapping the comparison point estimate is
  reported as "not shown", not as support).
- The method (not a hypothesis): if **neither positive control** is matched by the mapping,
  the nephrocalcinosis arm is uninterpretable and is reported as such.

## Inputs

All fetched 2026-09-24 into `build/it4/track2-e56/raw/` (not committed).

| file | source | bytes | sha256 (first 16) | licence |
|---|---|---|---|---|
| the callset (`WGS_EX2312012_HGWCNDSX7.vcf.gz`) | object store `s3://mva/source/` | 315,153,971 | `bec64c68d3ad10d0` | patient data — never leaves `build/` |
| `pharmcat-3.4.0-all.jar` | PharmGKB GitHub release v3.4.0 | 32,292,707 | `9317ef632bf6c978` | MPL-2.0 |
| `pharmcat-pipeline-3.4.0.tar.gz` (preprocessor, positions, regions BED) | same release | 28,541,287 | `8b3f3fc559a80c00` | MPL-2.0 |
| `pharmcat_positions_3.4.0.vcf.bgz` | same release | 11,027 | `01a28fe31675c9e8` | MPL-2.0 |
| `onsides-v3.1.1.zip` | tatonetti-lab GitHub release | 84,862,297 | `7739c73336786c92` | data CC BY 4.0, code MIT |
| GRCh38 reference FASTA | PharmCAT preprocessor auto-download (Zenodo 7288118) | 814,284,800 (tar) | — | public |
| openFDA `drug/event.json` | api.fda.gov, queried live | — | — | US public domain |

Tools: `bcftools 1.24` (htslib 1.24), OpenJDK `21.0.12.1` (Homebrew), PharmCAT `3.4.0` with
allele/guideline data `2026-07-13-11-40`, DuckDB via `uv run`.

Clinical input: [`ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`](../../../../ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md).
Candidate lists: [`ressources/track2/shortlist.tsv`](../../../../ressources/track2/shortlist.tsv)
(61 rows), [`do_not.tsv`](../../../../ressources/track2/do_not.tsv) (23 rows), plus dasatinib
(E2's D5 analogue, `model_interventions.tsv`) and the two positive controls — **85 distinct
drugs**.

## Commands

```sh
# 1. callset -> PharmCAT, both ways (the only step that touches patient sequence)
uv run python tools/patient_safety.py --work build/it4/track2-e56 pharmcat \
  --vcf build/it4/track2-e56/raw/patient.vcf.gz \
  --pharmcat build/it4/track2-e56/pharmcat --java-home /opt/homebrew/opt/openjdk@21

# 2. PharmCAT output -> actionability words + callability counts (coordinate-free)
uv run python tools/patient_safety.py --work build/it4/track2-e56 pgx \
  --pharmcat build/it4/track2-e56/pharmcat \
  --vcf build/it4/track2-e56/raw/patient.vcf.gz --genome-per-kb 1.529

# 3. OnSIDES: candidate rate vs matched comparison set
uv run python tools/patient_safety.py --work build/it4/track2-e56 labels \
  --onsides build/it4/track2-e56/onsides/csv \
  --drug-table ressources/track2/shortlist.tsv:drug_name:direction_id \
  --drug-table ressources/track2/do_not.tsv:drug_name:direction_id \
  --extra-drug dasatinib=D5 --extra-drug "furosemide=positive control (PMID 35348900)" \
  --extra-drug "calcitriol=positive control (FAERS nephrocalcinosis)" \
  --alias "valproic acid=valproate" --alias "nicotinamide=niacinamide" \
  --alias "cabozantinib s-malate=cabozantinib" --alias "mecasermin rinfabate=mecasermin" \
  --per-candidate 5

# 4. FAERS paediatric cross-check (18 drug-reaction pairs)
uv run python tools/patient_safety.py --work build/it4/track2-e56 faers \
  --pair "atorvastatin=MYOPATHY" --pair "atorvastatin=RHABDOMYOLYSIS" ... \
  --pair "furosemide=NEPHROCALCINOSIS"

# 5. the two-source table + provenance
uv run python tools/patient_safety.py --work build/it4/track2-e56 table \
  --drug-table ressources/track2/shortlist.tsv:drug_name:direction_id \
  --drug-table ressources/track2/do_not.tsv:drug_name:direction_id \
  --extra-drug dasatinib=D5 --extra-drug "furosemide=positive control (PMID 35348900)" \
  --extra-drug "calcitriol=positive control (FAERS nephrocalcinosis)" \
  --extra-gene "vincristine=CYP3A5,CEP72" --extra-gene "valproic acid=POLG" \
  --out ressources/track2/candidate_safety.tsv --entry <this file> --sources "..."

# 6. figures
uv run --group dev python tools/render_step9_e56.py
uv run pytest -q tests/test_patient_safety.py
```

## Observed output

### E5.0 — the targeted re-call from reads was measured, then abandoned, and why

The clean fix for a variant-only callset is to genotype PharmCAT's 1,226 definition
positions from the reads, so a reference call is *observed*. Three facts, measured today,
made that impossible inside this experiment's ≈ $3 Modal share:

| fact | measurement |
|---|---|
| there is no BAM/CRAM in the delivery | `ideation/data-findings.md` §1 — any read-level work means aligning 159.7 Gbases |
| the read store is 274 Parquet objects, 67.68 GB | `list_objects_v2` over `s3://mva/reads/`, today |
| the link to the object store is ~11 MB/s and does not parallelise | 315 MB single-stream in 27.4 s (11.5 MB/s); 268 MB over 8 concurrent streams in 25.2 s (10.7 MB/s) |

Alignment-free or aligned, a targeted re-call requires streaming the store **once**:
67.68 GB ÷ 11 MB/s ≈ **1.7 h of transfer**, which is the same wall time whether one
container or thirty-two do it, so the Modal cost scales with the container count against a
fixed network ceiling. Recorded as the reason; **the fallback the plan authorises was used
instead** — PharmCAT run both ways, with the difference reported as the uncertainty and a
regional callability proxy added to say where the assumption is defensible.

### E5.1 — how much of the pharmacogenome this callset can answer

**20 of 1,223 distinct definition positions (1.6 %) are genotyped.** (PharmCAT's positions
file holds 1,226 rows; 1,223 are distinct genomic positions. Its preprocessor reported 1,204
missing.) Per gene, `figures/it4/step9-e56-coverage.svg`.

| gene | positions genotyped / needed | regional density (× genome-wide) | verdict |
|---|---|---|---|
| CYP2C19 | 4 / 35 | 0.89 | region normally callable |
| CYP2B6 | 3 / 48 | 2.11 | region normally callable |
| CYP2D6 | 8 / 157 | 2.75 | region normally callable (still no diplotype — see below) |
| RYR1 | 1 / 319 | 1.30 | region normally callable |
| DPYD | 1 / 83 | 0.76 | region normally callable |
| CYP3A5 | 1 / 7 | **0.11** | region has almost no calls |
| SLCO1B1 | 0 / 35 | 0.52 | region normally callable |
| CYP2C9 | 0 / 88 | 0.96 | region normally callable |
| G6PD | 0 / 171 | **0.26** | sparsely called |
| UGT1A1 | 0 / 4 | **0.35** | sparsely called |
| CYP3A4 | 0 / 46 | **0.34** | sparsely called |
| ABCG2 | 0 / 1 | **0.00** | no calls in the region at all |
| CFTR | 0 / 93 | **0.045** | no calls in the region to speak of |
| CACNA1S, NAT2, NUDT15, TPMT, CYP4F2, VKORC1, IFNL3 | 0–1 / 1–47 | 0.00–1.43 | see `pgx_summary.json` |

### E5.2 — phenotypes, split into observed and assumed

**Observed (strict run, from genotyped positions only) — 5 genes:**

| gene | phenotype | from |
|---|---|---|
| **CYP3A5** | **Poor Metabolizer** | 1 of 7 positions |
| **CYP2C19** | **Poor Metabolizer / Intermediate Metabolizer** (two diplotypes fit) | 4 of 35 |
| **CYP2B6** | **Intermediate Metabolizer** | 3 of 48 |
| **RYR1** | **Uncertain Susceptibility** (malignant hyperthermia) | 1 of 319 |
| DPYD | Normal Metabolizer | 1 of 83 |

**Only under `--absent-to-ref` — 11 genes**, every one of them an assumption:
ABCG2 (Normal Function), SLCO1B1 (Normal Function), CYP2C9 (Normal Metabolizer), CYP3A4,
NUDT15, TPMT, UGT1A1 (Normal Metabolizer), G6PD (Normal), NAT2 (**Poor Metabolizer**),
CACNA1S (Uncertain Susceptibility), CFTR (ivacaftor non-responsive).

**No phenotype either way — 7:** CYP2D6, CYP4F2, VKORC1, IFNL3, MT-RNR1, HLA-A, HLA-B.
CYP2D6 is the instructive one: its region is called at 2.75× the genome-wide rate and 8 of
157 positions are genotyped, yet no diplotype is made — its structural and copy-number
alleles are outside what any small-variant VCF can carry.

**The join to guidelines.** PharmCAT's bundled CPIC/DPWG/FDA annotations tie our candidates
to: lovastatin, simvastatin, atorvastatin → SLCO1B1 (CPIC level A, guideline); chloroquine,
hydroxychloroquine → G6PD (FDA label); irinotecan → UGT1A1 (DPWG + FDA). **All four of those
genes are no-calls in the strict run.** The CPIC API itself was unreachable while this ran
(`https://api.cpicpgx.org/v1/pair_view` → HTTP 503, "connection to server at db.pharmgkb.org
… Host is unreachable", 2026-09-24), so the guideline text comes from PharmCAT's pinned data
release rather than a live query — a *better* provenance, and recorded here because the
plan asked for the API.

Two pairs no guideline covers were added from the literature and appear as flagged
non-coverage: **vincristine → CYP3A5** (PMID 38680001, paediatric rhabdomyosarcoma cohort)
and **vincristine → CEP72** (PMID 25710658), plus **valproic acid → POLG** (CPIC level A per
the data-sources note). CEP72 and POLG are outside PharmCAT's gene set entirely.

### E6.1 — the mapping and its positive controls

16 MedDRA ids over 5 usable proband phenotypes
([`hpo_to_adverse_terms.tsv`](../../../../ressources/track2/hpo_to_adverse_terms.tsv)).
Both controls are matched, so the nephrocalcinosis arm is interpretable:

| control | labels with a mapped effect / total | effects matched |
|---|---|---|
| furosemide (PMID 35348900) | 5 / 164 | Nephrocalcinosis, Nephrolithiasis |
| calcitriol | 7 / 46 | Calculus urinary, Muscular weakness |

**The control also corrected the method.** Furosemide's rate (0.03) is far *below* any base
rate, so the pre-registered rate test alone would have called the one published
drug–phenotype collision for this child "not flagged". A second, independent trigger was
therefore added and is reported separately in `phenotype_flag_reason`: a label carrying a
term that **is** one of the child's own phenotypes (tier `exact`: Nephrocalcinosis, Failure
to thrive, Muscle atrophy) flags at any rate. The pre-registered rate test is still the one
H091 is judged on.

### E6.2 — the rate, against a matched comparison set

`figures/it4/step9-e56-baserate.svg`.

| set | ingredients with ≥ 1 mapped effect | share | Wilson 95 % CI |
|---|---|---|---|
| **candidates** (75 ingredients OnSIDES holds) | 45 | **60.0 %** | 48.7 – 70.3 % |
| **matched comparison set** (375 ingredients, 5 per candidate on effect breadth) | 149 | **39.7 %** | 34.9 – 44.8 % |

The intervals do not overlap.

Per candidate, the rows that matter:

| drug | direction | labels with a mapped effect / total | effects |
|---|---|---|---|
| **lovastatin** | D4 (rank 1) | **80 / 80 = 100 %** | Myopathy, Rhabdomyolysis |
| **atorvastatin** | D4 (rank 11) | **382 / 397 = 96 %** | Myopathy, Rhabdomyolysis |
| **simvastatin** | D4 (rank 2) | **184 / 194 = 95 %** | Muscular weakness, Myopathy, Rhabdomyolysis |
| **bortezomib** | D2 (rank 6) | **35 / 35 = 100 %** | Failure to thrive, Muscular weakness, Rhabdomyolysis, Weight decreased |
| **hydroxychloroquine** | D2 (rank 10) | **45 / 58 = 78 %** | Myopathy |
| everolimus | D5 / D4 | 12 / 25 = 48 % | Malnutrition, Rhabdomyolysis, Weight decreased |
| docetaxel | do-not (A2) | 11 / 31 = 35 % | Muscular weakness, Myositis, Weight decreased |
| **vincristine** | do-not (A2) | **1 / 1** (its only OnSIDES label, UK) | **Muscle atrophy** (exact term) |
| dasatinib | D5 | 5 / 34 = 15 % | Rhabdomyolysis, Weight decreased |
| sirolimus | D5 / D4 | 2 / 25 = 8 % | Muscular weakness, Weight decreased |
| metformin | D2 (rank 8) | 21 / 402 = 5 % | Rhabdomyolysis, Weight decreased |
| colchicine | do-not (A2) | 1 / 53 = 2 % | Muscular weakness, Myopathy, Rhabdomyolysis |
| chloroquine | D2 (rank 5) | 0 / 7 | — |
| niacin / nicotinamide | D3 (ranks 3, 4) | 0 / 11, 0 / 7 | — |
| valproic acid (as *valproate*) | D3 (rank 7) | 0 / 149 | — |
| vorinostat | D3 (rank 9) | **0 / 0 — not in OnSIDES at all** | — |

### E6.3 — FAERS paediatric cross-check (0–17 years, exact MedDRA PT)

Spontaneous reports: a numerator with **no denominator**. These are signals, never rates.

| drug | reaction | reports |
|---|---|---|
| metformin | Rhabdomyolysis | 49 |
| **vincristine** | Muscular weakness | **57** |
| furosemide (control) | Nephrocalcinosis | 23 |
| hydroxychloroquine | Muscular weakness / Myopathy | 11 / 7 |
| simvastatin | Rhabdomyolysis / Myopathy | 9 / 1 |
| atorvastatin | Rhabdomyolysis / Myopathy | 5 / 1 |
| lovastatin | Rhabdomyolysis / Myopathy | 4 / 1 |
| bortezomib | Weight decreased / Rhabdomyolysis | 5 / 4 |
| vincristine | Muscle atrophy | 2 |
| dasatinib, sirolimus, colchicine | Rhabdomyolysis / Muscular weakness / Myopathy | 1 each |
| everolimus | Rhabdomyolysis | 0 |

### E6.4 — the two-source table

[`ressources/track2/candidate_safety.tsv`](../../../../ressources/track2/candidate_safety.tsv),
85 rows, `figures/it4/step9-e56-evidence.svg`:

| combined flag | n | which |
|---|---|---|
| **both sources flag a question** | **5** | lovastatin, simvastatin, atorvastatin, hydroxychloroquine, vincristine |
| genome flags a question only | 5 | chloroquine (G6PD no call), irinotecan (UGT1A1 no call), valproic acid (POLG not covered), gefitinib (CYP2D6 no call), ribavirin (IFNL3 no call) |
| phenotype flags a question only | 24 | bortezomib, everolimus, furosemide (control), and 21 RMS-context / do-not drugs |
| unflagged by these two sources (**not** evidence of safety) | 51 | incl. niacin, nicotinamide, metformin, dasatinib, sirolimus, colchicine |

## Verdict

**H090 — supported, but weakly, and the honest reading is the opposite of reassuring.**

The pre-registered prediction is met on its literal terms: **CYP3A5 Poor Metabolizer** is a
non-normal phenotype, it is in the named gene list, it comes from an **observed** position,
and CYP3A5 is the gene the one paediatric-rhabdomyosarcoma pharmacogenomic study attaches to
vincristine (PMID 38680001). Two further observed non-normal calls sit beside it —
**CYP2C19 Poor/Intermediate Metabolizer** and **CYP2B6 Intermediate Metabolizer** — and
**RYR1 Uncertain Susceptibility** is a malignant-hyperthermia flag in a child who will have
repeated anaesthesia and already has muscle disease.

Three qualifications, all of which belong beside the claim wherever it is quoted:

1. CYP3A5 poor metabolism (non-expresser) is the **majority** phenotype in European-ancestry
   populations, so it is "non-normal" by name and common by frequency; and CPIC has **no**
   vincristine–CYP3A5 guideline, only tacrolimus.
2. Every gene with a *guideline* for a shortlisted drug — SLCO1B1 (all three statins, CPIC
   level A), G6PD (chloroquine, hydroxychloroquine), UGT1A1 (irinotecan) — is a **no call**.
   The question H090 asks is therefore *unanswered* for exactly the drugs the shortlist ranks
   first.
3. The refutation condition's second clause ("too few positions are callable to make any
   diplotype") is 98.4 % true and 1.6 % false: a diplotype was made for 5 genes and not for
   18.

So: **supported**, low confidence, with the callable fraction (1.6 %) quoted every time.

**H091 — supported.** 45 of 75 candidate ingredients (60.0 %, CI 48.7–70.3 %) carry a
labelled adverse effect matching one of the child's own phenotypes, against 39.7 %
(CI 34.9–44.8 %) in a comparison set of 375 approved ingredients matched on label breadth.
The intervals do not overlap and the prediction's named phenotypes are the ones driving it
(myopathy/rhabdomyolysis on the statins, muscle atrophy on vincristine, failure to thrive on
bortezomib). Confidence moderate: the effect is carried mostly by the statins and by the
oncology block, the comparison set is matched on one variable, and the label is a hazard
statement, not an incidence.

## Limitations

- **The headline limitation is E5's denominator.** 1.6 % of PGx positions genotyped. Every
  "Normal Function" in this entry that is not in the observed list is an *assumption* from
  `--absent-to-ref`, which PharmCAT's own authors label DANGEROUS. The regional density proxy
  narrows but does not close the gap: it says SLCO1B1's region was normally callable (0.52×)
  and CYP3A5's, G6PD's, UGT1A1's and ABCG2's were not (0.11×, 0.26×, 0.35×, 0.00×). Only a
  targeted re-call from the reads produces observed reference calls.
- The density proxy uses region-level variant counts, not depth. A region can be called at a
  normal rate and still have a low-coverage hole at one PGx position.
- CYP2D6, HLA-A/B and MT-RNR1 need structural/copy-number or specialised calling that no
  small-variant VCF supports; their absence here is a property of the data type, not of this
  patient.
- OnSIDES v3.1.1 ships **no paediatric ADE table**; the paediatric view is FAERS only, which
  has no denominator, is subject to reporting bias, and cannot separate the drug from the
  disease. A child on vincristine has cancer, which itself causes muscle wasting.
- Label coverage is uneven: vincristine and irinotecan have 1 and 3 labels (UK only);
  vorinostat is absent from OnSIDES entirely; nicotinamide and valproic acid needed a
  declared RxNorm alias (`niacinamide`, `valproate`) to be found at all. A zero here can mean
  "no such effect" or "no such label".
- The HPO→MedDRA mapping is manual and mine. `Weight decreased` and `Rhabdomyolysis` are
  broad, high-base-rate terms; the matched comparison set is what corrects for that, and the
  per-effect breakdown in `label_summary.json` lets a reader re-do the flag with a narrower
  set.
- The furosemide nephrocalcinosis association it validates against is itself contested: the
  OR 1.26 (95 % CI 1.02–1.57) of PMID 35348900 is set against a 32-study systematic review
  (PMID 30473868) that found **no** evidence furosemide raises the risk, at low strength of
  evidence. The nephrocalcinosis constraint stands on precaution, not on settled evidence.
- "Unflagged" is not "safe". 51 rows are unflagged, and **all 51** are drugs for which
  no pharmacogene exists to consult — one source of the two was silent by construction.

## Conclusion

The two sources agree on **five** candidates, and the overlap is the finding: the three
statins that Track 2 ranks 1, 2 and 11 sit on a direction (D4) whose own guideline gene is
**uncallable from this callset**, and whose labels name the child's own skeletal muscle
atrophy on 95–100 % of them against a 40 % base rate. Hydroxychloroquine repeats the shape
(G6PD uncallable, 78 % myopathy). Vincristine — already in the do-not table for a mechanism
reason (spindle poison in a SAC-deficient background) — is now independently flagged by both
a genome result (observed CYP3A5 poor metabolism; CEP72 not covered by any caller) and an
exact phenotype term on its label (muscle atrophy, 57 paediatric FAERS reports of muscular
weakness).

The single most actionable sentence this experiment produces is a **test request, not a drug
recommendation**: the statin and antimalarial arms of Track 2 cannot be cleared or
contraindicated for this child from the delivered VCF, and a targeted pharmacogenomic panel
(or a re-call of the reads at PharmCAT's 1,226 positions) over SLCO1B1, ABCG2, CYP2C9, G6PD
and UGT1A1 would answer it in an afternoon.
