> **Archived 2026-08-29.** Superseded by `docs/decisions.md` (its §0.1 recommendation matrix) and `docs/roadmap.md` (its §12.2 still-open list). Numbers here predate later runs and may be wrong; `ideation/data-findings.md` owns them now. Never edited.

# draft0 — Answered

Companion to `draft0.md` (open questions) and `hackathon-intel.md` (strategy/intel).
Scope: every question in `draft0.md`, answered with concrete tools, schemas, math, and limitations.
Status of facts: biology/tooling = literature-grounded; **dataset internals are now measured, not inferred.**
Every dataset claim below traces to [`ressources/data-profile/`](../ressources/data-profile/) — committable
aggregate summaries (headers, counts, distributions; no variant record, no read sequence) of the gated 85 GB —
with the interpretation in [data-findings.md](data-findings.md) and per-question reproduction notes in
[`methodology/`](../methodology/). Claims that the pre-data version got wrong are marked **[was wrong]** next to
the correction, because those corrections change the plan rather than merely refine it.

### Revision log — the six measurements that changed decisions

| # | Pre-data assumption | Measured reality | Consequence |
|---|---|---|---|
| 1 | BAM/CRAM optionally shipped | **No BAM, no CRAM.** 85.0 GB = 1 VCF (+index) + 8 FASTQ + a phenotype `.docx` + a dataset README | Every read-level question starts with us aligning 161 Gbases. Realignment moved from insurance policy to required infrastructure (§1.1, §1.5) |
| 2 | VCF is `chr`-prefixed GRCh38 | Contigs are **bare** (`15`, not `chr15`); reference is the `…_no_chr` no-alt analysis set + hs38d1 decoys | `bcftools -r 15:…` on the way in, `chr15` on the way out. A coordinate copied straight from the VCF into the submission scores 0 while looking well-formed (§1.3, §5.1) |
| 3 | ~30× WGS | **52× raw / ~44× mapped**, 2 × 149 bp, 4 lanes, one library, NovaSeq 6000 | Enough depth for confident hets, for SV calling, and for a low-VAF mosaic scan (§1.2) |
| 4 | Phenotype ≈ microcephaly + intellectual disability + neoplasm | **Rhabdomyosarcoma, nephrocalcinosis, short stature, failure to thrive, skeletal muscle atrophy, 32-week prematurity, ~1 kg SGA, parental recurrent miscarriage.** Microcephaly and intellectual disability are *not* among the reported terms | The gene prior must be re-derived from the real terms, and the rhabdomyosarcoma differentials (*TP53*, *DICER1*) are now first-class panel members, not footnotes (§1.4, §3.4) |
| 5 | Read-backed phasing would collapse the compound-het space | On *BUB1B*: 1,653 candidate pairs → **3 trans, 2 cis, 1,648 unknown (0.3% resolved)**; reach ≈ a few hundred bp | Phasing is a tiebreaker, not the discriminator. Rarity + consequence must carry the ranking (§5.4, §10.1) |
| 6 | The provided VCF might already carry usable annotation | `INFO` is caller statistics only — no VEP, no gnomAD, no ClinVar, no CADD. `INFO/AF` is **within-sample** (0.5 or 1.0) and carries zero population information | Annotation is the critical path and the one blocking dependency. Reading `INFO/AF` as a frequency filter would be a serious, silent error (§2.1, §7.2) |

A seventh measurement is a *negative* result worth stating early: **there is no whole-chromosome mosaic
aneuploidy detectable in this sample** (§3.5). That does not contradict the diagnosis — it bounds it.

---

## 0. Executive summary (read this if nothing else)

| Question | One-line answer |
|---|---|
| Data type | Paired-end short-read WGS on GRCh38 (`no_chr` no-alt analysis set + hs38d1 decoys): 8 FASTQ (4 lanes × R1/R2, 2 × 149 bp, ~52× raw) + one germline VCF of 5,012,204 SNV/indel records + an HPO table in a `.docx`. **No BAM/CRAM, no SVs in the callset.** 85.0 GB, single subject, VCF sample column `WGS_EX2312012` (**not** `PROBAND01`). |
| Visualize / query | Query: yes, today — `bcftools`/`tabix` + VEP → Parquet → DuckDB SQL. Visualize reads: **not until we align the FASTQ ourselves** — IGV, mosdepth and samplot all need a BAM that was never shipped. HPO DAG via `pyhpo`/`oaklib` works now. |
| What is MVA | Autosomal-recessive chromosome-missegregation syndrome: 25–50% of somatic cells carry random gains/losses ("variegated"). Caused by biallelic loss of spindle-assembly-checkpoint / centrosome genes. Microcephaly, growth failure, cancer predisposition. |
| Literature access | Yes, fully open: PubMed E-utilities, Europe PMC, PubTator3, OMIM/GeneReviews/Orphanet, ClinVar, OpenAlex. Papers are public; the *patient data* is not — never mix them in a public repo. |
| Data structures | Canonical variant tuple `(chrom, pos, ref, alt)` → columnar variant table (Parquet/DuckDB) + interval index over gene models + HPO DAG + candidate-pair `frozenset` mirror of the scorer + append-only oracle ledger. |
| Open-source models | Callers (DeepVariant, Clair3, Manta/Delly/GRIDSS, GATK-gCNV, ExpansionHunter), effect predictors (CADD, REVEL, AlphaMissense, ESM-2/ESM1b, EVE, SpliceAI, Pangolin, AbSplice, ReMM, AlphaGenome, Evo 2), prioritizers (Exomiser, LIRICAL, AMELIE, Phen2Gene, GADO). Main limitations: ClinVar circularity, missense-only coverage, gene-level ≠ allele-level, poor non-coding calibration, no mosaicism model. |
| Statistical / math models | Bayesian ACMG point framework, LIRICAL-style likelihood ratios, Hardy–Weinberg carrier priors, binomial/beta-binomial for VAF & mosaicism, HMM for CNV segmentation, and — for submission strategy — adaptive group testing / sequential experimental design maximizing information gain per oracle query. |
| ML model families | Learning-to-rank (LambdaMART/XGBoost-rank) over annotated candidates, calibrated classifiers for `epcr`, PU-learning (only positives labeled), sequence/protein deep models as frozen feature extractors, GNN over a gene–phenotype–variant knowledge graph, LLM agents for literature triage. **No in-patient training: N = 1.** |
| Evaluation | Rank metrics (top-1, recall@k, MRR), F-max (the official metric — reimplement it), PR-AUC over ROC-AUC (extreme imbalance), calibration (Brier/ECE) because `epcr` is a probability, validated on synthetic probands built by spiking ClinVar pathogenic pairs into public control genomes (GIAB/1000G). |
| Deterministic vs probabilistic | Both, layered: deterministic = variant canonicalization, Mendelian/zygosity logic, phase-based exclusion, set algebra of the scorer; probabilistic = genotype likelihoods, Bayesian causality posterior, phenotype LRs, calibrated ranking. Deterministic layer shrinks the space; probabilistic layer orders what survives. |
| Aneuploidy visible? | **No.** Mean het VAF 0.472–0.497 and mean depth 43.7–46.1 across every autosome — flat. Below what allele balance can detect (≈<10–15% aneuploid fraction) in this bulk blood DNA. Report the negative with the numbers. |
| Proband sex | **Male**, from the data: chrX carries ~½ autosomal variant density with few hets (4,858, PAR-concentrated), chrY present at real depth (36.3×, 4,301 hets). |
| Own DB? | **No new curated database.** Reuse ClinVar / gnomAD v4 / HPO / OMIM / dbNSFP / VEP caches, and build only a thin local analytical store (one DuckDB file + Parquet) that is itself a *derived dataset* and must be deleted within 30 days of close. |

### 0.1 Recommendation matrix (best option per question, one line each)

