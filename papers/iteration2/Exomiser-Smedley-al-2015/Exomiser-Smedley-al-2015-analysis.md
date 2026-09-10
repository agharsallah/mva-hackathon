---
title: "Next-generation diagnostics and disease-gene discovery with the Exomiser"
authors: [Smedley Damian, Jacobsen Julius O.B., Jäger Marten, Köhler Sebastian, Holtgrewe Manuel, Schubach Max, Siragusa Enrico, Zemojtel Tomasz, Buske Orion J., Washington Nicole L., Bone William P., Haendel Melissa A., Robinson Peter N.]
year: 2015
venue: "Nature Protocols"
doi: "10.1038/nprot.2015.124"
arxiv: null
url: "https://doi.org/10.1038/nprot.2015.124"
paper_type: systems (lab protocol for a software tool)
domains: [computational biology, clinical genomics, rare disease diagnostics, gene prioritization, phenotype ontologies]
lens: bioinformatics
modes: [learn, apply]
code: "https://github.com/exomiser/Exomiser (current; paper-era code distributed via FTP as exomiser-cli-6.0.0, not GitHub)"
data: "Test VCF (Pfeiffer.vcf) + PED bundled with the tool; production run needs 1000 Genomes, ESP6500, dbNSFP, HPO, MGD/IMPC, ZFIN, STRING, OMIM/Orphanet — all bundled into a 5.5 GB H2/PostgreSQL database dump"
relevance: 5
analysed: 2026-09-09
analyst: paper-analyst
---

# Next-generation diagnostics and disease-gene discovery with the Exomiser

## Identity & citation

Damian Smedley, Julius O.B. Jacobsen, Marten Jäger, Sebastian Köhler, Manuel Holtgrewe, Max Schubach, Enrico Siragusa, Tomasz Żemojtel, Orion J. Buske, Nicole Washington, William P. Bone, Melissa Haendel, Peter N. Robinson. *Nature Protocols* 10(12):2004–2015, 2015. DOI: 10.1038/nprot.2015.124. Open-access copy: PMC5467691.

Nature Protocols is a peer-reviewed, top-tier methods journal (Nature Portfolio) — this is a *Protocol*, not a primary research article: its job is to be followed step-by-step, not to argue a novel finding.

```
APA 7:
Smedley, D., Jacobsen, J. O. B., Jäger, M., Köhler, S., Holtgrewe, M., Schubach, M., Siragusa, E.,
Zemojtel, T., Buske, O. J., Washington, N. L., Bone, W. P., Haendel, M. A., & Robinson, P. N. (2015).
Next-generation diagnostics and disease-gene discovery with the Exomiser. Nature Protocols, 10(12),
2004–2015. https://doi.org/10.1038/nprot.2015.124

BibTeX:
@article{smedley2015nextgeneration,
  title   = {Next-generation diagnostics and disease-gene discovery with the Exomiser},
  author  = {Smedley, Damian and Jacobsen, Julius O B and Jäger, Marten and Köhler, Sebastian and
             Holtgrewe, Manuel and Schubach, Max and Siragusa, Enrico and Zemojtel, Tomasz and
             Buske, Orion J and Washington, Nicole L and Bone, William P and Haendel, Melissa A and
             Robinson, Peter N},
  journal = {Nature Protocols}, volume = {10}, number = {12}, pages = {2004--2015}, year = {2015},
  doi     = {10.1038/nprot.2015.124}
}

Vancouver:
Smedley D, Jacobsen JOB, Jäger M, Köhler S, Holtgrewe M, Schubach M, et al. Next-generation
diagnostics and disease-gene discovery with the Exomiser. Nat Protoc. 2015;10(12):2004-2015.
doi:10.1038/nprot.2015.124
```

## Paper type & how to read it

This is a **lab-protocol / systems paper for a released software tool**: it packages a command-line pipeline for other labs to run. It owes the reader an installable tool, worked example with expected output at every step, troubleshooting for the failure modes users actually hit, and honest limitations — not a novel experimental result. The one quantitative claim borrowed from the tool's own validation paper (97% top-hit accuracy) is cited, not re-derived here, so it is read as a pointer, not first-hand evidence.

