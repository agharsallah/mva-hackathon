# Track 2 literature scan — verified references

**Verified:** 2026-09-24. Every PMID below was fetched from NCBI eutils
(`esummary.fcgi` + `efetch.fcgi`, `db=pubmed`); title, first author, journal and year in the
tables are the fetched values, not recalled. GEO accessions were fetched from `db=gds`.

**Scope note.** This is a *literature evidence file* for the Track 2 hypothesis-generation
exercise (drug repurposing directions for a BUB1B-hypomorph / mosaic variegated aneuploidy case).
It is preclinical and computational evidence only. Nothing here is a treatment recommendation, a
dose, or clinical advice; every candidate named is a research hypothesis requiring clinical
evaluation. Systems are recorded explicitly (cell line / mouse / patient cohort) so the gap
between model and child is visible in every row.

**Method.**
- `esearch` on PubMed with the paper's title or a boolean query → `esummary` for PMID/DOI/author/journal/year → `efetch` for the abstract.
- Key findings quote the number the abstract actually states. Where the abstract gives no number, the cell says so.
- Scripts used: `pm.py` (search/summary) in the session scratchpad; commands are plain eutils URLs.

## Scoring criterion tags

The Track 2 panel scores four questions. Every row carries a **criterion** column tagging which
it serves; a row may carry more than one.

| Tag | Criterion | Weight | What earns the tag |
|---|---|---|---|
| **R** | Rigor | 35 % | Characterises the variant mechanism (missense instability vs loss of function, SAC weakening, senescence, aneuploidy tolerance), or ties a drug class to that mechanism |
| **I** | Impact | 25 % | Would change understanding, diagnosis or management of MVA — for this child or others |
| **N** | Innovation | 25 % | Supplies a creative method, angle or tool rather than a replayed pipeline |
| **S** | Scalability | 15 % | Transfers to other individuals, diseases or larger datasets |

**Extra weight** (per the panel brief) goes to two kinds of row, marked **★** in the criterion cell:
(a) papers that connect the *mechanism* directly to a drug class, and (b) papers on **diagnosing
MVA or measuring BubR1 function in patients** — collected in §9, which is the highest-density
section for Rigor and Impact.

---

