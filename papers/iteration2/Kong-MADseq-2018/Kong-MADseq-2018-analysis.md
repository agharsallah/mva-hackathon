---
title: "Detecting, quantifying, and discriminating the mechanism of mosaic chromosomal aneuploidies using MAD-seq"
authors: ["Kong, Yu", "Berko, Esther R.", "Marcketta, Anthony", "Maqbool, Shahina B.", "Simões-Pires, Claudia A.", "Kronn, David F.", "Ye, Kenny Q.", "Suzuki, Masako", "Auton, Adam", "Greally, John M."]
year: 2018
venue: "Genome Research"
doi: "10.1101/gr.226282.117"
arxiv: null
url: "https://doi.org/10.1101/gr.226282.117"
paper_type: empirical
domains: [genomics, bioinformatics, mosaicism, Bayesian statistics, clinical genetics]
lens: bioinformatics
modes: [apply, review]
code: "https://github.com/ykong2/MADSEQ"
data: "dbGaP phs001557.v1.p1; SRA SRP105435; 1000 Genomes Project"
relevance: 5
analysed: 2026-09-10
analyst: paper-analyst
---

# Detecting, quantifying, and discriminating the mechanism of mosaic chromosomal aneuploidies using MAD-seq

## Identity & citation

Kong Y, Berko ER, Marcketta A, Maqbool SB, Simões-Pires CA, Kronn DF, Ye KQ, Suzuki M, Auton A, Greally JM. *Genome Research* 2018;28(7):1039–1052. DOI: 10.1101/gr.226282.117. Open-access PDF: http://genome.cshlp.org/content/28/7/1039.full.pdf. *Genome Research* is a peer-reviewed genomics journal (Cold Spring Harbor Laboratory Press); no impact-factor figure is quoted here because none was looked up.

```
APA 7: Kong, Y., Berko, E. R., Marcketta, A., Maqbool, S. B., Simões-Pires, C. A., Kronn, D. F.,
Ye, K. Q., Suzuki, M., Auton, A., & Greally, J. M. (2018). Detecting, quantifying, and
discriminating the mechanism of mosaic chromosomal aneuploidies using MAD-seq. Genome
Research, 28(7), 1039–1052. https://doi.org/10.1101/gr.226282.117

BibTeX:
@article{kong2018detecting,
  title = {Detecting, quantifying, and discriminating the mechanism of mosaic chromosomal
    aneuploidies using {MAD}-seq},
  author = {Kong, Yu and Berko, Esther R. and Marcketta, Anthony and Maqbool, Shahina B. and
    Simões-Pires, Claudia A. and Kronn, David F. and Ye, Kenny Q. and Suzuki, Masako and
    Auton, Adam and Greally, John M.},
  journal = {Genome Research}, volume = {28}, number = {7}, pages = {1039--1052}, year = {2018},
  doi = {10.1101/gr.226282.117}
}

Vancouver: Kong Y, Berko ER, Marcketta A, Maqbool SB, Simões-Pires CA, Kronn DF, et al.
Detecting, quantifying, and discriminating the mechanism of mosaic chromosomal aneuploidies
using MAD-seq. Genome Res. 2018;28(7):1039-1052. doi:10.1101/gr.226282.117
```

## Paper type & how to read it

This is an **empirical / methods** paper (a new assay plus a new statistical model, validated on simulations and real samples). What it owes the reader: a clear statistical model, a fair sensitivity/specificity evaluation (ideally against ground truth, not just simulation), and evidence the tool works on real data it wasn't tuned on. The analysis below weighs the simulation results (strong, well-designed) separately from the real-sample validation (real but small-n, and largely re-confirming samples already known to be abnormal).

## One-minute pitch

Some people are genetic mosaics: a subset of their cells carries an extra or missing chromosome copy, but standard clinical tests miss this because they only look at blood, and blood is often the wrong tissue. The authors built two things: a lab assay (MAD-seq) that sequences ~80,000–107,000 common SNPs spread evenly across the genome, and a statistical model (MADSEQ) that reads the resulting allele-balance and coverage patterns and decides — for each chromosome — whether it's normal, monosomic, trisomic, or has lost heterozygosity, whether an event happened during egg/sperm formation (meiosis) or afterward (mitosis), and what fraction of cells carry it. They show it works on serial DNA dilutions, on simulated data, and on real samples — including 1000 Genomes cell lines, a hemihyperplasia patient, and one Illumina Platinum Genomes sample — finding previously-unrecognized mosaicism in some of them. The software is released as open source.