| # | Question | ⭐ Recommended option | Why it beats the alternatives |
|---|---|---|---|
| 1 | Data handling | Headers-first checklist (**done** — §1), then **mapping-free k-mer strike** on FASTQ for published MVA alleles, with the alignment job launched in parallel on day 1 | Detects a known allele in minutes with no alignment; and with no BAM shipped, alignment is a 1–2 day dependency that must start immediately rather than on trigger |
| 2 | Query/visualize | DuckDB+Parquet for SQL, `slivar` for comp-het logic, igv-reports for evidence | Zero infra, deterministic, reproducible; dashboards are week-3 luxuries |
| 3 | Disease model | Soft Bayesian gene priors, **flattened** against the measured phenotype (*BUB1B* 0.40, not 0.55), never hard gene exclusion | Rhabdomyosarcoma still favours *BUB1B*, but the absent microcephaly removes the strongest MVA1-specific term and promotes the *TP53*/*DICER1* differentials — and a hard filter was always the classic trap |
| 4 | Literature | Automated **reported-allele catalogue** (PubTator3/LitVar2 + ClinVar) joined against the VCF, LLM triage on top | A published-allele match is a near-instant solve; join is mechanical |
| 5 | Data structures | Scorer-identical dataclasses + DuckDB + **probe simulator** with bitmask hypothesis space, plus one contig-namespace conversion (`15` → `chr15`) in exactly one place | The simulator turns probe design into computed optimization, not judgment; the namespace conversion is a measured, live scoring bug if done by hand |
| 6 | Models | Tiered escalation: **free tier (non-PASS + `1/2` sites)** → standard stack → raw-data rescue (now unconditional) → foundation models | Tier 1.5 is minutes and targets the "caller saw it and suppressed it" world; Tier 1 solves the published-allele scenario; Tier 2 is the only source of SV evidence that will ever exist; deep models only pay on a miss |
| 7 | Statistics | Bayesian ACMG posterior as `epcr` backbone; greedy info-gain probe policy | Defensible arithmetic in the report; decode tables are already near-optimal |
| 8 | ML | Reciprocal-rank fusion primary + LLM evidence-tournament re-ranker (audited) | Robust at N=1, transparent, and the agentic layer is the Innovation story |
| 9 | Evaluation | Local scorer reimplementation + GIAB spike-in probands + read-level spiked alleles | Only honest pre-oracle measurement; class-sensitivity table exposes blind spots |
| 10 | Det. vs prob. | Deterministic shrink → probabilistic rank → decision-theoretic probe | Soundness first, efficiency second; filters logged with removal counts |
| 11 | Database | No new DB; thin DuckDB layer; optionally publish the public-only "N-of-1 toolkit" | Reproducibility + Scalability points without curation liability |

---

## 1. What is the type of the data?

*Measured, not inferred. Evidence: [`ressources/data-profile/`](../ressources/data-profile/);
reproduction: `tools/profile-genomic-data.sh ~/ubuntu/data`; methodology entries
[001](../methodology/001-vcf-provenance-and-structure.md), [002](../methodology/002-callset-quality-and-composition.md),
[005](../methodology/005-fastq-structure-and-quality.md).*

### 1.1 The actual inventory

12 objects, **85.0 GB (79.1 GiB)** — `manifest.tsv`:

| File(s) | Size | What it is |
|---|---|---|
| `WGS_EX2312012_HGWCNDSX7.vcf.gz` + `.tbi` | 315 MB + 2.3 MB | Germline small-variant callset, **5,012,204** records |
| `…_S16_L00{1..4}_R{1,2}_001.fastq.gz` | 8 × ~10.5 GB = **84.7 GB** | Raw reads: 4 lanes × paired ends |
| `Challenge_Clinical_Phenotype_1.docx` | 17 KB | Phenotype — an HPO table in Word, transcribed to [`Challenge_Clinical_Phenotype_1.md`](../ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md) |
| `README.md` | 5 KB | Hugging Face dataset card |

**[was wrong] There is no BAM and no CRAM.** The pre-data version listed aligned reads as
"optionally present". They are absent. FASTQ is 99.6% of the payload, and *every* read-level
question — IGV evidence panels, SV/CNV calling, per-exon depth, read-backed phasing beyond what
the caller already emitted, the low-VAF mosaic scan — begins with us aligning 161 Gbases. That is
now the largest single compute item in the project and it is on the critical path for the report,
not just for the rescue tier.

So the three modalities, corrected:

| Modality | Format, as delivered | Role in the analysis |
|---|---|---|
| Raw reads | FASTQ, gzipped, 4 lanes × R1/R2. **Not aligned.** | The only source of SVs, CNVs, mosaic VAFs, and any read-level evidence. Requires alignment first. |
| Called variants | VCF, bgzip+tabix, GRCh38 `no_chr`, **SNV + indel only** | Primary hunting ground for the small-variant half of the pair |
| Phenotype | 8 HPO terms in a `.docx` table, with free-text notes | Gene priors, Exomiser/LIRICAL input, differential framing |

### 1.2 Sequencing shape and depth

`fastq_profile.tsv`, `fastq_qc_L001.tsv`, `fastq_read_headers.tsv`:

| Property | Measured | Reading |
|---|---|---|
| Instrument / flowcell | `A01973` (NovaSeq 6000), `HGWCNDSX7` (S4) | Standard clinical WGS run |
| Layout | 4 lanes, paired end, **one library** (single index pair) | Lanes are technical replicates — merge them; no multi-library batch effect |
| Read length | **2 × 149** (not 151) | Off-by-two matters for adapter and trimming configs |
| Reads / bases | ~1.08 billion reads, **160.9 Gb** | |
| Raw coverage | **51.9×** | |
| Mapped depth (from VCF `DP`) | **~44×** | ~15% loss to duplicates + unmapped — normal |
| Q30 | 91.5% before filtering, 92.2% after | Good |
| Duplication | 9.3% | Normal for PCR-free-ish clinical WGS |
| Insert size peak | **266 bp** | This is what caps read-backed phasing at a few hundred bases (§5.4) |
| GC | 41.4% | Human, no contamination signal |
| Adapter-trimmed reads | 32,746 / 1,000,000 sampled | Low; light trimming suffices |

**[was wrong] This is 52× raw / 44× mapped, not the ~30× the size estimate implied.** Practical
consequences, all favourable: 44× is comfortably enough for confident heterozygous calls, viable for
SV calling from split reads and discordant pairs, and enough to give a mosaic scan real power at
VAF ≳ 0.10 inside a small, prior-justified region (§7.4).

The strategic point from the pre-data version survives intact and is now confirmed: this is **WGS, not
WES**, so non-coding, deep-intronic and structural second alleles are in scope.

### 1.3 VCF provenance and the two identity traps

`vcf_header.txt`, `vcf_fields.tsv`, `vcf_contig_counts.tsv`:

```
##reference=…/GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta
##contig=<ID=15,length=101991189>
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT   WGS_EX2312012
##SentieonCommandLine.Haplotyper=<Version="sentieon-genomics-202308.02", …>
##SentieonCommandLine.GVCFtyper=<Version="sentieon-genomics-202308.02", …>
##GATKCommandLine=<ID=VariantFiltration, Version="4.2.4.0", Date="February 5, 2025">
```

**Trap 1 — the contig namespace. [was wrong]** The VCF says `15`. The submission template says `chr15`.
The scorer compares chromosome strings verbatim; it only `.strip()`s them. A coordinate copied straight
out of the VCF into a submission is a silent, total miss that still validates as well-formed CSV. Every
`bcftools` region query uses the bare contig (`-r 15:40140984-40241137`); the panel BED in this repo is
`chr`-prefixed. **Strip on the way in, add on the way out**, in exactly one place in the code
(`Variant.from_vcf()`), never by hand.

1,690 contigs are declared: 25 primary (`1`–`22`, `X`, `Y`, `M`) + 40 `_random` + 108 unplaced `Un_` +
1,517 hs38d1 `_decoy`. No alt contigs. 116,485 records (2.3%) sit off the primary assembly and are
noise for our purposes.

**Trap 2 — the sample identifier.** The VCF sample column carries the lab accession `WGS_EX2312012`.
Submissions are rejected unless `proband_id` is exactly `PROBAND01`. The two strings are unrelated and
the mapping exists nowhere in the data — it is a convention of the challenge.

**The callset is SNV + indel only.** Sentieon Haplotyper → Sentieon GVCFtyper → GATK `VariantFiltration`
is a small-variant pipeline end to end. There is no SV or CNV caller anywhere in the provenance chain,
no `<DEL>`/`<DUP>` symbolic ALTs, no `SVTYPE`. **The trap the strategy brief anticipated is real and
live:** if either causal allele is an exon deletion, a large insertion, or anything structural, it is
*not in this VCF at any FILTER level*, and no amount of VCF analysis will surface it. That allele can
only come from re-calling the FASTQ — which is precisely why 85 GB of reads ship alongside a 315 MB
answer-shaped file.

**The VCF carries no annotation worth ranking on. [was wrong]** `INFO` holds caller statistics only:
`AC AF AN BaseQRankSum ClippingRankSum DB DP ExcessHet FS InbreedingCoeff MLEAC MLEAF MQ MQRankSum QD
ReadPosRankSum SOR`. No VEP, no snpEff, no gnomAD, no ClinVar, no CADD. Note especially that `INFO/AF`
is **within-sample** — with one sample it is 0.5 or 1.0 and carries no population information at all.
The only usable raw annotation is the `DB` flag (dbSNP membership), a weak novelty proxy. Everything
else we must add ourselves, which is why annotation is the blocking dependency (§2.1).

Callset quality, from `vcf_stats_summary.txt` and `vcf_filter_gt_counts.tsv`:

| Metric | Value | Reading |
|---|---|---|
| Records | 5,012,204 | Normal for WGS |
| SNPs / indels | 4,086,641 / 930,181 | Normal ratio |
| Multiallelic sites | 66,860 | **`bcftools norm -m -both` is mandatory** |
| ts/tv | 1.94 | Slightly below the 2.0–2.1 ideal; acceptable, mildly noisy |
| Genotypes: `0/1` / `1/1` / `1/2` | 3,047,077 / 1,898,267 / 66,860 | het:hom-alt = 1.61 — normal, no gross contamination |
| PASS | 4,740,790 (94.6%) | |
| non-PASS | 271,414 (5.4%) | Dominated by `MQ40` (177,522) and `QD2` (35,402) |
| Records with `PGT`/`PID` | 770,458 (15.4%) | Physical phasing — see §5.4 for what it is actually worth |

**The 271k non-PASS records are a search space, not garbage.** They are calls the caller *saw* and did
not trust. `MQ40` (low mapping quality) is exactly the filter that fires in segmental duplications and
repeats, where a real variant hides. Mining them is minutes of work versus a day of re-calling, and it
comes before Tier 2 in the escalation order (§6.4).

### 1.4 Phenotype data shape — the real terms

**[was wrong]** The pre-data version guessed microcephaly / intellectual disability / small-for-gestational-age
/ neoplasm. Four of eight guessed terms are wrong, and the two most load-bearing MVA1 features are not in
the document at all. The delivered terms:

| HPO ID | Term | Note from the document |
|---|---|---|
| `HP:0002859` | Rhabdomyosarcoma | Malignant soft-tissue tumour — the oncological event that triggered urgent investigation |
| `HP:0000121` | Nephrocalcinosis | Calcium deposits in kidney tissue; **present since birth** |
| `HP:0004322` | Short stature | Significantly below expected for age and family background |
| `HP:0001508` | Failure to thrive | Documented repeatedly; poor weight gain from early life |
| `HP:0003202` | Skeletal muscle atrophy | Reduced muscle bulk alongside failure to thrive |
| `HP:0001622` | Premature birth | Born at 32 weeks |
| `HP:0001518` | Small for gestational age | ~1 kg at birth — severe IUGR |
| `HP:0200067` | Recurrent spontaneous abortion | Multiple parental pregnancy losses before the proband's birth |

Absent from the list: **microcephaly** (`HP:0000252`) and **intellectual disability** (`HP:0001249`) — the
two features most associated with MVA1 in the literature. Read that carefully: the document is titled
*"Clinical Features Leading to Diagnosis"*, so it is the referral-triggering subset, not a complete
phenotype. Their absence is weak evidence, not a rule-out — but it must not be silently overwritten by a
textbook MVA profile when computing phenotype likelihood ratios. Run the pipeline on the terms actually
given, and if a candidate gene requires microcephaly to fit, say so as an open discrepancy.

The document also flags `HP:0200067` explicitly as *phenotypic input, not background* — reproductive loss
is a direct read-out of a chromosome-instability mechanism in the parents. Whether the HPO term for a
parental feature belongs in the proband's term set is a real modelling decision (most tools assume proband
terms); the defensible handling is to score both with and without it and report the delta.

Handle all of these as *DAG nodes with ancestor closure*, never as strings: similarity requires walking the
ontology (Resnik/Lin/Phenomizer information-content measures, §7.3).

### 1.5 Solution space & ⭐ recommendation

The three attack routes, re-costed against what was actually delivered:

- **Option A — headers-first, VCF-only.** *Done; this section is its output.* It bought the six corrections
  in the revision log for ~10 minutes of compute. What it cannot do is finish: the VCF has no annotation to
  rank on and no SVs to find, so A terminates at "861 panel variants, mostly common intronic dbSNP entries".
- **Option B — mapping-free k-mer strike.** Build k=31 signatures for *every allele ever reported* in the MVA
  genes (ClinVar + OMIM allelic tables + literature-mined variants, §4) and scan the FASTQ directly,
  MALVA/jellyfish-style. **This got more attractive, not less:** with no BAM, alignment is a day of compute,
  and a k-mer scan needs none. If the child's allele is already published — plausible for *BUB1B*, where
  recurrent alleles exist — this finds it in minutes even though the VCF cannot contain it (SV) or did not
  trust it (non-PASS). Same trick doubles as alignment-free verification: count REF-kmers vs ALT-kmers
  spanning a site → crude VAF straight from FASTQ.
- **Option C — full realignment + re-calling (bwa-mem2 → DeepVariant, on Modal).** **[was wrong — this is no
  longer optional.]** It was scoped as the insurance policy for a novel hard allele. With no BAM shipped it is
  the *only* path to SVs, to per-exon depth, to IGV evidence panels for the report, and to any phasing beyond
  the caller's 266 bp reach. 161 Gb at 44× is real money and a day of wall-clock; start it now, in the
  background, so it is finished before it is needed.

**⭐ Recommendation: B immediately (hours, highest information-per-hour), C started in the background today
because it is on the critical path for the report regardless of how the search resolves, and A already banked.**
Before either, mine the 271k non-PASS calls in the panel genes — minutes of work, and it targets exactly the
"caller saw it and suppressed it" world that sits between A and C.

---

## 2. Can we visualize it? And query it?

Yes to both. Build two separate stacks — an *interactive inspection* stack and an *analytical query* stack —
because they answer different questions.

### 2.1 Query stack (the workhorse)

Pipeline: **VCF → normalize → annotate → columnar → SQL**

Two measured constraints bind this pipeline before a single command runs. **The reference must be the
`no_chr` build** — `GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta`,
the one named in the VCF header — or `bcftools norm` will silently fail to match contigs. And **the panel BED
in this repo is `chr`-prefixed while the VCF is not**, so the BED is stripped on the way in (§1.3, trap 1).

```bash
# 0. contig namespace: repo BED (chr15) -> VCF namespace (15)
sed 's/^chr//' ressources/data-profile/mva_panel_grch38.bed > panel_nochr.bed

# 1. canonicalize (critical for scorer string-equality matching)
#    66,860 multiallelic sites and 930,181 indels make -m -both mandatory, not hygienic
bcftools norm -f GRCh38_no_chr.fa -m -both -c w calls.vcf.gz -Oz -o norm.vcf.gz
bcftools index -t norm.vcf.gz

# 2. targeted extraction: MVA + SAC/centrosome panel first (minutes, not days)
#    -f PASS is deliberately absent: 271,414 non-PASS calls are a search space (§1.3)
bcftools view -R panel_nochr.bed norm.vcf.gz -Oz -o panel.vcf.gz

# 3. annotate (Ensembl VEP, offline cache + plugins)
vep -i norm.vcf.gz -o annotated.vcf --cache --offline --assembly GRCh38 \
    --vcf --everything --canonical --symbol --hgvs --af_gnomadg \
    --plugin CADD,... --plugin SpliceAI,... --plugin AlphaMissense,... \
    --plugin REVEL,... --plugin dbNSFP,...

# 4. flatten to a columnar table
bcftools +split-vep annotated.vcf -d -f '%CHROM\t%POS\t%REF\t%ALT\t%SYMBOL\t%Consequence\t...\n' \
  > variants.tsv     # → convert to Parquet
```

Steps 3–4 are the blocking dependency, not a refinement: with `INFO` carrying caller statistics only (§1.3),
**nothing in the delivered VCF separates the 861 panel variants into candidates.** Rarity (gnomAD) and
consequence (VEP) are the only discriminating signals available, and both have to be joined in by us.

Then query with **DuckDB** directly over Parquet — zero-server, SQL, fast on 5,012,204 rows:

```sql
SELECT chrom, pos, ref, alt, symbol, consequence,
       gnomad_af, cadd_phred, revel, alphamissense, spliceai_max
FROM 'variants.parquet'
WHERE symbol IN ('BUB1B','TRIP13','CEP57','CENPE','CEP192','SMC5','BUB1','BUB3','KNL1')
  AND coalesce(gnomad_af, 0) < 1e-3
ORDER BY cadd_phred DESC;
```

Alternatives, and when they earn their cost:
- **Hail** — genuinely valuable at cohort scale; overkill for N = 1, but a defensible "scalability" story.
- **GEMINI / slivar / vembrane** — expression-based VCF filtering; `slivar` is excellent for compound-het logic.
- **pysam / cyvcf2** — programmatic access for anything the CLI can't express; `cyvcf2` is the fast one.
- **`bcftools query`** — good enough for 90% of interactive questions; do not over-engineer before you have hits.

### 2.2 Visualization stack

| What you need to see | Tool |
|---|---|
| Reads over a candidate locus (the decisive human check) | **IGV** desktop on BAM/CRAM; `igv.js` for a shareable, screenshot-friendly report figure — **blocked until we align the FASTQ ourselves (§1.1)** |
| Per-exon / per-base coverage (single-exon deletions) | **mosdepth** + a simple matplotlib/Altair coverage track — **also blocked on alignment** |
| Sequencing / alignment QC | **FastQC/fastp → MultiQC** (runs on FASTQ today), `samtools stats` (needs a BAM), `bcftools stats` plots (done — §1.3) |
| Genome-wide CNV / aneuploidy view | Binned depth (mosdepth 10–100 kb) → log2 ratio plot; this is also how you *look for the aneuploidy itself* |
| SV inspection | **samplot** or IGV split-read/discordant-pair view; `svtools`/`AnnotSV` for tabular SV annotation |
| Gene/transcript context, domains | Ensembl / UCSC browser, UniProt feature viewer, AlphaFold structure + PyMOL/py3Dmol for residue mapping |
| Phenotype context | HPO term set vs disease profiles; a simple similarity heatmap makes a strong report figure |

Two visualization payoffs specific to MVA:
1. **A per-chromosome allele-balance chart — already computed, and it is a negative result.**
   `vcf_chrom_allele_balance.tsv` measures mean heterozygous VAF and mean depth per chromosome straight from
   the VCF, no alignment needed. A mosaic trisomy at fraction *f* shifts het VAF off 0.5 by ≈ *f*/(2+*f*) and
   shifts median depth; neither happens. Mean het VAF ranges **0.472–0.497** across chr1–22 and mean depth
   **43.7–46.1**. chr20 (0.472) and chr22 (0.473) are marginally low and within GC-driven noise. **No
   whole-chromosome mosaic aneuploidy is detectable in this sample** — see §3.5 for how to say that honestly.
   A binned-depth karyogram from aligned reads would push the detection floor lower and remains worth doing
   once Tier 2 produces a BAM; the allele-balance version is the free first pass and it is already done.