## 1. Senescence in BubR1-hypomorphic mice — the senolytic direction (NEW: D5)

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance to a new Track 2 direction |
|---|---|---|---|---|---|---|
| R | 15208629 | 10.1038/ng1382 | Baker DJ 2004 Nat Genet | Mice with low BubR1 develop progressive aneuploidy plus progeroid features: short lifespan, cachectic dwarfism, lordokyphosis, cataracts, loss of subcutaneous fat, impaired wound healing; graded BubR1 reduction in MEFs raises aneuploidy **and senescence**; both sexes infertile | Mouse (BubR1^H/H), MEFs | Establishes the animal model matching the child's phenotype axis (short stature, failure to thrive, muscle atrophy). Senescence is the mechanistic link, not a side effect |
| R ★ | 18516091 | 10.1038/ncb1744 | Baker DJ 2008 Nat Cell Biol | Skeletal muscle and fat — the two tissues that age early under BubR1 insufficiency — carry high p16^Ink4a and p19^Arf; **deleting p16^Ink4a attenuates senescence and premature ageing** there, deleting p19^Arf exacerbates them | Mouse (BubR1^H/H) | Names the effector (p16^Ink4a) and the exact tissues: skeletal muscle ≈ the child's muscle atrophy. Gives the drug-class target for D5, and warns the Cdkn2a locus is not one-directional |
| R, I ★ | 22048312 | 10.1038/nature10600 | Baker DJ 2011 Nature | INK-ATTAC drug-inducible killing of p16^Ink4a-positive cells **in the BubR1 progeroid background**: lifelong clearance delayed onset of fat/muscle/eye phenotypes; **late-life clearance attenuated already-established disorders** | Mouse (BubR1^H/H × INK-ATTAC) | The causal proof, in the exact genotype of interest. "Late clearance still works" is what makes a post-diagnosis intervention conceivable |
| I, S | 26840489 | 10.1038/nature16932 | Baker DJ 2016 Nature | Same clearance in *wild-type* mice from 1 year extended median lifespan in both sexes and two backgrounds; delayed tumorigenesis; preserved kidney glomeruli, cardio-protective K_ATP channels, adipocytes | Mouse (wild-type, INK-ATTAC) | Generalises beyond the progeroid background (scalability); the **kidney** readout matters given the nephrocalcinosis |
| R | 23242215 | 10.1038/ncb2643 | Baker DJ 2013 Nat Cell Biol | Sustained BubR1 over-expression preserves genomic integrity, reduces tumorigenesis even against oncogenic Ras, corrects mitotic-checkpoint and microtubule–kinetochore attachment defects, extends lifespan | Mouse (transgenic) | Dose-response leg of D3: more BubR1 = less aneuploidy + less cancer |
| R, I, N ★ | 31738183 | 10.1172/JCI126863 | Sieben CJ 2020 J Clin Invest | Mouse mimicking a human MVA compound-het (BubR1^H/L1002P) is viable with MVA features: cancer predisposition, short lifespan, dwarfism, lipodystrophy, **sarcopenia**, low cardiac stress tolerance; severity tracks **SASP complexity** in skeletal muscle; monoallelic carriers get late sarcopenia correlating with **mTORC1 hyperactivity**. (Erratum: PMID 33136097, 10.1172/JCI144781) | Mouse (allelic series) | Closest published genetic analogue to a compound-het missense+truncating MVA child. Two new leads: SASP as the severity dial, and **mTORC1 → a rapamycin/rapalog hypothesis** |
| R, N ★ | 25754370 | 10.1111/acel.12344 | Zhu Y 2015 Aging Cell | Senescent-cell anti-apoptotic pathways identified from transcriptomics; dasatinib + quercetin (D+Q) established as senolytics | Human/mouse cells, mice | Origin of D+Q — **dasatinib is market-approved**, quercetin is a supplement |
| R, N ★ | 29988130 | 10.1038/s41591-018-0092-9 | Xu M 2018 Nat Med | Transplanted senescent cells cause persistent physical dysfunction in young mice; intermittent oral D+Q alleviated dysfunction and **increased post-treatment survival by 36%**, mortality hazard to 65%; D+Q reduced senescent cells and frailty cytokines in **human adipose explants** | Mouse + human tissue explants | Strongest quantitative senolytic effect size with a human-tissue leg. Intermittent "hit-and-run" dosing is the safety-relevant schedule |
| R | 26657143 | 10.1038/nm.4010 | Chang J 2016 Nat Med | ABT-263 (navitoclax, BCL-2/BCL-xL inhibitor) selectively kills senescent cells; oral dosing depleted senescent HSCs and muscle stem cells and **rejuvenated aged MuSCs** | Mouse | Muscle-stem-cell rejuvenation maps to muscle atrophy. Navitoclax is **not market-approved** (thrombocytopenia) — mechanism, not candidate |
| N | 30279143 | 10.1016/j.ebiom.2018.09.015 | Yousefzadeh MJ 2018 EBioMedicine | Fisetin most potent of 10 flavonoids screened; acute/intermittent dosing reduced senescence markers in **progeroid** and old mice, reduced senescence in human adipose tissue, extended median and maximum lifespan | Mouse (progeroid + aged), human adipose explants | Food-derived flavonoid — low-toxicity comparator; the progeroid leg is the relevant one |
| R | 38041783 | 10.1007/s11357-023-01011-0 | Harrison DE 2024 Geroscience | NIA Interventions Testing Program: **fisetin did not significantly affect lifespan in either sex** at the doses/schedules used (astaxanthin and meclizine did, in males) | Mouse (UM-HET3, multi-site) | The disconfirming counterweight — cite beside PMID 30279143 or the direction is overstated |

**Direction D5 (new): senolytic clearance of p16^Ink4a-positive cells.** Chain of evidence is
unusually tight for a rare disease: the mouse model *is* BubR1 hypomorphic (15208629), the
effector is identified (18516091), genetic clearance works in that exact background including
late in life (22048312), a pharmacological substitute with a market-approved component exists
(dasatinib, 25754370 / 29988130), and the closest compound-het model points at SASP severity
(31738183). Gap to state plainly: **no published study applies D+Q, navitoclax or fisetin to
BubR1^H/H mice** — the pharmacological leg is in other progeroid/aged models. Pediatric use of
dasatinib is separately constrained and out of scope for this file.