## One-minute pitch

An exome — the ~1–2% of the genome that codes for proteins — from a person with a suspected genetic disease typically contains over 30,000 differences from the reference genome. Only one (or two, for a recessive disease) of those is the actual cause; the rest are normal human variation. Exomiser is a command-line tool that takes that list of variants (a VCF file) plus a short list of the patient's clinical signs and symptoms, written as standardized codes (HPO terms), and produces a ranked list of candidate genes. It does this by first throwing out variants that are common in the general population or don't affect protein-coding sequence, then scoring what's left twice: once for how damaging the mutation looks (frequency + predicted pathogenicity), and once for how well the gene's known disease/mouse/fish phenotypes match the patient's symptoms — then multiplying the two into one combined score. In the worked example, this takes a list of 37,709 candidate variants down to a single correct answer (FGFR2, the Pfeiffer-syndrome gene) as the #1 hit in 90 seconds on a laptop.

**TL;DR:** Exomiser ranks candidate disease genes from a VCF by combining a variant-pathogenicity score with a phenotype-similarity score computed against human, mouse and zebrafish disease/model-organism data (or against a user-supplied "seed gene" list via a network random walk). In the authors' cited simulations it puts the true causal gene top in 97% of known-disease cases and 87% for novel disease-gene discovery. It is free, runs locally (no patient data leaves the hospital), takes ~15–90 s per exome, and — as of this analysis — is still actively maintained (last GitHub push 37 days before this write-up, current release v15).

## Domains & keywords

Field: Clinical genomics / medical genetics. Subfield: Mendelian disease diagnostics, computational disease-gene prioritization. Techniques: phenotype-similarity scoring (semantic similarity over ontologies), cross-species phenotype comparison, random walk with restart on a protein-protein interaction network, variant annotation (Jannovar), pathogenicity/frequency-based variant filtering. Tasks/data: rare-disease exome triage, Human Phenotype Ontology (HPO), Mouse Genome Database/IMPC, ZFIN, OMIM/Orphanet, STRING PPI network, 1000 Genomes, Exome Sequencing Project (ESP6500), dbNSFP (MutationTaster, PolyPhen2, SIFT).

## Problem & research questions

Gap claimed: ranking exome candidate genes purely by variant rarity and predicted pathogenicity is not enough — every genome carries ~100 genuine loss-of-function variants and ~20 fully inactivated genes, so pathogenicity alone leaves too many false positives; some way to fold in clinical relevance is needed. Implicit question: can a patient's phenotype (HPO terms) be combined with cross-species model-organism phenotype data and protein-interaction context to reliably surface the single causal gene out of hundreds of post-filter candidates, in a tool a hospital can run behind its own firewall? Thesis, in one sentence built from the abstract: Exomiser "prioritizes genes and variants in NGS projects for novel disease-gene discovery or differential diagnostics of Mendelian disease" by combining phenotype similarity, interactome proximity, and variant-level filters.

## Background primer [learn]