**TL;DR:** MADSEQ turns ordinary allele-frequency-plus-depth signals from targeted or whole-genome sequencing into a mosaic-aneuploidy call, a cell-fraction estimate, and a meiotic-vs-mitotic mechanism call. It is validated mainly by simulation and by re-detecting known abnormalities, with a handful of genuinely new findings. The software has since been removed from Bioconductor (see Code & data), which matters for anyone planning to depend on it today.

## Domains & keywords

Genomics > cytogenomics/mosaicism > hierarchical Bayesian mixture modeling > variant-based CNV/aneuploidy detection. Keywords: mosaic chromosomal aneuploidy, copy-number-neutral loss of heterozygosity (cnnLOH), alternate allele frequency (AAF), targeted capture sequencing, Bayesian information criterion (BIC) model selection, MCMC/JAGS, 1000 Genomes Project, confined placental mosaicism.

## Problem & research questions

Gap: existing mosaic-aneuploidy assays (karyotyping, FISH, arrays, single-cell sequencing) each fail on some combination of sensitivity, cost, need for cell culture, or ability to name the mechanism (meiotic vs mitotic) — and none ships with open, general-purpose analysis software. Implicit research questions: (1) can allele-balance + depth from a cheap SNP-capture assay detect mosaicism below 10% with a hierarchical Bayesian model; (2) can the model additionally infer *how* the aneuploidy arose; (3) does this reveal previously-missed mosaicism in existing public sequencing data. Authors' framing (paraphrased, Introduction): *we currently lack an assay that combines cost-effectiveness, sensitivity to low mosaic fractions, no cell-culture requirement, mechanism inference, cross-ancestry robustness, and supporting software.*

## Method

**In plain language.** At every genome position where a person is expected to have one copy of each parent's DNA letter (a heterozygous site), a normal diploid cell shows reads split roughly 50/50 between the two versions. If a subset of a person's cells has gained or lost a whole chromosome, that 50/50 split shifts — and the *total* number of reads covering that chromosome also shifts up (extra copy) or down (missing copy). MADSEQ fits five competing explanations per chromosome — normal, monosomy, mitotic trisomy, meiotic trisomy, or copy-number-neutral loss of heterozygosity (LOH) — each predicting a specific shape for that read-split-plus-depth pattern, then picks the best-fitting explanation using a standard model-selection score (BIC). Meiotic trisomy gets a distinctive extra signature (a recombined stretch of chromosome with 3 haplotypes instead of 2) that lets the model tell it apart from a mitotic (post-fertilization) trisomy that looks identical in depth and allele balance.

**Technically.** Two components (Fig. 1): (1) preprocessing — BWA-MEM alignment, Picard duplicate marking, GATK/HaplotypeCaller genotyping, LOESS GC-content correction of per-region coverage; (2) five hierarchical Bayesian models, each a beta-binomial mixture over per-site alternate allelic depth (parameterized by mean AAF μ and precision κ ~ Gamma(0.1,0.1)) combined multiplicatively with a per-region negative-binomial coverage likelihood (size parameter r fixed from the empirical coverage/variance ratio), plus a fixed 1% outlier (uniform beta-binomial) component in every model. The LOH model additionally uses a reversible-jump-style pair of change-points (uniform priors over site index, ≥10% chromosome span) to bound the affected region. Posterior sampling: JAGS via `rjags`, 2 chains, 10,000 burn-in, 10,000 sampling steps thinned by 2, Gelman–Rubin convergence check via `coda`. Model choice: lowest BIC; a call is flagged low-confidence if ΔBIC < 10 versus the runner-up. Validation: (a) a controlled two-cell-line DNA mixing series (0.5–50% mixing) sequenced via a custom SeqCap capture (v1MAD-seq, 79,605 SNP loci); (b) computational simulations sweeping depth, heterozygous-site count, and mosaic fraction (500 simulated replicates per scenario); (c) re-analysis of 1000 Genomes exome BAMs (n=2,535); (d) a second-generation capture design (meMAD-seq, 106,402 loci) engineered for even representation across ancestries and chromosome sizes, tested on 12 samples. Genome build: hg19/GRCh37 throughout (stated).

## Figures & tables check

| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 1 | 6 | Schematic: preprocessing pipeline + the 5 Bayesian models' expected AAF/depth shapes + BIC selection | Method overview | OK | Diagram only, no data; correctly matches the Methods section equations |
| Fig. 2 | 8 | Simulated AAF and depth patterns across 0–100% mosaic fraction for each aneuploidy type | C1, C7 | Caution | Purely simulated (no real-data overlay), so it demonstrates the model's *design intent*, not measured performance; no axis units/error bars needed since it's illustrative, but a reader could mistake it for observed data at a glance |
| Fig. 3 | 13 | Same DNA (NA12889/NA12889-labelled sample), exome (152x) vs WGS (50x): both call segmental cnnLOH on chr11, 58.7% vs 53.5% of cells | C1, C4 | OK | Genuine cross-platform concordance on one real sample — the strongest single piece of real-data evidence in the paper, but n=1 |
| Fig. 4 | 14 | Hemihyperplasia patient, normal vs affected skin: exome (6.8%) vs meMAD-seq (5.4%) both call mitotic trisomy 12 on the affected side only | C1, C5 | OK | Good cross-assay concordance and correct laterality (normal side negative); mechanism-to-phenotype causal claim in Discussion goes beyond what this figure shows |
| Table 1 | 16 | 14 samples/individuals × 3 assay types (exome, v1MAD-seq, meMAD-seq) vs prior Coriell/literature characterization | C1, C4 | Caution | Recomputation: of 14 rows, 9 already had a known/expected aneuploidy from Coriell or a prior assay before MADSEQ was run — only HG01939, GM06990, GM19239 (negative-turned-different), the ES cell line, and the hemihyperplasia "unaffected side" are genuinely blind calls; this is a small blind-validation set, not stated as a limitation by the authors |
| Fig. 5 | 20 | Violin plots of heterozygous-site counts per chromosome for v1MAD-seq, exome-seq, and meMAD-seq, by sex and (panel B) by 1000 Genomes super-population | C2 | OK | Clear, well-designed comparison; meMAD-seq visibly flattens the per-chromosome and per-ancestry disparities exome-seq shows |

## Claims vs evidence

| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | MADSEQ detects mosaic aneuploidy <10% and classifies its type from AAF+depth | Simulation sweep (Fig. 2, Supp Fig S3/S4): >99% sensitivity at <2% FDR for 5% meiotic trisomy with 2,000 het sites @100x | Results, "Evaluation of MADSEQ performance" | strong (simulation) / moderate (real data) | Real-sample confirmations are mostly of *already-known* abnormalities (Table 1), not blind low-level (<10%) detections with independent ground truth |
| C2 | meMAD-seq capture gives uniform ≥2,000 het sites per chromosome across ancestries, unlike exome-seq or v1MAD-seq | Fig. 5, Supp Fig S10 (PCA showing ancestry diversity of the 12 test samples) | Results | strong | Directly measured on real capture data; the ancestry claim rests on only 12 own samples plus a PCA overlay against 1000G references, not 12 samples per super-population |
| C3 | False discovery rate <2% under simulated 10% noise injection | Supp Fig S5 (not rendered in this analysis — main-text page image unavailable, described only in text) | Results | weak-moderate | Simulation-only; noise model (uniform-random AAF at 10% of sites) is one specific noise model, not real sequencing artifacts (mapping bias, batch effects) |
| C4 | 1000 Genomes re-analysis reveals previously-unrecognized mosaic aneuploidy, concentrated in LCL (not blood) samples | 83 high-confidence (ΔBIC>10) events in 76/2,535 individuals; p=3.08×10⁻³⁴ blood-vs-LCL binomial test; trisomy-12 enrichment p=1.49×10⁻⁴ | Results, "Application of MADSEQ to sequencing data" | strong (statistical pattern) / unsupported (that specific calls are real biology, not culture artifact or model false-positives) | No orthogonal confirmation (karyotype, FISH, or independent tool) of any of the 76 individuals' calls; the paper's own interpretation is that these are cell-culture artifacts, which is plausible but also unverified |
| C5 | Hemihyperplasia phenotype plausibly caused by mosaic trisomy 12 of mitotic origin | Concordant calls across 2 assay types + laterality match + literature on trisomy-12 and proliferation | Results, Discussion | moderate (detection) / weak (causal mechanism for phenotype) | Detection is well-supported; "may therefore be the consequence of" is explicitly speculative language from the authors themselves |
| C6 | meMAD-seq capture costs ~40% of comparable exome sequencing | One institutional reagent-cost estimate | Discussion ("For a cost comparison...") | weak | Single-site, single-vendor estimate; no breakdown given, no sensitivity to reagent-price changes over 8 years |
| C7 | Meiotic vs mitotic trisomy origin can be distinguished from a real sample, not just simulation | 4 v1MAD-seq samples with known trisomies, "defined their origins as meiotic in all cases" | Results, "Development of a multi-ethnic MAD-seq" | moderate | n=4, and the paper doesn't state whether independent (e.g., parental genotype-based) confirmation of meiotic origin existed for comparison |

## What works

