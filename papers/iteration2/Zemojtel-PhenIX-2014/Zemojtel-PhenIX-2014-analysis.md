---
title: "Effective diagnosis of genetic disease by computational phenotype analysis of the disease-associated genome"
authors: ["Zemojtel, Tomasz", "Köhler, Sebastian", "Mackenroth, Luisa", "Jäger, Marten", "Hecht, Jochen", "Krawitz, Peter", "Graul-Neumann, Luitgard", "Doelken, Sandra", "Ehmke, Nadja", "Spielmann, Malte", "Øien, Nancy Christine", "Schweiger, Michal R.", "Krüger, Ulrike", "Frommer, Götz", "Fischer, Björn", "Kornak, Uwe", "Flöttmann, Ricarda", "Ardeshirdavani, Amin", "Moreau, Yves", "Lewis, Suzanna E.", "Haendel, Melissa", "Smedley, Damian", "Horn, Denise", "Mundlos, Stefan", "Robinson, Peter N."]
year: 2014
venue: "Science Translational Medicine"
doi: "10.1126/scitranslmed.3009262"
arxiv: null
url: "https://doi.org/10.1126/scitranslmed.3009262"
paper_type: empirical
domains: [medical genetics, clinical bioinformatics, phenotype-driven variant prioritization, Mendelian disease diagnosis]
lens: bioinformatics
modes: [learn, apply]
code: "http://compbio.charite.de/PhenIX/ (web server, no inspectable repo found)"
data: "none public (patient VCFs/HPO terms are clinical, not released); HGMD/HPO/dbSNP/EVS used as reference resources"
relevance: 5
analysed: 2026-09-10
analyst: paper-analyst
---

# Effective diagnosis of genetic disease by computational phenotype analysis of the disease-associated genome

