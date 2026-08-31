# Data findings — what is actually in the 85 GB

**Standing:** the **single owner of every measured number about the dataset**. Other
documents link here; none restate a value. Measured 2026-08-28, re-checked 2026-08-29
against the object-store inventory; §6.1 (panel annotation) added 2026-08-31. Evidence for how each number was produced is in the
[`methodology/`](../docs/step-0/methodology/) entry cited beside it.

Empirical companion to `data-inventory.md` (written before the files were opened, now in
[`archive/`](../archive/data-inventory.md)). Everything below was measured, not assumed.
Where a measurement contradicts an earlier assumption the contradiction is called out
explicitly.

Repository and infrastructure numbers — test counts, table counts, what is provisioned —
are **not** here; they belong to [`docs/current-state.md`](../docs/current-state.md).

Reproduce with `tools/profile-genomic-data.sh ~/ubuntu/data`. Committable summaries land
in [`ressources/data-profile/`](../ressources/data-profile/); patient-derived slices land
in `~/ubuntu/work/`, outside the repo.

---

## 1. Inventory

| File | Count | Size | What it is |
|---|---|---|---|
| `WGS_EX2312012_HGWCNDSX7.vcf.gz` (+`.tbi`) | 2 | 315 MB + 2.34 MB | The callset — 5,012,204 variants |
| `..._S16_L00{1..4}_R{1,2}_001.fastq.gz` | 8 | 8 × ~10.5 GB, 84.67 GB total | Raw reads, 4 lanes × paired ends |
| `Challenge_Clinical_Phenotype_1.docx` | 1 | 17 KB | Phenotype (transcribed to [`ressources/hackathon-rules/`](../ressources/hackathon-rules/)) |
| `README.md`, `.gitattributes` | 2 | 8 KB | HF dataset metadata |

**Delivery totals**, as counted in the object store
([`methodology/014`](../docs/step-0/methodology/014-source-of-truth-and-lineage.md)):

| | Value |
|---|---|
| Objects | **12** |
| Bytes | **84,985,953,378 — 84.99 GB** |
| Reads across the 8 FASTQ | **1,071,835,104** — exact census ([`methodology/023`](../docs/step-0/methodology/023-the-exact-read-census.md)) |
| Bases | **159.7 Gb** |

The "10 files" seen on disk and the 12 objects in the bucket are the same delivery counted
differently: the disk figure omits the HF `README.md` and `.gitattributes`, which are
dataset metadata rather than data. Both counts are correct for what they count.

There is **no BAM/CRAM**. Any read-level work means aligning 159.7 Gbases ourselves.

---

## 2. The five facts that change the plan

### 2.1 Contigs have no `chr` prefix — and the scorer will not fix that

```
##reference=file://refGenome/GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta
##contig=<ID=15,length=101991189>
```

The VCF says `15`. The submission template says `chr15`. The scorer compares chromosome
strings **verbatim, with no normalization** — it only `.strip()`s them. Copying a
coordinate straight out of the VCF into the submission is a silent, total miss that
still scores 0 while looking perfectly well-formed.

This is why `Variant.from_vcf()` exists and why nothing else in the codebase is allowed
to build a chromosome string by hand.

It also means every `bcftools` region query must use the bare contig (`-r 15:40140984-…`),
while the panel BED in the repo is chr-prefixed. Strip on the way in, add on the way out.

### 2.2 The sample is not called `PROBAND01`

```
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT   WGS_EX2312012
```

The VCF sample column carries the lab accession. Submissions are rejected unless
`proband_id` is exactly `PROBAND01`. The two identifiers are unrelated strings and the
mapping exists nowhere in the data — it is a convention of the challenge.

### 2.3 The callset is SNV + indel only. There are no structural variants.

The header records Sentieon Haplotyper 202308.02 → Sentieon GVCFtyper → GATK
`VariantFiltration`. That is a small-variant pipeline end to end. There is no SV or CNV
caller anywhere in the provenance chain, no `<DEL>`/`<DUP>` symbolic ALTs, no `SVTYPE`
INFO field.

**So the trap the strategy brief anticipated is real and live.** If one of the two causal
alleles is an exon deletion, a large insertion, or anything structural, it is *not in
this VCF at any FILTER level* and no amount of VCF analysis will surface it. That allele
can only come from re-calling the FASTQ — which is precisely why 80 GB of reads ship
alongside a 315 MB answer-shaped file.

### 2.4 Physical phasing exists, but reaches ~300 bp

770,458 records (15.4%) carry `PGT`/`PID`. That sounds like a lot, and it is not usable
the way it first appears. Sentieon phases variants only when they share read support, and
with a 266 bp insert size that means a few hundred bases.

Measured on the real BUB1B locus:

| | count |
|---|---|
| het calls in BUB1B | 58 |
| possible pairs | 1,653 |
| resolved **trans** by phasing | 3 |
| resolved **cis** by phasing | 2 |
| left **unknown** | 1,648 (99.7%) |