- The core statistical idea — pairing an AAF mixture model with a depth model and comparing five explicit competing hypotheses by BIC — is well-specified and directly reproducible from the equations given (confirmed against the actual R/JAGS source: `runNormal`/`runMonosomy`/`runMitoticTrisomy`/`runMeioticTrisomy`/`runLOH` in `RunModelHelper.R`, one `.txt` JAGS model file per state in `inst/rjags/`, and `dbetabinom.ab`/`dnbinom` log-likelihoods matching the paper's equations exactly).
- Cross-platform concordance on real DNA: the same physiological event (chr11 segmental cnnLOH; chr12 mitotic trisomy) is independently called from two different sequencing modalities (exome vs WGS; exome vs meMAD-seq) with cell-fraction estimates within ~5 percentage points of each other (58.7% vs 53.5%; 6.8% vs 5.4%). That is real, if small-n, internal replication.
- The meMAD-seq capture redesign measurably fixes a real problem (uneven per-chromosome and per-ancestry representation of exome-seq and the first-generation capture), which matters directly for any downstream user wanting even power across chromosome 13/18/21 (viable trisomies) or across ancestries.
- The model correctly separates a class of "false positive risk" (population-level aneuploidy prevalence rates: 0.79% monosomy, 0.99% mitotic trisomy, 1.46% LOH among LCLs, 0% in blood) that is internally consistent with prior literature that culture-derived clonal expansion, not donor biology, explains most LCL mosaicism.

## What doesn't work (or isn't shown)

- No blinded prospective validation: every real-sample "detection" either confirms a previously-known abnormality (Coriell characterization, prior study) or is an internal cross-platform re-detection of the same event — there is no case in the paper where MADSEQ made a novel call that was then independently confirmed by an orthogonal method (karyotype, FISH, ddPCR).
- Cancer / complex-karyotype samples: authors state directly (Discussion) that the method degrades when multiple chromosomes are simultaneously abnormal, because the model's expected-diploid-coverage baseline breaks down. This is an important negative result, honestly reported.
- No CNV (sub-chromosomal, non-whole-arm) detection capability yet; explicitly named as future work.
- No comparison to a contemporaneous competing computational tool run on the same data (e.g., no head-to-head against another mosaicism caller); comparisons are narrative citations of assay classes (karyotyping, FISH, arrays), not method benchmarking.
- No confidence interval / uncertainty band shown around the ΔBIC threshold of 10 itself — it is used as a fixed cutoff without a sensitivity analysis of how that threshold trades sensitivity against FDR beyond the one simulation regime shown.

## Limitations

**Stated by the authors.**
- Doesn't yet work well for cancer or other highly-abnormal-karyotype samples (multiple simultaneously affected chromosomes break the diploid-baseline assumption).
- No CNV (partial-chromosome) detection yet; would need denser loci in smaller chromosomal regions.
- Detection resolution is capped by locus spacing in the capture design (coarser on smaller chromosomes).
- Reference/LCL cell lines themselves accrue culture-derived mosaicism, complicating their use as "normal" reference material.

**Not stated (analyst).**
- Software preservation risk: MADSEQ has since been **removed from Bioconductor** (last available version 3.21, removed after the Bioconductor 3.20 release; no reason stated by Bioconductor). The GitHub source (`ykong2/MADSEQ`) has had no push in over two years and carries no LICENSE file, so redistribution/reuse rights are unclear beyond the DESCRIPTION's `GPL(>=2)` claim.
- No independent reproduction found in the citation graph (Semantic Scholar 3, OpenAlex 5, Crossref 4 citing works, 0 flagged "influential" 8 years after publication) — for a method paper this is a real adoption/impact ceiling worth naming plainly rather than assuming impact.
- The fixed 1% outlier weight and the negative-binomial dispersion parameter (fit from the observed coverage/variance ratio) are treated as constants across all chromosomes and samples; no sensitivity analysis of how mis-specifying these constants (e.g., in a very different sequencing platform or much lower coverage) would shift calls.
- Ancestry-robustness claim (Fig. 5) is validated on only 12 samples total across 5 super-populations — that's a handful of samples per population group, not a systematically powered cross-ancestry study.
- No multiple-testing correction is described for the per-chromosome ΔBIC screen across 2,535 individuals × ~22 chromosomes × 5 models, beyond the fixed ΔBIC>10 threshold — the binomial enrichment tests (trisomy-12, chr22 LOH) are post-hoc on the flagged set, which inflates apparent significance for the specific enrichments highlighted.

## Validity, bias & reproducibility

*Internal validity*: the simulation experiments are well-designed (parametric sweep over depth × heterozygous-site count × mosaic fraction × noise level, 500 replicates/scenario), and directly support the sensitivity/FDR/RMSE numbers quoted. The cross-platform real-sample concordance (Fig. 3, Fig. 4) is a genuine, if small, form of internal replication that most papers in this space skip. *External validity*: real-world validation is dominated by re-detecting already-known aneuploidies; the one prospective population screen (1000 Genomes) has no independent confirmation of its specific calls, only a plausible narrative (culture artifact) for the aggregate pattern. Generalization across sequencing platforms is shown (capture, exome, WGS) but all on Illumina short reads with GRCh37; no long-read or newer-build (GRCh38/T2T) validation, unsurprising for 2018. *Reporting*: MCMC settings, priors, and coverage-correction formulas are given exactly and match the released code; reference genome build and tool versions (BWA 0.7.10, GATK 3.4-46, Picard 1.119, R 3.2) are stated. *Conflicts of interest*: none declared; funded by a single departmental program grant.

**Reproducibility score: 3** — code is released (GitHub + the archived Bioconductor 3.21 landing page), with a vignette, reference manual, and example script, and the exact statistical model is verifiable line-for-line against the paper's equations. It falls short of a 4 because the package has since been **removed from Bioconductor**, the GitHub repo has no CI, no tests, no license file, and no independent third party has publicly reproduced its results — so a new user today faces real risk that `install_github("ykong2/MADSEQ")` fails against current R/Bioconductor/rjags/JAGS versions untested for ~8 years. Biggest obstacle: dependency and package-registry rot, not missing methodology detail.

## Related work & key citations

- **Foundations** — van Echten-Arends et al. 2011 and Rabinowitz et al. 2012 (embryo aneuploidy rates); Lestou & Kalousek 1998 (confined placental mosaicism terminology); Biesecker & Spinner 2013 (mosaicism review) — establish why mosaic aneuploidy detection matters clinically.
- **Competitors / prior assay classes** — Conlin et al. 2010 (SNP-array mosaicism detection); Knouse et al. 2014 (single-cell sequencing); Dong et al. 2016 (low-pass WGS for clinical cytogenetics); Faggioli et al. 2014 (FISH). The paper positions MAD-seq/MADSEQ against these classes narratively, not head-to-head on shared data.
- **Data & tools** — 1000 Genomes Project Consortium 2015 (the re-analyzed exome cohort); Eberle et al. 2017 (Illumina Platinum Genomes, the WGS validation sample); Li & Durbin 2009 / Li 2013 (BWA/BWA-MEM); McKenna et al. 2010 (GATK); Danecek et al. 2011 (VCFtools); Price et al. 2006 (EIGENSTRAT, ancestry PCA); Castel et al. 2015 (reference bias in allelic-expression analysis — cited but not corrected for).
- Read next, in order: (1) Biesecker & Spinner 2013 for the mosaicism/trisomy-rescue conceptual background, (2) Eberle et al. 2017 for what "platinum" WGS variant calls mean and their caveats, (3) Castel et al. 2015 if reference-mapping bias in AAF is a concern for a downstream use.

## Impact & follow-ups

Citation counts as of 2026-09-10: Semantic Scholar 3, OpenAlex 5, Crossref 4; 0 flagged as influential by Semantic Scholar. For a method+software paper 8 years old, this is low uptake — worth stating plainly rather than assuming impact grows with time. No erratum, retraction, or known independent reproduction attempt was found in this search. The clearest concrete "follow-up" signal is negative: Bioconductor's removal of the package (post-3.20 release) rather than a citing paper extending it.

## Code & data

**Availability.** Official implementation: `MADSEQ` R/Bioconductor package. Canonical source: https://github.com/ykong2/MADSEQ (confirmed as the maintainer-linked repo via the archived Bioconductor 3.21 package page, not discoverable from the paper's own text, which only names `bioconductor.org/packages/MADSEQ/`). License: `GPL(>=2)` per `DESCRIPTION`, but no `LICENSE` file in the repo. No push in >2 years; **removed from Bioconductor** after the 3.20 release (last available version 3.21); no stated removal reason. Data: raw sequencing under dbGaP `phs001557.v1.p1` (controlled access) and SRA `SRP105435` (accession range SRS2153291–SRS2153299); 1000 Genomes exome BAMs from the public FTP (open access).

**Completeness** (five-item checklist, from `inspect_repo.py` + manual read):

| Item | Status | Evidence |
|---|---|---|
| Dependencies | partial | `DESCRIPTION` lists all R/Bioc/CRAN deps (`rjags≥4.6`, `VGAM`, `coda`, `vcfR`, `GenomicAlignments`, etc.) but no lockfile/renv, no container |
| Install/run script | partial | README gives three install paths (Bioconductor `biocLite`, `devtools::install_github`, tarball) but no worked end-to-end example script beyond the vignette |
| Evaluation script | no | No script reproduces the paper's own Fig. 2/3/4/5 numbers from raw data |
| Pretrained "models" | partial | Ships reference `.RDS` GRanges objects for gap/HLA/AQP7 masking regions per genome build (hg19/hg38/hs37d5) — not model weights, but required auxiliary data |
| Results table | no | No results table in the README |

**Paper-to-code consistency.** Confirmed directly (not inferred): the five model-fitting functions in `R/RunModelHelper.R` (`runNormal`, `runMonosomy`, `runMitoticTrisomy`, `runMeioticTrisomy`, `runLOH`) each call `rjags::jags.model()` against one dedicated JAGS model file in `inst/rjags/` (`OneMix.txt`, `TwoMixMonosomy.txt`, `TwoMixTrisomy.txt`, `FourMix.txt`, `LOH.txt`), and the log-likelihood helpers (`log_likelihood_one/two/four/UPD`) use `dbetabinom.ab()` (beta-binomial) and `dnbinom()` (negative binomial) mixtures whose component weights (e.g., the fixed 1% outlier, the 0.495/0.495 monosomy split) match the paper's Methods equations exactly. `calculate_BIC()` exists as its own function, consistent with the stated model-selection procedure.

**Dry run.** Not attempted: this analysis was done in a sandboxed environment with no R, Rscript, or JAGS installed, and the package's removal from Bioconductor plus 2+ years of dependency drift make an install attempt non-trivial to time-box responsibly. Anyone adopting this for the current project should budget explicit time for an install/dry-run spike rather than assuming `install_github` succeeds against current R/Bioconductor.

## Concept-to-code map

| Concept in the paper | Where it lives in the code | Reading note |
|---|---|---|
| Model0–Model4 (diploid, monosomy, mitotic trisomy, meiotic trisomy, LOH) | `R/RunModelHelper.R::runNormal/runMonosomy/runMitoticTrisomy/runMeioticTrisomy/runLOH`, JAGS specs in `inst/rjags/*.txt` | One function + one `.txt` JAGS model per state, directly mirroring the paper's five-way BIC comparison |
| Beta-binomial AAF mixture, outlier component | `log_likelihood_one/two/four/UPD` using `dbetabinom.ab()` | The fixed `p_o = 0.01` outlier weight in the paper appears as a literal `0.01` in the R code |
| Negative-binomial depth model, GC/LOESS correction | `R/PreProcessingHelper.R` (coverage correction), `dnbinom()` calls in `RunModelHelper.R` | GC-correction formula (Methods, `D_corrected = D_raw / D_gc * D_expected`) should be checked against the LOESS-fit function here before reuse |
| BIC model selection, ΔBIC<10 low-confidence flag | `calculate_BIC()` in `R/RunModelHelper.R` | Confirm the ΔBIC threshold is a parameter, not hard-coded, before reusing on a different case |
| Reference masking regions (gaps, HLA, AQP7) per genome build | `inst/gap/`, `inst/HLA/`, `inst/AQP7/` `.RDS` GRanges files (hg19/hg38/hs37d5) | Needed if adapting to GRCh38 — the package already ships hg38 masks, which lowers the porting cost for a build already used in a GRCh38-based pipeline |

## Adaptation plan

Written against this project's own goal: the MVA hackathon plan cites this paper for step 8, an aneuploidy-burden bound (mosaic-fraction estimate + meiotic/mitotic mechanism call) on the proband's WGS data, not for re-running the full MADSEQ package verbatim.

1. **Keep as-is**: the statistical *logic* — beta-binomial AAF mixture × negative-binomial depth mixture, compared by BIC across a small enumerated hypothesis set (diploid / monosomy / mitotic trisomy / meiotic trisomy / segmental LOH) — is a clean, reusable design regardless of whether the original R package is run. The GC/LOESS coverage-correction step is also directly reusable as a preprocessing pattern.
2. **Swap**: don't attempt to install/run the archived `MADSEQ` R package as a black box, given its Bioconductor removal and stale dependencies; either (a) reimplement the five-model BIC comparison directly against the case's own WGS heterozygous-site AAF+depth table using the project's existing Python/statistical stack (matching the paper's exact priors and formulas, which are fully specified), or (b) attempt the original package only inside an isolated, time-boxed environment (e.g., a disposable container) purely to sanity-check a reimplementation, never as a production dependency.
3. **What will break first**: JAGS/rjags install (system-level MCMC dependency, not a pure-R package) is the most likely first failure point in any fresh environment; the package's own masking `.RDS` files are keyed to hg19/hg38/hs37d5 — confirm the case's reference build matches before reusing them.
4. **Minimum viable experiment**: before committing to a full per-chromosome BIC scan, reimplement just Model0 (diploid null) and Model2 (mitotic trisomy) for one chromosome of the proband's data and confirm the BIC/ΔBIC arithmetic reproduces a synthetic positive control (e.g., a simulated 20% mosaic trisomy) before trusting it on real, unlabeled data. Budget: a small spike, not a multi-day build — the model is five short beta-binomial/negative-binomial likelihoods.
5. **Risks**: (a) licence — no `LICENSE` file in the GitHub repo means redistribution rights rest only on the `DESCRIPTION`'s stated `GPL(>=2)`, worth treating cautiously if code is vendored rather than reimplemented from the published equations; (b) the model assumes a *single* affected chromosome's coverage can be judged against a genome-wide diploid baseline — the paper's own stated limitation for complex-karyotype samples — so this bound is only trustworthy per-chromosome, not if MVA's defining feature (aneuploidy across *many* chromosomes at once) breaks that baseline assumption, which should be checked explicitly before treating step 8's output as reliable; (c) small real-sample validation n in the source paper means the quantification accuracy (RMSE) numbers are simulation-only guarantees, not guarantees for this specific case's coverage/heterozygosity profile.