## Identity & citation
Zemojtel, Köhler, Mackenroth et al. (2014), *Science Translational Medicine* 6(252):252ra123. DOI [10.1126/scitranslmed.3009262](https://doi.org/10.1126/scitranslmed.3009262). Open-access copy: https://lirias.kuleuven.be/bitstream/123456789/463486/2/CP_14-131.pdf. *Science Translational Medicine* is a peer-reviewed AAAS journal (sister to *Science*), aimed at clinically translatable research — not a preprint.

```
APA 7:
Zemojtel, T., Köhler, S., Mackenroth, L., Jäger, M., Hecht, J., Krawitz, P., Graul-Neumann, L., Doelken, S.,
Ehmke, N., Spielmann, M., Øien, N. C., Schweiger, M. R., Krüger, U., Frommer, G., Fischer, B., Kornak, U.,
Flöttmann, R., Ardeshirdavani, A., Moreau, Y., ... Robinson, P. N. (2014). Effective diagnosis of genetic
disease by computational phenotype analysis of the disease-associated genome. Science Translational
Medicine, 6(252), 252ra123. https://doi.org/10.1126/scitranslmed.3009262

BibTeX:
@article{zemojtel2014effective,
  title   = {Effective diagnosis of genetic disease by computational phenotype analysis of the
             disease-associated genome},
  author  = {Zemojtel, Tomasz and Köhler, Sebastian and Mackenroth, Luisa and Jäger, Marten and
             Hecht, Jochen and Krawitz, Peter and Graul-Neumann, Luitgard and Doelken, Sandra and
             Ehmke, Nadja and Spielmann, Malte and Øien, Nancy Christine and Schweiger, Michal R. and
             Krüger, Ulrike and Frommer, Götz and Fischer, Björn and Kornak, Uwe and Flöttmann, Ricarda
             and Ardeshirdavani, Amin and Moreau, Yves and Lewis, Suzanna E. and Haendel, Melissa and
             Smedley, Damian and Horn, Denise and Mundlos, Stefan and Robinson, Peter N.},
  journal = {Science Translational Medicine},
  volume  = {6}, number = {252}, pages = {252ra123}, year = {2014},
  doi     = {10.1126/scitranslmed.3009262}
}

Vancouver:
Zemojtel T, Köhler S, Mackenroth L, Jäger M, Hecht J, Krawitz P, et al. Effective diagnosis of genetic
disease by computational phenotype analysis of the disease-associated genome. Sci Transl Med.
2014;6(252):252ra123. doi:10.1126/scitranslmed.3009262
```

## Paper type & how to read it
Empirical/systems paper: it introduces a diagnostic **pipeline** (wet-lab panel + software, PhenIX) and reports its performance on simulations, a retrospective cohort, and a prospective cohort. It owes the reader: a clearly specified method, honest comparison to a baseline (variant-only filtering), and evidence the numbers transfer from simulation to real patients — which is exactly the structure it follows. Read it as "does phenotype-driven ranking beat variant-only filtering, and does that hold up prospectively", not as a benchmark paper (no community truth set is used) or a tool paper (the tool itself, PhenIX, is a byproduct with no released source in the paper).

## One-minute pitch
Sequencing a patient's exome turns up tens of thousands of differences from the reference genome — most harmless. Finding the one or two that cause disease is like finding a needle in a haystack using only "how unusual does this variant look." This paper adds a second haystack-shrinking trick: compare what the *patient* looks like clinically (their symptoms, coded as standardized terms) to what's *known* about each candidate disease gene, and combine that phenotype match with the variant's oddness score. They built a gene panel of 2,741 genes already linked to Mendelian disease, sequenced 96 samples, and ranked candidate genes with a tool called PhenIX. In simulations the true gene landed in first place 86.5% of the time (versus under 5% using variant data alone); on 40 real undiagnosed patients this workflow closed the case for 11 of them (28%).

**TL;DR:** Combining a gene's mutation "badness" score with how well the patient's symptoms match the gene's known disease phenotypes (via ontology-based similarity) massively improves candidate-gene ranking over variant filtering alone. Retrospectively the correct gene ranked 2.1st on average among 2,741 candidates; prospectively it produced new diagnoses in 28% of previously unsolved cases in about 2 hours of analyst time per patient.

## Domains & keywords
Medical genetics > clinical bioinformatics > phenotype-driven variant prioritization > Mendelian disease diagnostics. Techniques: targeted gene-panel sequencing, semantic similarity over an ontology (HPO), variant pathogenicity scoring (PolyPhen-2, SIFT, MutationTaster via dbNSFP), rank-based evaluation. Resources: Human Phenotype Ontology (HPO), OMIM, Orphanet, HGMD, dbSNP, NHLBI Exome Variant Server.

## Problem & research questions
Gap: even after "extensive workups," diagnostic yield in suspected genetic disease is under 50%, and interpreting the ~30,000+ variants in an exome is impractical in a clinical (not research) setting. Implicit research questions: (1) does restricting sequencing to a curated panel of known disease genes (the "disease-associated genome," DAG) retain the clinically useful variants at lower cost/coverage burden than exome/genome sequencing? (2) does adding a phenotype-similarity score to the variant score materially improve how often the true causal gene is ranked at or near the top? Authors' framing in one line: "a phenotype-driven computational and clinical workflow for the efficient diagnosis of rare Mendelian diseases."

## Method
**In plain language.** Two ingredients feed a ranking: (1) how rare and how "damaging-looking" a variant is (like a spellchecker flagging a typo as more or less likely to be a real error), and (2) how well the patient's coded symptom list matches the symptom list already known for each candidate gene's diseases (like matching a search query to documents by shared keywords, except the keywords form a tree so "abnormal skull shape" partially matches "microcephaly" even if the exact term differs). The two scores are averaged into a final rank per gene, with a penalty if the pattern of variants found doesn't fit how the disease is inherited (e.g., only one broken copy found in a gene where you'd need two).

**Technically.** Wet lab: SureSelect targeted-capture panel over the coding exons of 2,741 genes with at least one Mendelian disease link (7.1 Mb), sequenced on Illumina HiSeq 1500 (100 bp paired-end), aligned with Novoalign to hg19, variants called with GATK 2.8, annotated with Jannovar. Coverage: mean 361.7±81.6× raw (135.6±10.6× after dedup); ≥20× at 98% of target bases across 96 samples.

