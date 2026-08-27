# Data Inventory — what we have, what's in it, how we use it

Companion to [hackathon-intel.md](hackathon-intel.md) (strategy) and [draft0-answers.md](draft0-answers.md) (method design).
This document is the *asset register*: every file we can touch, what it actually contains, and the concrete job it does for us.

Two buckets:

| Bucket | Location | Size | Status |
|---|---|---|---|
| **A. Challenge documents** | this repo, [ressources/hackathon-rules/](../ressources/hackathon-rules/) | ~83 KB | in git, always available |
| **B. Patient genomic data** | HF gated dataset `SageBio/mva-hackathon-2026-data` | ~85 GB, 10 files | **must never enter this repo** |

> **Hard rule:** bucket B is under a Data Transfer Agreement. No slice, no read, no variant dump from the patient data goes into git, into a public GitHub repo, into a screenshot, or into any external service. Derived summary statistics and *our own* candidate coordinates are what leave the perimeter — nothing else. Everything must be deleted within 30 days of hackathon close, and deletion confirmed by email to `RarediseaserealkidMVAhackathon2026@synapse.org`.

---

## Bucket A — Challenge documents (in repo)

### A1. `Challenge_Clinical_Phenotype_1.md` — the phenotype

The proband's clinical presentation, already encoded as HPO terms. This is the *entire* phenotype input; there is no separate phenopacket file.

| HPO ID | Term | Note from doc |
|---|---|---|
| HP:0002859 | Rhabdomyosarcoma | primary oncological event, triggered urgent investigation |
| HP:0000121 | Nephrocalcinosis | present since birth |
| HP:0004322 | Short stature | below expected for age *and family background* |
| HP:0001508 | Failure to thrive | repeatedly documented |
| HP:0003202 | Skeletal muscle atrophy | reduced muscle bulk |
| HP:0001622 | Premature birth | 32 weeks gestation |
| HP:0001518 | Small for gestational age | ~1 kg at birth (IUGR) |
| HP:0200067 | Recurrent spontaneous abortion | parental history, multiple losses |

**How we use it**

1. **Direct machine input.** These 8 IDs are the query vector for every phenotype-driven ranker — Exomiser, LIRICAL, AMELIE, Phen2Gene, phenotype-similarity over HPO. Write them once to a `phenotype/hpo_terms.txt` and never retype them.
2. **Prior sharpening.** `HP:0002859` (rhabdomyosarcoma) is the discriminating feature across MVA subtypes: BUB1B (MVA1) and TRIP13 (MVA3) carry cancer predisposition, CEP57 (MVA2) generally does not. The phenotype alone reorders our gene prior before we open a single variant.
3. **ACMG PP4 evidence.** "Phenotype highly specific for a disease with a single genetic etiology" — the co-occurring cluster (cancer + IUGR + nephrocalcinosis + parental reproductive loss) is what justifies PP4 in the written report.
4. **The miscarriage signal is data, not background.** The doc says so explicitly. Recurrent parental loss is consistent with aneuploidy-generating mechanisms — it argues for a chromosomal-instability gene and for *biallelic* inheritance (both parents carriers). Cite it in the report; it is free rigor points.
5. **Absent-feature reasoning.** Note what is *not* listed: no microcephaly, no reported intellectual disability. Classic BUB1B MVA1 usually has microcephaly. Do not let the prior override this — flag it as a genuine tension in the report rather than hiding it.

**What it does not give us:** no age, no sex, no ancestry, no karyotype/aneuploidy percentage, no parental sequencing. Sex must be inferred from the data (X/Y coverage or VCF chrX heterozygosity).

### A2. `track1_submission_template.csv` — the output contract

3 lines: header + 2 example rows. 12 columns.

```
proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes
```

| Column | Constraint that bites |
|---|---|
| `proband_id` | must be exactly `PROBAND01` — scorer rejects anything else |
| `chrom_1`/`chrom_2` | `chr`-prefixed, GRCh38 (`chr15`) |
| `pos_1`/`pos_2` | GRCh38 1-based VCF position |
| `ref_*`/`alt_*` | must string-match the answer key → **left-align and normalize with `bcftools norm` before writing**; an unnormalized indel is a silent miss |
| `*_2` group | fill only for compound-het pairs; blank = single-variant row |
| `epcr` | float in (0, 1]. Ties break by file order → always use strictly distinct descending values |
| `finding_type` | literally `primary` or `secondary` |
| `notes` | free text, unscored automatically, read by judges |

