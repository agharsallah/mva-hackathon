> **Archived 2026-08-29.** Superseded by `methodology/001`–`006`, which executed this
> exploration and measured it. Two values here are wrong: it says ~35–40× coverage and
> 2×151 reads; measured is 52× raw / 44× mapped and 2×149. Current findings live in
> `ideation/data-findings.md`. Never edited, never cited as current.

# Primary data exploration — the plan, before first contact with the files

*Formerly `ideation/hackathon-intel.md` §12.*


Inventory: 1 VCF (`WGS_EX2312012_HGWCNDSX7.vcf.gz`, 315 MB + .tbi) and 8 FASTQ (4 lanes × R1/R2, ~85 GB total). Everything below is read-only exploration — no alignment, no re-calling yet. Order matters: VCF first (minutes, holds the likely answer), FASTQ metadata second (minutes), heavy QC last (optional).

### 12.0 What the filenames already tell us (zero compute)

| Token | Meaning |
|---|---|
| `WGS` | Whole-genome sequencing (not exome) — intronic/intergenic variants ARE callable |
| `EX2312012` | Lab sample ID (likely 2023 accession) — probably the internal ID; VCF sample column may use this instead of `PROBAND01` → **check, submission needs `PROBAND01`** |
| `HGWCNDSX7` | Illumina flowcell ID; `DSX` pattern = NovaSeq 6000 **S4** flowcell — high-output clinical-grade run |
| `S16` | Position 16 on the sequencing sample sheet (multiplexed run) |
| `L001–L004` | 4 lanes, same library — merge freely, but keep lane-level read groups if realigning (per-lane QC catches lane failures) |
| ~85 GB gz total | ≈ 250–280 Gbp raw → **~35–40× mean coverage** on GRCh38 — enough for SV calling and low-VAF mosaic hunting |

### 12.1 VCF triage (first hour — tools: bcftools, tabix)

```bash
# 1. Header — the single highest-information command of the whole exploration
bcftools view -h WGS_EX2312012_HGWCNDSX7.vcf.gz | less
```
Extract from header: **sample name** (proband ID mapping), **caller + version** (`##source`: DRAGEN? GATK HaplotypeCaller? DeepVariant?), **reference** (`##reference` — confirm GRCh38, check chr-prefix style in `##contig` lines → must match submission format), **FILTER definitions** (what the pipeline considers PASS), **INFO/FORMAT fields** (is VEP/snpEff annotation already embedded? DP/AD/GQ available → VAF computable), and whether **SVs/CNVs** are included or SNV+indel only (DRAGEN sometimes ships separate SV VCF — if absent here, the SV blind spot is real → §3 trap).

```bash
# 2. Sample name + variant class census
bcftools query -l WGS_EX2312012_HGWCNDSX7.vcf.gz          # exact sample ID
bcftools stats WGS_EX2312012_HGWCNDSX7.vcf.gz > vcf.stats  # full QC panel
```
Read from `vcf.stats`: total records (~4.5–5.5 M expected for WGS), SNP/indel split, **ts/tv ≈ 2.0–2.1** (lower → noisy callset, re-calling more urgent), het/hom ratio (~1.5–2.0 genome-wide), indel length distribution, per-quality bins. Deviations = calibrate how much to trust the provided calls.

```bash
# 3. PASS discipline + chromosome coverage of the callset
bcftools view -H WGS... | cut -f7 | sort | uniq -c            # FILTER values in use
bcftools index -s WGS_EX2312012_HGWCNDSX7.vcf.gz               # records per contig
```
Per-contig counts confirm all chromosomes present (including chrX/chrY → **infer sex**: chrY variant count + chrX het rate) and expose the naming style actually used.

```bash
# 4. Normalize BEFORE any candidate extraction (§8.1 — exact-match scorer)
bcftools norm -f GRCh38.fa -m -both WGS... -Oz -o proband.norm.vcf.gz && tabix -p vcf proband.norm.vcf.gz
```

