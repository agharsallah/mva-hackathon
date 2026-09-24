# Track 2 — candidate data sources (research notes, iteration 4)

Verified: 2026-09-24. Every "verified y" row got a live HTTP response in this session (curl HEAD/GET
or a real query). "n" = from docs or search only. Not a methodology entry; nothing here is a result
about the patient.

**Criterion key** (Track 2 panel): **R** Rigor 35 % (mechanism sound, candidate supported by it) ·
**I** Impact 25 % (helps understand/diagnose MVA) · **N** Innovation 25 % · **S** Scalability 15 %
(other people, diseases, larger data).
Columns *generalises* (any gene or disease → S) and *MVA readout* (diagnostic or functional signal
for MVA → I) are per source.

Modal prices used for estimates (modal.com/pricing, fetched today): CPU $0.047/core-h,
memory $0.008/GiB-h, T4 $0.59/h, L4 $0.80/h, A10 $1.10/h, L40S $1.95/h, A100-80 $2.50/h,
H100 $3.95/h, H200 $4.54/h.

**The patient VCF** (not opened, not copied): `WGS_EX2312012_HGWCNDSX7.vcf.gz`, 315 MB, GRCh38
no-`chr` contigs (`ideation/data-findings.md` §1). The repo reads it from
`s3://mva/source/WGS_EX2312012_HGWCNDSX7.vcf.gz` (`src/mva/warehouse/cli_vcf.py`, default
`DEFAULT_VCF_OBJECT`); the profile script names `~/ubuntu/data/` (server path
`/home/abdu/ubuntu/data/`). **`~/ubuntu/` does not exist on this laptop** and a `find / -maxdepth 6`
found no copy — PharmCAT must run where the object store or server copy lives, or pull the object.

---

## 1. DepMap (CRISPR, models, PRISM, aneuploidy, expression)

The DepMap portal (`depmap.org/portal/api/download/files`) now returns a **Cloudflare Turnstile
page** to scripts (verified: HTTP 200 HTML "Quick check before you enter"). Scripted downloads go
through the **figshare mirrors** below instead. Latest release mirrored in full on figshare:
**24Q4** (10.25452/figshare.plus.27993248). A 26Q1 release exists (Chronos parameters article
31660582, 2026-08-03) but its full file set was not found on figshare.

