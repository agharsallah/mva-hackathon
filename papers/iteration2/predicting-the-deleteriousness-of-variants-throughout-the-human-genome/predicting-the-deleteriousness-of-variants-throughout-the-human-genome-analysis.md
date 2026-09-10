---
title: "CADD: predicting the deleteriousness of variants throughout the human genome"
authors: [Rentzsch Philipp, Witten Daniela, Cooper Gregory M., Shendure Jay, Kircher Martin]
year: 2018
venue: "Nucleic Acids Research (Database issue)"
doi: "10.1093/nar/gky1016"
arxiv: null
url: "https://doi.org/10.1093/nar/gky1016"
paper_type: dataset-benchmark
domains: [computational biology, genomics, variant effect prediction, machine learning, variant prioritisation]
lens: bioinformatics
modes: [learn, apply]
code: "https://github.com/kircherlab/cadd-scripts"
data: "https://cadd.gs.washington.edu (pre-scored ~9B SNVs, GRCh37/GRCh38); training/eval sets: Ensembl EPO alignments, ClinVar, ExAC"
relevance: 5
analysed: 2026-09-09
analyst: paper-analyst
---

# CADD: predicting the deleteriousness of variants throughout the human genome

## Identity & citation

Philipp Rentzsch, Daniela Witten, Gregory M. Cooper, Jay Shendure, Martin Kircher. *Nucleic Acids Research*, 2019, Vol. 47, Database issue, D886–D894. Published online 29 October 2018. DOI: 10.1093/nar/gky1016. Open access (CC-BY 4.0); PDF at academic.oup.com/nar.

Nucleic Acids Research's annual "Database issue" is a peer-reviewed venue specifically for describing databases/resources (not novel experiments) — this is the update paper for a resource, not the original method paper. The original method (2014, *Nature Genetics*, Kircher et al., DOI 10.1038/ng.2892, ref. 5 here) is a separate, foundational citation.

```
APA 7:
Rentzsch, P., Witten, D., Cooper, G. M., Shendure, J., & Kircher, M. (2018). CADD: predicting the
deleteriousness of variants throughout the human genome. Nucleic Acids Research, 47(D1), D886–D894.
https://doi.org/10.1093/nar/gky1016

BibTeX:
@article{rentzsch2018cadd,
  title   = {{CADD}: predicting the deleteriousness of variants throughout the human genome},
  author  = {Rentzsch, Philipp and Witten, Daniela and Cooper, Gregory M and Shendure, Jay and
             Kircher, Martin},
  journal = {Nucleic Acids Res.}, volume = {47}, number = {D1}, pages = {D886--D894}, year = {2018},
  doi     = {10.1093/nar/gky1016}
}

Vancouver:
Rentzsch P, Witten D, Cooper GM, Shendure J, Kircher M. CADD: predicting the deleteriousness of
variants throughout the human genome. Nucleic Acids Res. 2018;47(D1):D886-D894.
doi:10.1093/nar/gky1016
```

## Paper type & how to read it

This is a **bioinformatics resource / database-issue update paper** (secondary type: dataset-benchmark). It does not introduce a new method — CADD itself was introduced in 2014 — it reports what changed since (GRCh38 support, a new web API, an open-source scoring pipeline) and re-validates that the updated model still works. Read it for: (1) what CADD actually is and how its labels are built (this matters a lot for how you may use its scores), (2) the one benchmark figure that says CADD still discriminates known-pathogenic from common variants, and (3) the practical "how do I get scores" logistics. Do not expect ablations, architecture novelty, or a fresh performance claim beyond "not significantly worse than before."

## One-minute pitch

