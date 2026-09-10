---
title: "Pangenome-based genome inference allows efficient and accurate genotyping across a wide spectrum of variant classes"
authors: [Ebler Jana, Ebert Peter, Clarke Wayne E., Rausch Tobias, Audano Peter A., Houwaart Torsten, Mao Yafei, Korbel Jan O., Eichler Evan E., Zody Michael C., Dilthey Alexander T., Marschall Tobias]
year: 2022
venue: "Nature Genetics"
doi: "10.1038/s41588-022-01043-w"
arxiv: null
url: "https://doi.org/10.1038/s41588-022-01043-w"
paper_type: empirical
domains: [computational biology, genomics, variant genotyping, pangenome graphs, k-mer methods, hidden Markov models]
lens: bioinformatics
modes: [learn, apply]
code: "https://github.com/eblerjana/pangenie"
data: "https://doi.org/10.5281/zenodo.5607680 (assemblies/calls); GIAB, 1000 Genomes high-coverage, HGSVC, gnomAD v2 (public accessions)"
relevance: 3
analysed: 2026-09-09
analyst: paper-analyst
---

# Pangenome-based genome inference allows efficient and accurate genotyping across a wide spectrum of variant classes

## Identity & citation

Jana Ebler, Peter Ebert, Wayne E. Clarke, Tobias Rausch, Peter A. Audano, Torsten Houwaart, Yafei Mao, Jan O. Korbel, Evan E. Eichler, Michael C. Zody, Alexander T. Dilthey, Tobias Marschall. *Nature Genetics* 54(4):518–525, 2022. DOI: 10.1038/s41588-022-01043-w. Open access (Nature Portfolio); PMC copy at PMC9005351.

Nature Genetics is a top-tier, peer-reviewed genetics journal (Nature Portfolio) — this is not a preprint.

```
APA 7:
Ebler, J., Ebert, P., Clarke, W. E., Rausch, T., Audano, P. A., Houwaart, T., Mao, Y., Korbel, J. O.,
Eichler, E. E., Zody, M. C., Dilthey, A. T., & Marschall, T. (2022). Pangenome-based genome inference
allows efficient and accurate genotyping across a wide spectrum of variant classes. Nature Genetics,
54(4), 518–525. https://doi.org/10.1038/s41588-022-01043-w

BibTeX:
@article{ebler2022pangenomebased,
  title   = {Pangenome-based genome inference allows efficient and accurate genotyping across a wide
             spectrum of variant classes},
  author  = {Ebler, Jana and Ebert, Peter and Clarke, Wayne E. and Rausch, Tobias and Audano, Peter A.
             and Houwaart, Torsten and Mao, Yafei and Korbel, Jan O. and Eichler, Evan E. and Zody,
             Michael C. and Dilthey, Alexander T. and Marschall, Tobias},
  journal = {Nature Genetics}, volume = {54}, number = {4}, pages = {518--525}, year = {2022},
  doi     = {10.1038/s41588-022-01043-w}
}

Vancouver:
Ebler J, Ebert P, Clarke WE, Rausch T, Audano PA, Houwaart T, et al. Pangenome-based genome inference
allows efficient and accurate genotyping across a wide spectrum of variant classes. Nat Genet.
2022;54(4):518-525. doi:10.1038/s41588-022-01043-w
```

## Paper type & how to read it

This is an **empirical method paper** with a strong secondary identity as a **bioinformatics resource paper**: it proposes a new algorithm (PanGenie), then argues it beats existing genotypers on real datasets. It therefore owes a clear problem statement, fair comparison to the strongest existing baselines under equal conditions, and enough detail to reproduce — plus, because it is bioinformatics, biological validation (Hardy–Weinberg equilibrium, HLA truth sets, Mendelian consistency) rather than only a held-out split. Read it for: is the leave-one-out comparison fair, is there data leakage between the pangenome panel and the evaluated sample, and does the tool actually run.

## One-minute pitch