## Positioning

This paper sits in the mosaicism-detection-from-bulk-sequencing literature, occupying a specific niche between low-resolution population-scale mosaicism screens (which flag clonal hematopoiesis-type events from array intensity or depth alone, e.g., Jacobs et al. 2012, Laurie et al. 2012) and single-cell sequencing approaches (Knouse et al. 2014) that give ground-truth per-cell genotypes at much higher cost and technical difficulty. Its contribution over both is a fully specified, open hierarchical Bayesian model that jointly uses allele balance and depth to name a *mechanism* (meiotic vs mitotic) in addition to detecting and quantifying the event — a capability most contemporaneous tools didn't offer. What it leaves open is orthogonal, blinded validation of novel calls, and a maintained, currently-installable software artifact.

**Citation-ready summary (72 words):** Kong et al. (2018) introduce MAD-seq, a SNP-capture assay, and MADSEQ, a hierarchical Bayesian model that jointly analyzes allele-balance and read-depth to detect mosaic chromosomal aneuploidy and copy-number-neutral loss of heterozygosity below 10% cell fraction, quantify the mosaic fraction, and infer meiotic versus mitotic origin. Validated by computational simulation and by re-detecting known abnormalities in cell lines, 1000 Genomes exomes, and a hemihyperplasia patient, with open-source software since removed from Bioconductor.