Genome sequencing gives you millions of variants per genome and no way to know which ones matter. CADD is a single number, from 0 upward, that ranks every possible single-letter change (and short insertion/deletion) in the human genome by how likely it is to be damaging — like a spam score, but for DNA changes. It's trained not on a small curated list of "known pathogenic" mutations (which is biased and tiny), but on a clever proxy: it contrasts ~15 million variants that became fixed across all humans since we split from chimps (implying they survived natural selection, so are probably harmless) against a matched set of simulated random mutations (which include a healthy dose of harmful ones). A logistic-regression model learns to tell the two apart using 60+ biological annotations, and every one of the ~9 billion possible single-nucleotide changes in the genome gets pre-scored once, offline. This paper is the "what's new" report: CADD now also supports the newer human reference genome (GRCh38), and ships a proper API, web lookup and an installable offline pipeline. **TL;DR**: CADD scores are pre-computed everywhere; a higher score means "look at this variant first"; it is not, and should not be read as, a pathogenic/benign classifier with a fixed cutoff.

## Domains & keywords

Computational biology > variant effect prediction / genome annotation > machine learning (logistic regression, feature integration) > genomics resources > tasks: variant prioritisation for Mendelian disease, missense and non-coding variant scoring, evolutionary constraint.

## Problem & research questions

The gap: sequencing produces far more candidate variants than can be manually curated or experimentally tested, and existing scores were often trained on small, ascertainment-biased sets of curated pathogenic/benign variants. The paper's own framing: CADD "does not rely on manual/subjective variant curation in model training... [and] avoid[s] curated sets of pathogenic and benign variants during training" (Discussion). This is a resource paper, so there's no explicit hypothesis to test; its implicit question is "does the updated (GRCh38, v1.4) model still perform on par with the validated GRCh37 model, and can users actually get scores easily?"

## Background primer