Software (PhenIX): variant score = frequency score (from dbSNP + NHLBI EVS, `max(0, 1 − 0.13533·e^(100f))`, 1.0 for absent variants) × pathogenicity score (max of PolyPhen-2/SIFT/MutationTaster via dbNSFP 2.4, normalized 0–1). Gene relevance score = Phenomizer-style semantic similarity between the patient's HPO terms and the HPO annotations of all diseases linked to that gene, halved if the observed variant zygosity pattern is incompatible with the gene's known mode of inheritance. Final score = mean of variant score and gene relevance score; genes ranked by combined score, ties broken alphabetically.

Evaluation designs: (a) **simulation** — 10,000 HGMD disease-causing mutations spiked into real DAG-panel VCFs (with the true mutation stripped out first), three phenotype-input regimes (all HPO terms; ≤5 random terms; ≤5 terms with 2 terms generalized to a parent + 2 random noise terms), 8,504/3,471/5,006 runs for All/AD/AR; (b) **retrospective** — 52 patients (2010–2013) with Sanger-confirmed diagnoses, real HPO terms, frequency threshold 1%; (c) **prospective** — 40 previously undiagnosed patients, top-20 PhenIX candidates reviewed at clinical rounds, Sanger validation + cosegregation on the 1–2 chosen candidates.

## Figures & tables check
| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 1 | 3 | Simulated rank of the true gene as top/top-5/top-10/top-20 hit, for variant-only vs. phenotype-only vs. PhenIX, across 3 term-noise regimes (All/AD/AR × completeness) | "PhenIX placed correct gene first >86% of time; 32.5-fold improvement over variant filtering" | OK | Bar chart, no error bars/CIs given per bar; n per condition (8,504/3,471/5,006) stated in caption, not on the chart itself |
| Fig. 2 | 4 | PhenIX end-to-end workflow: clinical intake → DAG sequencing + deep phenotyping → variant/phenotype scoring → top-20 list → clinical rounds → Sanger/cosegregation → diagnosis | Frames the whole clinical-integration claim | OK | Schematic, not data; useful mainly for process, matches text description exactly |
| Table 1 | 3 | 52 retrospective patients, genes by mode of inheritance, mean rank (AD 1.7, AR 5, X 1.8) | "Average rank of correct gene was 2.1" | OK | Recompute: weighted mean isn't shown directly, but AR's higher (worse) rank is explained narratively by one SLC39A4 outlier (rank 14) — a single case materially drags the AR mean; no sensitivity analysis excluding it |
| Table 2 | 3 | Clinical presentation categories for the 40 prospective (undiagnosed) patients | Establishes the prospective cohort's phenotypic breadth | OK | Descriptive only |
| Table 3 | 5 | The 11 solved prospective cases: gene, rank (1–6, avg 2.5), diagnosis, mode of inheritance | "28% diagnostic yield at mean rank 2.4" (abstract) vs. "average rank... was 2.5" (table caption) | Caution | Minor inconsistency: abstract says 2.4, Table 3 caption says 2.5 — recomputing from the 11 listed ranks (2,4,1,6,1,2,2,1,4,1,3) gives mean = 2.45, so both roundings are defensible but the paper is internally inconsistent about which figure to quote |
| Fig. S2 / Table S5 | supp. (not rasterized here) | Computational evaluation detail; 29 patients where PhenIX failed | Bears on "what doesn't work" | Not verified | Supplementary; not in the main-text page range this scan rasterized — treat any claim about the 29 failed cases as coming from the text summary only, not directly inspected |