## Glossary

- **Alternate allele frequency (AAF)** — the fraction of sequencing reads at a genetic position that carry the non-reference DNA letter. *Role here*: the primary signal MADSEQ reads to detect mosaicism; a normal diploid site centers at 0.5, aneuploid sites shift away from it.
- **Aneuploidy** — having the wrong number of copies of a chromosome (e.g., 3 instead of 2). *Role here*: the core condition being detected.
- **Beta-binomial distribution** — a probability model for count data (like allele read counts) that allows more spread ("overdispersion") than a plain binomial. *Role here*: models AAF counts at each site under each hypothesis.
- **Bayesian information criterion (BIC)** — a score that ranks statistical models by fit while penalizing extra complexity. *Role here*: picks the winning aneuploidy-type model per chromosome; ΔBIC<10 flags low confidence.
- **Confined placental mosaicism (CPM)** — mosaic aneuploidy found in placental tissue but not in the fetus itself. *Role here*: motivates why prenatal diagnostic discordances happen and why a more sensitive assay matters clinically.
- **Copy-number-neutral loss of heterozygosity (cnnLOH)** — a chromosome region where both copies now come from one parent (identical), without any change in total copy number. *Role here*: one of the five states MADSEQ classifies; can result from "trisomy rescue" or DNA-repair using the other homolog as template.
- **Gelman–Rubin diagnostic** — a statistical check that multiple independent MCMC chains have converged to the same answer. *Role here*: used (via the `coda` R package) to validate the JAGS sampling.
- **Heterozygous site** — a genome position where a person's two chromosome copies carry different DNA letters. *Role here*: the only sites usable for AAF-based mosaicism detection, since homozygous sites carry no allele-balance signal.
- **Hierarchical Bayesian model** — a statistical model with parameters that themselves have their own probability distributions (priors on priors), fit via simulation-based inference. *Role here*: the overall MADSEQ modeling framework.
- **JAGS / rjags** — "Just Another Gibbs Sampler," MCMC software, and its R interface package. *Role here*: performs the actual posterior sampling for each of the five models.
- **LOESS correction** — a local, non-parametric curve-fitting method. *Role here*: used to remove GC-content bias from raw sequencing coverage before modeling.
- **Markov Chain Monte Carlo (MCMC)** — a family of algorithms for drawing samples from a complex probability distribution when it can't be solved directly. *Role here*: the inference engine behind every MADSEQ model fit.
- **Meiotic vs mitotic origin** — whether a chromosomal error happened during egg/sperm formation (meiosis, before fertilization) or afterward, during ordinary cell division (mitosis). *Role here*: the mechanism call MADSEQ makes using the recombination-breakpoint signature unique to meiotic trisomy.
- **Mosaic chromosomal aneuploidy** — a state where only a subset of a person's cells has an abnormal chromosome count, the rest being normal. *Role here*: the overall phenomenon under study.
- **Negative binomial distribution** — a probability model for overdispersed count data. *Role here*: models per-region sequencing read depth.
- **Non-disjunction** — failure of chromosomes to separate properly during cell division, the direct cause of most aneuploidy. *Role here*: the underlying mechanical event MADSEQ's mechanism call is trying to localize in developmental time.
- **Root-mean-square error (RMSE)** — a standard way to summarize how far predictions are, on average, from the true value. *Role here*: used to quantify how accurately MADSEQ estimates the mosaic cell fraction in simulation.
- **SeqCap (targeted capture)** — a technology (Roche-NimbleGen) for selectively sequencing only chosen genome regions. *Role here*: the underlying method behind both the v1MAD-seq and meMAD-seq assays.