## 2. Aneuploidy-selective vulnerability — DepMap / PRISM

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| R, S ★ | 33505028 | 10.1038/s41586-020-03114-6 | Cohen-Sharir Y 2021 Nature | Aneuploidy landscapes of ~1,000 cancer cell lines: aneuploid lines are **more sensitive to genetic perturbation of core SAC components**, yet *less* sensitive to short-term SAC-inhibitor exposure, becoming sensitive over time; **KIF18A depletion** is a specific aneuploid vulnerability, and KIF18A over-expression restores SAC-inhibitor response | Human cancer cell lines (DepMap/PRISM) | Directly relevant and partly **contradicts** a naive D1: pharmacologically weakening the SAC further is not acutely selective. Caveat — cancer-cell aneuploidy, not constitutional mosaic aneuploidy |
| R ★ | 33505027 | 10.1038/s41586-020-03133-3 | Quinton RJ 2021 Nature | ~10,000 tumours + ~600 cell lines: whole-genome-doubled cells depend more on **SAC signalling, DNA-replication factors and proteasome function**, and specifically on KIF18A | Human tumours + cell lines | The **proteasome** dependency is the mechanistic footing for bortezomib in D2 |
| R | 33619254 | 10.1038/s41467-021-21447-2 | Marquis C 2021 Nat Commun | KIF18A required for proliferation of CIN cells (TNBC, CRC) but not near-diploid cells; inhibition → mitotic delay, multipolar spindles, increased death; sensitivity correlates with centrosome fragmentation | Human cell lines | Independent replication of KIF18A selectivity; "not required in near-diploid cells" is the therapeutic-window argument |
| R, N ★ | 21315436 | 10.1016/j.cell.2011.01.017 | Tang YC 2011 Cell | AICAR (energy stress), 17-AAG (HSP90/protein folding) and **chloroquine** (autophagy) are selectively lethal to aneuploid cells; AICAR induces p53-mediated apoptosis in MEFs trisomic for chr 1, 13, 16 or 19; AICAR + 17-AAG especially effective | Mouse trisomic MEFs + human cancer lines | Source for D2's chloroquine. The *primary* (non-cancer) trisomic MEF leg is the closest system to constitutional aneuploidy in this whole scan |
| N, S ★ | 32613204 | 10.1038/s43018-019-0018-6 | Corsello SM 2020 Nat Cancer | PRISM barcoded screen of **4,518 drugs × 578 cancer cell lines**; many non-oncology drugs selectively inhibit subsets predictable from molecular features (disulfiram/metallothionein-low, tepoxalin/ABCB1, PDE3A-SLFN12, vanadium/SLC26A2); public resource at depmap.org/repurposing | Human cancer cell lines | Screening substrate for a *computable* Track 2 method: join PRISM viability against a DepMap aneuploidy/CIN score to rank **approved** drugs. Combining 32613204's drug matrix with 33505028's aneuploidy scores is the concrete new analysis |

No paper found that already publishes "PRISM-derived aneuploidy-selective **approved** drugs" as
its own result — Cohen-Sharir 2021 uses PRISM but reports the KIF18A genetic dependency. That gap
is an opportunity (Innovation), not a missing citation.

## 3. Transcriptional signature reversal

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| N, S | 29195078 | 10.1016/j.cell.2017.10.049 | Subramanian A 2017 Cell | L1000 CMap: **1.3 million profiles**, >1,000× scale-up; L1000 reproducible and comparable to RNA-seq, infers 81% of non-measured transcripts; used to find MoA, annotate disease-gene variants, inform trials | Human cell lines | The reversal engine. Query = a BUB1B-deficiency signature; hits = compounds whose signature is anti-correlated |
| N, S | 21849665 | 10.1126/scitranslmed.3001318 | Sirota M 2011 Sci Transl Med | Signature-reversal repurposing across 100 diseases × 164 drugs; prediction of **cimetidine for lung adenocarcinoma** validated in vitro and in mouse xenografts | Public expression compendia + mouse xenograft | Method precedent with a wet-lab validation — the template for "we computed it, then said how to test it" |
| R | 28100397 | 10.7554/eLife.17044 | Kandela I 2017 eLife | Reproducibility Project replication study of Sirota 2011 (registered report: PMID 25939392) | Mouse xenograft | Honest calibration of the method's robustness |
| R, N, S | 16921376 | 10.1038/ng1861 | Carter SL 2006 Nat Genet | CIN70: genes whose expression tracks *total functional aneuploidy*; net over-expression predicts poor outcome across **12 datasets, 6 cancer types**; higher in metastases | Human tumour expression data | A ready-made, citable **aneuploidy signature** to reverse — no new signature derivation needed for a first ranking |

**Expression datasets found (GEO, fetched from `db=gds`):**

| Criterion | Accession | Organism | n | Title | Use |
|---|---|---|---|---|---|
| R, N | GSE134780 | Mus musculus | 23 | BubR1 allelic effects drive phenotypic heterogeneity in MVA progeria syndrome [10-month RNA-seq] | Signature source for the Sieben 2020 compound-het allelic series (PMID 31738183) |
| R, N | GSE134781 | Mus musculus | 9 | Same, [3-month RNA-seq] | Younger timepoint — closer to a child |
| R, I | GSE22206 | Homo sapiens | 14 | Homozygous BUB1B mutation and susceptibility to multi-site gastrointestinal neoplasia | **Human** BUB1B-mutant expression data; companion to Rio Frio 2010 (PMID 21190457) |
| R | GSE277997 | Mus musculus | 12 | BubR1 Insufficiency Recapitulates Changes Associated with Age-Related Cardiac Pathologies | Tissue-specific BubR1-insufficiency profile |
| R | GSE270226 | Mus musculus | 2 | Single-cell expression of wild-type vs BubR1-knockout E10.5 hearts | Developmental, single-cell |
| N, S | GSE49894 | Mus musculus | 6 | Transcriptional and metabolic signature of primary aneuploidy in chromosomally-unstable cancer cells | Primary-aneuploidy signature, complements CIN70 |