## Claims vs evidence
| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | DAG panel reaches ≥20× coverage on 98% of target bases | Coverage stats across 96 samples, fig. S1/table S1 | Results, "Design and validation" | strong | Direct measurement, large n, but supplementary figure not independently inspected here |
| C2 | Variant-score-only ranking finds the true gene first <5% of the time | Simulation, fig. 1 "Variant" bars | Fig. 1 | strong | Reproduced across 3 noise regimes; internal baseline, not compared to an external variant-filtering tool's actual published numbers |
| C3 | PhenIX (variant + phenotype) ranks the true gene first >86% of simulations (86.5%, 8,504 runs) | Simulation, fig. 1 "PhenIX" bars | Fig. 1 | strong | Best-case regime uses realistic noise/imprecision injection, a genuine strength, but simulated phenotypes are drawn from the same HPO annotations used to build the scoring database — some circularity is inherent to this style of self-evaluation |
| C4 | Retrospectively, correct gene achieves mean rank 2.1 over 2,741 genes (52 real patients) | Table 1 | Results, "Retrospective analysis" | moderate | Real patients, real HPO terms — stronger than pure simulation — but n=52 is small, cohort drawn from the authors' own clinic (selection: cases with available parental DNA), and one gene (SLC39A4) shows a known failure mode (synonymous splice-disrupting variant missed), which the authors disclose |
| C5 | Prospectively, PhenIX enables diagnosis in 11/40 (28%) previously unsolved cases, mean rank 2.4–2.5 | Table 3, discussion | Results, "Prospective analysis" | moderate | Real, clinically meaningful outcome — the strongest evidence in the paper — but cohort is small (n=40), single-center, not blinded/pre-registered, and "solved" required human clinical-rounds judgment layered on top of the algorithm's top-20 list, so the 28% reflects the whole workflow (algorithm + expert triage + Sanger), not the algorithm alone |
| C6 | Whole workflow takes ~2 hours of clinician time per patient | Discussion, narrative estimate | Discussion | weak | Self-reported estimate by the authors performing the study, not measured with time-tracking; no comparison to time cost of standard WES analysis |
| C7 | DAG-panel approach is preferable to WES/WGS for this diagnostic setting on cost/coverage/interpretability grounds | Discussion argument, coverage down-sampling experiment (table S3) | Results + Discussion | weak-moderate | The down-sampling experiment (simulating 100× exome coverage from panel BAMs) is a real, if narrow, cost-benefit test; broader claims about "the ability to provide quick and accurate clinical interpretation" are argued, not benchmarked head-to-head against an actual WES pipeline on the same patients |

## What works
- The core idea — averaging a variant-damage score with an HPO-based phenotype-similarity score — produces a large, consistent lift over variant-only ranking across every simulation regime in Fig. 1, including the more realistic "≤5 terms + noise" condition (top-20 recall still far above the variant-only baseline).
- The retrospective cohort (real patients, real clinicians entering real HPO terms) shows the effect is not an artifact of simulation: mean rank 2.1 of 2,741 candidate genes is a strong reduction from "hundreds of candidates" to "read the first few rows."
- The prospective arm is the most convincing evidence class in the paper: 11 genuinely new diagnoses in patients who had already failed conventional workup (physical exam, array CGH, targeted Sanger) — a real clinical outcome, not just a ranking metric.
- The named failure case (SLC39A4 synonymous splice variant) is disclosed rather than hidden, and it correctly foreshadows a limitation the authors state explicitly (synonymous/noncoding variants with cryptic splice effects are missed by this pipeline).

## What doesn't work (or isn't shown)
- 29 of the 40 prospective patients remained undiagnosed (Table S5, not independently inspected here) — a 72% "miss rate" on the hardest cohort (patients selected specifically because standard workup already failed). The paper reports this but does not analyze *why* those 29 failed (e.g., candidate gene truly outside the 2,741-gene DAG panel vs. non-coding cause vs. phenotype miscoded) beyond the general discussion of panel scope limits.
- No head-to-head comparison on the same patients against a full WES/WGS pipeline, nor against the authors' own earlier tools (PHIVE/Exomiser, eXtasy) — the paper argues DAG+PhenIX is preferable but the strongest direct comparator (variant-score-only) is a weaker baseline than "current best alternative."
- No confidence intervals or variance reported for the simulation bars in Fig. 1, despite thousands of runs being computationally cheap to bootstrap.
- No error-mode breakdown by disease category, gene, or mode of inheritance beyond the AD/AR/X split in Table 1 — e.g., it is not shown whether recessive-disease ranking is systematically worse across the cohort or driven mostly by the one disclosed SLC39A4 case.
- Non-coding/regulatory variants are explicitly out of scope (panel captures coding exons only), and the discussion itself flags this as an open problem rather than something solved here.

