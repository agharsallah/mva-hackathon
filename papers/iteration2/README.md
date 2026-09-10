# Papers read for iteration 2

**Standing:** 2026-09-10. Eight papers, each with a full `paper-analyst` report (`*-analysis.md`)
and `metadata.json`; the PDFs are gitignored (`papers/**/*.pdf`), the `work/` folders (extracted
text, page renders, shallow clones of the papers' code) are local scratch and not tracked. What
each paper changed in the plan is recorded in
[`docs/iteration2/plan.md` §9 and §10](../../docs/iteration2/plan.md); the verified citations they added
are §8 G there. Numbers below are the papers' own, quoted with their page; none is a result of
ours.

## The eight papers and what they did to the plan

| Paper | Analysis | Backs | What it corrected (plan §9 id) |
|---|---|---|---|
| Ebler et al. 2022, PanGenie, *Nat Genet* (PMID 35410384) | [`ebler2022_pangenie/`](ebler2022_pangenie/ebler2022_pangenie-analysis.md) | step 3 (Poisson emission family, k = 31, genome-wide k-mer uniqueness) | it is a *panel* method that cannot type an allele absent from every panel haplotype (Discussion p. 524) — the case's private alleles — so it is no longer cited as precedent for single-allele counting (K6); its geometric copy-number-0 state became the false-positive model (K3) |
| Pajuste et al. 2017, FastGT, *Sci Rep* (PMID 28566690) | [`FastGT…/`](FastGT-%20an%20alignment-free%20method%20for%20calling%20common%20SNVs%20directly%20from%20raw%20sequencing%20reads/FastGT-Pajuste-2017-analysis.md) — written 2026-09-10 | step 3 genotyping — the direct precedent | ≥ 3 k-mer pairs per allele (K1); a fitted negative-binomial classifier on 100,000 markers, not a count band on 2,000 (K2); over-dispersed dropout (K3); uniqueness against reference **plus** known alternate alleles (K4); indels excluded from its validation |
| Pajuste & Remm 2023, GeneToCN, *Sci Rep* (PMID 37853040) | [`GeneToCN Pajuste et al-2023/`](GeneToCN%20Pajuste%20et%20al-2023/GeneToCN-Pajuste-2023-analysis.md) | step 3 copy number | *local flanking* denominator with ≥ 2,000 k-mers, not genome-wide; k = 25 with a GC filter over a 250 bp window; exon scale unvalidated (smallest unit 5.5 kb; 268 k-mers judged unreliable, 3,095 reliable) — so k-mer count per exon is printed and the deletion cut is calibrated on a 1,000-exon null (K5); its `GeneToKmer.py` selection rules and `KmerToCN.py` arithmetic are reused |
| Smedley et al. 2015, Exomiser protocol, *Nat Protoc* (PMID 26562621) | [`Exomiser-Smedley-al-2015/`](Exomiser-Smedley-al-2015/Exomiser-Smedley-al-2015-analysis.md) | steps 1, 4 | its benchmark is one sentence citing Zemojtel 2014 — the step-1 benchmark now follows that protocol and stops calling itself a mirror (S1); single-sample Exomiser never checks phase (p. 2005), which is why P(trans) and read phasing exist; hiPHIVE never leaves a gene unscored — the `uncurated` tier (S5); compound-het gene score = mean of the two best variant scores (p. 2012) as a comparator |
| Zemojtel et al. 2014, PhenIX, *Sci Transl Med* (PMID 25186178) | [`Zemojtel-PhenIX-2014/`](Zemojtel-PhenIX-2014/Zemojtel-PhenIX-2014-analysis.md) — read 2026-09-10 | steps 1, 4, 6 — the source of the degradation protocol step 1 already followed | its 86.5 % top-1 (Fig. 1) has no interval and its truth set is the corpus that built the scorer, so step 1's recall curve is an internal check and the spike-in harness is the quoted recall (Z1); its one disclosed miss is a synonymous splice allele, so synonymous / near-splice alleles stay in with SpliceAI Δ ≥ 0.2 (Z2); 29 of 40 prospective failures never triaged, so step 6 gets four pre-registered failure categories (Z3); single-variant-per-gene and panel-bound by its authors' statement — the two places this plan goes past it |
| Kong et al. 2018, MAD-seq, *Genome Res* (PMID 29773658) | [`Kong-MADseq-2018/`](Kong-MADseq-2018/Kong-MADseq-2018-analysis.md) — read 2026-09-10 | step 8 joint model | the model assumes a genome-wide diploid baseline and its authors say it degrades with several abnormal chromosomes — the definition of *variegated* — so step 8 gains a leave-one-chromosome-out baseline, a multi-chromosome simulation and an absolute k-mer-mass scale (M2); its > 99 % / < 2 % are simulation-only and the package is gone from Bioconductor, so the five-model BIC comparison is re-implemented in Python from the equations and ΔBIC < 10 is low confidence (M3); cost revised (M4) |
| Kosugi et al. 2019, SV benchmark, *Genome Biol* (PMID 31159850) | [`SVbenchmark Kosugi et al-2019/`](SVbenchmark%20Kosugi%20et%20al-2019/SVbenchmark-Kosugi-2019-analysis.md) — read 2026-09-10 | step 2 structural variants | cross-method-class caller pairs gain more precision than same-class pairs (Fig. 6–7), so GRIDSS joins Manta / Delly / LUMPY and consensus means two classes (V1); real-data DUP ≤ 57 % and INV ≤ 49 % precision (Table 1), so H016 is per type and DUP/INV need dosage confirmation (V2); GRCh37, 2019 versions, whole-genome alignments — its numbers are a prior and HG002 through our bait chain is the printed number (V3); the bait-edge artefact it never evaluated gets its own control (V4) |
| Rentzsch et al. 2019, CADD, *NAR* (PMID 30371827) | [`predicting-the-deleteriousness…/`](predicting-the-deleteriousness-of-variants-throughout-the-human-genome/predicting-the-deleteriousness-of-variants-throughout-the-human-genome-analysis.md) | step 4 genotype LR | PHRED is a rank, not a probability (p. D889); validated missense-only, no stop_gained / splice / indel breakdown; hyperparameters tuned on ClinVar-vs-ExAC, so CADD and ClinVar are correlated evidence; build mislabelling by third parties (p. D892) — one calibrated tool per lane, CADD as tie-break, version + build recorded (L1) |

## Reading list for a later iteration — ranked

Every PMID verified in one E-utilities `esummary` batch on 2026-09-10 (two PMIDs the reviews
had quoted were wrong and are corrected here). The three former must-reads (Zemojtel 2014, Kong
2018, Kosugi 2019) were read on 2026-09-10 and moved to the table above. Each row names the plan
change it would unlock.

| # | Paper | PMID | Why it is worth an iteration |
|---|---|---|---|
| 4 | Yuan X et al. 2022. Evaluation of phenotype-driven gene prioritization methods for Mendelian diseases. *Brief Bioinform* | 35134823 | LIRICAL / Exomiser / PhenIX / AMELIE / Xrare recall-at-rank on two diagnosed cohorts — the external calibration for H012, H022 and H030 |
| 5 | Edge P, Bafna V, Bansal V 2017. HapCUT2. *Genome Res* | 27940952 | the second read-backed phaser; step 2's trans claim should not rest on one tool's block boundaries |
| 6 | Karczewski KJ et al. 2020. The mutational constraint spectrum quantified from variation in 141,456 humans. *Nature* | 32461654 | LOFTEE — the rule set for the protein-truncating lane CADD cannot grade; LOEUF for IHW |
| 7 | Pejaver V et al. 2022 (already in plan §8 C) | 36413997 | must be *read*, not cited: its Table 2 holds the CADD / REVEL / AlphaMissense-era bin edges the step-4 lane rule needs; the values fetched by script were inconsistent and are unverified |
| 8 | Kaplinski L et al. 2015. GenomeTester4. *GigaScience* | 26640690 | the set-algebra toolkit FastGT and GeneToCN are built on — `glistmaker` / `glistquery` / `glistcompare`; Linux build (`-lrt`) |
| 9 | Shen F, Kidd JM 2020. QuicK-mer2. *Genes* | 32013076 | paralog-sensitive alignment-free CNV — the alternative GeneToCN never benchmarks against; relevant for any target gene with a pseudogene |
| 10 | Schubach M et al. 2024. CADD v1.7. *NAR* | 38183205 | the model actually served today; whatever `warehouse.coding_annotations` holds is this, not the v1.4 the 2019 paper validates |
| 11 | Cameron DL et al. 2017. GRIDSS. *Genome Res* | 29097403 | the assembly-class SV caller Kosugi 2019 ranks top-tier for DEL/DUP — added to step 2 by plan §10 (V1); its method paper is not yet read |

Also verified, lower priority: Köhler 2009 Phenomizer (19800049), Smedley 2013 PhenoDigm
(23660285), Zhao 2020 Phen2Gene (32500119), Ignatiadis 2016 IHW (27240256), Deorowicz 2015
KMC 2 (25609798), Kimura & Koike 2015 (25609790), Nurk 2022 T2T-CHM13 (35357919), Sibbesen
2018 BayesTyper (29915429), Ebler & Marschall 2025 (40841174), Rentzsch 2021 CADD-Splice
(33618777). Preprint, DOI only: Ebler et al. 2026, rare-variant-aware genome inference,
10.64898/2026.06.29.735275.

## How a paper enters this folder

1. `papers/<iteration>/<slug>/` with the PDF (gitignored) and, via the `paper-analyst` skill,
   `<slug>-analysis.md` + `metadata.json` (tracked). `work/` stays local.
2. A review against the current plan: what the paper backs, where the plan misreads it, gaps,
   tools, figures, follow-ups with **verified** PMIDs, limitations for an N-of-1 case.
3. Every PMID re-checked in one `esummary` batch before it enters `plan.md` §8.
4. The plan's gap-review section records the change with the paper and page.