Finding genetic variants in a person's genome from short DNA reads normally means aligning those reads to a reference genome — slow, and it struggles wherever the genome repeats itself. PanGenie skips alignment entirely. It builds a graph of known genetic variation from several already-fully-sequenced people (a **pangenome**), counts short fixed-length DNA fragments (**k-mers**) in the new sample's reads, and uses a probabilistic model to infer which combination of known haplotypes best explains those counts. Because it uses whole known haplotypes rather than read alignments, it recovers structural variants and repeat-region variants that alignment-based tools miss, and it runs four times faster. The authors show this on real human genomes and use it to genotype 300 samples, finding structural variants linked to disease-associated positions that standard pipelines would not have typed.

**TL;DR:** PanGenie replaces read alignment with k-mer counting plus a hidden Markov model over a haplotype-resolved pangenome graph. It matches or beats six standard genotypers on SNPs/indels/SVs, especially in repetitive regions, while being 4–4.6× faster at 30× coverage. It was later formalized as an integer-programming reformulation (Ebler/Marschall, *Genome Research* 2025) and is an actively maintained tool (180 GitHub stars, latest release Aug 2026).

## Domains & keywords

Field: Genetics / Genomics. Subfield: genome informatics, structural variation. Techniques: pangenome graphs, k-mer counting, hidden Markov models (forward–backward algorithm), Li–Stephens haplotype model. Tasks/datasets: variant genotyping (SNP/indel/SV), GIAB, 1000 Genomes high-coverage, HGSVC, gnomAD SV, syndip benchmark.

## Problem & research questions

Gap claimed: short-read alignment to a linear (or graph) reference is computationally expensive and systematically under-genotypes structural variants (SVs) and variants in repetitive/duplicated regions, because short reads cannot be aligned unambiguously there; existing k-mer-based genotypers are fast but also fail in those same repetitive regions because they lack unique k-mers. Implicit research question: can long-range haplotype information from assembled genomes substitute for read-alignment information to genotype hard variant classes faster and more accurately? Paper's thesis, in the authors' words: PanGenie "leverages a haplotype-resolved pangenome reference together with k-mer counts... to genotype a wide spectrum of genetic variation" (Abstract).

## Method

**In plain language.** Think of the pangenome graph as a diagram where every place two or more people's genomes differ is a fork in the road ("bubble"), and each already-sequenced person's genome is one specific path through all the forks. To genotype a new person from cheap short-read data, PanGenie counts, for each fork, how many times the DNA snippets unique to each branch show up in the new person's reads. If a branch's snippets are absent, that branch probably isn't present. Where the read evidence is thin (as happens in repeats), the model borrows the fact that nearby forks tend to be inherited together (linkage) to make an educated guess — exactly how you'd infer a missing word in a sentence from its neighbors.