## Limitations
**Stated by the authors.**
- The DAG panel captures only protein-coding exons; disease-causing regulatory/enhancer variants (their own example: sonic hedgehog enhancer mutations) are not captured.
- The method is not designed to discover *new* disease genes — by construction it only ranks within the 2,741 known genes; other tools (Exomiser, eXtasy) target novel-gene discovery.
- Synonymous or presumptively benign variants that actually disrupt splicing (as in the SLC39A4 case) are not flagged as pathogenic by the pipeline.
- Performance depends on the completeness/accuracy of HPO annotation for a given disease; under-annotated diseases would rank worse.
- Trio (parent) sequencing was not used, though the authors note it "could easily be adapted" into the workflow.

**Not stated (analyst).**
- Single-center, single-team cohort for both retrospective and prospective arms — no external validation site, so generalization to other clinics' phenotyping practices (which affects HPO-term quality, the input the whole method leans on) is untested.
- The phenotype similarity score and the "ground truth" gene-phenotype associations both derive from the same HPO/OMIM/Orphanet corpus that presumably also informed how the authors chose HPO terms clinically — a degree of circularity that is hard to fully separate from genuine signal, especially in the simulation arm.
- No inter-rater reliability check on HPO term selection — different clinicians assigning different (equally valid) terms to the same patient could shift rankings; this is exactly the kind of protocol-reporting gap the bioinformatics lens flags (see `references/lens-bioinformatics.md` §4).
- No statistical test (e.g., permutation test against a null ranking) accompanies the headline "32.5-fold improvement" figure; it's a ratio of proportions, not a hypothesis test with a p-value or CI.
- The abstract's "mean rank of 2.4" versus Table 3's "average rank...was 2.5" inconsistency (see Figures & tables check) suggests at least one number in the paper was not double-checked between abstract and body.

## Validity, bias & reproducibility
**Internal validity.** The simulation design (spike a known HGMD mutation into a real patient VCF, strip the true positive first) is a reasonable way to generate ground truth at scale, and the three noise/completeness regimes are a genuine attempt to stress-test realism. The retrospective and prospective arms add real-world validity the simulation alone couldn't provide. The main internal-validity risk is the circularity noted above: HPO-based gene-phenotype associations both generate the "expected" phenotype fingerprint for each gene *and* are the yardstick used to judge whether a patient's phenotype matches it — this is standard practice in the field but worth naming as a boundary on what "phenotype similarity" is actually measuring (agreement with curated annotation, not an independent biological ground truth).

**External validity.** Single institution (Charité, Berlin), likely a specific demographic and referral pattern (2 of 40 prospective cases were external referrals). Whether the ~28% yield transfers to other populations, other phenotyping teams, or non-European ancestry cohorts (relevant since allele-frequency filtering depended partly on NHLBI EVS "African American/European American" population labels) is untested here.

**Reporting.** Software version numbers are given for the pipeline (GATK 2.8, Jannovar, Novoalign, dbNSFP 2.4) — good reproducibility hygiene for 2014. No random seed is reported for the simulation draws (term subsampling, noise-term injection), and no code repository accompanies the paper — the described algorithm would have to be reimplemented from the Methods section rather than run directly, though the PhenIX web server (link in the paper) may still implement a version of it.

**Reproducibility score: 2** — detailed protocol in the paper (scoring formulas, thresholds, pipeline tool versions), but no released code, no released data (patient VCFs/HPO term lists are clinical and cannot be shared), and no independent reproduction found in this analysis. The single biggest obstacle: no algorithm implementation is distributed with the paper (only a hosted web server, `http://compbio.charite.de/PhenIX/`, whose current availability was not checked in this analysis) — anyone wanting to rerun the exact scoring pipeline must reimplement it from the formulas in Methods.

## Related work & key citations
**Foundations**
- Köhler et al. — Phenomizer / earlier semantic-similarity work on HPO (ref. 28 in-paper) — the similarity algorithm PhenIX's phenotype score is adapted from.
- Robinson et al. and the HPO project itself (ref. 3, 27) — the ontology of >10,000 phenotype terms and >110,000 disease annotations that both the retrospective/prospective clinical input and the gene-relevance scoring depend on.
- Ng et al. 2010 (ref. 7), *Nat. Genet.* — first use of exome sequencing to solve a Mendelian disease; frames why exome/genome diagnostics became attractive at all.