2. **IGV panels for the two final alleles.** The report is a tiebreaker (`hackathon-intel.md` §4 Phase 4);
   read-level screenshots of both alleles, plus the phasing evidence, is what a clinical reviewer wants to see.
   **Compliance:** screenshots of patient reads are patient data — they go in the report submitted to organizers,
   **never** into the public GitHub repo (`raw_hackathon.txt` data-resharing clause).

### 2.3 Solution space & ⭐ recommendation

- **Option A — DuckDB + Parquet + `slivar`** (as above): SQL analytics + expression-based comp-het filtering.
- **Option B — team dashboard**: a small Streamlit/marimo app over the DuckDB file (candidate table, filters,
  per-gene coverage, oracle-ledger view) + **igv-reports** for static, self-contained HTML locus views the whole
  team can open without a running IGV. Good for 3-person coordination once candidates exist.
- **Option C — Hail / Spark**: cohort-scale machinery. At N = 1 it buys nothing except a Scalability paragraph.
- **Option D — pure CLI (`bcftools query` + grep)**: fastest to first answer, unmaintainable past ~day 3.

**⭐ Recommendation: A as the backbone, D for hour-one questions, B only after the candidate list exists
(week 2+), C never executed — cite it as the documented scale-out path in the methods form.** Rationale:
the bottleneck is biological interpretation, not query throughput; every hour of infra before the first
panel-gene query is a strategic loss. Confirmed by the data: hour-one CLI work (D) produced §1 in its
entirety, and the measured blocker is annotation, not throughput. igv-reports is still worth the 30 minutes,
but note it is now **downstream of the alignment job**, so schedule it accordingly rather than assuming a
BAM exists.

---

## 3. What is MVA?

### 3.1 Definition

**Mosaic Variegated Aneuploidy (MVA)** is an ultra-rare, autosomal-recessive chromosome-instability syndrome.
Cytogenetic hallmark: a substantial fraction of somatic cells — classically **25–50%** — carry *different*
random whole-chromosome gains and losses (trisomies, monosomies, double trisomies). "Mosaic" = only a subset of
cells; "variegated" = the aneuploidy differs from cell to cell, i.e. it is generated continuously rather than
inherited as one constitutional event.

Diagnosis is made cytogenetically (karyotype of peripheral-blood lymphocytes and/or skin fibroblasts showing
multiple distinct aneuploidies across cells), then confirmed molecularly.

### 3.2 Mechanism

The causal genes all sit in the machinery that guarantees faithful chromosome segregation:

- The **spindle assembly checkpoint (SAC)** delays anaphase until every kinetochore is correctly attached to the
  mitotic spindle. Its effector is the **mitotic checkpoint complex (MCC)** = BUBR1 (*BUB1B*) + BUB3 + MAD2 + CDC20,
  which inhibits the **APC/C** ubiquitin ligase. Loss of SAC strength → premature anaphase → missegregation.
- **Centrosome/centriole integrity** (*CEP57*, *CEP192*, *PLK4*) governs bipolar spindle assembly; defects cause
  multipolar divisions and merotelic attachments.
- ***TRIP13*** (a AAA+ ATPase, also called PCH2) recycles MAD2 between its open and closed conformers; biallelic
  loss cripples MCC assembly.

Downstream chain (this is the exact chain to reproduce in the Track 2 mechanism section):

```
biallelic hypomorphic/LoF variant → reduced SAC or spindle fidelity → chromosome missegregation per division
  → constitutional mosaic aneuploidy (variegated) → (a) developmental phenotype: microcephaly, growth failure,
     dysmorphism, ID  and  (b) proteotoxic / metabolic / replication stress in aneuploid cells
  → selective pressure → clonal escape → childhood malignancy
```

### 3.3 Genetic subtypes

| Gene | Locus | OMIM phenotype | Distinguishing phenotype |
|---|---|---|---|
| **BUB1B** (BubR1) | 15q15.1 | MVA1, MIM 257300 | Most common. Microcephaly, intellectual disability, brain malformations, epilepsy, **strong cancer predisposition** (Wilms tumour, rhabdomyosarcoma, ALL). Biallelic *null* is lethal → patients are compound het with at least one hypomorph. |
| **CEP57** | 11q21 | MVA2, MIM 614114 | **Rhizomelic** shortening of the upper limbs, skull anomalies with preserved head circumference, typically **no malignancy**. |
| **TRIP13** | 5p15.33 | MVA3, MIM 617598 | Wilms-tumour predisposition; severe microcephaly; described in consanguineous families. |
| *CEP192* | 18p11.21 | candidate | Reported with tetraploidy and male infertility (case-level evidence). |
| *CENPE*, *SMC5*, *BUB1*, *BUB3*, *KNL1/CASC5*, *PLK4* | 4q24 / 9q21 / 2q13 / 10q26.3 / 15q15.1 / 4q28 | candidate / atypical, MVA-like | Individual case reports of SAC or kinetochore genes with aneuploidy phenotypes. Keep on the panel; do not lead with them. |

### 3.4 Why this drives the whole strategy — re-derived from the real phenotype

Four facts converge, and the third is now measured rather than assumed:

1. The leaked evaluator says the answer is **compound heterozygous** (`hackathon-intel.md` §2.1) → recessive,
   two variants, one gene, one per allele.
2. Biallelic *complete* BUB1B loss is not viable, so real *BUB1B* patients are typically **one truncating/null
   allele + one hypomorphic allele** — and hypomorphic alleles are frequently **deep-intronic / splice-altering
   or otherwise not called cleanly**. That is precisely why 85 GB of FASTQ ships alongside a 315 MB VCF, and
   §1.3 confirms the VCF cannot contain a structural allele at all.
3. **The phenotype is now known exactly (§1.4), and it is not the textbook MVA1 profile.** What it does contain:
   - **Rhabdomyosarcoma** (`HP:0002859`) — an early, aggressive solid tumour. This is the strongest single
     signal. Rhabdomyosarcoma is a documented tumour in *BUB1B*-MVA alongside Wilms tumour and ALL, and it is
     the classic reason to weight the **cancer-predisposing** subtypes: *BUB1B* ≫ *TRIP13* > *CEP57*
     (*CEP57*/MVA2 classically lacks malignancy).
   - **Severe IUGR** — 32-week prematurity at ~1 kg, short stature, failure to thrive, skeletal muscle atrophy.
     Growth restriction is core MVA across subtypes and is consistent with a chromosome-missegregation
     mechanism operating from early development.
   - **Parental recurrent miscarriage** (`HP:0200067`) — reproductive loss is a direct read-out of chromosome
     instability in the parental germline, and the challenge document explicitly instructs that it be treated
     as phenotypic input. It is also, quietly, a consistency argument for a *recessive* mechanism with carrier
     parents.
   - **Nephrocalcinosis since birth** (`HP:0000121`) — not a classic MVA feature. Either an independent finding,
     or a pointer worth one line of differential discussion. Do not force it into the MVA story.
4. **What the phenotype does *not* contain: microcephaly and intellectual disability.** These are the two
   features most tightly associated with MVA1 in the literature, and their absence is the single most
   important thing that changed from the pre-data version. Treat it as weak evidence, not a rule-out — the
   document lists the features that *led to* the diagnosis, not the complete phenotype (§1.4). But it does
   two concrete things: it removes the free win that a microcephaly-driven phenotype prior would have given
   *BUB1B* and *TRIP13*, and it means any candidate whose fit depends on microcephaly must be reported with
   that discrepancy stated.

A consequence worth making explicit: **rhabdomyosarcoma has strong, common non-MVA explanations**, and they
are already on the measured panel — *TP53* (Li-Fraumeni) with 120 variants and *DICER1* with 87 (§3.6). A
compound-het answer key does not by itself exclude a *TP53* or *DICER1* mechanism from being the *reason the
child was sequenced*; it constrains what the challenge is scoring. Keep both on the panel and check them.

**Working hypothesis, unchanged in direction but now differently supported: compound het in *BUB1B*
(15q15.1), one clean LoF + one hard (splice/intronic/SV/low-VAF) allele.** The malignancy still points here;
the missing microcephaly weakens it; nothing yet contradicts it. Fallbacks in order: *TRIP13*, *CEP57*,
*CEP192*/*CENPE*/*SMC5*, then novel gene. Note also that *KNL1/CASC5* sits at 15q15.1 next to *BUB1B* — do
not let a `15` hit auto-assign to *BUB1B* without checking the transcript.

### 3.5 Solution space & ⭐ recommendation (how to encode the disease knowledge)

- **Option A — hard gene panel filter**: analyse only the MVA genes. Fastest; catastrophic if the answer is the
  novel-gene world (the phenotype "MVA" is cytogenetic, not molecular — a new SAC/kinetochore gene is possible).
- **Option B — soft Bayesian gene prior**: weight, don't exclude. Re-derived against the measured phenotype
  (§1.4): rhabdomyosarcoma still concentrates mass on the cancer-predisposing subtypes, but the absent
  microcephaly removes the strongest MVA1-specific term, so the prior should be **flatter than the pre-data
  version proposed**. Concretely: *BUB1B* 0.40 (was 0.55) / *TRIP13* 0.15 / *CEP57* 0.05 (malignancy argues
  against, published exceptions exist) / other SAC-panel genes 0.15 / rhabdomyosarcoma predisposition
  differentials *TP53* + *DICER1* 0.10 / genome-wide remainder 0.15. These are stated priors, not measured
  quantities — their job is to be explicit and auditable, and the report should show the ranking's
  sensitivity to them. The prior multiplies the phenotype LR and ACMG posterior; nothing is ever removed.