## Open questions & extension ideas

Authors' own stated future work: extend to CNV (sub-chromosomal) detection, and improve handling of complex/cancer karyotypes with multiple simultaneously affected chromosomes.

Additional ideas worth considering for this project's own use:
1. **Blinded-validation spike**: before trusting a step-8 mosaic-fraction call on the proband's data, run the reimplemented model on a synthetic "held-out" chromosome with a known injected mosaic fraction, exactly mirroring the paper's own simulation protocol, to sanity-check the reimplementation independent of the archived package.
2. **Multi-chromosome baseline check**: since MVA is defined by aneuploidy across *multiple* chromosomes, explicitly test whether the paper's stated failure mode (diploid-baseline breakdown under multi-chromosome abnormality) applies to this case before quoting a MADSEQ-style mosaic fraction as reliable.
3. **Reference-bias check**: the paper cites Castel et al. 2015 on reference-mapping bias in allelic read counts but does not correct for it; worth checking whether this project's variant caller already applies such a correction (e.g., WASP-style filtering) before feeding AAFs into a reimplemented model.
4. **Threshold sensitivity**: run the ΔBIC>10 confidence threshold across a small grid (e.g., 5, 10, 15, 20) on this case's own coverage/heterozygosity profile rather than importing the paper's threshold unchanged, since that threshold was calibrated on the paper's own coverage regimes (100–200x targeted capture / WGS at 50x), which may not match this case exactly.
5. Questions for the authors, if reachable: (a) why was the Bioconductor package withdrawn, and is there a maintained fork; (b) was any independent/orthogonal confirmation (karyotype, ddPCR) ever attempted for any of the 76 flagged 1000 Genomes individuals; (c) how sensitive is the meiotic/mitotic discrimination to sequencing error near the recombination breakpoint in real (non-simulated) low-coverage data.