Max 10 rows. **How we use it:** this file is the schema our whole pipeline must terminate in. Build the emitter early and validate against this template locally (a mis-shaped CSV burns one of six oracle queries). Row layout strategy — pairs vs. singles as partial-match probes — is in [hackathon-intel.md §4 Phase 3](hackathon-intel.md).

### A3. `methods_description_form.xlsx` — the judging rubric in disguise

Two sheets (Track 1, Track 2), question/answer form, "up to 6 models". Voluntary, but the form itself states that submissions without it "may be judged less favorably on Innovation and Scalability."

Track 1 asks, verbatim in substance:

- describe model/approach in detail
- is the submission the **automated output** of the approach (*preferred*) or manually curated? describe any manual review
- **public data only** (*preferred*) or proprietary? describe each source
- **"Is your approach able to output proposed pairs of compound heterozygous candidate variants, or only single candidate variants?"**
- how were secondary/incidental findings handled?
- runtime and cost estimate
- 500-word method abstract with strengths *and limitations*

Track 2 mirrors it for drug repurposing: variant→mechanism→candidate reasoning, automated vs. manual literature review, public sources (DrugBank, ChEMBL, ClinicalTrials.gov, OMIM, PubMed), how the mechanism was characterized (LoF vs GoF, pathway, downstream consequence), effort estimate, 500-word abstract.

**How we use it:** treat it as the spec for the pipeline, not paperwork written afterwards. Three design decisions fall straight out of it:

- The pipeline must **emit the CSV automatically**, end to end. "Automated output (preferred)" is stated twice. Manual IGV curation is allowed but must be declared and costs us.
- The ranker must **natively propose pairs**, not singles that a human pairs up. They asked the question because it discriminates.
- Every external resource must be **public and logged**. Keep a machine-written `sources.md` with version/release date for gnomAD, ClinVar, VEP cache, HPO release — write it as the pipeline runs.
- Instrument runtime and cost from day one (wall clock + cloud spend per stage), because they ask for it and nobody else will have real numbers.

### A4. `raw_hackathon.txt` — site dump including backend source

58 KB scrape of the HF Space: README, about/story, tracks, prizes, timeline, FAQ, full official rules, **and the Python source of the submit tabs and scorer**. Fully mined in [hackathon-intel.md](hackathon-intel.md) — the exploitable content is the scoring internals (rank tiers, F-max sweep, per-submission oracle feedback returning `full_match_rank` / `partial_match_rank`) and the compound-het confirmation in the evaluation docstring.

**How we use it:** as the authority for anything procedural — submission mechanics, required GitHub URL prefix (`https://github.com/`), report format (`.pdf` or `.md` only), deadlines, deletion obligation. Do not re-derive rules from the website; quote this file.

---

## Bucket B — The 85 GB patient dataset

10 files. Decoding the naming: `WGS_EX2312012_HGWCNDSX7_S16_L00{1..4}_R{1,2}_001.fastq.gz`

| Token | Meaning |
|---|---|
| `WGS` | whole genome sequencing (not exome — non-coding and structural variation are in scope) |
| `EX2312012` | lab accession; the `2312` reads as Dec 2023 |
| `HGWCNDSX7` | Illumina flowcell ID. The `DSX` suffix is a NovaSeq 6000 **S4** flowcell |
| `S16` | sample 16 in a multiplexed run — our patient was pooled with 15 other samples |
| `L001`–`L004` | the four lanes of the S4 flowcell; the same library ran across all four |
| `R1` / `R2` | the two mates of each paired-end fragment |
| `001` | Illumina chunk counter, always 001 here |

### B1. `WGS_EX2312012_HGWCNDSX7.vcf.gz` (315 MB) + `.tbi` (2.34 MB)

Someone already ran the alignment and variant calling. This is the pre-computed answer sheet from the organizers' pipeline — a single-sample germline WGS VCF, bgzip-compressed and tabix-indexed.

Expect on the order of 4–5 M variants (typical single-sample WGS against GRCh38). 315 MB compressed is consistent with that.

**Unknown until we read the header** — first five minutes of work:

```bash
bcftools view -h WGS_EX2312012_HGWCNDSX7.vcf.gz | head -80
# answers: reference build + chrom naming, caller (##source), sample name (#CHROM line),
#          FORMAT fields available, whether ##contig lines are GRCh38 or hg19
bcftools stats WGS_EX2312012_HGWCNDSX7.vcf.gz > vcf_stats.txt   # counts, ts/tv, indel ratio
```

Three things to settle immediately, because each changes the plan:

1. **Build.** Submission coordinates must be GRCh38. Rules say GRCh38. If the header disagrees, everything needs liftover and error bars.
2. **Single-sample or trio?** If parental samples are in the VCF, phasing is free and compound-het confirmation is trivial. The file list shows one sample's FASTQ, so almost certainly single-sample — meaning **we cannot prove trans configuration from short reads alone** and must argue it from read-backed phasing or population logic. Say so honestly in the report.
3. **Already phased?** Look for `|` in GT and for `PS` or `HP` FORMAT fields. Read-backed phasing (WhatsHap) over the candidate gene is our fallback and is worth real rigor points for a compound-het claim.

**How we use it — this is where we start, not the FASTQ.**

- **Targeted strike first.** Extract the MVA panel — BUB1B (chr15q15.1), CEP57 (chr11q21), TRIP13 (chr5p15.33), plus CENPE, CEP192, SMC5 — before building anything general. `bcftools view -R panel.bed`. Minutes of work, and the prior says the answer is probably sitting there.
- **Normalize before comparing anything.** `bcftools norm -f GRCh38.fa -m -any` — split multiallelics, left-align indels. The scorer does string equality on ref/alt.
- **Annotate.** Ensembl VEP with an offline cache, plus gnomAD frequency, ClinVar, CADD/REVEL/SpliceAI plugins.
- **Genome-wide ranker in parallel.** Exomiser/LIRICAL with the eight HPO terms over the full VCF. Produces the scalability story the judges ask about, and catches a novel gene if the panel comes up empty.
- **Cheap remote querying.** The `.tbi` means we can pull a single gene's region over HTTPS range requests instead of downloading 315 MB — useful for a teammate who only needs to look at BUB1B.

### B2. Eight FASTQ files — the raw reads (~84.7 GB)

| Lane | R1 | R2 |
|---|---|---|
| L001 | 10.5 GB | 11 GB |
| L002 | 10.4 GB | 10.9 GB |
| L003 | 10.2 GB | 10.6 GB |
| L004 | 10.3 GB | 10.8 GB |

Balanced across lanes, R2 consistently slightly larger than R1 (normal — R2 quality is lower, so it compresses worse). This is one library sequenced across four lanes, which must be merged (or aligned per-lane with distinct `@RG` IDs and then merged) before calling.

Expected depth is roughly 30–40× PE150. Verify rather than assume:

```bash
# read length and count without decompressing everything
zcat L001_R1.fastq.gz | head -4
zcat L001_R1.fastq.gz | wc -l   # /4 = reads in this file
# depth ≈ (total_reads × read_length) / 3.1e9
```

**Why raw reads are provided when a VCF already exists.** This is the most important inference in the whole inventory. If the VCF alone contained both causal variants, giving us 85 GB of FASTQ would be pointless. The likely shape of the answer is the classic compound-het trap: **one easy coding SNV in the VCF, and one hard second allele that the standard pipeline missed** — a deep intronic splice variant, a structural variant or exon-level deletion, a variant in a repeat/low-mappability region, or a call filtered out for low quality.

**How we use them**

1. **Do not realign 85 GB first.** Full BWA-MEM alignment of 30× WGS is roughly 12–24 CPU-hours plus a 60–90 GB BAM. Start with the VCF.
2. **Targeted realignment.** Once the candidate gene is known, extract reads mapping to that locus and re-call there with DeepVariant, plus a structural-variant caller (Manta, Delly) and SpliceAI on the surrounding introns. Small compute, high yield.
3. **Read-backed phasing.** With reads over both candidate positions, WhatsHap can show whether they sit on the same read/fragment (cis, not causal) or opposite haplotypes (trans, compound het). This is the single strongest piece of evidence we can generate ourselves.
4. **Visual inspection.** IGV over BUB1B / TRIP13 / CEP57 to eyeball coverage dropouts (a homozygous deletion looks like a coverage hole) and soft-clipped read pileups (breakpoint signature).
5. **Don't skip the filtered calls.** Before re-calling, check whether the answer is already in the VCF but carrying a FILTER flag. Cheaper than any of the above.
6. **Mosaicism angle, if we're ambitious.** MVA means the child's cells carry *variable* aneuploidies. Read-depth analysis across chromosomes from the raw data could show mosaic aneuploidy directly in the blood sample. That is not the scored answer, but it is exactly the kind of finding that wins the Innovation award and enriches the Track 2 mechanism section.