**Competitors / baselines**
- The paper's own prior tools: **PHIVE / Exomiser** (ref. 26) — human-to-model-organism phenotype comparison for novel-gene discovery; explicitly contrasted with PhenIX (PhenIX restricts to known disease genes and human-only phenotype data). Directly comparable in this repository's context — an `Exomiser-Smedley-al-2015` analysis already exists alongside this one.
- **eXtasy** (ref. 25) — another phenotype-informed variant prioritization tool cited as addressing the novel-gene-discovery problem PhenIX deliberately does not.
- Yang et al. 2013 (ref. 8), *NEJM* — clinical WES on 250 unselected cases, 25% diagnostic yield — the paper's main external yield comparator.
- Another cited exome study on intellectual disability (ref. 46) — 16% diagnostic yield — second yield comparator.

**Data & tools**
- HGMD (Human Gene Mutation Database) — source of simulated disease-causing mutations.
- dbSNP, NHLBI GO Exome Sequencing Project (EVS) — population allele frequency filtering.
- dbNSFP 2.4 (aggregating PolyPhen-2, SIFT, MutationTaster) — variant pathogenicity prediction.
- GATK 2.8, Novoalign, Jannovar — the sequencing/variant-calling/annotation stack.
- ClinVar — cross-referenced for known pathogenic variants at the same position.

**Read next, in order:** (1) the HPO project papers (ref. 3/27) if HPO terms themselves are unfamiliar, (2) PHIVE/Exomiser (ref. 26) to see the sibling tool this repository already has analyzed, (3) Yang et al. 2013 for the WES-yield comparison this paper leans on.

## Impact & follow-ups
OpenAlex and Crossref both confirm **271–229 citing works** as of this analysis (checked 2026-09-10; the two sources disagree slightly, which is normal — OpenAlex and Crossref index different citing-source sets). Year-by-year counts show sustained, not declining, citation (29–43/year through 2016–2020, still 22 in 2024), consistent with this being a foundational phenotype-driven-diagnosis paper rather than a one-off result. Semantic Scholar's API was rate-limited (HTTP 429) during this analysis, so the "most influential citing papers" flag and reference/citation graph from that source are **unverified** — only OpenAlex/Crossref counts are confirmed. The paper predates, and is a direct precursor to, the authors' own later Exomiser work (already catalogued in this repository as `Exomiser-Smedley-al-2015`); a natural follow-up check is whether that paper's introduction explicitly cites this one as motivation (not verified here — would require opening that paper's reference list).

## Code & data
**Availability.** No GitHub/GitLab/Zenodo link appears anywhere in the PDF (`scan_paper.py` found zero `code_links`); the only pointer is the PhenIX web server URL `http://compbio.charite.de/PhenIX/`, described as "freely available for academic use." This is a hosted tool, not source code — its current online status was **not checked** in this analysis (no network fetch performed), so treat availability as unverified. Data: none released — patient VCFs and HPO term lists are clinical data under IRB consent (Charité IRB) and were never intended for public release; HGMD (used for simulation) is a licensed commercial database, not open data.

**Completeness (ML Code Completeness checklist, adapted).**
| Item | Status | Evidence |
|---|---|---|
| Dependencies/environment | Partial | Tool versions named (GATK 2.8, Jannovar, Novoalign, dbNSFP 2.4) but no environment file/container |
| Training/fitting script | N/A | Not a trained model; scoring formulas are closed-form, given in Methods |
| Evaluation script | No | Simulation procedure described in prose, not released as code |
| Pretrained models/weights | N/A | No ML model; rule-based/formula-based scoring |
| Results reproduction artifact | No | No released simulation outputs, VCFs, or scripts to rerun Fig. 1 |

**Paper-to-code consistency.** Cannot be assessed — no code was located to compare against the Methods description.

**Dry run.** Skipped: no repository or installable package exists to attempt a dry run against; the only executable artifact is a web server whose reachability and current behavior were not tested in this analysis.