**Phasing is a confirmatory tool for neighbouring variants, not the discriminator.** With
no parental samples, the ranking must be carried by rarity and consequence; phasing then
kills a handful of cis pairs and promotes a handful of proven-trans ones. Any plan that
assumed phasing would collapse the search space was wrong.

The one case where phase comes free: a `1/2` multiallelic genotype. One copy of each ALT
means one per haplotype — compound heterozygosity proven by the genotype itself. There
are 66,860 such sites.

### 2.5 The VCF carries no annotation worth ranking on

`INFO` holds only caller statistics: `AC AF AN BaseQRankSum ClippingRankSum DB DP
ExcessHet FS InbreedingCoeff MLEAC MLEAF MQ MQRankSum QD ReadPosRankSum SOR`.

No VEP, no snpEff, no gnomAD frequency, no ClinVar, no CADD. Note especially that
`INFO/AF` is **within-sample** — with one sample it is 0.5 or 1.0 and carries no
population information at all. Reading it as a frequency filter would be a serious error.

The only usable raw annotation is the `DB` flag (dbSNP membership), a weak novelty proxy.
Everything else must be added by us — hence the `Annotator` port.

---

## 3. Callset quality

| Metric | Value | Reading |
|---|---|---|
| Records | 5,012,204 | normal for WGS |
| SNPs / indels | 4,086,641 / 930,181 | normal ratio |
| Multiallelic sites | 66,860 | **must `bcftools norm -m -both`** |
| ts/tv | 1.94 | slightly below the 2.0–2.1 ideal; acceptable, mildly noisy |
| het / hom-alt | 3,047,077 / 1,898,267 = 1.61 | normal, no gross contamination signal |
| PASS | 4,740,790 (94.6%) | |
| non-PASS | 271,414 (5.4%) | dominated by `MQ40` (177,522) and `QD2` (35,402) |

**The non-PASS records are a search space, not garbage.** 271k suppressed calls are a
cheap place to look for a second allele that the caller saw but did not trust — minutes
of work versus a day of re-calling. `MQ40` (low mapping quality) is exactly the filter
that fires in segmental duplications and repeats, where a real variant can hide.

TRIP13 illustrates this: only 12 variants across the gene and **6 of 12 are non-PASS**,
mostly `MQ40`, with alt depths of 2–6 reads. TRIP13 sits at chr5:872,848–939,357, close
to the telomere in difficult sequence. Low confidence there is a *coverage and mappability*
statement, not evidence of absence.

---

## 4. Raw reads

| Property | Value |
|---|---|
| Instrument | `A01973` — NovaSeq 6000, flowcell `HGWCNDSX7` (S4) |
| Layout | 4 lanes, paired end, one library (single index pair, redacted) |
| Read length | **2 × 149** (not 151) |
| Reads | **1,071,835,104** (~1.07 billion) — every read counted, not sampled |
| Bases | **159.7 Gb → 51.5× raw** |
| Mean mapped depth (from VCF `DP`) | **~44×** |
| Q30 | 92.9% (R1), 90.0% (R2) |
| Duplication | 9.3% |
| Insert size peak | 266 bp |
| GC | 41.4% — human, as expected |

**Per lane**, from the read store's `runs` table — R1 and R2 match exactly in every lane,
which is what a paired-end delivery must do:

| Lane | R1 = R2 reads | Lane total |
|---|---|---|
| 1 | 136,586,642 | 273,173,284 |
| 2 | 134,884,912 | 269,769,824 |
| 3 | 133,053,308 | 266,106,616 |
| 4 | 131,392,690 | 262,785,380 |
| **All** | | **1,071,835,104** |

**This supersedes the 1,079,858,785 previously carried here**, which
[`methodology/005`](../docs/step-0/methodology/005-fastq-structure-and-quality.md)
estimated by scaling a 200 MB slice and which overstated the truth by 0.74%. The estimate
was also **odd**, and a paired-end total cannot be — R1 must equal R2 in every lane.

51.5× raw against 44× mapped is a normal ~15% loss to duplicates and unmapped reads. This
is a good, clinical-grade dataset: 44× is comfortably enough for confident heterozygous
calls, for SV calling, and for a low-VAF mosaic scan.

The 266 bp insert is what caps physical phasing at a few hundred bases (§2.4), and it is
short enough that large SV breakpoint resolution will lean on split reads and
discordant pairs rather than spanning inserts.

---

## 5. What the data says about the child

### Sex: male

| | chr15 | chrX | chrY |
|---|---|---|---|
| het SNVs | 62,699 | 4,858 | 4,301 |
| mean depth | 44.4 | 41.4 | 36.3 |

chrX carries ~½ the variant density of an autosome and few heterozygous sites (those
concentrate in the pseudoautosomal regions), and chrY is present at real depth. This is a
hemizygous X and a present Y: **the proband is male.**

### No whole-chromosome mosaic aneuploidy detectable in this sample

Mosaic trisomy or monosomy in a fraction of cells shifts heterozygous allele balance off
0.5 and shifts median depth. Neither happens:

| | range across chr1–22 |
|---|---|
| mean het VAF | 0.472 – 0.497 |
| mean depth | 43.7 – 46.1 |