- **What a variant is, in software terms.** A human genome is ~3.1 billion base-pair positions; a *variant* is one position where an individual's sequence differs from the reference (a SNV = single base substitution; an InDel = a short insertion/deletion). A VCF file is the standard record format: one row per variant, columns for chromosome, position, reference allele, alternative allele.
- **Why you can't just curate a pathogenic/benign training set.** Curated databases like ClinVar and HGMD are built from clinical case reports — they over-represent well-studied genes and easy-to-classify variant types (protein-truncating, missense in known disease genes) and under-represent regulatory/non-coding variants. A model trained only on these inherits that bias. CADD's trick is an "ascertainment-free" proxy: use evolutionary outcome (did the variant survive since the human-chimp split, i.e. did purifying selection tolerate it) as a stand-in label, at a scale (tens of millions of variants) curation could never reach. This "proxy-neutral vs proxy-deleterious" contrastive-simulation idea originates in the 2014 method paper (Kircher et al., *Nat. Genet.*).
- **PHRED-like scaling.** Named after the base-calling quality score Phred (Ewing & Green 1998) — the same idea of turning a probability into a `-10*log10(rank/total)` scale, so "CADD 20" means "top 1% most deleterious of all 9 billion possible SNVs," independent of the model internals.
- Prerequisite reading, in order: (1) Kircher et al. 2014 (*Nat. Genet.*, the original CADD method); (2) McLaren et al. 2016 (Ensembl VEP — the annotation engine CADD's features are built on); (3) Lek et al. 2016 (ExAC — the "common variant" comparison set used in the benchmark here); (4) Landrum et al. 2014 (ClinVar — the "pathogenic" comparison set); (5) this paper.

## Method

**In plain language.** Take two piles of DNA changes: one pile of changes that already happened and stuck around in humans (so evolution didn't weed them out — probably harmless), and one pile of made-up changes generated to look just like the first pile in terms of sequence context, but that never had to survive selection (so some fraction are probably harmful). Describe every change in both piles using 60+ measurements (conservation across species, chromatin state, predicted protein effect, etc.). Train a classifier to tell the two piles apart. Run that classifier on literally every possible single-letter change in the genome, once, and publish the resulting scores as a lookup table.

**Technically.** Proxy-neutral set: ~15M SNVs + 1.8M InDels fixed or near-fixed (95–100% derived allele frequency) in humans but absent from the reconstructed human–chimpanzee ancestor (from Ensembl EPO whole-genome alignments). Proxy-deleterious set: simulated de novo variants matching the proxy-neutral set's sequence composition. Features: >60 annotations from Ensembl VEP (transcript/consequence), phyloP/phastCons/GERP++ (conservation), ENCODE/Roadmap epigenomics (chromatin marks, DNase), UCSC tracks, and protein-effect scores (Grantham, SIFT, PolyPhen2) — expanded into "hundreds" of numerical model features. Model: v1.0 used a linear SVM (LIBOCAS); later versions used L2-regularised logistic regression, first in GraphLab Create, then (v1.4, this paper) via an open-source scikit-learn/SciPy pipeline. Training set size: >30M variants per iteration. Output: a raw score (unbounded, model-internal, not comparable across model versions) and a PHRED-scaled score (rank-normalised against all ~9B possible reference SNVs; version-comparable). New in v1.4: a parallel model trained on GRCh38-native annotations (not just a coordinate liftover from GRCh37), validated by comparing lifted vs. native scores (Pearson r=0.79 GRCh37↔GRCh38-v1.4; r=0.89 between GRCh37-v1.3 and v1.4). Validation set for the benchmark: ClinVar "pathogenic" vs. ExAC variants with mean allele frequency >5% (assumed neutral), 31,815 vs. 69,894 SNVs overall, and 1,288 gene-matched missense SNVs for the stricter comparison.

## Figures & tables check

| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 1 | D888 | The CADD training pipeline (phylogenetic tree → proxy-neutral/deleterious sets → logistic regression → PHRED scaling) and the user-facing scoring pipeline (VCF in, annotate, score, PHRED-lookup) | Method description (no specific claim number) | OK | Clear two-panel diagram; matches text exactly; good primary reference for how CADD is built vs. how it's used |
| Fig. 2 | D890 | AUROC of CADD (GRCh37-v1.4, GRCh38-v1.4, v1.3) vs. 9 other scores, separating ClinVar-pathogenic from common ExAC variants, for (A) all variants and (B) gene-matched missense only | "CADD GRCh38-v1.4 is not significantly different from the other CADD releases" and that CADD is competitive with dedicated missense scores | Caution | AUROC on a training-adjacent proxy task (ClinVar vs. ExAC, not blinded held-out clinical outcomes); no confidence intervals or significance test shown for the "not significantly different" claim in the main figure (only qualitative); axis fine, curves clear |
| Fig. 3 | D890 | UCSC Genome Browser tracks comparing CADD v1.3 (lifted) vs v1.4 (lifted) vs v1.4-native (GRCh38) scores over one locus (YAP1 region, chr11) | Cross-build score continuity | OK for illustration | n=1 locus, purely illustrative, not a systematic concordance metric (that's the r=0.79/0.89 numbers reported in text, not shown as a figure) |
| Fig. 4 | D891 | Screenshots of the CADD website (upload/lookup UI) and a flowchart of the offline-scoring vs. pre-scored-SNV-retrieval paths (web server / tabix / API) | Service/logistics description (no evidentiary claim) | OK | Informational only; useful for anyone integrating CADD programmatically |

Recomputation: the text's headline AUROC numbers (98.10% CADD GRCh37-v1.4 on the full set; 90.08% on gene-matched missense) are read directly off Figure 2's legend, not independently recomputed here — no table of these numbers exists separately from the figure.

## Claims vs evidence

| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | CADD integrates >60 diverse annotations into one score via a trained ML model | Fig. 1, Supplementary Tables S1/S2 (not in main text) | Fig. 1, CADD Framework section | moderate | Feature list itself is in supplementary material not scanned here; core mechanism is well described in main text |
| C2 | CADD v1.4 (GRCh38) performs comparably to prior CADD releases (GRCh37) | AUROC comparison, Fig. 2 | Fig. 2, Impact section | moderate | Same benchmark used to select tuning parameters historically for the CADD family (per Discussion), so this is closer to a consistency check than an independent test; no CI/p-value shown |
| C3 | CADD outperforms most other individual annotation scores (GERP, PhyloP, PhastCons, DANN) at separating ClinVar-pathogenic from common ExAC variants | Fig. 2A/2B AUROC ranking | Fig. 2 | moderate | Single benchmark, ClinVar/ExAC only; PolyPhen2/PROVEAN "perform on par" per the authors' own reading of the same figure — so "outperforms" only holds against some competitors, not all |
| C4 | CADD avoids the ascertainment bias of scores trained on curated pathogenic/benign sets, because its training labels come from evolutionary proxy variants, not curated calls | Framing in Introduction/Discussion; contrasted with ClinVar/HGMD-trained approaches | Introduction, Discussion | weak–moderate | Logical/design argument, not an empirical demonstration in this paper; plausible and widely cited, but no experiment here isolates "ascertainment bias avoided" as a measured quantity |
| C5 | CADD has become "one of the most widely used tools," cited ~1984 times (Google Scholar, 15 Sept 2018), ~24,000 unique website users/year | Self-reported usage stats | Impact section | weak (as evidence of quality) / strong (as evidence of adoption) | Adoption ≠ correctness; useful context, not a performance claim. This paper is now itself cited >3,900 times (Semantic Scholar/OpenAlex, checked 2026-09-09) |
| C6 | Raw scores are not comparable across CADD model versions or feature sets; only PHRED-scaled scores are safely comparable across releases | Explanation in "Raw versus scaled scores" section | Raw vs Scaled Scores section | strong | Internally consistent definitional claim (how the score is constructed), directly verifiable from the method description, not an empirical result needing a separate test |
| C7 | No universal pathogenic/benign cutoff should be applied to CADD scores; ranking + downstream filtering is recommended instead | Argument from information loss + context-dependence of appropriate thresholds | Raw vs Scaled Scores section | strong (as methodological guidance) | This is a stated design philosophy, backed by the argument given, not a numeric result — important practical implication for **your** hackathon scoring pipeline (see Adaptation plan) |

## What works

- The GRCh38 native model performs indistinguishably from the established GRCh37 model on the ClinVar-vs-ExAC benchmark (Fig. 2), and the two builds' scores correlate strongly after liftover (r=0.79 GRCh37↔GRCh38-v1.4; r=0.89 GRCh37-v1.3↔v1.4) — meaning the switch to GRCh38 did not silently degrade the resource.
- CADD ranks among the top-performing scores on both the full ClinVar/ExAC comparison (AUROC 97–98% for CADD variants) and the harder gene-matched missense-only comparison (AUROC ~90%, on par with PolyPhen2/PROVEAN/Eigen), while most single-annotation scores (GERP, conservation-only scores) lag behind.
- Practical infrastructure genuinely improved: an open-source, conda-installable offline scoring pipeline (`cadd-scripts`), a documented API, tabix-indexed pre-scored files, and third-party integration (dbNSFP, ANNOVAR, SeattleSeq, gnomAD) — these are real, checkable deliverables (verified against the live repo, see Code & data below), not just claims.

## What doesn't work (or isn't shown)

- No non-coding/regulatory-variant-specific benchmark numbers appear in the main text (only referenced as "Supplementary Figure S1"); the headline AUROC figures are for ClinVar-vs-ExAC, which is coding-variant-heavy by construction.
- No confidence intervals, bootstrap variance, or formal significance test accompanies the "not significantly different" comparison between GRCh38-v1.4 and other CADD releases in Fig. 2 — the claim is asserted qualitatively from overlapping curves, not tested statistically in what's shown here.
- Mitochondrial variant scoring was explicitly dropped in this release ("we have decided to no longer support scoring of mitochondrial variants") — a capability regression versus earlier CADD versions, stated plainly but easy to miss.
- The paper does not compare CADD against the newest deep-learning competitors head-to-head with matched training data (it discusses DANN, PrimateAI, ExPecto-type methods only in passing/Future Work, without a benchmark table).

## Limitations

**Stated by the authors.**
- Training-set labels ("proxy-neutral"/"proxy-deleterious") are an imperfect approximation of true benign/pathogenic status; an unknown fraction of proxy-deleterious variants are actually neutral.
- Because of this label uncertainty, CADD's own performance is evaluated on curated external sets (ClinVar/ExAC), not a held-out split of its own training data.
- A single universal pathogenic/benign score cutoff is inappropriate and was deliberately not provided.
- Mitochondrial variants and alternative haplotypes/contigs are not supported in this release.
- Non-coding annotation is acknowledged as an area needing more domain-specific scores (regulatory variants near promoters/enhancers/splice sites).
- A patent application exists on CADD held by four of the authors (disclosed conflict of interest).

**Not stated (analyst).**
- ClinVar-vs-ExAC as the primary validation benchmark has a leakage-adjacent property the lens flags: some of the same evolutionary-conservation and genomic-annotation signals used as CADD *features* (e.g. phyloP/GERP) are also correlated with why a variant ends up in ClinVar as pathogenic in the first place (severe, well-studied, often conserved-site variants) — this is not the same as train/test leakage, but it means the benchmark and the feature set are not fully independent lines of evidence.
- No stratification of AUROC by variant class (missense vs. splice vs. regulatory vs. synonymous) is shown outside the single missense-matched panel; performance could vary substantially by category, and a user prioritising, say, a splice-site or intronic candidate has no category-specific accuracy number from this paper alone (later CADD-Splice work, 2021, addresses this gap).
- No discussion of performance across ancestry groups — the proxy-neutral set derives from "fixed or nearly-fixed" alleles in humans generally; how well the same scores generalise across populations with different demographic histories is not addressed.
- The repository underlying this paper's v1.4 has since moved to v1.7 (2024) with substantial pipeline and feature changes — a reader in 2026 pulling the current repo is not evaluating the exact system this paper describes (see Code & data).

## Validity, bias & reproducibility

**Internal validity.** The design (contrast fixed-derived alleles vs. matched simulated de novo variants) is a coherent, previously peer-reviewed (2014) way to get a very large, ascertainment-reduced training label without manual curation — a genuine methodological strength relative to curated-set-trained competitors. The validation benchmark (ClinVar pathogenic vs. ExAC common) is standard in the field and matches what a practitioner would actually care about (can this separate real disease variants from common tolerated ones), but as noted above it isn't fully independent of the feature space.

**External validity.** Genome-wide coverage (22 autosomes + chrX, chrY with caveats) is a real strength — most alternative scores of the era covered only coding regions. Generalisation across ancestries and rare non-coding variant classes is untested in the main text.

**Reporting.** Model/version history is well documented (v1.0→v1.4, software library changes named). Training set sizes given (>30M variants/iteration, hundreds of features). No random seeds discussed (not obviously stochastic beyond standard logistic regression fitting, but data-simulation reproducibility depends on a described-but-not-fully-parameterised simulation procedure). Funding and one specific conflict of interest (a patent application by 4 of 5 authors) are disclosed.

**Reproducibility score: 4** — code (offline scoring pipeline) and pre-scored data are released, versions are named, and the pipeline is under active independent maintenance (see below); the training pipeline itself (the actual model-fitting code, the proxy-variant simulation code) is not in the public repo, only the downstream annotation/scoring pipeline is. The single biggest obstacle to a full reproduction: **you cannot retrain a CADD model from this repo** — you can only score new variants against the pre-trained models the authors distribute.

## Related work & key citations

- **Foundations:**
  - Kircher et al. (2014) — *A general framework for estimating the relative pathogenicity of human genetic variants*, Nat. Genet. — the original CADD method; read this first for the actual model-training methodology.
  - McLaren et al. (2016) — Ensembl VEP — the annotation engine that supplies most of CADD's raw feature inputs.
  - Landrum et al. (2014) — ClinVar — supplies the "pathogenic" half of this paper's validation benchmark.
- **Competitors / baselines** (from Fig. 2): DANN (Quang et al. 2015, a deep-learning model trained directly on CADD's own feature/label scheme), Eigen (Ionita-Laza et al. 2016), PolyPhen2 (Adzhubei et al. 2010), SIFT (Ng & Henikoff 2003), PROVEAN, GERP++ (Davydov et al. 2010), PhyloP/PhastCons (Pollard et al. 2010; Siepel et al. 2005).
- **Data & tools:** Lek et al. (2016) — ExAC, the "common variant" half of the benchmark; Ensembl comparative genomics / EPO alignments (Herrero et al. 2016) for the ancestral-genome reconstruction; scikit-learn (Pedregosa et al. 2011) and SciPy (Oliphant 2007) for the v1.4 model-fitting pipeline; Tabix (Li 2011) for indexed score retrieval.

Reading order for a newcomer: Kircher 2014 → McLaren 2016 (VEP) → this paper → CADD-Splice 2021 (Rentzsch et al., non-coding improvement) → CADD v1.7 2024 (Schubach et al., current model).

## Impact & follow-ups

Citation counts (checked 2026-09-09): Semantic Scholar 3,292; OpenAlex 3,985; Crossref 3,591; 314 "influential citations" per Semantic Scholar. This is a heavily used, still-growing resource paper — the underlying tool (not just this paper) has driven a lineage of follow-on work cited in its own repo: CADD-Splice (2021, adds deep-learning splice scores) and CADD v1.7 (2024, adds protein language models and regulatory CNNs), both by overlapping author teams. The paper itself also spawned imitators noted in-text: DANN reused CADD's exact feature/label scheme with a neural network instead of logistic regression; several ensemble scores (REVEL, M-CAP) combine CADD with other predictors rather than competing directly.

## Code & data

**Availability.** Official repository: `github.com/kircherlab/CADD-scripts` (confirmed live, `readme_links_paper: true`). Licence: **NOASSERTION/custom** — the repo's own LICENSE file must be read before any redistribution or commercial use; the paper text states scores/software are "freely available for all non-commercial applications" — treat as **non-commercial/research-only** until the LICENSE file is checked directly. Activity: actively maintained — last push 2025-10-30, latest release tag v1.7.3, 94 stars, 42 forks, 6 open issues/PRs (none flagged as reproduction complaints in the two most recent open-issue titles scanned). Data: pre-scored SNV/InDel files for GRCh37 and GRCh38, distributed via the CADD website (cadd.gs.washington.edu, now also cadd.bihealth.org) and via tabix/API; no registration required, but users must confirm authorisation and that uploaded data contains no identifiable information (per the paper's stated web-server terms).

**Completeness** (ML Code Completeness Checklist, heuristic score **1.5/5** from `inspect_repo.py`, confirm by opening files):

| Item | Status | Evidence |
|---|---|---|
| Dependencies | Yes | `Dockerfile`, `Snakefile`, `install.sh`, conda-based install documented in README |
| Training script | No | Not present — this repo is the *scoring* pipeline only, not the model-training code |
| Evaluation script | No | No held-out benchmark script for reproducing Fig. 2's AUROC comparison |
| Pretrained models | Partial | `data/models/{GRCh37,GRCh38}` directories exist with their own LICENSE files, but not confirmed downloadable without the full ~100GB–1TB annotation install |
| Results table | No | No README table matching this paper's AUROC numbers |

**Paper-to-code consistency.** The repository has moved past this paper's version (v1.4 → now v1.7.3, 2024/2025), with its own newer publication (Schubach et al. 2024) describing protein-language-model and regulatory-CNN features not present in v1.4. Config files exist for v1.6 and v1.7 (both builds) but not v1.4 specifically — a reader trying to reproduce *this exact paper's* GRCh38-v1.4 model from the current repo cannot do so directly; they would need an older tagged release.

**Dry run.** Skipped — the README states 100GB–1TB of disk and ≥12GB RAM are required for the offline annotation install, which the "never download multi-gigabyte datasets" dry-run constraint in this skill's assessment protocol rules out. The web/API/tabix score-lookup path (no local install) is the realistic way to obtain scores for a project like this one without the full offline install.

## Concept-to-code map

| Concept in the paper | Where it lives in the code | Reading note |
|---|---|---|
| VCF-in, annotate, score pipeline (Fig. 1B) | `Snakefile` + `CADD.sh` (top-level entry point) | `CADD.sh` is the CLI wrapper a user actually runs; the Snakefile defines the annotate→score→PHRED-lookup DAG |
| Per-genome-build model artefacts | `data/models/GRCh37/`, `data/models/GRCh38/` | Each has its own LICENSE — confirms build-specific models are packaged separately, matching the paper's description of independently trained GRCh37/GRCh38 models |
| Config per version/build | `config/config_GRCh3{7,8}_v1.{6,7}.yml` | No v1.4 config remains in the current repo; use `install.sh`/`config` from an older git tag if reproducing this paper's exact model |
| Dependency management via conda (paper's "Future Work"/"Updates" section) | `envs/`, `install.sh` | Matches the paper's stated shift to conda-based dependency management for the v1.4 release |
| Bundled test/example input | `test/input.vcf`, `test/output_GRCh3{7,8}.tsv.gz` | Smallest way to sanity-check an install without the full annotation download, once environment is set up |

## Adaptation plan

Context: MVA hackathon project needs to prioritise candidate compound-heterozygous variants for one proband against clinical HPO terms; CADD is one of the standard genome-wide deleteriousness annotations a variant-prioritisation pipeline would want as a feature.

1. **Keep as-is:** Use pre-scored, PHRED-scaled CADD values looked up via the web API or tabix against the published pre-scored files — do **not** attempt the local offline-annotation install (100GB–1TB, not warranted for a fixed proband VCF). Use PHRED-scaled scores, never raw scores, per the paper's own C6/C7 guidance, and confirm genome build match (GRCh37 vs GRCh38) against whatever reference build the case's VCF/BAM were called against — the paper's Fig. 3 shows build mismatches change scores non-trivially at some loci.
2. **Swap:** Nothing to swap in the tool itself; the adaptation is entirely about *how CADD scores are combined with other evidence* (HPO terms, ClinVar/gnomAD population frequency, inheritance pattern) — that combination logic is outside this paper's scope (a gene/variant prioritisation tool like Exomiser is the right complementary reference; the project already has a paper on Exomiser in `papers/iteration2/`).
3. **What breaks first / how you'd notice:** (a) genome-build mismatch — a variant looked up against the wrong build's pre-scored file will silently return a score for the wrong physical position; guard by checking a handful of known positions against both builds. (b) Applying a fixed pathogenicity cutoff (e.g. "CADD > 20 = pathogenic") contradicts the paper's own explicit recommendation (see C7) — use CADD as one ranked feature, not a binary filter, especially given the compound-heterozygosity requirement (two independently-inherited variants, likely of different severity) central to MVA.
4. **Minimum viable check:** look up CADD PHRED scores for the handful of top compound-het candidate pairs already surfaced by the pipeline, cross-tabulate against their ClinVar status and gnomAD frequency, and confirm the ranking is directionally sane (known-severe consequence types score higher) before trusting it as a tie-breaker between candidate pairs. This requires only API/tabix lookups — minutes, not compute-heavy.
5. **Risks:** (i) licence — confirm the CADD LICENSE file permits use in a hackathon submission context (stated non-commercial use is very likely fine, but check before any commercial/derivative claim); (ii) coverage — CADD does not score mitochondrial variants or alt-haplotypes/contigs in this version, and non-coding/regulatory accuracy is less validated than coding — if the causal variant pair includes a non-coding candidate, treat CADD as weaker evidence there and lean more on splice-specific/regulatory-specific scores (CADD-Splice, a 2021 follow-up, is the more appropriate tool for splice candidates); (iii) this paper describes v1.4 — if any tooling pulls "the latest CADD" it will be v1.7 (different features), so the report's provenance/lineage notes must record exactly which CADD version and pre-scored file were queried, per this project's standing lineage-documentation rule.

## Glossary

- **AUROC (Area Under the Receiver Operating Characteristic curve)** — a single number (0.5=random, 1.0=perfect) summarising how well a score separates two classes across all possible thresholds. Used here to compare CADD against other variant scores.
- **ClinVar** — a public NCBI database of clinically reported variant-to-phenotype relationships, curated from clinical labs and literature. Supplies the "pathogenic" side of this paper's benchmark.
- **Compound heterozygote** — two different broken copies of the same gene, one inherited from each parent, together causing a recessive condition (central to this project's own case).
- **ExAC (Exome Aggregation Consortium)** — a large database of exome sequencing from population samples, used as a proxy for "common, presumably non-disease-causing" variants.
- **GRCh37 / GRCh38** — two successive versions ("builds") of the human reference genome coordinate system; a genomic position means different things depending on which build it's read against.
- **HPO term (Human Phenotype Ontology)** — a standardised vocabulary describing a clinical sign or symptom, used here only contextually (this paper doesn't use HPO; the project's clinical dataset does).
- **InDel** — a short insertion or deletion of DNA bases, as opposed to a single-base substitution (SNV).
- **Liftover** — converting genomic coordinates from one reference build to another.
- **Logistic regression** — a linear statistical classifier producing a probability-like output; CADD's model family since v1.0's SVM was replaced.
- **PHRED-scaled score** — a `-10·log10(rank/total)` transformed score, so higher numbers indicate rarer/more-extreme rank; borrowed from Phred base-calling quality scores.
- **Purifying selection** — evolutionary pressure that removes harmful mutations from a population over generations; the reason "fixed" human variants are assumed mostly benign.
- **Reference assembly** — the standardised representative human genome sequence variants are described relative to.
- **SIFT / PolyPhen2 / PROVEAN** — dedicated computational scores predicting whether a missense (amino-acid-changing) mutation disrupts protein function; used as comparators against CADD.
- **SNV (Single Nucleotide Variant)** — a change at one single DNA base position.
- **Tabix** — a tool/index format for fast retrieval of records (like CADD scores) from a large sorted, position-indexed file without loading the whole file.
- **VCF (Variant Call Format)** — the standard row-oriented text file format for describing genetic variants (chromosome, position, reference/alternative allele, plus metadata columns).
- **VEP (Variant Effect Predictor)** — Ensembl's tool for annotating what a variant does to nearby genes/transcripts (e.g. missense, intronic, splice-site); supplies many of CADD's input features.

## Open questions & extension ideas

Authors' stated future work: add more domain-specific non-coding/regulatory scores (promoters, enhancers, splice sites); integrate functional multiplex-assay data (MAVE-type); explore non-linear/interaction-term model architectures (with an explicit overfitting caution).

Analyst's extension ideas for this project:
1. Compare CADD PHRED scores against the CADD-Splice (2021) scores specifically for any candidate variant near a splice junction — the base CADD model here is explicitly weaker on splicing.
2. Cross-check whether the compound-het candidate pair's CADD scores are unusually sensitive to the GRCh37-vs-GRCh38 build choice (using the same liftover-comparison logic as this paper's Fig. 3) as a data-quality sanity check on the case's own VCF provenance.
3. Since CADD explicitly recommends against a fixed cutoff, run a small sensitivity analysis: does the ranking of the top candidate pairs change materially between raw-score ranking and PHRED-score ranking, and does that change the final call — worth reporting either way as a "robustness of the score-based ranking" note in the methodology entry.

Questions for the authors: (1) What specific fraction of the proxy-deleterious simulated set do you estimate is actually neutral, and how would that bias the learned decision boundary? (2) Given the repo has since diverged materially (v1.4 → v1.7), is there an archived, pinned release that exactly reproduces this paper's GRCh38-v1.4 model for citation-grade reproducibility?

## Confidence notes

- Metadata (citation counts, venue, DOI) came from a clean API fetch (Semantic Scholar/OpenAlex/Crossref/arXiv via `fetch_metadata.py`) — high confidence.
- Repo health/licence/completeness came from a live GitHub API call (`inspect_repo.py`, no clone) — high confidence on metadata (stars, push date, licence flag), but the completeness checklist is explicitly a filename/README heuristic and was **not** confirmed by opening the actual pipeline scripts; treat the 1.5/5 completeness score as directional.
- Dry run was skipped by design (disk/RAM requirements exceed what a sandboxed few-minute check should attempt) — no first-hand evidence the pipeline installs cleanly.
- Supplementary Tables S1–S3 and Supplementary Figures S1–S2, referenced repeatedly in the main text for the full feature list, non-coding benchmark and correlation-scatter data, were **not** available in the scanned PDF (9 main-text pages only) — any claim about their exact contents is inferred from in-text descriptions, not verified directly.
- The AUROC percentages (98.10%, 90.08%, etc.) are read from Figure 2's legend text as rendered in the rasterised page image, not from a machine-readable table — transcription checked visually but not independently recomputed from raw data (none provided).