## Concept-to-code map
Not applicable in the usual sense (no repository), but the Methods section is precise enough to map concept → formula directly:
| Concept in the paper | Where it's defined | Reading note |
|---|---|---|
| Frequency score | Methods, "PhenIX: Bioinformatic ranking" | `max(0, 1 − 0.13533·e^(100·f))`; f = max minor allele frequency across dbSNP/EVS African-American/European-American; unseen variants get 1.0 |
| Pathogenicity score | Methods | Max of normalized PolyPhen-2/SIFT/MutationTaster (dbNSFP 2.4), 0 (benign)–1 (pathogenic) |
| Variant score | Methods | Frequency score × pathogenicity score, most-pathogenic variant per gene kept |
| Gene relevance (phenotype) score | Methods, references Phenomizer (ref. 28) | Semantic similarity between patient HPO terms and merged HPO annotations of all diseases linked to the gene; halved if variant zygosity pattern conflicts with the gene's mode of inheritance |
| Final rank score | Methods | Mean of variant score and gene relevance score; ties broken alphabetically after sorting |

## Adaptation plan
Written against this repository's own project (`mva-hackathon`): ranking compound-heterozygous candidate gene pairs for one Mosaic Variegated Aneuploidy (MVA) patient, cross-referencing genomic variant calls against the patient's 8 HPO terms.

1. **Keep as-is:** the core idea of averaging a variant-badness score with an HPO-based phenotype-similarity score against a curated gene→disease→phenotype table is directly reusable conceptually — it is exactly the "genomic result states what the clinical terms say about it" cross-referencing this project's `CLAUDE.md` already mandates.
2. **Swap:** (a) this paper's flat per-gene ranking assumes single-gene Mendelian disease; MVA is compound-heterozygous (two variants, same gene, different parental origin), so the ranking function needs a pair-aware scoring step, not a single-variant one; (b) replace dbNSFP 2.4/PolyPhen-2/SIFT/MutationTaster with whatever pathogenicity annotation this project's warehouse already uses (check `docs/toolset.md` for the current annotation source rather than re-deriving); (c) the semantic-similarity computation (Phenomizer-style) would need either a reimplementation or an existing HPO-similarity library (e.g. `pyhpo`, `hpo3`), since PhenIX's own scorer is not distributed.
3. **What breaks first:** the mode-of-inheritance penalty term assumes a clean AD/AR/X split per gene; MVA's mosaic aneuploidy mechanism (whole-chromosome loss/gain events, not just SNVs) does not map cleanly onto "one vs. two heterozygous hits," so this penalty term would need rethinking rather than direct reuse — a naive port would silently down-rank the correct MVA mechanism.
4. **Compute/time estimate:** the phenotype-similarity computation over 2,741–8,000+ genes is cheap (the original ran on standard hardware in 2014); the minimum viable experiment is a small script that scores the project's existing candidate gene list against the proband's 8 HPO terms using an off-the-shelf HPO semantic-similarity library, compared against variant-score-only ranking — directly testing this paper's central claim (C2 vs. C3) on this project's own data before investing in a full pair-aware reimplementation.
5. **Risks:** HGMD (used here for simulation) is commercially licensed — do not assume free access; HPO/OMIM/Orphanet annotation completeness for MVA-associated genes specifically should be checked before trusting phenotype-similarity scores for this rare mechanism, since the paper itself notes performance depends on annotation depth for the disease in question.