```bash
# 5. Immediate targeted strike — MVA genes (GRCh38 coordinates)
# BUB1B chr15:40,090,000-40,150,000 | TRIP13 chr5:892,000-930,000 | CEP57 chr11:95,790,000-95,850,000
bcftools view proband.norm.vcf.gz chr15:40090000-40150000   # BUB1B ± padding
bcftools view proband.norm.vcf.gz chr5:892000-930000        # TRIP13
bcftools view proband.norm.vcf.gz chr11:95790000-95850000   # CEP57
```
For each hit record: genotype (het/hom), DP, AD → **VAF = alt/(ref+alt)**, FILTER, quality. Two rare hets in one gene = pair hypothesis (§4 Phase 1). Verify exact gene coordinates against Ensembl GRCh38 before running — the ones above are approximate spans with padding.

### 12.2 MVA-specific signal: mosaic aneuploidy IS visible in this data

The disease itself (variegated aneuploidy, mosaic) leaves fingerprints — extracting them is both a sanity check and report material (rigor points):

- **Per-chromosome het VAF distributions** from the VCF: `bcftools query -f '%CHROM\t[%AD]\n' -i 'GT="het"'` → for a euploid chromosome, het VAF clusters at 0.5; a chromosome in mosaic trisomy/monosomy in a fraction of cells shifts the band (e.g. 0.33/0.67 bands appearing). Plot per chromosome → potential direct evidence of which chromosomes are aneuploid in the child.
- **Per-chromosome depth** (after alignment, or crudely from VCF DP medians per contig): mosaic gains/losses shift median DP by the mosaic fraction.
- Caveat: blood-derived DNA, mosaicism fraction may be modest — treat as soft signal. Proper tool once BAM exists: `mosdepth` per-chrom + `indexcov`.

### 12.3 FASTQ metadata (minutes, no heavy compute — tools: zcat/seqkit)

```bash
# Read headers: instrument, run, flowcell, lane, index sequences
zcat WGS_..._L001_R1_001.fastq.gz | head -8
# Read length + count per file (seqkit is fast, streams gz)
seqkit stats -a WGS_..._L001_R1_001.fastq.gz
```
Extract: **read length** (expect 2×151), instrument ID (`@A0xxxx` = NovaSeq), index/barcode (sample identity cross-check), reads per lane. Then coverage arithmetic: `total_read_pairs × 2 × 151 / 3.1e9` → confirm the ~35–40× estimate. This number goes in the methods form (Q17 runtime/cost credibility).

### 12.4 FASTQ quality QC (background job, not blocking — tools: fastp or FastQC)

```bash
# fastp on ONE lane pair in QC-only mode ≈ representative; full run on Modal later
fastp -i L001_R1.fastq.gz -I L001_R2.fastq.gz --disable_adapter_trimming \
      --json l1.fastp.json --html l1.fastp.html --reads_to_process 5000000
```
Extract: Q30 rate (clinical NovaSeq ≥ 90% expected), adapter content, duplication rate, GC (~41% human). Purpose: decide whether re-alignment needs trimming, and document data quality in the report. Not a gate for Phase 1 — VCF strike proceeds regardless.

### 12.5 Exploration output checklist (what we KNOW after ~1 day)

| Knowledge | Source | Feeds |
|---|---|---|
| Exact sample ID ↔ PROBAND01 mapping | VCF header/query -l | submission validity |
| Caller, reference, chr naming, PASS semantics | VCF header | normalization + trust level |
| Callset quality (ts/tv, counts, het/hom) | bcftools stats | re-call urgency |
| SVs included or absent | VCF header/records | whether §3 trap (missing second allele) is live |
| All variants in BUB1B/TRIP13/CEP57 + VAF/DP | targeted bcftools view | Probe S₁ candidate list |
| Child's sex | chrX/chrY variant pattern | phenotype interpretation |
| Mosaic aneuploidy fingerprint per chromosome | het VAF + DP distributions | diagnosis support, report rigor |
| Coverage (~35–40×), read length, Q30 | FASTQ headers + fastp | Modal sizing, methods form Q17 |
| Lane consistency | per-lane seqkit/fastp | read-group design for realignment |

Tool install (all conda/brew, no GPU): `bcftools htslib seqkit fastp` — heavy tools (bwa-mem2, DeepVariant, Manta) only needed at §4 Phase 2, on Modal.