| what | URL / endpoint (verified) | size | licence | registration | the query for our question | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| CRISPRGeneEffect 24Q4 (Chronos, models × genes) | `https://ndownloader.figshare.com/files/51064667` (y; streamed; 1,178 models) | 428.7 MB | CC BY 4.0 | no | BUB1B/BUB3/MAD2L1/TTK dependency in the 13 RMS lines vs all; genes co-essential with BUB1B (correlation over models) | ~1 min laptop download; pandas in RAM (~3 GB) OK | R, S | any gene | functional (loss-of-BUB1B tolerance), cancer lines not MVA cells |
| Chronos gene_effect 26Q1 | `https://ndownloader.figshare.com/files/67214582` (y, listed) | 413.5 MB | CC BY 4.0 | no | same, newer; needs model-ID mapping (Model.csv 26Q1 not mirrored) | ~1 min | R | any gene | as above |
| Model.csv 24Q4 | `https://ndownloader.figshare.com/files/51065297` (y, downloaded) | 0.6 MB | CC BY 4.0 | no | `OncotreeCode in (ERMS, ARMS, RMS, PLRMS)` → **22 RMS models** | seconds | R, S | any lineage | none |
| OmicsSignatures 24Q4 (per-line Aneuploidy, CIN, Ploidy, WGD, MSI, LoH) | `https://ndownloader.figshare.com/files/51065726` (y, downloaded) | 0.1 MB | CC BY 4.0 | no | aneuploidy score as covariate: drug response ~ aneuploidy in PRISM (Cohen-Sharir-style) | seconds | R, N | any | proxy for "aneuploid-cell vulnerability" |
| OmicsExpressionProteinCodingGenesTPMLogp1 24Q4 | `https://ndownloader.figshare.com/files/51065489` (y, listed) | 506.6 MB | CC BY 4.0 | no | BUB1B expression in RMS lines; expression-matched line selection | ~1 min | R | any gene | none |
| PRISM Repurposing **24Q2** (REP1M + REP300, 1,522 cpds, 906 lines, 2.5 µM, 5 d) | article 25917643; key files: `Extended_Primary_Data_Matrix.csv` (72.5 MB, files/46630984), `Cell_Line_Meta_Data.csv` (files/46630978), `Extended_Primary_Compound_List.csv` (files/46630981, cols: dose, target, MOA, IDs, name — **no clinical phase**), `LFC_COLLAPSED.csv` (150 MB) (y) | ~1.5 GB all; ~75 MB needed | CC BY 4.0 | no | **15 RMS lines screened**: CW9019, JR, KYM1, RD, RH28, RH30, RH36, RH4, RH41, RHJT, RMSYM, SCMCRM2, SMSCTR, TE617T, TTC442 → rank candidate drugs by RMS-selective kill | minutes, laptop | R, I | any lineage/drug | functional on RMS (the child's tumour), not on MVA |
| PRISM Repurposing **20Q2** primary + **secondary** (dose-response AUC/IC50) | article 20564034; `secondary-screen-dose-response-curve-parameters.csv` (290 MB, files/36794595), `secondary-screen-replicate-collapsed-treatment-info.csv` (files/36794619, has **`phase` column**: 597 Launched compounds) (y) | ~1.2 GB all | CC BY 4.0 | no | **13 RMS lines in secondary** (same list minus RMSYM, SCMCRM2; primary has only 3) → AUC per candidate drug in RD/RH30/RH4/RH41 | minutes | R | any | as above |
| Cohen-Sharir 2021 aneuploidy scores (Nature 590:486) | supplementary table (n, not fetched) | small | journal | no | superseded by OmicsSignatures `Aneuploidy` for our use | — | R | any | — |

Notes:
- **A-204 is annotated `Rhabdoid Cancer (MRT)`** in Model.csv, not RMS. "RD18" is `RH18` (ERMS; has
  signatures, not in PRISM/CRISPR 24Q4).
- RMS lines in CRISPR 24Q4: CW9019, JR, KYM1, RD, RH28, RH30, RH4, RH41, RHJT, RMSYM, SCMCRM2,
  SMSCTR, TTC442 (13).
- RMS aneuploidy scores span 0 (TE617T) to 30 (RH36); all-line median 19.
- Clinical phase: join PRISM `IDs`/names to ChEMBL `max_phase` (repo already pulls ChEMBL), or use
  the 20Q2 `phase` column.

## 2. LINCS L1000 / CMap

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| **SigCom LINCS** up/down enrichment | 1) `POST https://maayanlab.cloud/sigcom-lincs/metadata-api/entities/find` `{"filter":{"where":{"meta.symbol":{"inq":[...]}},"fields":["id","meta.symbol"]}}` → UUIDs; 2) `POST https://data-api.sigcom-lincs.k8s.maayanlab.cloud/v1/api/v1/enrich/ranktwosided` `{"up_entities":[..],"down_entities":[..],"database":"l1000_cp","limit":N}` (the `maayanlab.cloud/.../data-api` path 307-redirects here; urllib does not follow POST redirects); 3) `POST .../metadata-api/signatures/find` with UUIDs → `pert_name, cell_line, pert_dose, pert_time` (y — ran a 20-up/20-down toy query: 3.6 s, returned mimickers/reversers over 693,215 signatures) | API | LINCS data public; SigCom terms not checked (n) | no | up = genes raised in BubR1-deficient / aneuploid cells, down = lowered → **reversers** = candidate drugs; mimickers = drugs to avoid | seconds per query; free | N, S, R | any gene signature | none directly; needs an MVA/BubR1-KD signature (e.g. a GEO BUB1B knockdown) |
| **iLINCS** up/down concordance | `POST https://www.ilincs.org/api/ilincsR/findConcordancesSC` JSON `{"mode":"UpDn","metadata":true,"signatureProfile":{"genesUp":[..],"genesDown":[..]}}` — arrays, not comma strings (a string gives HTTP 400) (y — 10+10 toy query returned `concordanceTable` with compound, cell line, dose, time, similarity, p) | API | "Creative Commons Terms of Use" (exact CC variant n) | no | same as SigCom — a second, independent method | seconds | N, R | any | as above |
| iLINCS signature metadata | `GET https://www.ilincs.org/api/SignatureMeta?filter={"limit":1}` (y) | API | as above | no | map LINCSCP ids → compound | seconds | — | — | — |
| clue.io (CMap query API) | `https://api.clue.io/api/perts` (y: HTTP 401 "User Key must be specified") | API | CMap terms; academic free | **yes — user key** | full CMap query tool | — | N | any | none |
| GEO LINCS Level 5 Phase I | `ftp.ncbi.nlm.nih.gov/geo/series/GSE92nnn/GSE92742/suppl/GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx.gz` (y) | **20 GB** (+ sig_info 11 MB, pert_info 1.1 MB) | GEO public | no | local connectivity scoring (own method, e.g. weighted KS on landmark genes) | download ~10–20 min on Modal; needs ~64 GB RAM or h5py slicing; ~$0.2 CPU | N, S | any | none |
| GEO LINCS Level 5 Phase II | `.../GSE70nnn/GSE70138/suppl/GSE70138_Broad_LINCS_Level5_COMPZ_n118050x12328_2017-03-06.gctx.gz` (y) | 5.0 GB | GEO public | no | same | ~5 min | N | any | none |