## Confidence notes

- Metadata (citation counts, venue, DOI) came from `fetch_metadata.py` (Semantic Scholar / OpenAlex / Crossref / arXiv), no fallback needed — high confidence.
- The GitHub repository (`ykong2/MADSEQ`) and its Bioconductor-removal status were **not** found via `inspect_repo.py` alone (the paper's own dbioconductor.org link is dead) — confirmed instead by fetching the live Bioconductor "removed packages" page and the archived 3.21 package page via `WebFetch`. This is a secondary-source confirmation, not a primary paper statement, and is flagged as such throughout.
- Paper-to-code consistency (the concept-to-code map and the "what works" claim about matching equations) was checked by direct inspection of a shallow git clone of the source — high confidence, not inferred.
- The dry run was **not attempted** (no R/JAGS in this environment) — the reproducibility score and adoption risk in "Code & data" and "Limitations" rest on static inspection only, not an actual install/run attempt. Anyone with an R+JAGS environment available should treat that as the natural next verification step before relying on this package.
- Six of the paper's eight main figures/tables (Figs. 1–5, Table 1) were visually inspected as rendered page images; the referenced supplementary figures (S1–S11) were not available in this PDF and are described only via the main text's citations of them — claims resting solely on supplementary figures (C3's FDR figure, in particular) are marked accordingly as less independently verified.
- No independent web search for post-2018 papers explicitly re-implementing or critiquing MADSEQ was run beyond the citation-count check; "no independent reproduction found" reflects the citation graph only, not an exhaustive literature search.