No GEO series was found for a direct **BUB1B knockdown in human cells** with a clean control
(queries: "BUB1B knockdown", "BUB1B siRNA expression"). GSE22206 (human patient cells) and
GSE134780/1 (mouse allelic series) are the best available substitutes.

## 4. Pharmacogenomics relevant to candidate drugs and RMS chemotherapy

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| R, I, S ★ | 35152405 | 10.1002/cpt.2557 | Cooper-DeHoff RM 2022 Clin Pharmacol Ther | CPIC guideline: SLCO1B1 (hepatic uptake of **all** statins), ABCG2 (rosuvastatin), CYP2C9 (oxidation of some statins) alter systemic statin exposure and risk of statin-associated musculoskeletal symptoms; replaces the 2012/2014 SLCO1B1–simvastatin guidelines | Human, guideline over published associations | Makes D4 (statins for RMS) *genotype-conditional*, and the case genome can be genotyped at these three loci. Musculoskeletal toxicity collides directly with the child's muscle atrophy |
| I, S | 25710658 | 10.1001/jama.2015.0894 | Diouf B 2015 JAMA | GWAS in 321 children on ALL protocols: **CEP72 promoter rs924607 TT** (MAF 37%; 16% homozygous) — 56% of TT patients had grade ≥2 vincristine neuropathy vs lower in CC/CT; severity 2.4-fold higher (Poisson, P<.0001); reducing CEP72 raised vincristine sensitivity in neurons and leukemia cells | Children (patients) + iPSC neurons | Vincristine is core RMS chemotherapy. A pharmacogenomic call readable *from the case's own WGS*, about a drug the child may actually receive |
| I | 38680001 | 10.31557/APJCP.2024.25.4.1391 | Shalaby N 2024 Asian Pac J Cancer Prev | Vincristine efficacy/toxicity vs **CYP3A5** polymorphism in **pediatric rhabdomyosarcoma** patients (Egyptian cohort) | Children with RMS | The rare PGx study in the exact tumour type; esummary-verified only — effect sizes not extracted |
| N, S | 31306493 | 10.1002/cpt.1568 | Sangkuhl K 2020 Clin Pharmacol Ther | PharmCAT: extracts CPIC-relevant variants from a genome VCF and emits guideline-matched annotations | Software | Executable bridge from the case VCF to this section's guidelines — a reusable pipeline stage, not a one-off |
| S | 36350094 | 10.1002/cpt.2790 | Li B 2023 Clin Pharmacol Ther | How to run PharmCAT (operational companion paper) | Software | Implementation reference |
| S | 26417955 | 10.1002/cpt.269 | Gammal RS 2016 Clin Pharmacol Ther | CPIC guideline for **UGT1A1** and atazanavir prescribing | Human, guideline | The only CPIC UGT1A1 guideline found. **No CPIC UGT1A1–irinotecan guideline was located**; see "Not found" |
| S | 37757824 | 10.1016/j.ajhg.2023.09.001 | Li B 2023 Am J Hum Genet | Frequencies of pharmacogenomic alleles across biogeographic groups in a large biobank | Human biobank | Prior probabilities for interpreting a single genome's PGx calls |

## 5. Label-derived adverse-effect resources and the two organ constraints

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| N, S ★ | 40179876 | 10.1016/j.medj.2025.100642 | Tanaka Y 2025 Med | OnSIDES: PubMedBERT fine-tuned on FDA Structured Product Labels; **F1 0.90, AUROC 0.92, AUPR 0.95** on the Adverse Reactions section; **>3.6M drug–ADE pairs, 3,233 ingredient combinations, 47,211 labels**; includes a **pediatric-specific** ADE extraction and Boxed-Warning subset, plus UK/EU/Japan labels (OnSIDES-INTL) | NLP over regulatory labels | The machine-readable safety filter for a candidate list. The **pediatric** subset is the part that matters here |
| S | 26481350 | 10.1093/nar/gkv1075 | Kuhn M 2016 Nucleic Acids Res | SIDER: database of marketed drugs and their recorded adverse reactions from public label documents | Curated label data | Older, smaller, still the standard cross-check against OnSIDES |
| I | 35348900 | 10.1007/s00467-021-05417-w | Fayard J 2022 Pediatr Nephrol | 525 very-low-birth-weight infants: nephrocalcinosis prevalence **17.1%** at 35 weeks corrected age; **furosemide exposure an independent risk factor (OR 1.26, 95% CI 1.02–1.57)**, as was postnatal growth; resolved in 61% within 12–18 months | Preterm infants | The child has IUGR/prematurity **and** nephrocalcinosis — quantifies a drug-attributable component and makes loop diuretics an explicit do-not-add |
| R | 30473868 | 10.1186/s40748-018-0092-2 | Jackson W 2018 Matern Health Neonatol Perinatol | Systematic review, 32 studies (20 on nephrocalcinosis/nephrolithiasis): **found no evidence** that furosemide raises the risk, but strength of evidence rated **low**, only one RCT | Preterm infants | Honest counterweight to the row above; the safety constraint stands on precaution, not settled evidence |
| I | 31696945 | 10.1002/14651858.CD006401.pub5 | Vuorio A 2019 Cochrane Database Syst Rev | Cochrane review of statins in children with familial hypercholesterolaemia | Children (RCTs) | Pediatric-safety anchor for D4; abstract not extracted |
| I | 31053349 | 10.1016/j.jpeds.2019.03.032 | Mamann N 2019 J Pediatr | Intermediate-term efficacy and tolerance of statins in children | Children | Second pediatric-tolerance source |