**Technically.** Variants are called from 14 PacBio HiFi haplotype-resolved assemblies (hifiasm v0.15.2 → paftools) into a biallelic, multi-sample VCF; overlapping alleles are merged into bubbles, giving an acyclic directed pangenome graph with one path per haplotype (11 unrelated samples used as the panel, 22 haplotypes). K-mers (k=31) are counted per bubble along haplotype paths with Jellyfish v2.2.10; the pangenome's total k-mer set is also counted in the target sample's raw reads. Genotyping is cast as a **hidden Markov model**: hidden states at each bubble are all pairs of the N panel haplotype paths (state space O(N²) per bubble); transition probabilities follow the **Li–Stephens** population-genetics recombination model (parameterised by recombination rate, effective population size N_e, inter-bubble distance); emissions model k-mer-count distributions per copy number (Poisson for copy number 1/2, geometric for spurious copy-number-0 k-mers from sequencing errors). Genotype likelihoods per bubble come from the forward–backward algorithm. Evaluated with a **leave-one-out** design (panel built from 10 of 11 samples, held-out sample's assembly-derived calls used as ground truth) against BayesTyper, Platypus, GATK HaplotypeCaller, GraphTyper, Paragraph and Giraffe, at 5×/10×/20×/30× coverage, using a custom **weighted genotype concordance (wGC)** metric plus adjusted precision/recall/F-score (Supplementary Note). Applied at scale to 300 samples (100 trios, 1000 Genomes high-coverage) to build a Mendelian-consistency + genotype-quality filtered "lenient" SV set, validated against Hardy–Weinberg equilibrium and against gnomAD SVs.

## Figures & tables check

| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 1 | 2 | Schematic: graph construction → k-mer counting → HMM genome inference | Method overview (no data) | OK | Illustrative only, correctly labelled as such |
| Fig. 2 | 3 | Assembly/callset QC: ti:tv, het:hom ratios, insertion/deletion counts, bubble composition | "Callset is high quality" (QC, not a genotyping claim) | OK | Standard genomics QC metrics, values match text (ti:tv 2.01–2.02) |
| Fig. 3 | 4 | wGC vs. % genotyped, and adjusted F-score, split by variant size/repeat status, 7 tools × 4 coverages | C: PanGenie beats mapping-based tools in repeats/SVs | Caution | **n = 1 leave-one-out sample per panel (NA12878; NA24385 in supplement)** — no error bars, no per-sample variance shown in the main figure; two held-out samples total is a thin basis for "consistency across samples" |
| Fig. 4 | 5 | Hexbin AF-vs-heterozygosity (HWE check), AF boxplots vs. assembly AFs, length distributions vs. gnomAD | C: lenient-set genotypes are population-genetically plausible | OK | Independent checks (HWE, AF agreement) not used to build the filter — genuinely informative validation, not circular |
| Fig. 5 | 6 | LD plot around the ABO-linked 129bp insertion | C: specific SV in LD with GWAS SNPs, PanGenie recovers it | OK | Single worked example, appropriately framed as illustrative, not a systematic discovery claim |

Recomputation: "4× faster" (abstract) matches "between 3.97× and 4.6× faster... at 30×" (Runtimes, p.521) — abstract rounds down conservatively, consistent.

## Claims vs evidence

| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | PanGenie is >4× faster than mapping-based genotypers at 30× | Wall-clock runtime table, Supplementary Table 5 | Runtimes, p.521 | strong | Direct measurement, but hardware/parallelism details for competitors not in main text |
| C2 | Better genotype concordance for "almost all variant types and coverages" | wGC/F-score curves, Fig. 3, Extended Data Figs. 3–8 | Results | moderate | True for the two leave-one-out samples tested; "almost all" not quantified as a count of conditions |
| C3 | Improvements especially pronounced for large insertions (≥50bp) and repeat-region variants | wGC 85/92/76% (PanGenie) vs 64/79/51% (best mapping tool) for large biallelic ins/del/complex | Results, p.520–521 | strong | Numbers directly quoted and reproduced from text; large, consistent margins |
| C4 | PanGenie genotypes SVs inaccessible to short-read-only callers, enabling GWAS-relevant discovery | gnomAD comparison (71% of PanGenie SV alleles absent from gnomAD); ABO-linked LD example | Comparison to gnomAD; LD analysis | moderate | Absence from gnomAD is consistent with novelty but doesn't independently prove correctness of those specific alleles beyond the HWE/AF checks in Fig. 4 |
| C5 | Method generalises beyond the specific pangenome built here — works for "any acyclic genome graph with fully phased path information" | Assertion in Discussion | Discussion | weak | Not tested in this paper; a design claim, not an empirical one (fair, since the paper says so explicitly) |
| C6 | Assembly quality (and thus panel quality) is high, evidenced by HLA typing and Mendelian consistency | HLA*ASM concordance (9 samples, 85 comparisons, 100% agreement); Mendelian consistency 96.8–97.9% across 3 trios | Accuracy in MHC; Variant calling | strong | Concrete counts given, cross-validated against an independent public HLA dataset |

## What works

- Large structural variants and repeat-region indels: PanGenie ('all') reaches wGC 85%/92%/76% for large biallelic insertions/deletions/complex regions at 30×, vs. 64%/79%/51% for the best mapping-based tool (GATK) — a large, reproducible margin (Results, Fig. 3).
- Runtime: consistently 3.97–4.6× faster than the fastest mapping-based competitor across all four tested coverages (Supplementary Table 5).
- HLA-region genotyping: 98–100% wGC for HLA-C/-DPA1/-DPB1/-DRA in biallelic regions; assembly-derived HLA types independently agree 100% with public 1000 Genomes HLA genotypes.
- Population-genetic plausibility at scale: 90.7–90.9% of 300-sample SV genotypes show no significant HWE deviation, and AF estimates from 200 unrelated samples match coarse AF estimates from the original 11-sample panel — two checks not used to build the filter, so they are genuine external validation.

## What doesn't work (or isn't shown)

- SNPs in nonrepetitive regions: essentially a tie — "all methods reach excellent... F scores >0.95 at coverage 30×" (Results). PanGenie's advantage is concentrated in the harder variant classes, not everywhere.
- HLA-DRB1 and -C4: lowest wGC among HLA genes (58% and 79% respectively) — the paper reports this rather than hiding it.
- No experiment at coverage below 5×, no ancient-DNA or degraded-sample regime, no non-human species (stated as future work in Discussion).
- Cannot genotype variants absent from the input panel by design (a "closed-world" limitation the authors state explicitly) — no experiment quantifies how much real-world variation this excludes for a given population.
- No independent replication of the wGC benchmark reported outside this paper (as of this analysis); comparisons rely entirely on the authors' own reimplementation/configuration of six competing tools.

## Limitations

**Stated by the authors.**
- Repetitive regions (segmental duplications, α-satellite, acrocentric DNA) remain hard even for PanGenie, due to lack of unique k-mers and because those regions are themselves hard to assemble.
- The model assumes the sample's true haplotypes are mosaics of panel haplotypes — it cannot discover variants absent from every panel haplotype (not a variant caller in the traditional sense).
- Runtime scales with the number of input haplotypes (state space is O(N²) per bubble); scaling to much larger panels needs further engineering; polyploid genomes are "prohibitively slow" without further optimisation.
- Tested only on human data so far.

**Not stated (analyst).**
- Benchmark n is very small for a "wide spectrum of variant classes" claim: only two leave-one-out held-out samples (NA12878, NA24385), both of European/Ashkenazi ancestry with unusually deep public characterisation (GIAB reference samples) — no leave-one-out test on the Yoruban, Puerto Rican or Han Chinese samples in the same 14-sample cohort, despite those being available. This limits how far "consistent across samples" (p.521) generalises across ancestries.
- No confidence intervals or per-variant variance are shown in the headline wGC/F-score plots (Fig. 3) — a single point estimate per tool/coverage/category.
- Competing tools were run with what the paper calls sensible per-tool configurations (e.g., GATK only on SNPs/small/midsize, GraphTyper/Giraffe only on large variants) — reasonable given tool scope, but it means no single table shows all seven tools on all variant classes; cross-tool comparison for some cells relies on partial data.
- All panel samples and evaluation samples derive from the same set of 14 assemblies produced by the same pipeline (PGAS) and the same assembler (hifiasm) — a systematic bias in that pipeline (e.g. a specific collapse/expansion tendency) would affect ground truth and panel identically, which the leave-one-out design cannot detect.

## Validity, bias & reproducibility

**Internal validity.** The core design — leave-one-out with assembly-derived ground truth — is appropriate and standard for this field (same logic HGSVC and GIAB benchmarks use), and it correctly avoids testing a genotyper against a genotyper's own beliefs. But ground truth and panel share the same upstream assembly/variant-calling pipeline (PGAS, hifiasm), so this design tests self-consistency of that pipeline more than it tests genotyping against an orthogonal biological truth (e.g., long-read validation of the specific held-out variants). **External validity.** Only 2 of 11 possible held-out samples tested in the main figures; all pangenome/HLA data are human — the Discussion is explicit that other species are untested. **Reporting.** Coverage levels, k, tool versions, and commit hash for PanGenie are all specified (rare and commendable level of exact versioning for a bioinformatics paper) — see Methods, "PanGenie (commit 1f3d2d2)". No random seeds discussed (mostly deterministic HMM inference, though the SV-scoring step uses a support-vector-regression model whose training randomness is not described). **Conflicts/funding.** NIH and BMBF grants disclosed; funders stated to have no role in design/analysis/publication.

Bioinformatics-lens leakage check: since this is genotyping (not classification with an arbitrary train/test split), the relevant leakage question is whether the held-out sample's true haplotypes could be indirectly present in the panel via relatedness — the three trios in the 14-sample cohort mean some panel haplotypes are parent–child related to each other, but the two evaluated leave-one-out samples (NA12878, NA24385) are not from trios in this dataset, so no parent/child leakage there specifically.

**Reproducibility score: 4/5.** Code, exact commit hash used for benchmarks, all public data accessions, and versioned dependencies (Jellyfish v2.2.10, minimap2 v2.18, hifiasm v0.15.2, GATK 4.1.3.0, etc.) are all stated; a Zenodo DOI (10.5281/zenodo.5607680) archives the pipeline. Missing for a 5: no independent third-party reproduction of the exact wGC numbers has been published (as far as this analysis found), and the SV-scoring SVR model's exact hyperparameters/training code for the "lenient set" filter are not fully specified in the main text (Supplementary Note only). Biggest obstacle to reproduction: assembling the 14 haplotype-resolved genomes yourself requires PacBio HiFi data and the PGAS pipeline (a nontrivial, expensive prerequisite) — reusing the tool on new samples against the authors' existing panel is comparatively easy (this is exactly the demo path a downstream user, e.g. this hackathon, would take).

## Related work & key citations

- **Foundations** — Li & Stephens (haplotype recombination model this HMM's transition probabilities reuse); Chin et al. hifiasm (assembler); Ebert et al. 2021 *Cell* (HGSVC haplotype-resolved assemblies, the source of most input data here).
- **Competitors / baselines** — BayesTyper (Sibbesen et al., k-mer-based, closest prior-art competitor); Paragraph (Chen et al., graph+alignment SV genotyper); GATK HaplotypeCaller; GraphTyper2; Platypus; Giraffe (Sirén et al., pangenome-aware read mapper).
- **Data & tools** — GIAB (Zook et al.), 1000 Genomes Project high-coverage (Byrska-Bishop et al.), gnomAD-SV (Collins et al.), Jellyfish (Marçais & Kingsford, k-mer counting).

Read next, in order: (1) Sibbesen et al. BayesTyper — the nearest k-mer-based competitor, to understand exactly where PanGenie's HMM adds value; (2) Ebler & Marschall, *Genome Research* 2025, "Pangenome-based genome inference using integer programming" — the authors' own follow-up reformulation, directly relevant if adapting the algorithm; (3) Sirén et al. (vg/Giraffe) for the alignment-based pangenome alternative.

## Impact & follow-ups

301 citations (OpenAlex, checked 2026-09-09); 257 (Crossref). Citation counts by year show sustained, growing uptake (28 in 2022 → 96 in 2024 → 44 already in partial-year 2026), consistent with adoption as infrastructure rather than a one-off result. Most concrete confirmed follow-up found: Ebler & Marschall, "Pangenome-based genome inference using integer programming," *Genome Research* 35(12):2661 — the same group reformulating PanGenie's HMM as an integer program, i.e. a methodological extension rather than a contradiction. Semantic Scholar's influential-citation flag could not be retrieved (API rate-limited during this analysis — see Confidence notes); this section should be revisited when reachable.

## Code & data

**Availability.** Official repo: `github.com/eblerjana/pangenie`, MIT licensed, 180 stars, 17 forks, **actively maintained** (last push 2026-08-18, 22 days before this analysis; latest tagged release v4.2.2 ships prebuilt `PanGenie`/`PanGenie-index`/`PanGenie-vcf` binaries). C++ core (85%) with Python tooling (14%), CMake build, 74 unit tests, Snakemake-style `pipelines/` for building a panel from assemblies or from a Minigraph-Cactus graph, and ReadTheDocs documentation. Open issues (24 scanned) are mostly usage questions about VCF preparation and pangenome-graph construction, not correctness bug reports against the paper's numbers. Data: assemblies/variant calls/genotypes on Zenodo (DOI 10.5281/zenodo.5607680, and a second Zenodo record for pipelines, both cited in-text); all raw sequencing data are public accessions (GIAB, 1000 Genomes BioProject PRJEB31736, syndip via CHM-eval GitHub release).

**Completeness (ML Code Completeness Checklist, heuristic + manual read of README/repo tree).**

| Item | Status | Evidence |
|---|---|---|
| Dependencies specified | Yes | `environment.yml`, `pyproject.toml`, `CMakeLists.txt`, Docker/`container/` folder |
| Training/run script | Partial | `pipelines/run-from-callset/` gives an end-to-end Snakemake pipeline; no single "train" step since PanGenie's HMM has no learned weights (SVR filter script is separate and less documented) |
| Evaluation script | Partial | `scripts/test_plot_path_coverages.py` exists; the wGC/F-score benchmark code from the paper itself is not obviously in this repo (likely in the separate `bitbucket.org/jana_ebler/genotyping-experiments` repo referenced in-text but not independently inspected here) |
| Pretrained models/weights | No | Not applicable in the ML sense (HMM has no trained weights); latest release ships compiled binaries, not "weights" |
| Results table in README | No | README (455 chars) is a short pointer to docs, not a results summary |

Automated completeness score: 1.5/5 — this understates real usability for a probabilistic/HMM tool (no "pretrained weights" concept applies), but it correctly flags that reproducing the paper's own benchmark numbers requires the separate, un-inspected `genotyping-experiments` Bitbucket repo, not the main PanGenie repo.

**Paper-to-code consistency.** Benchmarks used "PanGenie (commit 1f3d2d2)" per Methods — an old commit relative to the current v4.2.2 release; current defaults (k, filtering behaviour) should be checked against that commit if exact paper-number reproduction is attempted, rather than assumed unchanged.

**Dry run.** Not attempted in this pass (no dependency install/build was run) — the repo requires a C++ build (CMake) plus a constructed pangenome VCF as input, which is a nontrivial first step; recommended before relying on the tool: `git clone`, build via the documented CMake path or pull the v4.2.2 binary, then run the shipped `demo/` example from the repo tree.

## Concept-to-code map

| Concept in the paper | Where it likely lives in the code | Reading note |
|---|---|---|
| Pangenome graph / bubble construction (Methods, "Pangenome construction") | `src/` (C++ core, graph-builder classes per `tests/GraphBuilderTest.cpp`) | Confirmed test file exists; did not open source to verify class names beyond the test inventory |
| k-mer counting & unique-k-mer identification | `src/` (`ColumnIndexerTest.cpp`, `DnaSequenceTest.cpp` suggest a k-mer/column indexing module) | Paper uses external Jellyfish for graph k-mer counting; PanGenie's own indexer likely handles read-side counting |
| HMM emission probabilities (Poisson/geometric) | `src/` (`EmissionProbabilityComputerTest.cpp`) | Name matches paper's "Observable states" section directly |
| Copy-number states (Hᵢⱼ) | `src/` (`CopyNumberTest.cpp`) | Matches the aᵥ,ᵢ,ⱼ copy-number vector in Methods |
| Genotype output / VCF | `src/` (`GenotypingResultTest.cpp`, `CommandsTest.cpp`) | End-to-end CLI likely wraps these |
| Panel construction from assemblies or Minigraph-Cactus graphs | `pipelines/prepare-vcf-from-assemblies/`, `pipelines/prepare-vcf-from-MC/` | Two supported panel-construction routes, config-driven |

Note: this map is inferred from test-file names and the repository tree returned by `inspect_repo.py`, not from opening the C++ source directly — treat class-level mappings as a reading guide, not a verified API reference.

## Adaptation plan

Written against this project's likely use (MVA hackathon: identifying a compound-heterozygous causal variant pair from the proband's 85GB raw dataset, VCF + FASTQ):

1. **Keep as-is:** the core genotyping question PanGenie solves (given a set of candidate variants and a haplotype panel, genotype a new short-read sample) is directly relevant if the hackathon's pipeline needs to re-genotype candidate SVs/indels in repetitive regions that standard callers miss — exactly the variant classes most likely to hide a causal SV in a rare-disease case.
2. **What to swap:** PanGenie needs a haplotype-resolved *panel* (assembly-derived pangenome VCF) to genotype against — the hackathon case is a single proband, not a cohort with existing assemblies. The realistic adaptation is to use one of the project's existing public pangenome panels (e.g., HPRC/HGSVC-derived, if already used upstream) rather than building a new one from scratch; check `ideation/data-findings.md` for whether such a panel is already part of the analysis toolset.
3. **What breaks first:** PanGenie only genotypes variants already present as an allele in the panel — it will not discover a truly private de novo variant unique to the proband. If the causal variant is a known SV/repeat-expansion class present in public pangenome resources (gnomAD-SV, HPRC), PanGenie is a strong genotyping/confirmation tool; if the causal variant is private and never seen before, PanGenie cannot find it and a discovery-mode caller is still needed upstream.
4. **Compute/time estimate:** paper reports ~30 single-core CPU hours per sample against an 11-sample/22-haplotype panel at 30× — for a single proband this is a same-day run on typical hackathon compute; minimum viable experiment: run PanGenie's shipped `demo/` example first (should take minutes) before pointing it at real 85GB proband data, to catch build/config issues cheaply.
5. **Risks:** panel-ancestry mismatch (the paper's panel skews toward the samples in GIAB/1000G/HGSVC — mismatch with the proband's ancestry could reduce genotyping quality, per Fig. 3's untested-ancestry gap noted above); MIT licence poses no reuse restriction; version drift between the paper's benchmarked commit (1f3d2d2) and the current v4.2.2 release means current defaults should be re-checked, not assumed identical to the published numbers.

## Glossary

- **Bubble** — a site in a pangenome graph where haplotypes diverge and later reconverge, representing one genetic variant or a cluster of overlapping ones. Role here: the basic unit PanGenie genotypes.
- **Compound heterozygote** — two different broken copies of the same gene, one inherited from each parent. Not used in this paper, but the concept driving why the hackathon project cares about accurate SV/indel genotyping in the first place.
- **Emission probability** — in an HMM, the probability of observing a given output (here, a k-mer count) given the hidden state (here, a copy-number assignment). Role here: models sequencing noise via Poisson/geometric distributions.
- **Forward–backward algorithm** — a dynamic-programming method to compute, for each position in a sequence, the probability of each hidden state given all the observed data. Role here: computes genotype likelihoods per bubble.
- **Genotype** — whether a known variant is present on none, one, or both copies of a chromosome pair. The central quantity PanGenie predicts.
- **GIAB (Genome in a Bottle)** — an NIST-led public consortium producing reference-quality "truth set" genomes for benchmarking. Role here: source of Illumina sequencing data and truth SV callsets.
- **Hardy–Weinberg equilibrium (HWE)** — the expected relationship between allele frequency and genotype frequency in a randomly mating population, absent selection/drift. Role here: used as an independent sanity check on genotyping quality at scale (Fig. 4a).
- **Haplotype** — one specific sequence of DNA along one copy of a chromosome, i.e. which alleles travel together. Role here: PanGenie's panel is built from fully phased (haplotype-resolved) assemblies.
- **Hidden Markov model (HMM)** — a probabilistic model where a sequence of hidden states generates observed emissions, with state transitions following Markov (memoryless, position-to-position) probabilities. Role here: models an unknown genome as a chain of haplotype-pair choices, one per bubble.
- **k-mer** — a short DNA subsequence of fixed length k (here k=31). Role here: PanGenie's entire read-evidence pipeline is built on counting k-mers instead of aligning full reads.
- **Leave-one-out experiment** — an evaluation design where one sample is held out from the panel/training set and used only as ground truth for testing. Role here: the paper's core benchmark design (Fig. 3).
- **Li–Stephens model** — a population-genetics model of how haplotypes recombine, used to estimate how likely a new haplotype is to switch between two panel haplotypes at a given genomic distance. Role here: source of PanGenie's HMM transition probabilities.
- **Linkage disequilibrium (LD)** — the tendency of nearby genetic variants to be inherited together more often than by chance. Role here: what lets PanGenie infer genotypes at poorly-covered bubbles from well-covered neighbors, and what the LD analysis (Fig. 5) exploits to link SVs to disease-associated SNPs.
- **Mendelian consistency** — whether a child's genotype is explainable by combining the parents' genotypes, per the rules of inheritance. Role here: used both as a QC filter and to build the "lenient" high-confidence SV set.
- **Pangenome (graph)** — a reference representation that includes multiple genomes' worth of variation (not just one linear reference), typically as a graph. Role here: PanGenie's core input structure, built from bubbles and haplotype paths.
- **Structural variant (SV)** — a genetic variant ≥50bp (insertion, deletion, duplication, etc.), as opposed to small SNPs/indels. Role here: the variant class PanGenie improves on most.
- **STR/VNTR (short tandem repeat / variable-number tandem repeat)** — genomic regions made of a short motif repeated many times, with the repeat count varying between people. Role here: the hardest, most repeat-rich regions the paper stratifies its evaluation by.
- **wGC (weighted genotype concordance)** — a custom metric introduced in this paper that equally weights how well a tool detects all three possible genotypes (hom-ref/het/hom-alt), avoiding the bias of plain accuracy toward the common genotype. Role here: the paper's primary accuracy metric (Fig. 3, Fig. 4).

## Open questions & extension ideas

Authors' own future work: extend to telomere-to-telomere assemblies (to reach segmental duplications/acrocentric DNA); develop rare-variant discovery on top of PanGenie's "unexplained" k-mers; scale to much larger haplotype panels via pruning (as statistical phasing tools do); extend to polyploid genomes.

Analyst's ideas:
1. **Ancestry-stratified leave-one-out.** Rerun the leave-one-out benchmark on the Yoruban, Puerto Rican, and Han Chinese samples already present in the 14-sample cohort (not just the two GIAB reference samples used) — would directly test the generalisation gap flagged above, at essentially no new data-generation cost.
2. **Orthogonal ground truth.** Validate a subset of PanGenie's held-out predictions against long-read (HiFi) alignment of the same held-out sample directly, rather than only against that sample's own assembly-derived calls — breaks the shared-pipeline circularity noted in Validity.
3. **Panel-ancestry sensitivity sweep.** For a hackathon-style N-of-1 case, genotype the same proband sample against panels of varying ancestry composition and measure wGC drift — directly informs whether PanGenie's stated accuracy transfers to an out-of-panel-ancestry individual.
4. **Repeat-expansion case studies beyond ABO.** The paper found one striking case (ABO-linked LTR10B2 expansion); systematically screening the "lenient" SV set for other GWAS-linked repeat expansions could be a natural extension using the same released data.

Questions for the authors: (1) Was the ABO-region LD finding (Fig. 5) tested for replication in any subsequent cohort? (2) What is current recommended practice for building a panel for a single ancestry-mismatched sample (e.g., non-European) given the panel here skews GIAB/1000G/HGSVC?

## Confidence notes

- Semantic Scholar API returned HTTP 429 (rate-limited) during metadata fetch; citation count, influential-citation list, and TLDR came from OpenAlex/Crossref only. Citation counts (301/257) and the "growing yearly" trend are solid (OpenAlex), but the specific "most influential citing papers" claim in Impact & follow-ups could not be verified and is marked unverified beyond the one concrete follow-up (Genome Research 2025) found via web search.
- The benchmark-specific code repo the paper cites (`bitbucket.org/jana_ebler/genotyping-experiments`) was identified from the PDF text but not independently inspected (`inspect_repo.py` only supports GitHub/GitLab-style hosts in this run) — the completeness/consistency assessment above covers the main `eblerjana/pangenie` repo only, not the benchmark-reproduction code.
- Concept-to-code mapping is inferred from file/test names returned by the repo-inspection script, not from reading the C++ source directly — treat as a reading guide, weight it lower than the rest of the report.
- No dry run of the tool was attempted (would require a C++ build and a constructed pangenome VCF) — Code & data's "Dry run" section reflects this as skipped, not failed.
- Original PDF download was initially blocked by PMC's bot/proof-of-work gate (curl); the user retrieved the true publisher PDF manually, which is what this analysis (figures, page numbers) is based on. An earlier JATS-XML-only extraction (Europe PMC full-text API) was used for text but discarded once the real PDF arrived, since the PDF carries page numbers and figures the XML route did not reliably expose in this environment.
