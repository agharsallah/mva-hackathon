# Statistical methods survey — what we can apply, and what we cannot

**Standing:** literature survey, 2026-08-31. Web research run before any method execution;
nothing here is a result. Each method adopted from this list must still go through the
register (`mva-science hypothesis-add`) before its run. Owner of the topic; the roadmap
links here, never restates.

Data constraints every method must fit: **one sample** (no parents, no matched normal),
**no BAM** (reads are alignment-free, k-mer-presence queryable only), VCF with caller
statistics only (no population/consequence annotations), 44x depth, 18-probe oracle budget.

The strongest untapped signal: `AD` (allele depths) at heterozygous sites — a clean
per-site binomial observation. `DP` exists only at variant records, so it is a sparse,
het-biased coverage track; every depth method inherits that bias.

---

## Framing corrections (change how we test, not just what)

1. **A test on mean BAF has ~zero power for unphased mosaic gain.** Under mosaic trisomy
   at cell fraction *f*, het-site BAF splits into two **symmetric** bands —
   `1/(2+f)` and `(1+f)/(2+f)` — so the mean stays 0.5. The right statistic is the
   fold-over **B-deviation** `Bdev = |BAF − 0.5|` (a dispersion statistic) or a CDF fit
   (DANFIP, Markello 2012, PMID 22300746: shift the theoretical CDF, minimize L1
   residuals; mosaic fraction from the band position, `f̂ = (2·BAF−1)/(1−BAF)`).
   Monosomy bands: `(1−f)/(2−f)` and `1/(2−f)`.
2. **The 18-probe budget is generous in bits, tight in noise.** 18 noiseless binary
   answers distinguish 2^18 = 262,144 hypotheses; naming 1 pair among ~200 candidates
   needs ⌈log₂ 200⌉ ≈ 8 perfect bits. Noise handling and query expressiveness are the
   binding constraints, not the count.
3. **Plain binomial VAF p-values are anticonservative.** Sequencing VAF is overdispersed
   (GC bias, PCR duplication); fit a beta-binomial with overdispersion estimated from our
   own genome-wide het sites.
4. **A PASS-vs-nonPASS classifier is mis-specified.** We have noisy positives (PASS) and
   no true negatives — the correct frame is **PU learning** (positive-unlabeled), not
   binary classification (Elkan & Noto 2008).
5. **NMF mutational-signature extraction is not meaningful here.** Needs a cohort matrix;
   a single germline callset's spectrum reflects population history, not this child.
   Legitimate narrow use: single-sample signature *fitting* (NNLS vs COSMIC refs) as a
   QC/artifact flag only, labelled as QC. MVA's relevant "signature" is aneuploidy, not
   SBS classes.

---

## Adopted additions — top 8 by expected value

| # | Method | Serves | Core |
|---|---|---|---|
| 1 | **gnomAD variant co-occurrence → P(trans)** (Guo 2023, Nat Genet, PMID 38057443; `broadinstitute/gnomad_chets`) | compound-het ranking | Excoffier–Slatkin EM on gnomAD 2×2 genotype counts → haplotype frequencies → P(pair in trans). Trio-validated (77–99% accuracy); only published no-parents no-BAM phasing. Caveat to quote: rare-pair estimates poorly calibrated. |
| 2 | **Bdev + DANFIP CDF fit** (Markello 2012) | mosaic quantification | See framing correction 1. Runs on `AD` alone, no external reference; validated 0.1% precision over 4–80% mosaicism. |
| 3 | **Greedy EIG, Jedynak–Frazier–Sznitman optimality, EVSI loss** (J Appl Probab 2012; Howard 1966) | oracle budget | One-step-greedy expected-information-gain is Bayes-optimal over the full horizon for a fixed noise channel; swap entropy for expected P(final answer correct) — the quantity the scorer rewards. |
| 4 | **MosaicHunter-style 4-state posterior** {0/0, 0/1, 1/1, mosaic-f} (Huang 2017, PMID 28132024) | mosaic sites | Beta-binomial likelihood, overdispersion fitted from our het sites, mosaic fraction integrated over a prior. Reimplementable from `AD`; the tool itself needs BAM. |
| 5 | **k-mer 4-way phase test + Poisson dropout arithmetic** | phasing + probe design | Two het variants within k−1=30 bp: build all 4 allele-combination k-mers; exactly 2 present ⇒ deterministic cis/trans. Dropout: P(false absent) = e^(−λ), λ = 0.8·c·VAF → het λ≈17.6 (dropout 2e−8), mosaic 10% λ≈3.5 (dropout 0.03), mosaic 5% dropout 0.17 — below ~10% VAF, "absent" is not evidence of absence. No published standalone tool — innovation claim. |
| 6 | **Tavtigian/Pejaver Bayesian ACMG** (GIM 2018; Pejaver AJHG 2022, PMID 36413997) | variant pathogenicity | Prior P(path)=0.10; evidence LR ladder 2.08/4.33/18.7/350 (geometric, hence 1/2/4/8 points). Calibrated, comparable across genes, no training data of ours. |
| 7 | **EC² + generalized binary splitting** (Golovin/Krause/Ray NeurIPS 2010; Hwang 1972) | oracle budget | Pooled probes ("pair among these 5 genes?") reach the ~8-query floor; EC² keeps a (1−1/e) greedy guarantee under noise where plain binary search collapses. Finish with **SPRT** (Wald 1945) for confirmatory re-asks. |
| 8 | **IHW + PELT + Dirichlet-process VAF clustering** | machinery upgrades | IHW (Ignatiadis 2016) beats BH given covariates (depth, LOEUF); PELT (Killick 2012) exact where CBS is greedy; DP mixture (PyClone-style, Roth 2014) does not fix the clone count — the defining property of *variegated*. |