**Standing safety constraints for candidate screening** (each traceable to a row above):
nephrocalcinosis → screen out loop diuretics, and anything with a calcium/vitamin-D or
carbonic-anhydrase-inhibitor nephrocalcinosis label signal (query OnSIDES pediatric subset,
PMID 40179876); muscle atrophy → statin candidates are genotype-conditional on SLCO1B1/ABCG2/CYP2C9
(PMID 35152405), and the myopathy signal is the collision risk.

## 6. Rare-disease knowledge-graph repurposing

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| N, S ★ | 39322717 | 10.1038/s41591-024-03233-x | Huang K 2024 Nat Med | TxGNN: graph foundation model ranking drugs as indications/contraindications for **17,080 diseases**, explicitly **zero-shot** for diseases with no existing drugs; vs 8 baselines, **+49.2% indication accuracy and +35.1% contraindication accuracy**; Explainer gives multi-hop rationales; predictions align with real off-label prescribing | Knowledge graph + health-system data | Built for exactly this situation — a disease with no approved therapy. The **contraindication** head is as valuable as the indication head given §5's constraints. (Preprint: PMID 39148855) |
| N, S | 36732524 | 10.1038/s41597-023-01960-3 | Chandak P 2023 Sci Data | PrimeKG: 20 resources, **17,080 diseases, 4,050,249 relationships**, ten biological scales, with indication/contraindication/off-label drug–disease edges and clinical-guideline text | Knowledge graph | TxGNN's substrate, and directly queryable: MVA/BUB1B → phenotype → protein → drug paths, with HPO terms as first-class nodes (satisfies the two-source cross-reference rule) |

## 7. Recent (2020–2026) work on BubR1-deficiency rescue and MVA tumour spectrum

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| R, N ★ | 24825348 | 10.15252/embj.201386907 | North BJ 2014 EMBO J | BubR1's age-related decline is caused by falling NAD+ and loss of SIRT2-mediated deacetylation of **BubR1 lysine-668**, opposed by the acetyltransferase CBP; SIRT2 over-expression **or treating mice with the NAD+ precursor NMN raises BubR1 abundance in vivo**; SIRT2 over-expression in **BubR1^H/H** mice increased median lifespan, more in males | Mouse (incl. BubR1^H/H) | Mechanistic core of D3, and the only paper here that raises BubR1 *pharmacologically* in the hypomorphic genotype. The acetylation site is the actionable node |
| R | 39490401 | 10.1016/j.semcancer.2024.10.005 | Pun R 2024 Semin Cancer Biol | Review: SIRT2 as upstream regulator of BubR1; NAD+ and SIRT2 modulate BubR1 expression and function; proposed as a therapeutic target | Review | Current synthesis of D3; use for framing, cite primaries for claims |
| R | 41533580 | 10.1093/nar/gkaf1517 | Choi SY 2026 Nucleic Acids Res | Aurora B's role in **BubR1 acetylation**, linking kinetochore attachment to checkpoint control | Cells (title/summary verified; abstract not extracted) | Extends the acetylation-control story behind D3's HDAC-inhibitor arm |
| R, I, N ★ | 31738183 | 10.1172/JCI126863 | Sieben CJ 2020 J Clin Invest | (see §1) sarcopenia predisposition in monoallelic carriers correlates with **mTORC1 hyperactivity** | Mouse | The only published pointer to an **mTOR/rapamycin** hypothesis in a BUB1B-mutant background — a candidate new sub-direction, market-approved (sirolimus/everolimus) |
| R, I ★ | 41249736 | 10.1038/s44321-025-00336-x | Gizaw NY 2025 EMBO Mol Med | De novo **cholesterol biosynthesis** is a metabolic vulnerability in RMS (PROX1 upstream); genetic or pharmacological inhibition halts proliferation and triggers PERK–ATF4–CHOP ER-stress apoptosis; RMS cells **cannot be rescued by exogenous LDL**, unlike myoblasts and astrocytes | Human RMS lines + clinical/scRNA-seq | Strongest and most recent mechanistic backing for D4 (statins), plus an explicit **selectivity argument** — normal myoblasts rely on uptake, RMS on synthesis — which is exactly the muscle-safety question |
| R ★ | 38473215 | 10.3390/cancers16050853 | Codenotti S 2024 Cancers | Lovastatin and simvastatin induce apoptosis in RMS lines by lowering Akt1 and Cav1 and raising ROS; statin + irradiation increased DNA damage and apoptosis (γH2AX, FACS); statin + actinomycin D reduced survival | Human RMS lines (RD, RH30) | Names **specific market-approved statins** and a combination context (radiotherapy, actinomycin D — both standard in RMS) |
| I | 31081598 | 10.1002/pbc.27804 | Ochiai K 2019 Pediatr Blood Cancer | Long-term remission of bilateral Wilms tumours in PCS/MVA syndrome after bilateral nephrectomy and peritoneal dialysis | Patient case report | MVA tumour spectrum includes bilateral Wilms; a renal-function precedent relevant to the nephrocalcinosis constraint |
| I | 42595739 | 10.1080/01676830.2026.2715719 | Vempuluru VS 2026 Orbit | Sequential Wilms tumour then orbital rhabdomyosarcoma in a child with MVA syndrome 3 | Patient case report | Recent confirmation of Wilms + RMS co-occurrence in MVA — supports surveillance framing, though MVA3 (TRIP13) not MVA1 |