### B3. What is *not* in the dataset

Worth stating explicitly, because each absence shapes the method:

| Missing | Consequence |
|---|---|
| BAM/CRAM | rules said "optionally" — not provided. Any alignment we want, we produce ourselves from FASTQ |
| Parental samples | no trio. De novo status cannot be established; phasing must be read-backed |
| RNA-seq / methylation | no transcriptome evidence to confirm a splice effect — SpliceAI prediction is as far as we can go |
| Karyotype / aneuploidy report | the defining MVA feature is not quantified for us; would have to be inferred from read depth |
| Sex, age, ancestry | infer from data; ancestry matters for correct gnomAD population frequency filtering |
| Ground truth | held server-side. The submit endpoint is the only channel to it — see the oracle strategy in [hackathon-intel.md §2.3](hackathon-intel.md) |

---

---

## Getting a representative slice of each file into the repo

Two scripts, one per bucket. Both are reproducible and neither puts patient sequence in git.

```bash
# Bucket A — split the site dump into addressable sections, xlsx -> markdown
tools/extract-rules.sh
#   -> ressources/hackathon-rules/extracted/   (10 files, ~58 KB total)

# Bucket B — profile the 85 GB without copying it
tools/profile-genomic-data.sh ~/mva-data/raw
#   -> ressources/data-profile/    committable summaries, ~100–500 KB
#   -> ~/mva-data/work/            panel extract + smoke sample, LOCAL ONLY
```

The split between the two destinations is the whole point: headers, contig lists, field
inventories and aggregate counts describe the dataset well enough to plan against, and
contain no patient genotype. Per-artifact contents, expected sizes and runtimes are in
[ressources/data-profile/README.md](../ressources/data-profile/README.md).

Bucket A's extraction is already run and committed — `evaluation.txt` and
`groundtruth.txt` hold the scorer source, `rules.txt` the official rules,
`track1-submit.txt` the submission contract, `methods_description_form.md` the judging
rubric in question form.

## Local readiness — current gaps

Checked on this machine:

- **The 85 GB is not on this machine.** Spotlight and filesystem search find no `WGS_EX2312012*`. Root volume has **44 GB free** — the raw dataset alone does not fit, let alone a BAM and intermediates.
- **No bioinformatics toolchain installed**: `bcftools`, `samtools`, `tabix`, `bwa`, `vep`, `nextflow`, `docker` all absent. Only `python3` is present.

Implications for the plan:

- Budget **~300 GB** of working space: 85 GB FASTQ + 60–90 GB BAM + reference + VEP cache (~25 GB) + intermediates. External drive or cloud volume, not the laptop root.
- The **VCF-first strike is entirely feasible locally** — 315 MB plus a VEP cache. Only the FASTQ work needs the big machine.
- Split the work accordingly: VCF triage and annotation local; alignment, SV calling and re-calling on Modal or equivalent, per [hackathon-intel.md §7](hackathon-intel.md).
- Install order: `brew install bcftools samtools htslib` first (they cover the VCF phase), Docker/Nextflow only when the FASTQ phase starts.

## Suggested on-disk layout (outside the repo)

```
~/mva-data/                    # gitignored, outside the git tree entirely
  raw/                         # the 10 downloaded files, read-only, never modified
  ref/                         # GRCh38 fasta + index, VEP cache, gnomAD, ClinVar
  work/                        # normalized VCF, panel extracts, BAM slices
  results/                     # ranked candidates, submission CSVs
```

The repo holds code, phenotype terms, documentation, and submission CSVs containing *our predictions only*. Nothing from `raw/` or `work/` is ever committed. Add a hard `.gitignore` guard plus a pre-commit check for `.vcf`, `.fastq`, `.bam`, `.cram` before the data ever lands.