## 3. Pharmacogenomics

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| **PharmCAT v3.4.0** (2026-07-14) | `https://github.com/PharmGKB/PharmCAT/releases/download/v3.4.0/pharmcat-3.4.0-all.jar` (32 MB), `pharmcat-pipeline-3.4.0.tar.gz` (28.5 MB), `pharmcat_positions_3.4.0.vcf.bgz` (y, release API) | ~60 MB + GRCh38 FASTA ~0.9 GB (auto-downloaded) | MPL-2.0 | no | `pharmcat_pipeline patient.vcf.bgz` → CYP2C9, SLCO1B1, UGT1A1, G6PD, DPYD, TPMT/NUDT15, CYP3A5… diplotypes + CPIC recommendations for the child | minutes, laptop (pure Java, arm64 fine) | R, S | any person's VCF | none for MVA; safety of candidates for this child |
| PharmCAT requirements (pharmcat.clinpgx.org, y) | Java **17+** (25 recommended) — **laptop has Corretto 11** → `brew install openjdk@21`; Python ≥ 3.10.14; bcftools/htslib ≥ 1.18 (laptop has **1.24**); GRCh38; CHROM must be `chr##` (**our VCF is no-chr** → `bcftools annotate --rename-chrs`); left-aligned (`bcftools norm -m+`); every PGx position must be present — **variant-only VCF means absent positions = no-call** unless `--absent-to-ref` (flagged DANGEROUS); a gVCF or targeted re-call at `pharmcat_positions.vcf` from BAM is the clean fix | — | — | — | — | — | R | — | — |
| **CPIC API** | `GET https://api.cpicpgx.org/v1/pair_view?drugname=in.(simvastatin,atorvastatin,…)&select=drugname,genesymbol,cpiclevel,clinpgxlevel,guidelinename,usedforrecommendation,pgxtesting` (y — note column is `clinpgxlevel`, `pgkbcalevel` errors 42703) | API (PostgREST) | CC0 (CPIC; n) | no | result today: statins → **SLCO1B1, CYP2C9, ABCG2** (level A, guideline); irinotecan → **UGT1A1** (A, "Testing Recommended"); chloroquine/HCQ → **G6PD** (C, actionable); valproate → **POLG** (A/B, "Testing Required"), urea-cycle genes (B); metformin → level D only; **no pairs for vincristine, nicotinamide, niacin, bortezomib, dasatinib** | seconds | R | any drug | none |
| ClinPGx (ex-PharmGKB) clinical annotations | `https://api.clinpgx.org/v1/download/file/data/clinicalAnnotations.zip` (y: 303 → 200, 1.23 MB); per-drug JSON `https://api.clinpgx.org/v1/data/clinicalAnnotation?relatedChemicals.name=irinotecan&view=min` (y) | 1.2 MB | **CC BY-SA 4.0** (share-alike on derived tables) | no (accounts no longer needed) | vincristine–CEP72 and other non-CPIC annotations for our candidates | seconds | R | any | none |