## 8. MVA1 BUB1B alleles — do missense variants lose function or lose protein?

| Criterion | PMID | DOI | First author, year, journal | Key finding | System | Relevance |
|---|---|---|---|---|---|---|
| R, I | 15475955 | 10.1038/ng1449 | Hanks S 2004 Nat Genet | Truncating and missense **BUB1B** mutations in five MVA families, **two with embryonal rhabdomyosarcoma**; first germline spindle-checkpoint-gene mutations tied to a human disorder | Patients | The founding MVA1 paper — and it already contains the RMS association this case shows |
| R ★★ | 20516114 | 10.1158/0008-5472.CAN-09-4319 | Suijkerbuijk SJ 2010 Cancer Res | **In biallelic patients a missense pairs with a truncating mutation.** Patient cells show impaired mitotic checkpoint, chromosome alignment defects and **low overall BubR1 abundance**; ectopic BubR1 restores checkpoint activity. MVA mutations split into two classes: (i) specific checkpoint/attachment defects, (ii) **lowered BubR1 protein abundance** — the latter from absent transcripts of truncating alleles plus **high protein turnover of missense mutants**, whose substitutions consistently fall in or near the **kinase domain** | Patient-derived cell lines + functional protein replacement | The single most decision-relevant paper for this case's architecture. "Ectopic BubR1 restored checkpoint activity" says the defect is **dose-reversible** — the premise D3 rests on. It also predicts a missense allele's class from its position relative to the kinase domain |
| R, I | 16411201 | 10.1002/ajmg.a.31069 | Matsuura S 2006 Am J Med Genet A | Monoallelic BUB1B mutations with defective mitotic-spindle checkpoint in seven PCS-syndrome families (see §9 for the assay detail) | Patients | Establishes PCS/MVA equivalence and that even monoallelic states show checkpoint defects |
| R, I | 21190457 | 10.1056/NEJMoa1006565 | Rio Frio T 2010 N Engl J Med | Homozygous intronic **BUB1B c.2386-11A→G** creating a preferred de novo splice site; PCS + MVA with structural chromosomal abnormalities; adult-onset ampullary, colon and gastric cancers; evidence for APC–BubR1 interdependency | Patient | Expands the MVA phenotype into adulthood and common cancers — a surveillance argument. Companion expression data: **GSE22206** |
| I | 39014450 | 10.1186/s12929-024-01056-z | Silva MP 2024 J Biomed Sci | BUB1B **monoallelic germline variants** contribute to prostate cancer predisposition by triggering chromosomal instability | Human | Heterozygous BUB1B carriage is not phenotypically silent — relevant to the parents |
| I | 42434306 | 10.3389/fendo.2026.1838559 | Wei TY 2026 Front Endocrinol | Functional and clinical evidence for two novel heterozygous **BUB1B** variants in **recurrent pregnancy loss**, with genetic-counselling value | Patients | Directly addresses the parental recurrent-miscarriage feature; title/summary verified, abstract not extracted |
| I, S | 40555658 | 10.3760/cma.j.cn511374-20240716-00393 | Qu J 2025 Zhonghua Yi Xue Yi Chuan Xue Za Zhi | Two fetuses with MVA from **compound heterozygous BUB1B variants plus upstream regulatory-element variants**, with literature review | Fetuses | Precedent for compound-het BUB1B MVA including non-coding regulatory alleles — the second hit is not always coding |