- **Option C — phenotype-blind genome-wide first**: run Exomiser/LIRICAL with no MVA assumption at all, compare
  with B. Useful as a bias control and as an ablation row in the report ("the pipeline finds it *without* being
  told the diagnosis" is a powerful Scalability claim if true).
- **Creative check — diagnose the aneuploidy itself from the data: run, and it came back negative.**
  Per-chromosome het allele balance and depth (`vcf_chrom_allele_balance.tsv`, §2.2) are flat: mean het VAF
  0.472–0.497 and mean depth 43.7–46.1 across chr1–22. **No whole-chromosome mosaic aneuploidy is detectable.**

  This needs care in the write-up, because it is easy to misreport in both directions. MVA is diagnosed by
  *karyotype*, typically on cultured lymphocytes or fibroblasts, and the aneuploid fraction varies widely by
  tissue and by cell-division history. A bulk blood WGS sample showing no aneuploidy signal **does not
  contradict the diagnosis** — it says the aneuploid fraction in *this DNA* is below what allele balance can
  detect, roughly <10–15%. Stating that explicitly, with the numbers and the detection floor, is stronger than
  staying silent about a negative result, and it is exactly the kind of thing Scientific Rigor rewards.
  A binned-depth + BAF karyogram from aligned reads (§7.5) would lower the floor and is still worth running
  once Tier 2 produces a BAM. Also worth one line: the **PCS trait** — *BUB1B* cases show premature chromatid
  separation, not directly testable in WGS, but a real differential point.

**⭐ Recommendation: B as the ranking prior + C as the honesty control, panel-first only as an *ordering* of
effort (grep the panel first because it is cheap, not because the rest is excluded).** Rationale: soft priors
capture all the biology value of the panel with zero risk of excluding the truth, and the B-vs-C comparison
itself becomes methods-form content.

### 3.6 The panel, measured

`mva_panel_grch38.bed` (Ensembl GRCh38 gene spans + 20 kb padding) joined against the real VCF —
`panel_variant_counts.tsv`, methodology [003](../methodology/003-panel-gene-variant-counts.md):

| Gene | Locus (repo BED is `chr`-prefixed; the VCF is not) | All | PASS | Role |
|---|---|---|---|---|
| **BUB1B** | chr15:40,140,984–40,241,137 | 80 | 76 | MVA1. 58 het, 23 hom-alt, 4 non-PASS |
| **CEP57** | chr11:95,769,965–95,857,070 | 13 | 13 | MVA2 |
| **TRIP13** | chr5:872,849–939,357 | 12 | **6** | MVA3 — half filtered, see below |
| CENPE | chr4:103,085,349–103,218,463 | 169 | 166 | Atypical MVA |
| CEP192 | chr18:12,971,283–13,145,053 | 255 | 251 | Candidate, centrosome |
| SMC5 | chr9:70,238,270–70,374,874 | 125 | 124 | Candidate, chromosome maintenance |
| TP53 | chr17:7,641,779–7,707,546 | 120 | 118 | Rhabdomyosarcoma differential (§3.4) |
| DICER1 | chr14:95,066,228–95,178,010 | 87 | 87 | Rhabdomyosarcoma differential |

**861 variants across the panel, and without annotation this table cannot be narrowed further.** The spans
include introns, and *BUB1B*'s 80 variants are overwhelmingly `DB`-flagged common dbSNP entries. Six *BUB1B*
variants lack the dbSNP flag; that is the only novelty signal available today, and it is a starting point,
not a candidate list. This is the concrete, measured reason annotation is the blocking dependency (§2.1) and
not a refinement.

**TRIP13 is the cautionary case.** 6 of its 12 variants are non-PASS, mostly `MQ40`, with alt depths of 2–6
reads. *TRIP13* sits at chr5:872,849–939,357, close to the telomere in difficult sequence. Low confidence
there is a **coverage and mappability statement, not evidence of absence** — precisely the situation where a
`FILTER == PASS` habit deletes the answer. Any "no variant found in *TRIP13*" conclusion must be paired with
per-exon depth from the aligned reads before it means anything.

---

## 4. Can we access papers on this disease, similar diseases, and on predicting the causal variant?

Yes — everything on the literature side is public and scriptable. Only the *patient data* is restricted.

### 4.1 Programmatic literature access

| Resource | Access | Use |
|---|---|---|
| **PubMed E-utilities** | REST, free (register an API key for 10 rps) | Query construction, PMID harvesting |
| **Europe PMC REST** | free, includes **full text** for OA articles | Full-text mining of case reports (variant-level detail lives in tables/supplements) |
| **PubTator3** | free API | Pre-computed gene/variant/disease entity annotations per PMID — the fastest way to pull "every variant ever reported in *BUB1B*" |
| **OpenAlex / Semantic Scholar** | free API | Citation-graph expansion; find the reviews that cite all case reports |
| **OMIM** | free for academics via API key | Allelic variant tables per gene (curated, variant-level) |
| **GeneReviews / NCBI Bookshelf** | free | Clinical management chapters; good for the report's clinical framing |
| **Orphanet / Orphadata** | free | Rare-disease nomenclature, epidemiology, HPO annotations |
| **ClinVar** | FTP + API | Every submitted classification for the candidate genes — the single most valuable file |
| **ClinGen** | free | Gene–disease validity, variant curation expert panel specs, ACMG rule specifications |
| **DECIPHER / gnomAD / dbNSFP** | free | Population and precomputed prediction data |

Example harvest (documented, reproducible, belongs in the public repo — it contains no patient data):

```
PubMed:  ("mosaic variegated aneuploidy"[tiab] OR "MVA syndrome"[tiab])
         OR (BUB1B[tiab] AND aneuploidy[tiab]) OR CEP57[tiab] OR TRIP13[tiab]
PubTator3: /publications/export/biocjson?pmids=<batch>   → extract Mutation + Gene annotations
ClinVar:   variant_summary.txt.gz  → filter GeneSymbol ∈ panel  → all reported alleles + classifications
```

### 4.2 Two literature corpora to build (they answer different questions)

**Corpus A — disease/gene:** every MVA case report and functional study. Purpose: (i) a *reported-allele
catalogue* per gene, so that if a proband variant matches a published MVA allele the case is nearly closed;
(ii) genotype–phenotype mapping to reconcile with the proband's HPO terms; (iii) mechanism detail for Track 2.
Include adjacent phenotypes: constitutional chromosome-instability / cohesinopathy / centrosomopathy syndromes
(Roberts, Warsaw-breakage, microcephalic primordial dwarfism, PCS/MVA overlap) — useful differential and useful
if the answer turns out to be a novel gene.

**Corpus B — method:** how the field predicts causal variants. Phenotype-driven prioritization (Exomiser,
LIRICAL, AMELIE, Phen2Gene, GADO, Xrare) and the benchmark papers comparing them; ACMG/AMP 2015 + the Bayesian
reformulation (Tavtigian) + ClinGen SVI rule specifications; splice prediction (SpliceAI, Pangolin, AbSplice);
missense prediction (CADD, REVEL, AlphaMissense, EVE, ESM1b, PrimateAI-3D); non-coding (ReMM/Genomiser,
AlphaGenome, Evo 2). Purpose: justify the pipeline in the methods form (Innovation + Scalability points) and
avoid reinventing solved components.

### 4.3 LLM-assisted triage is explicitly allowed

The Track 2 methods form lists *"LLM-assisted search"* as a legitimate automated approach
(`hackathon-intel.md` §10.2). Use it — but keep it auditable: every LLM-surfaced claim must carry a PMID/DOI,
and the retrieval + prompt code goes in the public repo. Hallucinated citations in a rare-disease report are
the fastest way to lose Scientific Rigor (35% of Track 2).

### 4.4 Compliance boundary (do not blur it)

Papers, annotations, prediction scores, code: public, shareable, repo-safe.
Anything derived from the proband's reads or genotypes — VCF slices, read snippets, IGV screenshots, coordinate
lists of proband variants, intermediate annotation tables — is **patient data**: private repo only, deleted
within 30 days of close, deletion confirmed by email (`raw_hackathon.txt` §6, `hackathon-intel.md` §6).

### 4.5 Solution space & ⭐ recommendation

- **Option A — manual expert reading**: read the ~30–50 MVA case reports by hand. High precision, days of work,
  no reuse value.
- **Option B — automated reported-allele catalogue (the decisive artefact)**: PubTator3/LitVar2 variant
  annotations + ClinVar `variant_summary` + OMIM allelic tables → normalize every reported MVA-gene allele to
  GRCh38 `(chrom,pos,ref,alt)` (HGVS → VCF via VariantValidator/mutalyzer, then `bcftools norm`) → **one SQL
  join against the proband VCF (and one k-mer scan against the FASTQ, §1.5-B)**. If either allele of the pair
  has ever been published, this closes the case in day 1–2. The catalogue is public-data-only → publishable in
  the open repo.
- **Option C — agentic LLM literature layer**: a retrieval-grounded agent that (i) triages Corpus A/B,
  (ii) extracts variant/phenotype claims with PMID anchors, (iii) drafts ACMG evidence text. 2025–26 systems
  (agentic traceable-reasoning diagnosis, DAVP-style iterative LLM tournaments, LA-MARRVEL) show this works when
  grounded; ungrounded it hallucinates. Every claim must carry a PMID/DOI and survive a human spot-check.

**⭐ Recommendation: B first (it is a *solver*, not a helper — highest expected-value artefact per hour in the
whole project), C wrapped around it for recall and report drafting, A reserved for the final 10 candidate
alleles.** Rationale: the intersection of "published allele" ∩ "proband genotype" is mechanical, exhaustive and
auditable; LLMs add recall and speed but only the join produces certainty.

---

## 5. What data structure can we use?

Design principle: **one canonical variant identity everywhere**, and it must be byte-identical to what the
scorer compares. The scorer builds `Variant = (chrom.strip(), int(pos), ref.upper(), alt.upper())` and compares
pairs as a `frozenset` (`hackathon-intel.md` §8.1–8.2). Mirror that exactly in code, or you will lose on
formatting rather than on biology.

### 5.1 Core types

```python
from dataclasses import dataclass
from typing import FrozenSet, Optional

@dataclass(frozen=True, order=True)
class Variant:                      # canonical, hashable, scorer-identical
    chrom: str                      # 'chr15'  — chr-prefixed, lowercase 'chr', NOT normalized by the scorer.
                                    # MEASURED: the delivered VCF says '15'. from_vcf() adds the prefix;
                                    # nothing else in the codebase builds this string. (§1.3, trap 1)
    pos: int                        # 1-based VCF POS, after `bcftools norm -m -both` left-alignment
    ref: str                        # uppercase
    alt: str                        # uppercase, single allele (66,860 multiallelic sites must be split first)

Pair = FrozenSet[Variant]           # exactly how the scorer represents a row; |Pair| ∈ {1, 2}
```

Everything downstream keys off `Variant`. One normalization function, one place, unit-tested against a handful
of hand-built indel cases (the indel-representation trap in `hackathon-intel.md` §8.1 is the #1 silent failure).

Two measured facts make this stricter than it looks. **The contig namespace differs between the source and the
sink** — `15` in, `chr15` out — so a hand-built chromosome string is a scoring bug that no test of biology will
catch. And **930,181 indels plus 66,860 multiallelic sites** mean left-alignment and allele splitting are load-
bearing on a large fraction of the callset, not an edge case.

### 5.2 Storage layer

| Layer | Structure | Why |
|---|---|---|
| Raw callset | `bgzip` + `tabix` (CSI/TBI) VCF | Random access by region in O(log n); the standard everyone expects |
| Contig namespace | One conversion function, `15` ⇄ `chr15`, applied at the two boundaries (VCF in, submission and repo BED out) | Measured mismatch between source and sink (§1.3); a hand-built chromosome string is a silent scoring bug |
| Analytical table | **Parquet**, partitioned by chromosome, read via **DuckDB** | Columnar scan of millions of rows, SQL joins to annotations, no server, trivially reproducible |
| Annotation joins | dbNSFP / gnomAD / ClinVar slices as Parquet, joined on `(chrom,pos,ref,alt)` | Avoids re-running VEP for exploratory questions |
| Gene models | Interval index (**interval tree** / `pyranges`, or `bcftools -R` over a BED) | O(log n + k) "which variants fall in this gene/exon/intron" |
| Phenotype | **HPO DAG** (`hp.json`) with precomputed ancestor closures and information content per node | Semantic similarity needs ancestors, not string matching |
| Knowledge graph (optional) | property graph: `Gene —associated_with→ Disease —has_phenotype→ HPO`, `Variant —in→ Gene`, `Drug —targets→ Gene` | Serves both tracks; enables GNN/path-based scoring (§8.5) and the Track 2 drug hop |
| Candidate hypotheses | priority queue / sorted table of `PairHypothesis` | Ranking is the actual deliverable |
| Oracle interaction | append-only **ledger** (CSV/JSONL, committed to the private repo) | 18 irreplaceable queries; every one must be reconstructible |

### 5.3 The two records that matter

```python
@dataclass
class PairHypothesis:
    pair: Pair                      # 1 or 2 variants
    gene: str
    epcr: float                     # calibrated probability, strictly in (0,1], distinct per row (ties → file order)
    finding_type: str               # 'primary' | 'secondary'  (informational only for the automated score)
    notes: str                      # free text — reviewed qualitatively, so make it count
    # --- evidence, for the report and for ranking ---
    acmg_codes: list[str]           # PVS1, PM2, PP3, ...
    acmg_points: int                # Tavtigian Bayesian point total
    in_silico: dict[str, float]     # cadd, revel, alphamissense, spliceai_ds_max, ...
    gnomad_af: float
    phase: str                      # 'trans' | 'cis' | 'unknown'  ← decisive for compound het
    phase_evidence: str             # 'read-backed:PS=1234' | 'trio' | 'none'
    provenance: dict                # caller, filters, depth, VAF — auditability

@dataclass
class OracleProbe:                  # one submission = one adaptive experiment
    submission_id: str              # member + index, e.g. 'member2#3'
    member: str
    probe_type: str                 # 'S' singles-scan | 'P' pair-scan | 'F' final strike
    rows: list[PairHypothesis]      # ≤ 10, distinct descending epcr
    # --- returned by the scorer ---
    rank_points: int
    f_max: float
    f_max_threshold: float
    full_match_rank: Optional[int]
    partial_match_rank: Optional[int]
    decoded: str                    # human-readable inference, per §9.1 of hackathon-intel.md
```

### 5.4 Structures for the hard second allele

- **Phase blocks**: union-find / disjoint-set over variants linked by shared reads (this is what WhatsHap
  computes, and what Sentieon already emitted as `PGT`/`PID`). Two candidate variants in the same phase block
  with *opposite* haplotype assignment = *trans* = a valid compound het; same haplotype = *cis* = excluded
  deterministically.

  **[was wrong] Measured, this resolves almost nothing.** 770,458 records (15.4%) carry `PGT`/`PID`, which
  sounds usable and is not: with a 266 bp insert size (§1.2) the reach is a few hundred bases. On *BUB1B* —
  58 het calls, 1,653 candidate pairs — phasing returns **3 trans, 2 cis, 1,648 unknown: 0.3% resolved**, and
  the four phase-resolved pairs at distinct positions were 3, 42, 3 and 4 bp apart
  ([methodology 006](../methodology/006-phasing-power-on-bub1b.md)). The pre-data version cited SmartPhase's
  ~22%-of-pairs figure; that does not transfer to this dataset's insert size and gene-scale pair distances.

  Three design consequences: (i) **`UNKNOWN` is the verdict on 99.7% of pairs and must never be treated as a
  rejection** — only `CIS` excludes; (ii) ranking must be carried by rarity and consequence, with phase as a
  tiebreaker that kills a handful of cis pairs and promotes a handful of proven-trans ones; (iii) real phasing
  power needs longer fragments than this library has, so it is not recoverable by re-aligning — the ceiling is
  physical.

  **The one place phase comes free: a `1/2` multiallelic genotype.** One copy of each ALT means one per
  haplotype — compound heterozygosity proven by the genotype itself, no read evidence required. There are
  **66,860** such sites in the callset. Splitting them with `bcftools norm -m -both` produces two calls that
  are `TRANS` by construction, and that rule belongs in the pair finder explicitly.
- **Coverage arrays / HMM state sequence** for CNV and single-exon deletions: per-base or per-exon depth →
  normalized log2 ratio → HMM segmentation (§7.5).
- **Sparse VAF table** for the mosaic scan: MVA involves mosaicism, so a somatic-style low-VAF second hit is
  plausible; keep `(variant, alt_depth, total_depth)` and test against a binomial/beta-binomial null (§7.4)
  rather than a fixed VAF cutoff.

### 5.5 Solution space & ⭐ recommendation

- **Option A — scorer-identical dataclasses + DuckDB** (as above): minimal, auditable, unit-testable.
- **Option B — bitmask hypothesis space + probe simulator (creative, high leverage)**: with a candidate pool
  `C` of N alleles, represent each pair hypothesis as a bit in a `C(N,2)`-bit vector (N=200 → 19,900 bits ≈
  2.5 KB). A **probe simulator** — the local reimplementation of `evaluation.py` run against every surviving
  hypothesis as if it were the truth — computes, for any candidate probe, the exact partition of outcomes
  `(full_match_rank, partial_match_rank, f_max, threshold)` over the hypothesis space. Probe design then stops
  being judgment and becomes computation: pick the probe whose worst-case surviving set is smallest (minimax)
  or whose expected posterior entropy is lowest (Bayes, §7.6). Oracle feedback = one bitwise AND to collapse
  the space. ~200 lines of Python, testable end-to-end without touching patient data.
- **Option C — full knowledge graph store (Neo4j/RDF)**: premature for Track 1; the graph earns its keep only
  for the Track 2 drug hop, and a property table in DuckDB serves that too.

**⭐ Recommendation: A + B; C deferred to Track 2 and only if the drug hop outgrows SQL joins.** Rationale: B is
the piece that converts the leaked scorer from "intel" into "machinery" — it guarantees no probe is wasted on a
question whose answer wouldn't discriminate hypotheses, and it is the single most defensible Innovation claim in
the methods form ("sequential experimental design with an exact simulator of the official scorer").

---

## 6. What open-source models can we use for prediction, and what are their limitations?

Split by job. Nothing here needs training on the proband — all are pretrained or rule-based, which is the only
option at N = 1.

### 6.1 Variant calling / discovery (recover the allele the VCF missed)

Two measured facts reframe this whole table. **There are no structural variants in the delivered callset at
any FILTER level** — the provenance chain is Sentieon Haplotyper → Sentieon GVCFtyper → GATK
`VariantFiltration`, a small-variant pipeline end to end, with no `SVTYPE` and no symbolic ALTs (§1.3). So the
SV callers below are not "recovering what the VCF missed"; they are the *only* source of SV evidence that will
ever exist for this case. And **no BAM was shipped**, so every tool in this table that takes an alignment is
gated behind aligning 161 Gbases first (§1.1).

Before any of that, there is a cheaper move: **271,414 non-PASS records** are calls the caller saw and did not
trust, dominated by `MQ40` (177,522) — exactly the filter that fires in segmental duplications and repeats
where a real variant hides. Mining them inside the panel is minutes; re-calling is a day.

| Tool | Job | Key limitation |
|---|---|---|
| **DeepVariant** | SNV/indel re-calling from reads (CNN over pileup images) | Trained for germline diploid genotypes → *systematically penalizes low-VAF mosaic* alleles; slow without GPU |
| **Clair3** | Alternative caller, short & long read | Same diploid prior assumption |
| **GATK HaplotypeCaller** (`-ERC BP_RESOLUTION`, or Mutect2 in tumour-only mode) | Sensitive re-calling; **Mutect2 tumour-only is the trick for low-VAF mosaic alleles** | Mutect2 tumour-only produces many artefacts → needs a panel-of-normals or manual review |
| **Manta**, **Delly**, **smoove/LUMPY**, **GRIDSS** | Structural variants (deletions, dups, inversions, insertions) | Poor in repeats/segmental dups; breakpoint precision varies; each caller has distinct blind spots → **use a 2-of-3 consensus** |
| **GATK-gCNV**, **CNVnator**, **ExomeDepth** | Copy-number, incl. single-exon deletions | Single-sample CNV from WGS depth is noisy; needs a matched reference panel for calibration |
| **ExpansionHunter**, **STRipy** | Repeat expansions | Only for known loci |
| **MELT / scramble** | Mobile-element insertions | Rarely the answer, cheap to check |
| **AnnotSV** | SV annotation + ranking | Only as good as the SV call it is given |

### 6.2 Variant effect prediction

| Model | Scope | Limitations that matter here |
|---|---|---|
| **CADD** (v1.7) | genome-wide, all classes | Trained to separate simulated from observed variants → a *deleteriousness* proxy, not a disease-causality probability; weak discrimination inside a single gene |
| **REVEL**, **MetaRNN**, **BayesDel** | missense meta-predictors | **ClinVar circularity**: trained on ClinVar labels, so "independent support" for an already-classified variant is partly illusory. Missense only. |
| **AlphaMissense** | missense, proteome-wide | Missense only; scores are gene-context-agnostic; strong but not a replacement for functional data. Licence: non-commercial for the released predictions — fine for a hackathon, must be declared |
| **ESM-2 / ESM1b, EVE, PrimateAI-3D** | zero-shot missense from sequence/MSA | Unsupervised → *no ClinVar leakage* (a real advantage in the methods writeup); but uncalibrated — log-likelihood ratios are not probabilities |
| **SpliceAI**, **Pangolin**, **AbSplice**, **SQUIRLS** | splice-altering, incl. deep intronic | The single most important class here: a hypomorphic *BUB1B* allele is very plausibly a leaky splice variant. Limitations: SpliceAI's default ±50 nt window misses distal effects (use ±1000 nt masked/unmasked), no tissue specificity (AbSplice adds it), and it predicts *splice disruption*, not *residual protein activity* |
| **ReMM / Genomiser** | non-coding regulatory | Low precision genome-wide; only usable inside a strong prior region |
| **AlphaGenome** | 1 Mb context → expression, splicing, chromatin, contacts; matched or beat the best external model in 25/26 variant-effect evaluations | API-gated, non-commercial terms; regulatory-track predictions are correlative, not causal; still weak for "is this the disease allele" |
| **Evo 2** | genomic LLM, log-likelihood-based variant effect, coding **and** non-coding, no fine-tuning | Compute-heavy; delta-likelihood is uncalibrated and gene-agnostic; best used as one orthogonal feature, not as an arbiter |
| **LoF logic**: VEP + **LOFTEE**, NMDEscPredictor, `pext` | is a truncating variant really LoF? | Last-exon / NMD-escape / rescue-transcript exceptions are exactly where a *hypomorph* hides — and hypomorphs are the MVA1 rule, not the exception |

### 6.3 Phenotype-driven prioritizers (the automated-pipeline backbone)

| Tool | Method | Notes / limitations |
|---|---|---|
| **Exomiser** (+ **Genomiser** for non-coding) | filters + variant score × phenotype score (hiPhive: human/mouse/fish + PPI random walk) | Best-in-class top-1 in published benchmarks (~80%+ top-1 on large diagnostic cohorts); ships compound-het (AR) inheritance modes. Needs current data releases; phenotype priors *penalize novel genes* by construction |
| **LIRICAL** | explicit **likelihood ratio** per phenotype and per genotype → interpretable Bayesian posterior | Often best in top-5; LRs make it the most report-friendly (you can show the arithmetic). Sensitive to noisy/imprecise HPO terms |
| **AMELIE** | literature-based ML gene ranking | Depends on published knowledge → weak for novel genes; actively maintained |
| **Phen2Gene**, **GADO**, **Phenolyzer** | HPO-only gene ranking | Cheap and fast, no variant model; consistently lower performance than Exomiser/LIRICAL in benchmarks. Use as an orthogonal opinion, not as a primary |
| **slivar** | expression-based Mendelian filtering incl. comp-het logic | Deterministic, fast, transparent — ideal for the hard-filter layer |
| **ClinGen ACMG automation** (InterVar/TAPES/CharGer/Genebe) | rule-based ACMG classification | Automated ACMG is a *draft*: PVS1 and PP1/PS3 in particular need human review. Use it to standardize, then curate |

**Systemic limitations to state honestly in the methods form (Q18 wants limitations):**
1. **Circularity** — most supervised predictors trained on ClinVar; if the true alleles are already in ClinVar,
   the "prediction" is partly retrieval. Mitigate by reporting unsupervised scores (ESM/EVE/Evo 2) alongside.
2. **Gene-level vs allele-level** — phenotype-driven tools rank *genes* well and *alleles within a gene* poorly.
   For a compound het in a known gene, the hard part is exactly the intra-gene allele choice, where these tools
   are weakest.
3. **Non-coding blind spot** — if allele 2 is deep intronic or regulatory, the whole standard stack degrades.
4. **No mosaicism model** — every germline caller/predictor assumes a diploid 0/0.5/1 VAF. MVA is a mosaicism
   disorder. This mismatch is a plausible reason a real allele is missing from the provided VCF.
5. **Reference and ancestry bias** — gnomAD AF thresholds behave differently across ancestries; GRCh38 has
   known false-duplication regions; a `PASS` filter can drop a true call in a hard region.
6. **Calibration** — nearly all of these emit scores, not probabilities. `epcr` must be in (0,1] and should be
   *meaningfully* calibrated for F-max to behave (§9.3).

### 6.4 Solution space & ⭐ recommendation (which models actually run, and when)

Escalation tiers — each tier runs only if the previous one has not produced a confirmed pair:

| Tier | Trigger | Stack | Cost |
|---|---|---|---|
| **1 — standard strike** (day 1–3) | always | `bcftools norm` → VEP(+LOFTEE, SpliceAI ±1000, AlphaMissense, dbNSFP) → slivar comp-het → Exomiser + LIRICAL → ACMG points → probe S₁ | hours, local |
| **1.5 — the free tier (do this first)** | always, before Tier 2 | Mine the **271,414 non-PASS** records inside the panel; split and re-phase the **66,860 `1/2`** multiallelic sites (free trans evidence, §5.4); check the 6 non-`DB` *BUB1B* variants | minutes, local |
| **2 — raw-data rescue** (start day 1 in the background, not day 2 on trigger) | **[was wrong — no longer trigger-gated]** No BAM shipped and no SVs in the callset, so this is the only path to SV/CNV evidence, per-exon depth, IGV panels for the report, and phasing beyond 266 bp | bwa-mem2 align 161 Gb → DeepVariant; Manta+Delly+smoove 2-of-3 SV consensus; GATK-gCNV/mosdepth exon deletions; Mutect2 tumour-only low-VAF scan restricted to the localized gene; WhatsHap phasing | ~$20–60, 1–2 days |
| **3 — foundation-model sweep** (week 3+) | Tiers 1–2 exhausted | Evo 2 delta-likelihood + AlphaGenome splicing/regulatory tracks over the full candidate gene; ESM1b for all missense; MALVA-style k-mer re-check of every literature allele | GPU-days on Modal |

Cross-cutting choices:
- Splice prediction: **SpliceAI (±1000 nt, masked+unmasked) + Pangolin, agree/disagree flagged** — the two
  disagree exactly where human review is needed. AbSplice only if tissue-specificity becomes an argument.
- Missense: **AlphaMissense + REVEL (supervised) alongside ESM1b (unsupervised)** — the supervised/unsupervised
  agreement pattern is the circularity disclosure, pre-packaged.
- LoF verification: **LOFTEE + NMD-escape logic on every truncating candidate** — the MVA1 null+hypomorph rule
  means a "LoF" that escapes NMD may actually be the hypomorph.

**⭐ Recommendation: Tier 1.5 immediately (minutes), Tier 1 as the main line, and Tier 2 launched on day 1 in
the background rather than held as a trigger.** Rationale: expected time-to-solve is still dominated by the
published-allele and clean-comp-het worlds that Tier 1 covers, but the measured absence of a BAM and of any SV
call means Tier 2 is a *dependency of the report itself*, not a contingency — and a 1–2 day job you might need
in week 2 should be started in week 1. Deep models keep the worst information-per-hour early and the best late;
Tier 3 stays gated.

---

## 7. Are there statistical and mathematical models we can use?

Yes — and they are what makes the submission defensible rather than a pile of tool outputs.

### 7.1 Bayesian ACMG/AMP (the clinical standard, now quantitative)

The 2015 ACMG/AMP rules were re-expressed by Tavtigian et al. as a Bayesian point system: each evidence code
carries points (supporting 1, moderate 2, strong 4, very strong 8; benign codes negative), and the total maps
monotonically to a posterior probability of pathogenicity under a prior of ~0.1:

```
Odds_path(total) = OR_strong ^ (points / 4),      posterior = prior·Odds / (1 + prior·Odds − prior)
Pathogenic ≥ 10 pts · Likely path 6–9 · VUS 0–5 · Likely benign −1…−6 · Benign ≤ −7
```

Value here: it converts heterogeneous evidence (PVS1 truncating, PM2 absent from gnomAD, PP3 in-silico, PM3
in-trans with a pathogenic allele, PS4/PP4 phenotype specificity) into a **single number you can defend**, and
it is a principled source for `epcr`. Note PM3 explicitly rewards the *in-trans* observation — i.e. the
compound-het structure itself is evidence.

### 7.2 Prior probability of the biallelic genotype (population genetics)

For a recessive gene with total pathogenic allele frequency `q` (summed over pathogenic alleles in gnomAD),
Hardy–Weinberg gives a population disease prevalence `q²`, and for a *specific* pair of distinct alleles with
frequencies `p₁, p₂` the compound-het genotype frequency is `2·p₁·p₂`. Two consequences:

- With MVA at <50 patients worldwide, plausible pathogenic alleles must be **vanishingly rare** — an allele at
  gnomAD AF 1e-3 as *one half* of the pair implies far too many affected individuals. Hard filter: AF < 1e-4
  for the primary hypothesis, AF < 1e-3 as the permissive boundary **[verify against gnomAD v4 per gene]**.

  ⚠️ **Measured trap: `INFO/AF` in the delivered VCF is *within-sample*, not population frequency.** With one
  sample it takes the value 0.5 or 1.0 and carries no population information whatsoever (§1.3). Every `AF`
  threshold in this section refers to **joined gnomAD v4 frequency**, which does not exist in the file and must
  be added by annotation. Filtering on the VCF's own `AF` column would remove roughly every heterozygous
  variant in the genome and look like it worked.
- Ratio of `2·p₁·p₂` across candidate pairs is a legitimate, quantitative prior term in the ranking model.

Also use **gene-level constraint** (gnomAD pLI / LOEUF, and the missense z-score) as a prior on the gene, and
note the MVA1 subtlety: since biallelic *null* is lethal, the expected genotype is **null + hypomorph**, so a
pair of two unambiguous nulls should be *down*-weighted on biological grounds. This is the kind of reasoning no
off-the-shelf tool applies, and it is a genuine edge.

### 7.3 Phenotype likelihood ratios and ontology semantics

LIRICAL's formulation: for each observed HPO term `h` and candidate disease `d`,

```
LR(h | d) = P(h | d) / P(h | ¬d)
```

with `P(h|d)` from HPO disease annotations (with ontology propagation to ancestors) and `P(h|¬d)` from the
background term frequency. Multiply LRs across terms (with the usual independence caveat), multiply by the
genotype LR, get a posterior per disease. Semantic similarity between term sets uses information content
`IC(t) = −log p(t)` with Resnik/Lin/Jiang–Conrath aggregation (Phenomizer-style), which handles the fact that
"Microcephaly" and "Severe microcephaly" are near-synonyms while "Neoplasm" is highly informative.

Practical caution: the independence assumption is wrong (HPO terms are correlated by construction), so treat
these as scores for ranking, not as calibrated probabilities.

### 7.4 Read-level probabilistic models (where the hidden allele is found)

- **Genotype likelihoods**: the VCF `PL`/`GL` fields *are* a probabilistic model output. A variant with a weak
  het call (low `GQ`) is not evidence of absence — re-examine, don't filter.
- **Binomial test for allelic balance**: for a true germline het at depth `n`, alt reads `k ~ Binomial(n, 0.5)`
  (modulo reference bias). Significant depletion → mosaic, CNV-overlapping, or artefact. Use
  **beta-binomial** to absorb overdispersion across the genome.
- **Mosaic detection**: hypothesis test `H₀: VAF = 0` (sequencing error, error rate `ε ≈ 1e-3`) vs
  `H₁: VAF = f` for `f ∈ [0.02, 0.35]`. With 30× coverage, power for f = 0.1 is poor at a single site — which
  is why the mosaic scan must be **restricted to the candidate gene** (small multiple-testing burden, so a
  lenient threshold is defensible). This is Bayes at work: a strong prior region buys you sensitivity.
- **Poisson/negative-binomial depth model** for deletion detection: expected reads per bin ∝ copy number;
  a heterozygous exon deletion halves the mean. Test per exon, and correct for GC and mappability.
- **Multiple testing**: genome-wide scans need FDR (Benjamini–Hochberg); panel-restricted scans need almost
  none. Say this explicitly in the report — it is the statistical justification for the targeted-first strategy.

### 7.5 HMM / segmentation for copy number and aneuploidy

Hidden states = copy number {0,1,2,3,…}; emissions = binned normalized log2 depth (plus B-allele frequency if
you use het-site allelic ratios); transitions encode segment length priors. Standard for CNV segmentation, and
it doubles as the **mosaic aneuploidy detector**: a subclonal trisomy at mosaic fraction `f` shifts log2 by
`log2(1 + f/2)`, and shifts het-site BAF away from 0.5 by ~`f/(2+f)` — the BAF channel is the more sensitive one.

### 7.6 Decision theory for the oracle: adaptive group testing

This is the mathematically interesting part, and it is the strategy layer of `hackathon-intel.md` §9 stated
properly. Let `C = {c₁ … c_N}` be the ranked candidate allele pool. The unknown truth is an unordered pair
`{A, B} ⊂ C` (assuming both are in the pool). Search space size:

```
|H| = C(N,2) = N(N−1)/2        →  H(H) = log₂ C(N,2) bits
N = 50  →  1225 hypotheses  →  10.3 bits
N = 200 →  19900 hypotheses →  14.3 bits
```

Each submission returns `(rank_points, f_max, f_max_threshold, full_match_rank, partial_match_rank)` — a
multi-valued observation, so its information content far exceeds one bit:

- A **singles scan** (10 single-variant rows) partitions outcomes by `(i, j)` = ranks of the first and second
  true allele among the 10; the observed `f_max` value decodes `j` given `i` over a useful range
  (the verified decode table in `hackathon-intel.md` §9.1). Distinct observable outcomes ≈ tens →
  **~4–6 bits per probe**, and in the best case *both* alleles are identified from a single submission.
- A **pair scan** (10 pair rows sharing one confirmed allele) tests 10 hypotheses with an unambiguous readout
  (`full_match_rank`) → up to `log₂(11) ≈ 3.5` bits, and it is *decisive* rather than merely informative.

Formal frame: **sequential Bayesian experimental design**. Maintain a posterior `P(pair)` from the pipeline's
calibrated scores; choose the next probe `π` maximizing expected information gain

```
π* = argmax_π  I(pair ; obs(π))  =  argmax_π  [ H(pair) − E_obs H(pair | obs) ]
```

subject to the constraints (≤10 rows, distinct `epcr`, ≤18 total probes, per-member quota of 6). In practice
greedy maximization over the two probe templates (S and P) is near-optimal, and the arithmetic in
`hackathon-intel.md` §9.4 (expected 2 submissions if both alleles are in the top 10; ~8 worst realistic case)
falls out of it. Classical relatives worth citing in the report: **Dorfman group testing**, **Rényi–Ulam
searching with a truthful oracle**, and **best-arm identification with a fixed budget**.

One honesty constraint: the oracle is a *validator*, so use it as an adaptive hypothesis test (legitimate) and
make the *final* leaderboard submission the genuine output of a pipeline that independently ranks the pair
first (`hackathon-intel.md` §9.5). Report both layers in the methods form.

### 7.7 Solution space & ⭐ recommendation

Where should `epcr` come from?
- **Option A — Bayesian ACMG posterior** (§7.1): every number traceable to a named evidence code; the exact
  framework clinical judges already trust.
- **Option B — calibrated ML score** (§8.2): better ranking on benchmarks, but its calibration lives on
  synthetic data and its reasoning is a feature table.
- **Option C — rank-fusion pseudo-probability**: robust ordering, but the values are not probabilities and
  F-max thresholds inherit that arbitrariness.

How should probes be chosen?
- **Option D — fixed playbook** (S-scan → decode → P-scan → F): simple, already near-optimal for the expected
  candidate-pool sizes.
- **Option E — simulator-driven experimental design** (§5.5-B): exact minimax/max-EIG probe selection over the
  surviving hypothesis space; matters when candidates are many, correlated (shared alleles across pairs), or
  when a probe must double as a leaderboard attempt.
- **Option F — formal ILP/covering optimization** of probe composition: correct but over-engineered below a few
  hundred hypotheses; enumeration in the simulator answers the same question.

**⭐ Recommendation: A for `epcr` (with B computed as a cross-check and reported), E for probe design with D as
its sanity baseline, F skipped.** Rationale: `epcr` is read by human judges — the ACMG arithmetic *is* the
report; probe choice is read by no one but decides the 18-query budget — so let the machine do it exactly.

---

## 8. What types of machine learning models can be applied to this data?

**Framing first, because it decides everything:** this is not a classification problem on a training set. It is
**ranking/retrieval on a single instance** — N = 1 patient, ~4–6 M candidate variants, exactly 2 positives.
There is nothing to train *on this patient*. Any learning must happen on external labelled data and transfer in.

### 8.1 Learning-to-rank (the right primary model)

Objective: order candidate variants (and pairs) so the true pair is rank 1. Use **LambdaMART / XGBoost or
LightGBM with a ranking objective** (`rank:pairwise`, `lambdarank`), trained on *synthetic probands*: public
control genomes (GIAB/HG002, 1000 Genomes) spiked with ClinVar pathogenic pairs, one query group per synthetic
proband, features as below. Optimizes NDCG/top-1 directly, which is exactly what rank points reward.

Feature families (per variant, then aggregated per pair):
`gnomAD AF (global + popmax) · gene constraint (pLI/LOEUF/mis-z) · consequence class · CADD/REVEL/AlphaMissense/
ESM/EVE · SpliceAI/Pangolin/AbSplice · conservation (phyloP/GERP) · ClinVar status of the variant and of the gene ·
HPO similarity of the gene's disease profile to the proband's terms · call quality (DP, GQ, VAF, FILTER, strand
bias) · segmental-dup/repeat context · phase (trans/cis/unknown) · pair-level: same-gene, AF product 2p₁p₂,
"one LoF + one hypomorph" indicator`

### 8.2 Calibrated classification for `epcr`

Rank order determines rank points; the *values* determine F-max thresholds. So a second, calibrated head:
logistic regression or gradient boosting + **isotonic regression / Platt scaling** on held-out synthetic
probands, so that `epcr = 0.9` means something. Note the F-max mechanics (`hackathon-intel.md` §8.4): the sweep
only visits thresholds present in the file and rows below the optimal threshold cannot hurt — so calibration
matters for the *top* rows and rows further down are free.

### 8.3 Positive-unlabeled and anomaly-detection framings

Labels are one-sided: ClinVar pathogenic = positives; "everything else" is unlabeled, not negative (VUS today,
pathogenic tomorrow). Two principled responses: **PU learning** (Elkan–Noto style class-prior correction) and
**one-class / anomaly detection** — model the distribution of a healthy genome's variation and score the
proband's variants by how *atypical* they are given the gene's constraint. The second is attractive for a
novel-gene fallback, since it does not require the gene to be known.

### 8.4 Deep models as frozen feature extractors (not as end-to-end learners)

- **Protein language models** (ESM-2/ESM1b): zero-shot masked-marginal LLR per missense — no ClinVar leakage.
- **Sequence-to-function models** (SpliceAI, AlphaGenome, Enformer-class, Evo 2): splice/regulatory features
  for the intronic-allele hypothesis.
- **Structure**: AlphaFold model of BUBR1 → map candidate residues onto the TPR / pseudo-kinase / KEN-box and
  Bub3-binding regions; interface-proximity and ΔΔG proxies (FoldX/Rosetta or a learned ΔΔG predictor) as
  features, and as excellent report figures.
Fine-tuning any of these on N = 1 is meaningless; using them as fixed features is correct and defensible.

### 8.5 Graph learning over a knowledge graph

Build `Variant → Gene → Pathway/PPI (STRING, Reactome) → Disease → HPO`, plus `Drug → Target` for Track 2.
Then either (a) classical **network propagation / random walk with restart** from the proband's HPO terms —
which is essentially what Exomiser's hiPhive does, is transparent, and needs no training; or (b) a **GNN /
knowledge-graph-embedding link predictor** (R-GCN, or TransE-class on Open Targets/PrimeKG). (a) is the safe
default; (b) is the Innovation-points option — and it transfers directly to the Track 2 drug hop, which is the
same link-prediction problem on `Drug → Target/Pathway`.

### 8.6 LLM agents (used narrowly and auditably)

Good at: literature triage and evidence extraction from case reports, ACMG evidence drafting from structured
inputs, orchestrating tool calls, generating the report scaffold, and Track 2 drug-candidate mining (explicitly
sanctioned in the methods form). Bad at: being the variant predictor. Never let an LLM *assert* a coordinate or
a citation — every variant claim must be traceable to the VCF/BAM, every citation to a PMID/DOI.

### 8.7 Ensembling and the honest final model

Stack the components (Exomiser rank, LIRICAL posterior, ACMG points, LTR score, phase constraint) by rank
aggregation — **Borda count** or **reciprocal rank fusion** — or a small logistic meta-model fitted on synthetic
probands. Rank fusion is robust, needs almost no training data, and is easy to explain to judges.

**Overfitting warning that is specific to this contest:** once the oracle confirms the pair, any "tuning until
the pipeline ranks it first" is fitting to a single data point. Do it (the rules invite an automated final
model), but (i) keep the tuning *biologically motivated* (e.g. "added AR compound-het mode and SpliceAI ±1000 nt",
not "reweighted feature 7 until it worked"), (ii) demonstrate generalization on the synthetic-proband benchmark,
and (iii) declare it plainly in the methods form. Judges reward a pipeline that works on *any* N-of-1 case —
that is the Scalability criterion (15%).

### 8.8 Solution space & ⭐ recommendation

- **Option A — pure classical ensemble**: Exomiser + LIRICAL + ACMG + slivar, fused by reciprocal-rank fusion.
  Zero training, maximally defensible, ~the current published state of practice.
- **Option B — A + learning-to-rank trained on synthetic probands** (§8.1): measurable gains on the benchmark,
  a real ML contribution for the methods form; risk is benchmark–reality mismatch.
- **Option C — A + agentic LLM evidence tournament (creative, 2026-current)**: for the top ~20 fused candidates,
  compile a structured dossier per pair (annotations, ACMG codes, phenotype LRs, literature hits with PMIDs) and
  run pairwise LLM comparisons in a bracket/tournament that must cite dossier fields to justify each verdict —
  the DAVP-style pattern that reached expert-level prioritization in 2026 benchmarks. Auditable because inputs
  are structured and every verdict is traceable; cheap because it touches only 20 candidates.
- **Option D — end-to-end deep model / GNN as primary ranker**: nothing to train on at N = 1; the KG link
  predictor belongs to Track 2, not here.

**⭐ Recommendation: A as the backbone (it must stand alone), C as the re-ranking layer and headline Innovation
claim, B if week-3 time allows (its benchmark table strengthens Scalability), D only as the Track 2 drug-hop
model.** Rationale: at N = 1 the win comes from *combining verified evidence*, not from model capacity; C adds
reasoning over evidence without adding unverifiable parameters, and it is the only option that also writes half
the report as a side effect.

---

## 9. What are the methods to evaluate the performance of these models?

### 9.1 The official metrics — reimplement them exactly

Two automated metrics (`raw_hackathon.txt:87-97`, mechanics in `hackathon-intel.md` §2.2/§8):

**Rank points** — tiered by the rank of the matching row: rank 1 → 100; ranks 2–3 → 50; ranks 4–5 → 25;
ranks 6–10 → 10; else 0. A *full* match (row's variant set exactly equals the true pair) scores the tier;
a *partial* match (row intersects the true pair) scores half the tier. Full match anywhere beats any partial
match — so the final submission must place the confirmed pair at rank 1 with nothing above it.

**F-max** — at the individual-variant level, sweeping the thresholds present in the file:

```
For each threshold t ∈ {epcr values in the file}:
    S(t) = union of variants in all rows with epcr ≥ t
    Precision P(t) = |S(t) ∩ T| / |S(t)| ,   Recall R(t) = |S(t) ∩ T| / |T| ,   |T| = 2
    F(t) = 2·P·R / (P + R)
F-max = max_t F(t)      (ties kept at the highest threshold, strict >)
```

`F-max = 1.0` requires the top-threshold set to be exactly the two true variants — i.e. the exact pair in one
rank-1 row. **Build a local reimplementation of the scorer and unit-test it** (the leaked `evaluation.py`
semantics are documented in `hackathon-intel.md` §8). Every submission CSV gets validated locally first:
schema, `PROBAND01`, `chr`-prefix, distinct descending `epcr` in (0,1], ≤10 rows, `finding_type` ∈
{primary, secondary}. A malformed CSV wastes one of 18 irreplaceable queries.

### 9.2 Offline evaluation without the answer key

The only honest way to measure the pipeline before the oracle answers: **synthetic probands**.

1. Take public control genomes (GIAB HG001–HG007, 1000 Genomes) — no restricted data involved.
2. Spike in known pathogenic **pairs** from ClinVar (recessive genes, compound-het configurations), including
   hard cases: deep-intronic splice variants, single-exon deletions, and low-VAF mosaic alleles.
3. Attach the corresponding disease's HPO profile, with realistic noise: drop 30% of terms, add 2–3 unrelated
   terms, and generalize some terms to parents (real referrals are noisy and imprecise).
4. Run the full pipeline blind; measure.

Metrics on that benchmark:

| Metric | Why |
|---|---|
| **Top-1 / top-3 / top-10 recall of the pair** | Mirrors the rank-point tiers directly |
| **MRR**, **NDCG@10** | Smooth ranking quality; NDCG is what LambdaMART optimizes |
| **F-max** (official formula) | Same code path as the real submission |
| **PR-AUC** (not ROC-AUC) | 2 positives among ~5 M candidates; ROC-AUC is uninformative under that imbalance |
| **Calibration: Brier score, ECE, reliability diagram** | `epcr` is a probability and drives F-max thresholds |
| **Sensitivity by variant class** (SNV / indel / splice / SV / mosaic) | Exposes exactly which class of hidden second allele the pipeline would miss — the designed trap |
| **Runtime + cloud cost per case** | Methods form Q17 asks for it; concrete numbers score on Scalability |

Also worth reporting: **ablations** (what does removing HPO / SpliceAI / phase constraint cost?) — cheap to run,
and it is the difference between "we ran tools" and "we understand our pipeline".

### 9.3 Technical QC — what has already passed, and what is still gated

Done, on the delivered files (`ressources/data-profile/`, methodology
[002](../methodology/002-callset-quality-and-composition.md),
[004](../methodology/004-sex-and-aneuploidy-from-allele-balance.md),
[005](../methodology/005-fastq-structure-and-quality.md)):

| Check | Result | Verdict |
|---|---|---|
| Read QC (fastp, 500k pairs from L001) | Q30 91.5% → 92.2%, GC 41.4%, dup 9.3%, insert peak 266 bp | Pass |
| `bcftools stats` | ts/tv **1.94** (ideal 2.0–2.1), het:hom-alt **1.61**, indel size distribution normal | Pass, mildly noisy |
| Contamination proxy | het:hom-alt 1.61 shows no gross excess heterozygosity | No contamination signal |
| Sex check, from allele balance | chrX at ~½ autosomal variant density with 4,858 hets (PAR-concentrated); chrY present at 36.3× with 4,301 hets | **Male** |
| Aneuploidy check | Mean het VAF 0.472–0.497 and mean depth 43.7–46.1 across chr1–22 | Flat — no detectable mosaic aneuploidy (§3.5) |
| Depth | ~44× mapped from VCF `DP`, 52× raw from FASTQ | Ample |

Still gated behind alignment (§1.1), and each one blocks a conclusion rather than a refinement:

- `samtools stats` + **mosdepth** per-exon and per-splice-site coverage of the candidate genes. A "no variant
  found" conclusion is worthless in a 5× region, and *TRIP13* — 6 of 12 calls filtered, telomere-proximal
  (§3.6) — is exactly that scenario waiting to be misread.
- Concordance of the provided VCF against our re-called VCF (`hap.py`/`rtg vcfeval`; GIAB for validating the
  *method*, provided-vs-recalled for *this* sample). This is how we measure what the delivered callset lost.
- `verifyBamID` / `somalier` for contamination and for confirming that the FASTQ and the VCF really come from
  the same individual — both need a BAM, so both are Tier 2 deliverables.

### 9.4 Using the oracle without fooling yourself

18 queries = a very small validation set. Treat it as a **held-out test set that you are allowed to query
adaptively**, and record every probe and outcome in the ledger. Two disciplines: (i) never let oracle feedback
silently rewrite the reported pipeline performance — report offline benchmark numbers and oracle outcomes
separately; (ii) keep ≥2 submissions in reserve for indel-representation retries and endgame defense.

### 9.5 Solution space & ⭐ recommendation

- **Option A — VCF-level spike-ins** (§9.2 as written): inject ClinVar pathogenic pairs into GIAB/1000G VCFs.
  Tests the *ranking* layer only — the injected variants are, by construction, already "called".
- **Option B — read-level spike-ins (tests what actually decides this contest)**: edit the alleles into the
  *reads* of a public BAM (BAMSurgeon/VarBen), including a leaky splice variant, a single-exon deletion, and a
  20%-VAF mosaic SNV, then run the **full** pipeline from alignment onward. This measures the discovery layer —
  exactly the class of failure the hidden second allele is designed to exploit. The per-class sensitivity table
  it produces is the most informative figure the methods form can contain.
- **Option C — time-split ClinVar honesty check**: evaluate the ranker using only predictor versions/labels
  predating the spiked variants' ClinVar submission dates, to bound the circularity inflation (§6 limitation 1).
- **Option D — Stenton/CAGI6 RGP replication**: the official metric's source benchmark; data access is gated and
  slow — do not block on it; cite it as the metric provenance instead.

**⭐ Recommendation: A for fast iteration (minutes per run, drives day-to-day development), B once, seriously,
in week 2 (it is the only honest answer to "would we find the hard allele?"), C as a one-paragraph disclosure,
D cited not executed.** Rationale: A optimizes the layer we iterate on; B validates the layer we bet on; the
combination is cheap and covers both.

---

## 10. Is there a deterministic theory and a probabilistic theory that can be applied to this data?

Both, and the winning design is **layered**: deterministic logic to *shrink and constrain* the space,
probabilistic inference to *order* what survives, decision theory to *choose the next experiment*.

### 10.1 Deterministic layer (exact, no free parameters)

| Deterministic object | Content | Payoff |
|---|---|---|
| **Variant canonicalization** | Left-alignment + parsimony (`bcftools norm -f REF -m -both`) gives a *unique* representation per allele; multiallelic splitting makes identity well-defined | Makes the scorer's string equality safe; eliminates the #1 silent-failure mode |
| **Mendelian / zygosity logic** | AR compound het requires: two distinct rare variants, same gene, both het, **in trans**. Homozygous or hemizygous configurations are excluded by the leaked "compound-heterozygous answer key". The proband is **male** (measured, §9.3), so chrX is hemizygous and cannot host a compound het at all — chrX is deterministically out of scope for the pair | Removes whole classes of hypotheses with certainty |
| **Phase exclusion** | Read-backed phasing (WhatsHap/SmartPhase/HiPhase, plus the caller's own `PGT`/`PID`): any pair proven *in cis* cannot be the compound het. A `1/2` multiallelic genotype proves *trans* outright | Certain, but rare: **measured 0.3% of pairs resolved on BUB1B** (3 trans, 2 cis, 1,648 unknown). A tiebreaker, not a space-collapser (§5.4). The 66,860 `1/2` sites are the free half |
| **Set algebra of the scorer** | Rows are `frozenset`s; order within a row is irrelevant; a duplicated variant collapses to a single-variant row; ranks come from sorting by `epcr` desc with ties broken by file order | Lets you *prove* what each probe can and cannot reveal, and construct probes deliberately |
| **Interval / graph logic** | Which variants lie in which transcript, exon, splice region; NMD-boundary rules; reading-frame arithmetic for indels | Deterministic consequence assignment (the basis of PVS1) |
| **Combinatorial enumeration** | With N rare variants in a gene, exactly `C(N,2)` pairs; the probe design is then a covering problem over that finite set | Turns "search" into a bounded, auditable enumeration |
| **Constraint propagation** | Once the oracle confirms allele A, every hypothesis not containing A is dead | Collapses the space by orders of magnitude in one step |

### 10.2 Probabilistic layer (uncertainty, calibrated)

| Probabilistic object | Model |
|---|---|
| Is the variant really there? | Genotype likelihoods (`PL`), binomial/beta-binomial allele-balance tests, mosaic VAF hypothesis tests (§7.4) |
| Is the allele damaging? | In-silico predictors as (imperfectly calibrated) probabilities; ESM/EVE LLRs as evidence, ACMG PP3/BP4 strength tiers via ClinGen calibration |
| Is the gene the right gene? | Phenotype likelihood ratios over the HPO DAG (LIRICAL), network propagation scores, gnomAD constraint as a prior |
| Is the genotype plausible in a population? | Hardy–Weinberg / `2·p₁·p₂` allele-frequency priors (§7.2) |
| Is the pair causal? | Bayesian ACMG posterior (§7.1) combined with the phenotype posterior; report as a posterior probability = `epcr` |
| Where is the copy-number boundary? | HMM posterior over copy-number states (§7.5) |
| Which probe should we spend next? | Sequential Bayesian experimental design / expected information gain (§7.6) |

### 10.3 How they compose

```
FASTQ/VCF ──[deterministic: normalize, canonicalize]──► unique allele identities
          ──[deterministic: AF/zygosity/gene-panel filters, phase-cis exclusion]──► finite candidate set (10²–10³)
          ──[probabilistic: ACMG posterior × phenotype LR × AF prior, rank-fused]──► ranked pair hypotheses with epcr
          ──[decision-theoretic: max expected information gain under the 18-query budget]──► probe S / P
          ──[deterministic: constraint propagation on oracle feedback]──► collapsed hypothesis space
          ──► confirmed pair ──► probe F: rank 1, epcr 1.0 → 100 rank points, F-max 1.0
```

Read the deterministic layer as **soundness** (never wrongly exclude the truth — so every hard filter needs a
justification and a documented sensitivity check) and the probabilistic layer as **efficiency** (spend attention
where the posterior mass is). The classic failure mode in rare-disease pipelines is an over-aggressive
deterministic filter — a `FILTER != PASS` drop, an AF cutoff, a "coding only" restriction — that removes the
answer before any model sees it. **Every filter must be logged with the count of variants it removed**, and for
the candidate genes the pipeline should be run *unfiltered* as well.

### 10.4 Solution space & ⭐ recommendation

The composition order itself has alternatives:
- **Option A — deterministic-first** (as in §10.3): shrink, then rank, then probe. Risk: an unsound filter.
- **Option B — probabilistic-first**: score everything genome-wide, never filter, rank 5M variants. Sound by
  construction but drowns the signal in predictor noise and multiple-testing burden (§7.4).
- **Option C — dual-lane (recommended)**: run A as the fast lane and keep a slow lane where every "deterministic"
  exclusion is demoted to a strong negative prior instead of removal (filtered variants keep a small posterior
  mass, revisited only if the fast lane's hypotheses are refuted by probes). The oracle's refutations then have
  somewhere principled to redirect probability mass — without this, a refuted top-10 forces ad-hoc re-filtering.

**⭐ Recommendation: C.** It costs one boolean column (`hard_excluded` → `prior_penalty`) and buys a principled
recovery path for exactly the scenario that kills teams: "our candidates were all wrong and we don't know what
we filtered away."

---

## 11. Should we create our own database, or use an existing one?

**Use existing sources; build only a thin local analytical layer.** Do not curate a new database.

### 11.1 Reuse (authoritative, versioned, citable)

| Purpose | Source | Note |
|---|---|---|
| Variant classifications | **ClinVar** (weekly VCF + `variant_summary.txt`) | Record the release date; classifications change |
| Population frequency | **gnomAD v4** (genomes+exomes), plus per-gene constraint (pLI/LOEUF) | Use popmax, not just global AF |
| Precomputed predictor scores | **dbNSFP** (v5.x) — CADD, REVEL, MetaRNN, AlphaMissense, ESM1b, phyloP … in one join | Saves days of tool wrangling |
| Splice | SpliceAI / Pangolin precomputed sets + on-the-fly for novel positions | Precomputed sets are SNV-only near genes; indels need a run |
| Annotation engine | **Ensembl VEP** offline cache (+ LOFTEE, dbNSFP, SpliceAI, AlphaMissense plugins) | Pin the VEP and cache versions |
| Gene/transcript models | Ensembl / RefSeq (MANE Select) | Always report HGVS on the MANE transcript |
| Phenotype ontology | **HPO** (`hp.json`) + disease annotations (`phenotype.hpoa`) | Monthly releases; pin the version |
| Disease/gene knowledge | **OMIM**, Orphanet, ClinGen, GenCC, GeneReviews | Gene–disease validity and allelic variant tables |
| Structural variants | gnomAD-SV, DGV, dbVar; **AnnotSV** for annotation | For SV frequency filtering |
| Pathways / interactions | Reactome, STRING, Open Targets | Feeds the KG and Track 2 |
| Structures | AlphaFold DB, PDB, UniProt | Residue-level mechanism figures |
| Drugs (Track 2) | **DrugBank, ChEMBL, ClinicalTrials.gov, Open Targets, DGIdb, PubChem** | The methods form name-drops exactly these — use them and cite them |

### 11.2 Build (small, local, disposable)

A single **DuckDB file + Parquet** store, produced by a scripted pipeline:

```
variants        (chrom, pos, ref, alt, filter, dp, gq, vaf, gt, phase_set, ...)     -- from the proband VCF  [PRIVATE]
annotations     (chrom, pos, ref, alt, gene, transcript, consequence, hgvsc, hgvsp,
                 gnomad_af, cadd, revel, alphamissense, spliceai_max, esm_llr, ...) -- VEP/dbNSFP join       [PRIVATE: keyed on patient variants]
genes           (symbol, ensg, mane_transcript, pli, loeuf, mis_z, panel_tier)      -- public
hpo_terms       (term_id, label, ic, parents)                                       -- public
gene_disease    (symbol, disease_id, moi, validity, hpo_profile)                    -- public
candidates      (variant_key, gene, score components…, epcr)                        -- derived               [PRIVATE]
pair_hypotheses (var1_key, var2_key, gene, phase, acmg_points, epcr, notes)         -- derived               [PRIVATE]
oracle_ledger   (submission_id, member, probe_type, rows_json, rank_points, f_max,
                 f_max_threshold, full_match_rank, partial_match_rank, decoded)     -- derived               [PRIVATE]
```

Why this and not more:
- **Time**: ~8.5 weeks to Oct 24, and the answer is very likely already sitting in the provided VCF
  (`hackathon-intel.md` §4 Phase 1). Database engineering is not the bottleneck; the hidden second allele is.
- **Credibility**: judges reward reproducibility and standard, citable resources. A bespoke database is an
  unreviewable black box and a liability in the methods writeup.
- **Reproducibility**: the build should be one command (Snakemake/Nextflow + a pinned container), so the whole
  store is reconstructible from public sources + the gated input.

### 11.3 Compliance constraints on the store (non-negotiable)

1. **Physical separation.** Public reference data in one directory/volume; anything keyed on proband variants in
   another. The tables marked `[PRIVATE]` above are **derived patient datasets** under the rules and must be
   deleted within 30 days of close, along with local files, cloud volumes, notebooks, and private repo history.
2. **Two repositories.** Public repo = code, configs, environment specs, synthetic-benchmark results, figures
   built from public data only. Private repo = everything touching the proband. Add a pre-commit hook that
   rejects `*.vcf*`, `*.bam`, `*.cram`, `*.fastq*`, and any file containing `PROBAND01` from the public repo —
   an accidental commit of a VCF slice is a resharing violation.
3. **Deletion is a deliverable.** Script it (`make purge` covering local paths, cloud volumes, caches, and
   notebook outputs), log it, then email `RarediseaserealkidMVAhackathon2026@synapse.org` to confirm.
4. **Provenance.** Pin every external resource version in a manifest (ClinVar release, gnomAD version, VEP
   cache, HPO release, container digests). Needed for the report, and it is what makes results reproducible
   after the data is destroyed.

### 11.4 Solution space & ⭐ recommendation

- **Option A — thin DuckDB layer over authoritative sources** (as above).
- **Option B — publish the public half as an "N-of-1 toolkit" (creative, CC-BY-safe)**: the reported-allele
  catalogue builder (§4.5-B), the scorer reimplementation + probe simulator, the synthetic-proband benchmark,
  and the pinned annotation-join recipes contain **zero patient data** — released as a documented package they
  become a reusable resource for other undiagnosed cases, which is verbatim the hackathon's stated purpose
  ("methods developed for this case can be reused for other undiagnosed individuals") and a direct play for the
  Innovation/Community award ($2k+$2k, judged on community impact independent of placement).
- **Option C — a genuinely new curated database** (e.g. hand-curated MVA allele registry): curation liability,
  unreviewable in 8 weeks, and the moment it contains a proband-derived row it becomes deletable patient data.

**⭐ Recommendation: A during the contest, B packaged in the final week from artefacts that already exist,
C never.** Rationale: B costs ~2 days of packaging because every component is already required by the strategy;
it is the cheapest credible shot at a second prize category.

---

## 12. Remaining unknowns and how to close them

### 12.1 Closed by the data profile

| Was unknown | Answer | Evidence |
|---|---|---|
| Exact file inventory | 85.0 GB: 1 VCF + index, 8 FASTQ, 1 phenotype `.docx`, 1 dataset README. **No BAM, no CRAM** | `manifest.tsv`, §1.1 |
| Singleton vs trio/duo | **Singleton.** One sample column, `WGS_EX2312012` | `vcf_header.txt`, §1.3 |
| Exact HPO term list | 8 terms; rhabdomyosarcoma, nephrocalcinosis, short stature, failure to thrive, muscle atrophy, prematurity, SGA, parental recurrent miscarriage. **No microcephaly, no intellectual disability** | Phenotype document, §1.4 |
| Malignancy type | **Rhabdomyosarcoma** (`HP:0002859`) | §1.4 |
| Chromosome naming + reference | Bare contigs (`15`); `GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta`; 1,690 contigs incl. 1,517 decoys | `vcf_header.txt`, §1.3 |
| Caller + filter status | Sentieon Haplotyper 202308.02 → GVCFtyper → GATK `VariantFiltration` 4.2.4.0. 94.6% PASS, 271,414 non-PASS (`MQ40` 177,522) | §1.3 |
| Are structural variants in the callset? | **No.** SNV + indel only; no SV/CNV caller in the provenance chain | §1.3 |
| Does the VCF carry annotation? | **No.** Caller statistics only; `INFO/AF` is within-sample | §1.3 |
| How much does phasing resolve? | 0.3% of *BUB1B* pairs (3 trans, 2 cis, 1,648 unknown) | [methodology 006](../methodology/006-phasing-power-on-bub1b.md), §5.4 |
| Mosaic aneuploidy visible in allele balance? | **No.** Het VAF 0.472–0.497, depth 43.7–46.1 across chr1–22 | §3.5 |
| Proband sex | **Male** | §9.3 |
| Sequencing depth and read shape | 2 × 149 bp, 4 lanes, 1 library, 52× raw / ~44× mapped | §1.2 |

### 12.2 Still open

| Unknown | How to resolve | Blocks what |
|---|---|---|
| Consequence and population frequency of the 861 panel variants | VEP + gnomAD v4 + dbNSFP join — **the blocking dependency** | Everything downstream of §3.6; there is no ranking signal in the file today |
| Coverage of BUB1B/TRIP13/CEP57 exons and splice sites | `mosdepth` on the candidate loci — needs a BAM, so gated on Tier 2 | Whether "absent" means absent, especially for telomere-proximal *TRIP13* |
| Whether an SV is one of the two alleles | Align 161 Gb → Manta/Delly/smoove 2-of-3 consensus + GATK-gCNV | The single largest blind spot: an SV allele *cannot* be in the delivered VCF |
| Whether either candidate allele is already in ClinVar | ClinVar join (public data, runnable today) | Circularity disclosure; near-instant confirmation if yes |
| Whether the aneuploid fraction is simply below the allele-balance floor | Binned-depth + BAF karyogram from aligned reads (lower floor than §3.5's VCF-only pass) | Strength of the diagnostic corroboration paragraph |
| Whether `HP:0200067` (a parental feature) should enter the proband's term set | Run Exomiser/LIRICAL with and without, report the delta | Phenotype LR calibration, §1.4 |
| Whether nephrocalcinosis is part of the MVA picture or independent | Literature check against reported MVA cases | Whether it is a differential lead or a footnote |

### Priority ordering, revised

1. ~~Inventory + headers + QC~~ — **done** (§1.1–§1.3, §9.3). It produced six plan-changing corrections.
2. **Annotate.** `bcftools norm -f <no-chr GRCh38> -m -both`, then VEP + gnomAD v4 + dbNSFP over the panel and
   then genome-wide. This is the only step that turns 861 counted variants into candidates, and nothing after
   it can start without it.
3. **Launch the alignment job** (bwa-mem2 → DeepVariant → SV consensus) in the background on day 1. It is a
   1–2 day dependency of the report and of the entire SV hypothesis, not a contingency (§6.4).
4. Mine the **271,414 non-PASS** calls and split the **66,860 `1/2`** sites inside the panel — minutes, and
   free trans evidence (§5.4, §6.4 Tier 1.5).
5. Run Exomiser + LIRICAL on the **real** 8 HPO terms, genome-wide, with and without `HP:0200067`.
6. Enumerate rare het pairs per gene, compute ACMG points and phase, rank.
7. Build the local scorer reimplementation + CSV validator **before** the first submission — including the
   `15` → `chr15` conversion test, which is now a known live failure mode rather than a hypothetical one.
8. Only then spend probe S₁.

---

## 13. Sources

Disease and mechanism:
- [Mosaic variegated aneuploidy in development, ageing and cancer — Nature Reviews Genetics (2024)](https://www.nature.com/articles/s41576-024-00762-6)
- [Mosaic variegated aneuploidy syndrome — Atlas of Genetics and Oncology](https://atlasgeneticsoncology.org/cancer-prone-disease/10167/mosaic-variegated-aneuploidy-syndrome)
- [BubR1 allelic effects drive phenotypic heterogeneity in mosaic-variegated aneuploidy progeria syndrome — JCI](https://www.jci.org/articles/view/126863)
- [MVA syndrome mutation or haploinsufficiency in Cep57 impairs tumor suppression — JCI](https://www.jci.org/articles/view/120316)
- [Mutations in CEP57 cause mosaic variegated aneuploidy syndrome — PubMed](https://pubmed.ncbi.nlm.nih.gov/21552266/)
- [MVA syndrome 2 caused by biallelic variants in CEP57: two new cases and review of the phenotype — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1769721221002044)
- [MVA syndrome with tetraploidy and predisposition to male infertility triggered by mutant CEP192 — medRxiv](https://www.medrxiv.org/content/10.1101/2023.07.22.23292907.full.pdf)
- [GTS5: Mosaic variegated aneuploidy (BUB1B, CEP57, TRIP13, BUB1, BUB3) — Compendium of Cancer Genome Aberrations](https://ccga.io/index.php?title=GTS5%3AMosaic_variegated_aneuploidy_%28BUB1B%2C_CEP57%2C_TRIP13%2C_BUB1%2C_BUB3%29)

Variant prioritization methods and benchmarks:
- [Evaluation of phenotype-driven gene prioritization methods for Mendelian diseases — Briefings in Bioinformatics](https://academic.oup.com/bib/article/23/2/bbac019/6521702)
- [Evaluation of a whole-exome sequencing pipeline and benchmarking of causal germline variant prioritizers — PubMed](https://pubmed.ncbi.nlm.nih.gov/36054330/)
- [Benchmarking Exomiser on real patient whole-exome data — PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7230372/)
- [Phenotype-driven approaches to enhance variant prioritization and diagnosis of rare disease — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9288531/)
- [Phenotype-aware prioritisation of rare Mendelian disease variants — Trends in Genetics](https://www.cell.com/trends/genetics/fulltext/S0168-9525(22)00179-2)
- [Phen2Gene: rapid phenotype-driven gene prioritization for rare diseases — NAR Genomics and Bioinformatics](https://academic.oup.com/nargab/article/2/2/lqaa032/5843800)

Phasing / compound heterozygosity:
- [SmartPhase: accurate and fast phasing of heterozygous variant pairs for genetic diagnosis of rare diseases — PLOS Comp Biol](https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1007613)
- [Phasing and WhatsHap — EPI2ME](https://epi2me.nanoporetech.com/phasing-and-whatshap/)
- [Exome-wide evidence of compound heterozygous effects across common phenotypes in the UK Biobank — Cell Genomics](https://www.cell.com/cell-genomics/fulltext/S2666-979X(24)00196-4)
- [Advancing long-read nanopore genome assembly and accurate variant calling for rare disease detection — PubMed](https://pubmed.ncbi.nlm.nih.gov/39862869/)

Sequence models:
- [Advancing regulatory variant effect prediction with AlphaGenome — Nature](https://www.nature.com/articles/s41586-025-10014-0)
- [AlphaGenome preprint — bioRxiv](https://www.biorxiv.org/content/10.1101/2025.06.25.661532v1)
- [Assessing large-scale genomic language models in predicting personal gene expression: promises and limitations — bioRxiv](https://www.biorxiv.org/content/10.1101/2025.07.09.664024v1.full)
- [Evo 2 technical overview](https://medium.com/meta-multiomics/evo2-demystified-the-ultimate-technical-guide-to-genomic-language-modeling-a75b0afe7b87)

Aneuploidy-selective pharmacology (Track 2):
- [Identification of aneuploidy-selective antiproliferation compounds — Cell (AICAR, 17-AAG, chloroquine)](https://www.sciencedirect.com/science/article/pii/S0092867411000560)
- [Selective vulnerability of aneuploid human cancer cells to inhibition of the spindle assembly checkpoint — bioRxiv](https://www.biorxiv.org/content/10.1101/2020.06.18.159038.full.pdf)
- [Targeting the mitochondrial RNA methyltransferase TRMT61B in aneuploid cancer cells — bioRxiv](https://www.biorxiv.org/content/10.1101/2021.04.25.441348.full.pdf)
- [AICAR-mediated selection of karyotypically normal cells in Pallister–Killian syndrome fibroblasts — bioRxiv](https://www.biorxiv.org/content/10.1101/2022.01.27.478025.full.pdf)
- [Homing in on genomic instability as a therapeutic target in cancer — Nature Communications](https://www.nature.com/articles/s41467-021-23965-5)

Agentic / LLM prioritization (2025–2026, feeds §4.5-C and §8.8-C):
- [An agentic system for rare disease diagnosis with traceable reasoning — PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12999473/)
- [Deep Agentic Variant Prioritisation for expert-level genetic diagnosis (DAVP) — medRxiv](https://www.medrxiv.org/content/10.64898/2026.02.17.26346421v2.full)
- [Hygieia: a versatile AI agent for rare disease diagnosis and risk gene prioritization — arXiv](https://arxiv.org/html/2605.06226v2)
- [LA-MARRVEL: knowledge-grounded LLM framework for rare disease gene prioritization — arXiv](https://arxiv.org/pdf/2511.02263)
- [LLM-assisted reanalysis of unsolved rare disease genomes increases diagnostic yield — ResearchGate](https://www.researchgate.net/publication/407279253_LLM-Assisted_Reanalysis_of_Unsolved_Rare_Disease_Genomes_Increases_Diagnostic_Yield)

Mapping-free / k-mer genotyping (feeds §1.5-B):
- [MALVA: genotyping by mapping-free allele detection of known variants — iScience](https://www.sciencedirect.com/science/article/pii/S2589004219302366)
- [2-kupl: mapping-free variant detection from DNA-seq of matched samples — PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8180056/)
- [SKA2: split k-mer analysis — Genome Research](https://genome.cshlp.org/content/34/10/1661)