## 4. Adverse effects

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| **OnSIDES v3.1.1** (data, Apr 2026; v3.2.1 is code-only) | `https://github.com/tatonetti-lab/onsides/releases/download/v3.1.1/onsides-v3.1.1.zip` (y, release API) | 84.9 MB zip; 6.93 M ADE rows, 1,866 ingredients, US/EU/UK/JP labels | data **CC BY 4.0**, code MIT | no | label ADEs of each candidate ∩ the child's phenotypes mapped to MedDRA (nephrocalcinosis, myopathy/muscle atrophy, growth retardation, microcephaly) → "do-not-worsen" filter | seconds, laptop (DuckDB) | R, S | any drug | none (safety) |
| SIDER 4.1 (2015, MedDRA 16.1) | `https://sideeffects.embl.de/media/download/meddra_all_se.tsv.gz` (y, 2.38 MB) | 2.4 MB | CC BY-NC-SA 4.0 (n; page shows a licence block) | no | same, older; cross-check only | seconds | R | any | none |
| **openFDA FAERS** | `https://api.fda.gov/drug/event.json` — ranges must be URL-encoded (`%5B0+TO+17%5D`) (y). Working examples: `?search=patient.reaction.reactionmeddrapt.exact:"NEPHROCALCINOSIS"+AND+patient.patientonsetage:%5B0+TO+17%5D+AND+patient.patientonsetageunit:801&count=patient.drug.openfda.generic_name.exact&limit=8` → calcitriol 27, topiramate 25, furosemide 23…; `?search=patient.reaction.reactionmeddrapt.exact:"MYOPATHY"+AND+patient.patientagegroup:(2+OR+3+OR+4)&count=…generic_name.exact` → etoposide 9, methotrexate 8…; `?search=patient.drug.openfda.generic_name:"atorvastatin"+AND+patient.patientagegroup:(3+OR+4)&count=patient.reaction.reactionmeddrapt.exact` | API | public domain (US gov) | no (optional free key: 240 req/min, 1k/day → 120k/day with key) — **hit a 429 once** | per candidate: paediatric reaction counts for our phenotype MedDRA terms; per phenotype: drugs over-reported in children | seconds; add sleep | R | any drug | none (spontaneous reports, no denominator) |