**Answer to the section's question:** both, and the class is predictable. Suijkerbuijk 2010
(PMID 20516114) shows MVA missense alleles divide into function-impairing and
abundance-lowering, with abundance-lowering missense alleles destabilised (high protein turnover)
and clustering in or near the kinase domain — while truncating alleles contribute no transcript at
all. A compound het of stop-gained + missense therefore usually lands at low total BubR1, which is
precisely the state that ectopic BubR1 rescued in the same paper.

## 9. Diagnosing MVA and measuring BubR1 function in patient cells ★

The panel's Rigor and Impact questions turn on whether the mechanism is *measurable in a patient*,
not only inferable from a variant call. These are the papers that make the mechanism an assay.

| Criterion | PMID | DOI | First author, year, journal | Assay / finding | System | Relevance |
|---|---|---|---|---|---|---|
| R, I ★ | 16411201 | 10.1002/ajmg.a.31069 | Matsuura S 2006 Am J Med Genet A | Full patient-cell workup in seven PCS/MVA families: **premature chromatid separation of all chromosomes** cytogenetically; RT-PCR showing transcripts reduced by nonsense-mediated decay; **Western blot showing reduced BubR1 protein**; **diminished BubR1 kinetochore localisation**; abolished kinetochore association of p55cdc (CDC20) with normal total p55cdc; **abnormal response to colcemid** (the checkpoint challenge). Microcell-mediated transfer of chromosome 15 (carrying BUB1B) **restored** BubR1 level, p55cdc localisation and the colcemid response. Concludes that a **>50% decrease in BubR1 expression or activity** underlies PCS syndrome | Patient lymphocytes / cell lines | The assay panel, end to end: cytogenetic PCS count → BubR1 Western → kinetochore immunofluorescence → colcemid/nocodazole checkpoint challenge, with a genetic rescue as the positive control. The ">50% decrease" threshold is the quantitative bar a candidate drug would have to move |
| R, I ★ | 20516114 | 10.1158/0008-5472.CAN-09-4319 | Suijkerbuijk SJ 2010 Cancer Res | Patient-cell mitotic checkpoint assay + chromosome alignment scoring + BubR1 abundance, then **functional protein replacement** to assign each allele to a class (function-impairing vs abundance-lowering) | Patient-derived cells | Turns "which allele does what" into an executable protocol; the abundance readout is the biomarker a BubR1-raising drug would be judged on |
| R, I, S ★ | 28553959 | 10.1038/ng.3883 | Yost S 2017 Nat Genet | Six individuals with biallelic **TRIP13** loss of function, **all six developed Wilms tumour**; patient cells have no detectable TRIP13 and **substantial SAC impairment** with high chromosome missegregation, both **rescued by restoring TRIP13**. Key stratifier: biallelic **TRIP13 or BUB1B** patients have high embryonal-tumour risk and **severe SAC impairment**, whereas **CEP57**-caused or unexplained MVA is *not* associated with embryonal tumours and shows **minimal SAC deficiency** | Patients + patient cells | The strongest diagnostic-impact paper in the scan: **degree of SAC impairment, measured in patient cells, stratifies tumour risk across MVA genes.** It makes a functional SAC assay a candidate prognostic test, not just a confirmation — and it generalises to every MVA gene (scalability) |
| I, S | 37796616 | 10.1172/jci.insight.170079 | Abdel-Salam GMH 2023 JCI Insight | Homozygous **MAD2L1BP (p31^comet)** R253* in two siblings with microcephaly, epileptic encephalopathy and juvenile granulosa cell tumours; patient cells show **high-grade mosaic variegated aneuploidy**, slowed proliferation, unstable truncated mRNA and protein; recombinant protein defective in TRIP13/MAD2/REV7 binding, unable to silence the SAC or support homology-directed repair; a second truncation (R227*) gave low-level aneuploidy | Patients + patient cells + recombinant protein | Newest MVA-spectrum gene. Shows the same evidence template (patient aneuploidy grade + biochemical defect + protein instability) applied to a novel gene — the reusable pattern for N-of-1 mechanism work |
| I | 21190457 | 10.1056/NEJMoa1006565 | Rio Frio T 2010 N Engl J Med | PCS + MVA detected cytogenetically in an adult, leading to the intronic BUB1B splice variant; companion expression data **GSE22206** | Patient | Diagnosis driven by the *cytogenetic phenotype* rather than the variant — the direction a functional assay makes possible |
| I | 41700350 | 10.1515/jpem-2025-0643 | Viudes CP 2026 J Pediatr Endocrinol Metab | Novel **CEP57** mutation in MVA syndrome 2 (case report) | Patient | Differential-diagnosis anchor; pairs with Yost 2017's finding that CEP57-MVA carries minimal SAC deficiency and no embryonal-tumour association |
| I | 36635612 | 10.1111/cge.14297 | Langeh N 2023 Clin Genet | MVA2 with biallelic novel **CEP57** splice-site variation in Indian siblings, expanding the clinical and molecular spectrum | Patients | Second CEP57 reference for the same differential; esummary-verified, abstract not extracted |