## Glossary
- **Compound heterozygote** — two different broken copies of the same gene, one inherited from each parent; not this paper's model organism (it assumes single-variant or simple recessive homozygous/compound cases per Table 1's AR entries) but directly relevant to this project's target case.
- **DAG (disease-associated genome)** — this paper's term for the 2,741 genes already known to cause a Mendelian disease; the targeted sequencing panel is built to cover exactly this set.
- **dbNSFP** — a precomputed database bundling several variant-pathogenicity predictors (PolyPhen-2, SIFT, MutationTaster) so a pipeline can look up a score instead of running each predictor itself.
- **HGMD (Human Gene Mutation Database)** — a curated, commercially licensed catalog of published disease-causing mutations; used here purely to generate realistic simulated "true positive" mutations.
- **HPO (Human Phenotype Ontology)** — a structured, tree-shaped vocabulary of >10,000 standardized terms for human phenotypic abnormalities (e.g. "microcephaly"), each linked to diseases known to cause it; used both to describe patients and to describe genes' associated diseases.
- **Mode of inheritance (AD/AR/X)** — the pattern by which a disease variant is passed on: autosomal dominant (one broken copy is enough), autosomal recessive (both copies must be broken), X-linked; used here to penalize genes whose observed variant zygosity doesn't fit their known pattern.
- **Phenomizer** — the authors' earlier semantic-similarity algorithm for comparing HPO term sets, adapted here as PhenIX's phenotype-matching engine.
- **PhenIX (Phenotypic Interpretation of eXomes)** — this paper's ranking tool/web server; combines variant and phenotype scores into a single candidate-gene rank.
- **Semantic similarity (ontology-based)** — a numeric measure of how closely two sets of terms match given the tree structure of the ontology (a general term like "abnormal skull shape" partially matches a specific one like "microcephaly"), rather than requiring exact term overlap.
- **VCF (variant call format)** — a standard row-oriented file format listing genomic positions where a sample differs from the reference genome; the required input format for PhenIX.
- **Zygosity** — whether a variant is present on one copy of a gene (heterozygous) or both (homozygous); combined with mode of inheritance to judge whether a candidate gene's variant pattern is biologically plausible.

## Open questions & extension ideas
Authors' stated future work: extending capture to non-coding/regulatory disease-associated sequence (their sonic hedgehog enhancer example); deeper HPO annotation of diseases to improve ranking; better handling of synonymous/cryptic-splice variants; adapting the workflow to trio sequencing.

Analyst's extensions:
1. **Pair-aware scoring for compound heterozygotes** — extend the variant-score aggregation step (currently "take the single most pathogenic variant per gene") to explicitly model two-hit combinations and their combined pathogenicity, directly relevant to this project's MVA case.
2. **Ablation on HPO-term count/specificity using this project's own 8 terms** — replicate Fig. 1's "≤5 terms" / "noise term" regimes using the proband's actual 8 HPO terms to estimate how much ranking confidence to expect given a fixed, small real term set (rather than assuming best-case "all terms" performance).
3. **Bootstrap/permutation test on the 86.5% top-rank figure** — the paper reports no variance; recomputing with resampling would show how sensitive this headline number is to the specific 8,504 simulated cases drawn.
4. **Check whether MVA's aneuploidy mechanism is HPO-annotatable at all** — before relying on phenotype-similarity scoring for this project's specific case, verify how many of the candidate genes/diseases in the mechanism have adequate HPO annotation depth (paper's own limitation: thin annotation hurts ranking).
5. Questions for the authors: (a) how was the 1% frequency filter threshold chosen, and how sensitive is the retrospective mean rank (2.1) to that choice? (b) for the 29 unsolved prospective cases, was a post-hoc check done for causal variants outside the 2,741-gene DAG panel (i.e., would WES/WGS have found them)?

## Confidence notes
- Full main text (through Discussion and Methods) was read directly from the extracted PDF text; reference list beyond entry 17 was not individually verified against citation databases.
- Semantic Scholar metadata fetch failed (HTTP 429, rate-limited) — citation count, "influential citing papers," and cross-checked reference list rely on OpenAlex/Crossref only; treat "most influential citing papers" claims anywhere in this report as absent/unverified, not merely thin.
- PhenIX web server current availability (`http://compbio.charite.de/PhenIX/`) was **not checked** — no network fetch was performed in this analysis; do not assume it is still live.
- Supplementary figures/tables (Fig. S1/S2, Tables S1–S6) were referenced from in-text descriptions and captions only; the rasterized page-007 excerpt was not individually re-examined pixel-by-pixel for this report, so any number attributed to them should be treated as text-derived, not figure-verified.
- The Adaptation plan section is written specifically for this repository's stated MVA/compound-heterozygote goal (per this project's `CLAUDE.md`) rather than a generic reader; a different project would need a different plan.