Every autosome sits on 0.5 balance at ~44×. chr20 and chr22 are marginally low (0.472,
0.473) but within GC-driven noise.

**This is a real finding and it needs care in the write-up.** MVA is diagnosed by
karyotype, typically on cultured lymphocytes or fibroblasts, and the aneuploid fraction
varies widely by tissue and by cell-division history. A bulk blood WGS sample showing no
aneuploidy signal does not contradict the diagnosis — it says the aneuploid fraction in
this DNA is below what allele balance can detect (roughly <10–15%). Stating that
explicitly, with the numbers, is stronger than staying silent about a negative result.

---

## 6. The MVA panel, measured

Counts from the real VCF over Ensembl GRCh38 gene spans + 20 kb padding.

| Gene | Locus | All | PASS | Note |
|---|---|---|---|---|
| **BUB1B** | chr15 | 80 | 76 | MVA1. 58 het, 23 hom-alt, 4 non-PASS |
| **CEP57** | chr11 | 13 | 13 | MVA2 |
| **TRIP13** | chr5 | 12 | **6** | MVA3. Half filtered — mappability, see §3 |
| CENPE | chr4 | 169 | 166 | atypical MVA |
| CEP192 | chr18 | 255 | 251 | candidate |
| SMC5 | chr9 | 125 | 124 | candidate |
| TP53 | chr17 | 120 | 118 | rhabdomyosarcoma differential |
| DICER1 | chr14 | 87 | 87 | rhabdomyosarcoma differential |

861 variants across the panel. Almost all are common intronic dbSNP entries — the gene
spans include introns, and BUB1B's 80 variants are overwhelmingly `DB`-flagged commons.
**Without annotation this table cannot be narrowed further**, which is the concrete reason
the annotation port is the next blocking dependency rather than a refinement.

Six BUB1B variants lack the dbSNP flag and are the only novelty signal available today.
That is a starting point, not a candidate list.

### 6.1 The panel, annotated (VEP REST, 2026-08-31)

The annotation gap above is now closed for the panel
([methodology 031](../docs/step-0/methodology/031-vep-rest-panel-annotation.md)):
861 sites split into **874 alleles** (13 multiallelic ALT splits), all 874 annotated via
Ensembl VEP REST (release 116, GRCh38) into `warehouse.panel_annotations`.

| Measured | Value |
|---|---|
| Alleles annotated | 874 of 874 |
| With a gnomAD frequency | 863 (11 novel) |
| With a ClinVar record | 56 |
| Impact | 850 MODIFIER · 13 MODERATE · 9 LOW · 2 HIGH |
| Distinct gene symbols hit | 18 (panel spans catch flanking genes) |

**The headline:** filtering to protein-altering (`impact ∈ {HIGH, MODERATE}`) **and** rare
(gnomAD AF absent or < 0.01, the recessive threshold) leaves **exactly two alleles, both in
BUB1B, both heterozygous, both PASS**:

1. `stop_gained`, HIGH impact, gnomAD AF 3.29e-05, already ClinVar
   `pathogenic;likely_pathogenic`.
2. `missense_variant`, MODERATE impact, **absent from gnomAD**, no ClinVar record.

That is the exact shape of a compound heterozygote in the strongest prior gene (MVA1).
**Phase is not established** — two `0/1` calls are equally consistent with *cis* — so this
is an observation, not a verdict. It belongs in the hypothesis register with a prediction
and a refutation condition before any probe is spent.

Population-reference context measured alongside
([methodology 030](../docs/step-0/methodology/030-population-reference-data.md)):
ClinVar (release 2026-08-29) holds 2,129 P/LP records across the panel genes (BUB1B 84);
gnomAD v4.1 constraint scores BUB1B pLI = 2.6e-14 and CEP57 pLI = 6.8e-06 — the recessive
carrier effect, which is why constraint must not be used to rank these candidates.

---

## 7. What this implies for the pipeline

1. **Annotation is the critical path.** Rarity (gnomAD) and consequence (VEP) are the
   discriminating signals. Nothing else in the VCF separates 861 panel variants into
   candidates. *Closed for the panel* (§6.1) — and it collapsed 874 alleles to 2
   candidates in one pass. Genome-wide annotation (offline VEP cache) remains open.
2. **Normalize before comparing anything.** 66,860 multiallelic sites and 930k indels,
   against a scorer that does exact string matching with no left-alignment. `bcftools
   norm -m -both -f <no-chr GRCh38>` is mandatory, and the reference must be the
   *no-chr* build to match the VCF.
3. **Budget for the FASTQ path from the start.** No SVs in the callset is not a
   maybe-later problem; if the second allele is structural it is the *only* path. 44×
   coverage makes it viable. Aligning 161 Gb is the largest compute item.
4. **Mine the 271k non-PASS calls before re-calling.** Minutes versus a day, and `MQ40`
   is exactly where a real variant in repetitive sequence gets suppressed.
5. **Treat phasing as a tiebreaker.** It resolves 0.3% of pairs. Useful, not structural.
6. **Report the negative aneuploidy result.** With numbers. It is rigor, not a gap.