Runners-up (one paragraph each when written up): LIRICAL's LR chain — its AR genotype LR
*degrades* rather than zeroes when only 1 of 2 alleles is seen (relevant to a missed second
hit, PMID 32755546); bcftools/RoH HMM autozygosity (PMID 26826718); PanGenie/KAGE Poisson
emission models as peer-reviewed backing for k-mer → genotype likelihood (Nat Genet 2022;
Genome Biol 2022); Merqury containment QV as final-answer validator against the 1.07B reads
(Rhie 2020); conformal prediction for calibrated variant-classification sets; GATK VETS as
the modern single-sample recalibration baseline.

---

## Baseline list (kept, from the pre-survey plan)

Mosaicism/aneuploidy: binomial → beta-binomial VAF tests; Poisson/NB depth models;
robust-z chromosome dosage; Wilson CIs; GMM/EM VAF mixture (EM-mosaic, PMID 32349777, is
the published version — runs on VAF alone); HMM over (VAF, depth); changepoint (now PELT);
hierarchical Bayes per-chromosome pooling.
Ranking: permutation gene burden; empirical-Bayes shrinkage; FDR (now IHW); KS/Mann-Whitney
QUAL comparisons; Bayesian posterior ranking (rarity × consequence × gene prior — needs
external gnomAD/CADD annotation, the pipeline's main missing input); PL-based LRTs;
PGT/PID phasing; non-PASS rescue (now framed as PU learning, GATK VETS baseline).
Probes: Poisson k-mer presence test (formalizes the ~35-read expectation); Bayesian
experimental design (now Jedynak/EC²/SPRT); group testing; top-two Thompson sampling for
the endgame only.
QC: chi-square substitution spectrum; bootstrap; signature fitting as QC only.

---

## Explicitly NOT applicable (say so, never fudge)

- **Needs BAM/read-level access:** MosaicHunter, MosaicForecast, MrMosaic, DeepMosaic,
  Samovar, DRAGEN mosaic caller, CNVkit, CNVnator, WhatsHap, HapCUT2.
- **Needs matched normal / pair:** ASCAT, FACETS, Sequenza, VarScan copynumber,
  AbsCN-seq, VCF2CNA.
- **Needs a cohort:** GATK gCNV, CODEX2, ExomeDepth, PatternCNV, NMF signature
  extraction, **NIPT z-score/NCV/SeqFF** (the seductive false friend: z-score divides by a
  between-sample SD that does not exist at N=1).
- **Needs parents/pedigree:** pVAAST, triPOD, trio binning/hapmers.
- **Needs controls:** VAAST CLRT.
- **Wrong objective (cumulative regret, not pure exploration):** UCB, Gittins, plain
  Thompson sampling, ε-greedy.
- **Overhead at N≤200 discrete hypotheses:** variational BOED, Deep Adaptive Design.
- **Partial / weak regime, use with corroboration only:** SHAPEIT5 statistical phasing of
  ultra-rare variants against small public panels (its <5% switch-error claim is
  within-cohort at n=500k, not this regime); MoChA/J-LOH (need a reference haplotype
  panel); GenomeScope mixture (needs a k-mer histogram we can only approximate);
  GC-bias correction (needs a coverage track; our DP is sparse).

Full per-method table with citations: produced by the research run of 2026-08-31
(subagent web survey); key sources — MosaicHunter NAR 45:e76 · EM-mosaic Genome Med 12:42 ·
DANFIP Mol Genet Metab 105:665 · MoChA Nature 559:350 · gnomAD co-occurrence Nat Genet 2023 ·
LIRICAL AJHG 106:356 · Tavtigian GIM 20:1054 · Pejaver AJHG 109:2163 · PanGenie Nat Genet
54:518 · KAGE Genome Biol 23:209 · Merqury Genome Biol 21:245 · GenomeScope 2.0 Nat Commun
11:1432 · Jedynak J Appl Probab 49:114 · Golovin & Krause JAIR 42:427 · Hwang JASA 67:605 ·
Wald Ann Math Statist 16:117 · IHW Nat Methods 13:577 · PELT JASA 107:1590 · PyClone Nat
Methods 2014 · Ignatiadis/Killick/Roth as cited inline.