## 5. Mouse phenotypes

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| **MGI_GenePheno.rpt** | `https://www.informatics.jax.org/downloads/reports/MGI_GenePheno.rpt` (y, downloaded 37.7 MB) | 37.7 MB | MGI: free with citation (CC BY 4.0, n) | no | `grep Bub1b` → **134 rows, 73 distinct MP terms, 14 genotypes**, incl. hypomorph `Bub1b<tm1Jvd>` (BubR1 H/H, PMID 15208629 — the closest model of the child's hypomorph), `Bub1b<tm2.1Jvd>` overexpression (PMID 23300461), gene-trap `Gt(neo-btk)1Dai` | seconds | R, I | any gene | **yes** — hypomorph phenotypes (short lifespan, cachexia/muscle loss, aneuploidy) are the mechanistic prior; drugs that rescued H/H mice are candidates |
| MGI_PhenoGenoMP.rpt | same folder (y, 54.1 MB) | 54 MB | as above | no | genotype-level MP, backgrounds | seconds | R | any | as above |
| IMPC Solr | `https://www.ebi.ac.uk/mi/impc/solr/genotype-phenotype/select?q=marker_symbol:Bub1b` (y) | API | CC BY 4.0 | no | **0 phenotype rows** for Bub1b (gene doc MGI:1333889 exists, no phenotyping) — IMPC adds nothing here | — | — | any gene | no |
| **HP↔MP mapping** (Mouse-Human mapping initiative SSSOM) | `https://raw.githubusercontent.com/mapping-commons/mh_mapping_initiative/master/mappings/mp_hp_mgi_all.sssom.tsv` (y, 329 KB) | 0.3 MB | CC BY 4.0 (n) | no | map the child's 8 HPO terms to MP → score overlap with Bub1b H/H MP set | seconds | S, N | any disease | cross-species phenotype match |
| uPheno cross-species mapping | `purl.obolibrary.org/obo/upheno/mappings/upheno-cross-species.sssom.tsv` (**404**), `data.monarchinitiative.org/mappings/latest/upheno_custom.sssom.tsv` (162-byte error) (y, both dead) | — | — | — | use the SSSOM above or Monarch semsim | — | — | — | — |
| **Monarch v3 semsim** | `POST https://api-v3.monarchinitiative.org/v3/api/semsim/search` `{"termset":[8 HPO],"group":"Mouse Genes","limit":≤50}` (y; limit capped at 50; Bub1b not in top 10 for the 8 terms); `/v3/api/semsim/compare` for set-vs-set (n) | API | CC BY 4.0 (n) | no | HPO set vs Bub1b MP set similarity (compare); phenotype-first gene ranking | seconds | N, S | any | cross-species phenotype match |
| MONDO id check | `GET https://api-v3.monarchinitiative.org/v3/api/entity/MONDO:0009759` (y) → **"mosaic variegated aneuploidy syndrome 1"**, xref OMIM:257300 | — | — | — | — | — | — | — | — |

## 6. TxGNN

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| TxGNN code | `github.com/mims-harvard/TxGNN` (y; last push 2024-05-06, 288★) | small | MIT | no | zero-shot indication score for the PrimeKG MVA node | — | N, S | any PrimeKG disease | none |
| Pretrained weights | Google Drive `1fxTFkjo2jvmz9k6vesDbCeucQjGRojLj` (y: view page 200; direct download needs gdown/confirm token) | n | MIT | no | `TxGNN.load_pretrained('./model_ckpt')` then predict for the MVA disease node | — | N | — | — |
| Environment | Python **3.8**, **DGL 0.5.2** (pinned), PyTorch matching CUDA; PyG for disease-area split (README) | — | — | — | — | CPU inference plausible on Modal (debian_slim py3.8 + dgl 0.5.2 CPU wheel); pretrain on GPU: README example 2 epochs; untested → est. L4/A10 1–3 h, $1–4 | — | — | — |
| TxGNN Explorer | `http://txgnn.org` (y: **HTTP 503**) — no downloadable per-disease predictions file found (paper data availability lists only PrimeKG Dataverse doi:10.7910/DVN/IXA7BM) | — | — | — | — | — | — | — | — |
| PrimeKG MVA node (local, `build/primekg/kg.parquet`) | x_id `13582_9759_54736_141` (MONDO_grouped, includes 9759): 5 disease–protein, 107 disease–phenotype, 3 disease–disease edges (y, DuckDB) | — | CC0 | no | the node TxGNN would score | — | — | — | — |

## 7. Structures / docking

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| AlphaFold DB BubR1 O60566 | `https://alphafold.ebi.ac.uk/api/prediction/O60566` → `AF-O60566-F1-model_v6.pdb` (y; mean pLDDT **63.6**, long disordered stretches) | ~1 MB | CC BY 4.0 | no | map the child's missense onto the structure; pocket search on ordered domains only | seconds | R, I | any UniProt | **yes** — variant-in-structure (functional hypothesis for the hypomorph) |
| AlphaFold BUB3 O43684 | same API (y; pLDDT **95.9**) | ~0.5 MB | CC BY 4.0 | no | — | — | R | — | — |
| AlphaFold CDC20 Q12834 | same API (y; pLDDT **84.1**) | ~0.5 MB | CC BY 4.0 | no | — | — | R | — | — |
| PDB entries containing human BubR1 (RCSB search on UniProt O60566) | `POST https://search.rcsb.org/rcsbsearch/v2/query` (y) → **9**: 2WVI (N-term TPR, 1.8 Å), 3SI5 (KNL1–BUBR1, 2.2 Å), 4GGD (CDC20 + BubR1 degron, 2.4 Å), 5JJA/5K6S/5SWF (PP2A-B56–BubR1 KARD), 5KHU/5LCW/6TLJ (APC/C–MCC cryo-EM, 3.8–4.8 Å) | — | CC0 | no | 6TLJ = best human MCC context; 2WVI/3SI5 for N-terminal variants | seconds | R | — | as above |
| 4AEZ | (y) *S. pombe* MCC (2.3 Å) — **not human**; no human BUB3–BubR1 GLEBS entry among the 9 | — | CC0 | — | — | — | — | — | — |
| **ChEMBL 37 approved small molecules** | `GET https://www.ebi.ac.uk/chembl/api/data/molecule.json?max_phase=4&molecule_type=Small%20molecule` (y; **3,475** molecules); bulk `ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/latest/chembl_37_chemreps.txt.gz` (y, checksums) | API / ~250 MB bulk | CC BY-SA 3.0 | no | SMILES → RDKit ETKDG conformers → Meeko PDBQT = the approved-drug docking library | ~10 min CPU laptop or Modal (~$0.05) | R, S | any target | none |
| ZINC20/ZINC15 "fda" subset | `zinc20.docking.org/substances/subsets/fda.smi?count=all` (y: **302 → captcha**) | — | free academic | captcha (human) | — | — | — | — | — |
| DrugBank open structures | `go.drugbank.com/releases/latest/downloads/all-open-structures` (y: **403**) | — | open structures CC0; full DB CC BY-NC 4.0 | browser/account | — | — | — | — | — |
| AutoDock Vina | PyPI `vina` **1.2.7**, Apache-2.0, wheels **manylinux x86_64** + musllinux (y) → `pip install vina meeko rdkit` on Modal CPU | small | Apache-2.0 | no | dock 3,475 drugs to a BubR1/CDC20 pocket | ~30 s/ligand/core → 3,475 × 32 cores ≈ 1 h ≈ **$1.5** | R | any | functional hypothesis only |
| GNINA v1.3.3 (2026-06-29) | GitHub release `gnina.cuda12.8.static` (2.06 GB binary) (y); not on PyPI | 2 GB | Apache-2.0 (GPL deps) | no | CNN rescoring of Vina poses | L4 ≈ $0.80/h; ~1–2 h ≈ $1–2 | R, N | any | — |

## 8. Tissue and single-cell expression

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| GTEx v8 median expression | `GET https://gtexportal.org/api/v2/expression/medianGeneExpression?gencodeId=ENSG00000156970.12&datasetId=gtex_v8` (y; 54 tissues) | API | GTEx open-access tier free | no | BUB1B TPM: EBV lymphocytes 71.1, testis 46.8, fibroblasts 15.7; **skeletal muscle 0.05, kidney cortex 0.26, medulla 0.58** (adult, post-mitotic → low) | seconds | R, I | any gene | tissue context for the phenotype |
| HPA gene JSON | `https://www.proteinatlas.org/ENSG00000156970.json` (y, 10 KB; tissue, single-cell, cancer, cell-line specificity fields) | 10 KB | CC BY-SA 3.0 | no | single-cell type and cell-line nTPM for BUB1B | seconds | R | any | as above |
| **Pediatric RMS single-cell/nucleus atlas** (Patel…Dyer, Dev Cell 2022, PMID 35483358) | GEO **GSE174376**, `GSE174376_RAW.tar` (y) | **13 GB** (64 samples; MTX/TSV/BED) | GEO public | no | BUB1B / SAC-gene expression per RMS cell state (progenitor vs myocyte-like); candidate-target expression | download on Modal ~10 min; scanpy on 32 GB CPU ~$0.5 | I, R | RMS | RMS state context |
| RMS stem-cell hierarchies (Wei et al., GSE195709) | `GSE195709_RAW.tar` (y) | 5.8 GB (+2.6 MB processed) | GEO public | no | same, independent cohort | ~$0.3 | R | RMS | — |
| Fetal limb skeletal muscle development (Xi et al. 2020, GSE147457) | `GSE147457_RAW.tar` (y) | 154 MB | GEO public | no | BUB1B in fetal myogenic progenitors (proliferating) vs adult → does the hypomorph bite during muscle growth (muscle atrophy, short stature) | laptop, minutes | I, N | any gene | **yes** — developmental window of the muscle phenotype |

## 9. PubTator3

| what | URL / endpoint (verified) | size | licence | registration | the query | cost/time | criterion | generalises | MVA readout |
|---|---|---|---|---|---|---|---|---|---|
| Entity ids | `GET https://www.ncbi.nlm.nih.gov/research/pubtator3-api/entity/autocomplete/?query=BUB1B&concept=GENE` → `@GENE_BUB1B` (NCBI gene 701); MVA → `@DISEASE_Mosaic_variegated_aneuploidy_syndrome` (MeSH C536987); `@DISEASE_Aneuploidy` (D000782) (y) | API | NCBI public | no | — | seconds | — | any | — |
| Relations | `GET .../relations?e1=@GENE_BUB1B&e2=Chemical` (y: **137** relations; top nocodazole 13, paclitaxel 10 pubs); `?e1=@DISEASE_Mosaic_variegated_aneuploidy_syndrome` (y: **379**; BUB1B 27, CEP57 14, PLK1 11, paclitaxel "cause" 6, caffeine "treat" 6); `?e1=@DISEASE_Aneuploidy&e2=Chemical` (y: **527**; colchicine, benzene, DES top) | API | NCBI public | no | chemical–gene/disease edges → literature prior per candidate; relation types (treat/cause/associate/negative_correlate) | seconds; 3 req/s | N, S | any entity | literature-derived; text-mining noise (e.g. caffeine "treat" MVA is likely mis-typed — verify each by PMID) |
| "mitotic checkpoint" | no PubTator entity (a GO process, not a gene/chemical/disease); use `search/?text=` free text or gene set (BUB1B, BUB3, MAD2L1, TTK, CDC20) relations | — | — | — | union of per-gene relations | seconds | — | — | — |

## 10. Modal assets for a local LLM

| what | observed (y) | notes |
|---|---|---|
| Volumes | `mva-zoo-{boltz2,ntv2,evo2,esmc}-weights` (2026-09-23), `vllm-cache`, `huggingface-cache` (2026-07-19) | `modal volume list` |
| Secrets (names only) | `qwen3-next-api-key` | `modal secret list` |
| `huggingface-cache` | `hub/models--Qwen--Qwen3-Next-80B-A3B-Instruct-FP8` (one snapshot `c5f5f263…`) | 80B MoE, 3B active, FP8 ≈ 80+ GB weights → **1× H200 ($4.54/h) or 2× H100 ($7.90/h)**; cold load several minutes; a 30-min extraction session ≈ $2.5–4 |
| `vllm-cache` | `modelinfos/` with `Qwen3NextForCausalLM` + `Qwen3NextMTP` (vLLM model-info cache, no weights) | pairs with the HF cache above |

---

## Summary

**Usable today, no registration (verified live):** DepMap 24Q4 + PRISM 20Q2/24Q2 via figshare
(CC BY 4.0), SigCom LINCS + iLINCS up/down APIs, GEO LINCS level-5, PharmCAT jar, CPIC API,
ClinPGx zip, OnSIDES, SIDER, openFDA, MGI reports, HP–MP SSSOM, Monarch semsim, AlphaFold, RCSB,
ChEMBL approved set, Vina (PyPI), GNINA binary, GTEx, HPA, GEO scRNA atlases, PubTator3.

**Needs a human:** DepMap portal (Turnstile, for 26Q1 Model.csv), clue.io key, ZINC (captcha),
DrugBank (403 / account), TxGNN weights (Google Drive confirm), openFDA key (optional).

**Blockers:**
1. PharmCAT: Java 17+ (laptop has 11), `chr` rename, and a variant-only VCF gives no-calls at
   reference PGx sites. VCF not on this laptop.
2. TxGNN: explorer returns 503, no predictions file, legacy DGL 0.5.2 / Python 3.8.
3. No MVA/BubR1 transcriptional signature in hand yet, so the LINCS queries have no input.
4. PRISM has RMS lines, not MVA cells, so it can only give an RMS-directed readout.