- **VCF (Variant Call Format).** A tab-separated record format: one row per genomic position where a patient's DNA differs from the reference, with columns for chromosome, position, reference/alternate allele, and per-sample genotype. Software-engineering analogue: a diff between the patient's genome and a reference "base branch," one line per changed position. This paper assumes VCF already exists — it starts *after* sequencing, alignment and variant calling (see "Alternative analysis packages").
- **HPO (Human Phenotype Ontology).** A controlled vocabulary of ~11,000 standardized terms for clinical signs and symptoms (e.g. HP:0001156 = Brachydactyly syndrome), each linked to which diseases and which genes are known to cause it. Analogue: an enum of clinical findings instead of free-text doctor's notes, so a symptom can be matched programmatically across species and databases.
- **Phenotype-driven gene prioritization.** The general idea (Moreau & Tranchevent 2012, ref. 14; the tool's own precursor is Köhler et al. 2008/2014, PhenoDigm) that instead of ranking candidate genes only by how "broken" their variant looks, you also rank by how well the gene's known disease/model-organism phenotypes match the patient's specific symptoms — because a gene can carry a rare damaging variant and still be the wrong gene if its known phenotype has nothing to do with the patient.
- Prerequisite reading, in order: (1) Köhler et al. 2008, *Am J Hum Genet* — introduces the HPO; (2) Köhler et al. 2009, *Am J Hum Genet* — Phenomizer, the semantic-similarity method PhenIX reuses; (3) Smedley et al. 2013, *Database* — PhenoDigm, the cross-species algorithm behind PHIVE; (4) Köhler et al. 2008, *Am J Hum Genet* 82 — the random-walk-with-restart interactome method behind ExomeWalker/hiPHIVE; (5) Zemojtel et al. 2014, *Sci Transl Med* — the original clinical validation this protocol's 97%/28%-extra-yield numbers come from.

## Method

**In plain language.** Feed Exomiser a VCF (and, for families, a pedigree file) plus a handful of HPO codes describing the patient. It throws out variants that are common, non-coding, or don't fit the suspected inheritance pattern, scores what survives for how damaging it looks, then re-scores each gene for how well its known disease/mouse/fish phenotypes match the patient's HPO terms (or how close it sits, in a protein-interaction map, to a user-given list of "genes we already suspect"). The two scores are multiplied into one number per gene, and genes are output ranked highest-first, as HTML for a clinician to read or TSV/VCF for a pipeline to consume.

**Technically.** Pipeline (Fig. 1): variant annotation against the UCSC hg19 transcript set via Jannovar (ref. 27); filtering removes off-target/synonymous variants, variants above a user-set minor-allele-frequency threshold (checked against 1000 Genomes + ESP6500), variants below a VCF QUAL threshold, and (for multisample VCF + PED file) variants inconsistent with the specified inheritance model (AD/AR/X-linked, including compound-heterozygous detection for AR). Variant score = combination of rarity + predicted pathogenicity (MutationTaster, PolyPhen2, SIFT via dbNSFP, ref. 51); for a gene with two heterozygous variants (compound het), the gene's variant score is the *average of the top two* variant scores — a detail worth knowing if using Exomiser's compound-het output on the MVA case (see Adaptation plan). Gene score is produced by one of four interchangeable prioritizers, chosen via the decision tree in Fig. 2: **PhenIX** (semantic similarity, human-only, restricted to the ~3,101 genes with known Mendelian disease association; Phenomizer algorithm); **PHIVE** (semantic similarity against mouse knockout phenotypes, MGD + IMPC, PhenoDigm algorithm; ~33% gene coverage at time of writing); **hiPHIVE** (PHIVE + zebrafish ZFIN data + human OMIM/Orphanet data, falling back to a STRING-network random walk with restart, ref. 20, for genes with no phenotype data in any source — "tool of choice" per the authors when the causal gene could be known or novel); **ExomeWalker** (no phenotype input at all — random walk with restart from a user-supplied seed-gene list, for genetically heterogeneous "disease-gene families"). Variant and gene scores are combined via a logistic-regression model into one ranking score. Compute: ~3 GB RAM, 15–90 s per exome on a standard desktop; distribution is a 1.2 GB CLI jar plus a 5.5 GB H2 (or PostgreSQL) database dump of all integrated reference data, versioned as a unit so results are reproducible against a stated data-release.

## Figures & tables check

| Fig/Table | Page | What it shows | Claim it supports | Verdict | Note |
|---|---|---|---|---|---|
| Fig. 1 | 2 | Pipeline schematic: VCF/PED → Jannovar annotation → filter/rank by pathogenicity → 4 alternative prioritizers → ranked genes | Overview of the method (no data) | OK | Correctly illustrative-only; verified against body text, matches exactly |
| Fig. 2 | 4 | Decision tree for choosing PhenIX/PHIVE/hiPHIVE/ExomeWalker by data availability | Guidance, not an empirical claim | OK | Matches body text describing the same tree |
| Fig. 3 | 5 | Screenshot of Exomiser HTML output for the worked FGFR2/Pfeiffer example, scores annotated | Worked-example claim ("FGFR2 top hit, combined score 0.993") | OK | Numbers in the screenshot match the "Anticipated results" text exactly (0.9933) |
| Table 1 | 9 | Troubleshooting table (install errors, OutOfMemory, wrong candidate) | N/A — operational guidance | OK | Standard protocol troubleshooting, not a scientific claim |

No recomputation needed: this is a protocol, not a benchmark paper — the only numbers are the worked example's own reported scores, and they are self-consistent between the figure, the info-column example (`EXOMISER_GENE_COMBINED_SCORE=0.99334514`) and the anticipated-results text (0.9933).

## Claims vs evidence

| # | Claim (paper's wording, short) | Evidence offered | Where | Strength | Analyst note |
|---|---|---|---|---|---|
| C1 | hiPHIVE finds the correct variant as top hit in 97% of simulated known-disease cases | Cited from the tool's own prior validation paper (Zemojtel et al. 2014) | Body text, ref. 5 | moderate | Not re-run in this paper; it's a citation, not first-hand evidence in this protocol |
| C2 | 87% top-hit rate for simulated *novel* disease-gene discovery (known association masked) | Cited, ref. 45 (Bone et al., "in the press" at time of publication) | Body text | weak | Reference was unpublished at submission time; not independently checked here |
| C3 | Worked example: FGFR2 ranks #1 of 892 post-filter genes for the Pfeiffer-syndrome test VCF, across all four prioritizer modes tried | Actual command output shown (combined scores 0.993 hiPHIVE, 0.998 PhenIX, 0.989 ExomeWalker; row 31/95 with no phenotype data at all) | "Anticipated results" section, Fig. 3 | strong | Directly reproducible by the reader — this is the paper's one piece of first-hand evidence, on n=1 spiked example |
| C4 | ~15–90 s runtime, ~3 GB RAM on a "standard desktop" | Stated as a fact, not benchmarked with numbers/hardware spec in this paper | Abstract, "Timing" section | weak | No hardware spec, no repeated trials, no variance — an assertion, not a benchmark |
| C5 | Clinical WES adds 28% additional diagnostic yield in patients already extensively worked up | Cited from Zemojtel et al. 2014 | Intro | moderate | Again a citation to the tool's separate validation study, not evidence generated here |
| C6 | Running locally avoids "data security issues involved in sending patient data to a web server" | Asserted architectural benefit | Discussion | strong (as an architecture fact) | True by construction (self-hosted jar + local DB) — not an empirical claim needing a citation |

## What works

- The one thing demonstrated first-hand (not cited from elsewhere): on the bundled Pfeiffer-syndrome test case, every phenotype-aware mode (hiPHIVE, PhenIX, ExomeWalker) puts the true causal gene at rank 1 out of 892 post-filter candidates, and even the no-phenotype baseline (Step 2D) still recovers it at rank 31/95 — i.e., pathogenicity/frequency filtering alone already does a lot of the narrowing, and phenotype data closes the rest of the gap. This n=1 result is consistent with, and illustrates, the larger validation numbers (C1/C2) cited from the separate Zemojtel et al. study.
- Architecturally: filtering alone (frequency + off-target + inheritance pattern) is stated to cut ~37,700 variants to ~1,200 in the worked example — a concrete, checkable number from real tool output, not a simulation.

## What doesn't work (or isn't shown)

- No benchmark against competitor tools is run *in this paper* (Phevor, eXtasy, Phen-Gen, PhenIX's own competitors are only named in the discussion, refs. 67–70) — head-to-head numbers live in other papers, not here.
- No statement of what happens when the patient's true causal gene has *no* mouse/fish/human phenotype annotation at all under PHIVE/PhenIX (only hiPHIVE's random-walk fallback is described as covering that case) — readers aren't shown a worked example of that failure mode.
- No handling of copy-number variants or larger structural variants — stated explicitly as a limitation, not silently absent.
- No batch/runtime numbers on a modern large VCF (e.g. whole-genome-derived variant sets) — the timing numbers are exome-only and single-sample.

## Limitations

**Stated by the authors.**
- Mendelian disease only — searches for a single causal gene, not polygenic or oligogenic explanations.
- Coding + splice-consensus regions only; no CNV/structural-variant support (beta ExAC integration and gVCF support flagged as future work).
- Mouse phenotype coverage only ~33% of protein-coding genes at time of writing (IMPC targeting near-complete by 2021 — worth checking whether that materialized, since it directly affects PHIVE's recall).
- Underlying data sources (dbSNP, 1000 Genomes, HPO, model-organism DBs) "may still contain inaccuracies or omissions that can change from release to release," which changes Exomiser's performance release to release.
- Pedigree filtering intended only for small/simple families (trios, nuclear families) — explicitly not validated for larger pedigrees, where linkage analysis is recommended first.

**Not stated (analyst).**
- The one worked example is a single *spiked* case (known disease mutation inserted into an otherwise-unaffected exome), not a real diagnostic-uncertainty case — real patients can have incomplete penetrance, phenocopies, or two candidate genes both plausible under HPO overlap, none of which this protocol's example touches.
- No discussion of what a *tied* or *near-tied* top score means for the user's next action, which matters a lot for an N-of-1 workflow that must commit to one candidate.
- No version-pinning guidance for reproducibility across releases beyond "use the same or higher DB version" — for a diagnostic tool whose score changes with each data release, this is a bigger reproducibility gap than the paper treats it as (lens sec. 4/6).
- 2015-era software distribution (5.5 GB H2 DB, FTP download, Java 7, `exomiser-cli-6.0.0.jar`) is already stale relative to the current GitHub-hosted, Spring-Boot-based v15 — the CLI flags and file layout described in this protocol (Boxes 1–4, `--settings-file`, `application.properties`) will not match current usage 1:1 (see Code & data below).

## Validity, bias & reproducibility

**Internal validity.** The protocol's own demonstrated result is a single positive-control example (a known disease mutation spiked into a normal exome) — it shows the pipeline runs and ranks correctly on an easy case, not that it discriminates well on hard cases; the harder claims (97%/87%/28%) are imported from a separate publication and not re-derived here, so their validity rests on that paper, not this one. **External validity.** Explicitly restricted to Mendelian, coding-region disease; cross-species phenotype data (mouse/fish) generalizes only as far as those model organisms' phenotype annotation is complete (stated ~33% mouse coverage) — for a disease gene with no model-organism knockout phenotype recorded, PHIVE/hiPHIVE's phenotype-driven advantage over the no-phenotype baseline shrinks toward hiPHIVE's random-walk fallback. **Reporting.** No seeds/variance reported (not applicable — deterministic ranking), but no hardware spec for the 15–90 s timing claim, and no explicit reference-data version number quoted as the one used for the worked example beyond "database file is currently 5.5 GB" and jar version 6.0.0. **Conflicts of interest.** Declared but not detailed in the main text ("details are available in the online version") — several authors are the same people who develop/maintain the tool, standard for a methods-paper-about-your-own-tool but worth naming.

**Reproducibility score: 3/5** — the exact worked-example VCF/PED files ship with the tool and the CLI commands are given verbatim, but the reference database is a versioned 5.5 GB external download not itself archived alongside the paper (only "current version" pointers to an FTP mirror that has since moved to GitHub Releases), and the paper-era version (6.0.0, H2 DB, FTP distribution) is no longer what a fresh install gets — the single biggest obstacle to reproducing *this paper's exact numbers today* is that the reference data (1000 Genomes, dbNSFP, HPO, MGD/IMPC snapshots) has moved on through several releases since 2015, and only the current v15 is realistically installable.

## Related work & key citations

**Foundations**
- Köhler et al. 2008, *Am J Hum Genet* 82:949–958 — "Walking the interactome" — random-walk-with-restart method behind ExomeWalker/hiPHIVE's fallback. Read this to understand the network-proximity scoring.
- Köhler et al. 2009, *Am J Hum Genet* 85:457–464 — Phenomizer — the semantic-similarity engine PhenIX reuses for human-only phenotype matching.
- Smedley et al. 2013, *Database* bat025 — PhenoDigm — the cross-species (mouse) phenotype-similarity algorithm behind PHIVE.
- Zemojtel et al. 2014, *Sci Transl Med* 6:252ra123 — the actual clinical validation study this protocol's headline 97%/87%/28% numbers come from. **Read this next**, first, before trusting C1/C2/C5.

**Competitors / baselines** (named in Discussion, not benchmarked here)
- Phevor (Singleton et al. 2014), eXtasy (Sifrim et al. 2013), Phen-Gen (Javed et al. 2014) — other phenotype-driven prioritizers; useful for a "why not just use X" comparison the paper itself doesn't run.
- ANNOVAR (Wang et al. 2010), Ensembl VEP (Cunningham et al. 2015) — pure annotation tools Exomiser is explicitly *not* competing with (they don't rank candidates).

**Data & tools**
- Jannovar (Jäger et al. 2014) — the variant-annotation library Exomiser depends on.
- HPO (Köhler et al. 2014/2008) — the phenotype vocabulary the whole clinical-matching side of the tool depends on; this is also the vocabulary the MVA case's own clinical dataset uses (`ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`), so it is a shared input, not just a citation.
- STRING v9.05 (Franceschini et al. 2013) — the protein-interaction network behind ExomeWalker/hiPHIVE's fallback.

## Impact & follow-ups

Citation counts as of 2026-09-09: **483 (OpenAlex)**, **425 (Crossref)** — high for a methods/protocol paper, consistent with Exomiser being a widely adopted clinical-diagnostics tool over a decade. Semantic Scholar's influential-citation count and citing-paper list were unreachable this session (HTTP 429 rate limit) — **impact section is metadata-partial**; the citation counts and open-access link are OpenAlex/Crossref-sourced and verified, but which citing papers are "influential" is unverified. The tool itself is still actively developed (current v15, GitHub `exomiser/Exomiser`, last push 37 days before this analysis) — a decade-plus of continuous maintenance is itself a strong impact signal independent of citation count.

## Code & data

**Availability.** Official repo: `https://github.com/exomiser/Exomiser` (Java, Maven build; the paper-era 2015 distribution was FTP-hosted `exomiser-cli-6.0.0-distribution.zip`, now superseded — GitHub is the current home, confirmed by the README's install instructions matching current Spring-Boot/CLI structure, not the FTP/H2 layout described in this paper). AGPL-3.0 licence (copyleft — a derivative tool built on Exomiser's code, not just its output, would need to be released under the same terms; this matters if considering embedding rather than just running it as a CLI). 265 stars, 67 forks, 157 open issues/PRs, pushed 2026-08-03 (37 days before this analysis) — actively maintained, not abandoned. Reference data: versioned H2/PostgreSQL database dumps, several GB, distributed via the project's own release channel (paper says FTP; current releases are documented on ReadTheDocs at `exomiser.readthedocs.io`) — a licence/access restriction check on the current data bundle was not performed this session (unverified).

**Completeness (heuristic, from `inspect_repo.py` — confirm by opening files).**

| Item | Status | Evidence |
|---|---|---|
| Dependencies declared | yes | Maven `pom.xml` per module |
| Training script | n/a | Not a trained model — rule-based/statistical scoring, not ML training |
| Evaluation script | no (heuristic) | No benchmark/eval script detected by filename scan; may exist under a name the heuristic missed |
| Pretrained models/weights | n/a | No weights — reference data (H2/PG dump) plays the equivalent role |
| Results table in README | no | README documents usage, not benchmark numbers |
| Tests | 0 detected at top level by the heuristic scan (likely undercounted — Java test files exist under `src/test/java` per the file tree, e.g. `Hg19ConfigTest.java`) | `structure.tests` empty but `config_files` list shows multiple `*Test.java` files |

**Paper-to-code consistency.** Not checked line-by-line this session (no clone performed) — the CLI flags shown in the paper (`--prioritiser=hiphive`, `--hpo-ids`, `--max-freq`, `--ped`, `--settings-file`, `--batch-file`) are 2015-era (jar `exomiser-cli-6.0.0.jar`); current v15 usage should be checked against `exomiser.readthedocs.io` before assuming these flags are unchanged — **flagged as unverified, do not copy-paste the paper's commands into a current install without checking the current docs first.**

**Dry run.** Not attempted this session (no clone; would require downloading the multi-GB reference database, out of scope for a paper-analysis pass) — skipped by design, not by failure. If picked up for `apply`, the dry run is the very first thing to do, using the tool's own bundled `Pfeiffer.vcf` test case exactly as this paper describes, before pointing it at the MVA case's real VCF.

## Concept-to-code map [learn + apply]

| Concept in the paper | Where it (likely) lives in current code | Reading note |
|---|---|---|
| Variant annotation (Jannovar) | External dependency, not in this repo — `exomiser-data-genome` module configures it (`JannovarFactoryConfig.java`) | Confirm current Jannovar version pin before trusting hg19/hg38 transcript consistency |
| Filtering (frequency, quality, inheritance/compound-het) | `exomiser-core` (not enumerated by the heuristic scan — needs a clone to locate exact classes) | Compound-het scoring rule ("average of top two variant scores per gene") is the one paper-stated implementation detail worth grepping for by name in the codebase before relying on it for the MVA case's compound-het hypothesis |
| PHIVE/PhenIX/hiPHIVE/ExomeWalker prioritizers | `exomiser-core/.../prioritisers/` package (named in `TestDataSourceConfig.java` path) | Four interchangeable strategies — confirm which is default in current CLI/YAML config before running |
| REST API for prioritization | `exomiser-rest-prioritiser` module (present in top-level tree) | Not described in this 2015 paper (CLI-only then) — a newer surface worth checking if programmatic (non-CLI) access is wanted |

## Adaptation plan [apply]

Directly relevant to Track 1 (identify the causal compound-heterozygous pair): the MVA case already has both inputs Exomiser needs — a callset (VCF) and 8 HPO terms (`ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`) — so this is a near-direct fit, not a stretch adaptation.

1. **Keep as-is:** the overall pipeline shape (filter by frequency/inheritance → score by pathogenicity → re-rank by phenotype similarity) — this is exactly the two-source (genomic + clinical) cross-referencing the project's standing directive already requires; Exomiser is a ready-made implementation of that cross-reference, not a new methodology to justify.
2. **Swap:** (a) inheritance mode — set `-I AR` (or the current-version equivalent) since MVA's target is a compound-heterozygous pair, not AD/X-linked; (b) HPO term list — the case's own 8 terms, not the paper's 4-term Pfeiffer example; (c) reference build — confirm whether the callset is hg19 or hg38 and match Exomiser's data bundle accordingly (the paper is hg19-only; current versions support hg38).
3. **What will break first:** (a) CLI syntax mismatch — the paper's `--prioritiser=hiphive --hpo-ids ... --vcf ...` flags are v6.0.0-era; check `exomiser.readthedocs.io` for current CLI/YAML config before running; (b) reference-build mismatch, which silently produces wrong annotations rather than an error — verify build match first; (c) compound-het scoring's "average of top two variant scores" detail interacting with the project's own register-based confidence weighting (`mva-science verdict`) — Exomiser's combined score is a separate, non-calibrated heuristic and should not be quoted as a probability, same caveat this project already applies to its own scoring.
4. **Compute/time estimate:** reference database download and load is the dominant cost (several GB, one-time); actual scoring run is 15–90 s per mode per VCF per the paper — cheap enough to run all four prioritizer modes (hiPHIVE, PhenIX, PHIVE, ExomeWalker-if-seed-genes-available) as a minimum viable experiment and compare rankings before committing further analysis time.
5. **Risks:** AGPL-3.0 licence — fine for using the CLI as an external tool (no linking/embedding), would matter only if code from Exomiser were vendored into this project's own codebase; data-version drift (the bundled reference DB changes what "top hit" means release to release — record the exact DB/release version used, per this project's own lineage-tracking directive, in the `methodology/` entry that runs this); and the paper's own stated limitation that Exomiser doesn't reason about CNVs/SVs — irrelevant if MVA's causal variants are SNVs/indels, worth flagging if not.

## Glossary

- **Compound heterozygous** — two different damaged copies of the same gene, one inherited from each parent, together causing a recessive disease neither parent has. Directly relevant: MVA's causal genotype under investigation.
- **HPO (Human Phenotype Ontology)** — a controlled vocabulary of standardized clinical-symptom terms (e.g. HP:0001156), each linked to which diseases/genes cause it. Role here: the input format for the patient's clinical picture; same standard the MVA clinical dataset uses.
- **Jannovar** — a Java library that maps raw genomic positions to gene/transcript-level consequences (e.g. missense, nonsense). Role: Exomiser's first annotation step, upstream of all filtering.
- **MAF (minor allele frequency) filter** — removes variants above a user-chosen population-frequency threshold, on the assumption a common variant can't cause a rare disease. Role: the main volume-reduction filter (37,709 → 1,181 variants in the worked example).
- **PED file** — a tab-separated pedigree/family-structure file (who's related to whom, who's affected). Role: required input for multisample, inheritance-pattern-aware filtering (including compound-het detection).
- **PhenIX / PHIVE / hiPHIVE / ExomeWalker** — Exomiser's four interchangeable gene-scoring strategies: human-only known-disease genes (PhenIX), mouse-only cross-species (PHIVE), mouse+fish+human combined with a network-proximity fallback (hiPHIVE), and pure protein-network proximity to a user-given seed-gene list with no phenotype input at all (ExomeWalker). Role: the paper's core contribution — choosing among them is Fig. 2's decision tree.
- **Random walk with restart** — a network-proximity scoring method: simulates a random walker on the protein-interaction graph that occasionally "teleports" back to a seed gene, so genes structurally close to the seed accumulate higher visit-scores. Role: powers ExomeWalker and hiPHIVE's no-phenotype-data fallback.
- **VCF (Variant Call Format)** — a tab-separated file format, one row per genomic position where a sample differs from the reference, with genotype columns per sample. Role: Exomiser's primary input.
- **wGC-style combined score** — Exomiser's own logistic-regression combination of a variant score (rarity + predicted pathogenicity) and a gene score (phenotype/network similarity) into one ranking number per gene. Role: what the ranked output is sorted by; explicitly *not* a calibrated probability.

## Open questions & extension ideas

Authors' stated future work: ExAC integration (beta at time of writing — worth checking if that's now standard in v15), gVCF format support.

Own extension ideas for this project:
1. Run hiPHIVE, PhenIX and (if a plausible MVA-related seed-gene list exists, e.g. known aneuploidy/mitotic-checkpoint genes) ExomeWalker independently on the case's VCF+HPO terms and compare rankings — do they converge on the same candidate gene(s), which is itself evidence; do they disagree, which narrows *where* to invest manual review.
2. Cross-check whichever gene(s) Exomiser ranks highest against the project's own register (`mva-science hypothesis-add`) — Exomiser's score is one more *sourced* piece of evidence, not a replacement for the register's sourcing discipline.
3. Specifically test the compound-heterozygous inheritance filter (`-I AR`) against the case's parent/child trio structure via a PED file — this is the one feature in the paper built exactly for the MVA scenario (two different heterozygous variants, one per parent, present in the affected child).
4. Questions for the authors (if reachable): what is the current (non-2015) top-hit accuracy for compound-heterozygous cases specifically, isolated from single-variant AD/X-linked cases in the original 97% figure? And has IMPC's "near-complete mouse phenotype coverage by 2021" target actually been reached, given PHIVE's recall depends on it?

## Confidence notes

- Citation-count and impact section: **partial** — OpenAlex (483) and Crossref (425) counts obtained; Semantic Scholar (citation count, influential-citations, citing-paper list) failed with HTTP 429 (rate limit) and was not retried. Treat "who builds on this and how" as unverified beyond what the paper's own Discussion names.
- Code section: repo health (stars/forks/licence/last-push) verified live via GitHub API; paper-to-code CLI-flag consistency and the five-item completeness checklist are **heuristic only** — no clone, no dry run performed this session (explicitly out of scope: multi-GB reference database download).
- All numeric claims in Claims-vs-evidence table are either read directly off the PDF text/figures (verified) or explicitly marked as imported from a cited paper not re-checked here (C1, C2, C5) — do not upgrade those to "strong" without reading Zemojtel et al. 2014 directly.
- "Current v15" and "37 days since last push" are live facts as of 2026-09-09 (this analysis's run date), not facts stated in the 2015 paper — flagged inline throughout to avoid conflating 2015-era and current tool state.