**What §9 buys the submission.** (1) A *measurable* mechanism: BubR1 protein level, kinetochore
localisation, and a colcemid/nocodazole checkpoint challenge in patient cells (PMID 16411201),
with the ">50% of normal BubR1" threshold as the quantitative target. (2) A *stratifier*:
SAC-impairment severity separates the tumour-prone MVA genotypes (BUB1B, TRIP13) from the ones
that are not (CEP57) — PMID 28553959 — which is a diagnostic contribution, not only a
therapeutic one. (3) A *validation endpoint* for any D3-type candidate: the drug should raise
BubR1 abundance (PMID 24825348's readout) and improve the checkpoint response (PMID 20516114's
readout) in the patient's own cells.

---

## Not found / could not verify

| Item sought | Status |
|---|---|
| Pharmacological senolytic (D+Q, navitoclax, fisetin) applied **in BubR1^H/H mice** | **Not found.** Searched senolytic + BubR1/progeroid combinations. Genetic clearance in BubR1^H/H exists (PMID 22048312); pharmacological senolysis exists in other progeroid and aged models (30279143, 29988130, 26657143). The bridge study appears not to be published — state this as a gap, never imply it exists |
| CPIC guideline for **UGT1A1 and irinotecan** | **Not found** as a CPIC guideline. Only the CPIC UGT1A1–**atazanavir** guideline (PMID 26417955) was retrieved; DPWG/CPNDS/RNPGx comparisons appear in PMID 33568995 (Abdullah-Koolmees 2020 Front Pharmacol). Do not cite a CPIC irinotecan guideline |
| A paper whose own result is "**PRISM-derived aneuploidy-selective approved drugs**" | **Not found.** Cohen-Sharir 2021 (33505028) uses PRISM but reports a genetic (KIF18A) dependency. The analysis is available to run, not to cite |
| GEO series for **BUB1B knockdown in human cells** with clean controls | **Not found.** Nearest substitutes: GSE22206 (human BUB1B-mutant patient cells), GSE134780/GSE134781 (mouse MVA allelic series) |
| **Valproate / vorinostat acting on BubR1 acetylation** (the HDAC arm of D3) | **Not verified.** Searches for valproate/HDAC + BubR1 + mitotic checkpoint returned no hit. The acetylation biology is verified (24825348 SIRT2/K668/CBP; 41533580 Aurora B), but no verified paper connects an approved HDAC inhibitor to raising BubR1. Mark the HDAC arm as **unsupported by a verified primary source** |
| A **metformin** aneuploidy-selectivity primary paper (D2) | **Not found** by the queries run. Tang 2011 (21315436) supports AICAR (energy stress, not an approved oral drug), 17-AAG and chloroquine — not metformin. If the report cites metformin, the AMPK/energy-stress link is analogical and must say so |
| A **bortezomib** aneuploidy-selectivity primary paper (D2) | **Not directly found.** The proteasome-dependency evidence is genetic in Quinton 2021 (33505027). Frame bortezomib as inferred from that dependency, not as a screened hit |
| Rapamycin/mTOR or exercise intervention **in an MVA/BubR1 model** | **Not found as an intervention study.** Only the correlative mTORC1-hyperactivity observation in Sieben 2020 (31738183). Hypothesis-generating pointer, not an executed rescue |
| A standardised, published **clinical diagnostic threshold** for a BubR1 functional assay | **Not found.** Matsuura 2006 (16411201) gives ">50% decrease in expression or activity" as a conclusion, not a validated clinical cut-off; Yost 2017 (28553959) reports SAC impairment qualitatively (severe vs minimal). Any assay threshold used in the report must be presented as derived here, not as an established standard |
| Abstract-level effect sizes for PMIDs 38680001, 41533580, 42434306, 31696945, 31053349, 36635612, 41700350 | Titles/authors/journals/years/DOIs verified by esummary; **full abstracts not fetched**, so no numbers are quoted for these rows |
