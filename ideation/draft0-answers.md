# draft0 — Answered

Companion to `draft0.md` (open questions) and `hackathon-intel.md` (strategy/intel).
Scope: every question in `draft0.md`, answered with concrete tools, schemas, math, and limitations.
Status of facts: biology/tooling = literature-grounded; dataset internals = inferred from the rules dump
(`ressources/hackathon-rules/raw_hackathon.txt`) and marked **[verify on data]** where it must be checked
against the actual files before it drives a decision.

---

## 0. Executive summary (read this if nothing else)

| Question | One-line answer |
|---|---|
| Data type | Paired-end short-read WGS: FASTQ + germline VCF on GRCh38, optional BAM/CRAM, phenotype as HPO term list. ~85 GB, 11 files, single subject `PROBAND01`. |
| Visualize / query | Yes. `bcftools`/`tabix` + VEP → Parquet → DuckDB SQL for querying; IGV/igv.js + mosdepth/MultiQC for visual inspection; HPO DAG via `pyhpo`/`oaklib`. |
| What is MVA | Autosomal-recessive chromosome-missegregation syndrome: 25–50% of somatic cells carry random gains/losses ("variegated"). Caused by biallelic loss of spindle-assembly-checkpoint / centrosome genes. Microcephaly, growth failure, cancer predisposition. |
| Literature access | Yes, fully open: PubMed E-utilities, Europe PMC, PubTator3, OMIM/GeneReviews/Orphanet, ClinVar, OpenAlex. Papers are public; the *patient data* is not — never mix them in a public repo. |
| Data structures | Canonical variant tuple `(chrom, pos, ref, alt)` → columnar variant table (Parquet/DuckDB) + interval index over gene models + HPO DAG + candidate-pair `frozenset` mirror of the scorer + append-only oracle ledger. |
| Open-source models | Callers (DeepVariant, Clair3, Manta/Delly/GRIDSS, GATK-gCNV, ExpansionHunter), effect predictors (CADD, REVEL, AlphaMissense, ESM-2/ESM1b, EVE, SpliceAI, Pangolin, AbSplice, ReMM, AlphaGenome, Evo 2), prioritizers (Exomiser, LIRICAL, AMELIE, Phen2Gene, GADO). Main limitations: ClinVar circularity, missense-only coverage, gene-level ≠ allele-level, poor non-coding calibration, no mosaicism model. |
| Statistical / math models | Bayesian ACMG point framework, LIRICAL-style likelihood ratios, Hardy–Weinberg carrier priors, binomial/beta-binomial for VAF & mosaicism, HMM for CNV segmentation, and — for submission strategy — adaptive group testing / sequential experimental design maximizing information gain per oracle query. |
| ML model families | Learning-to-rank (LambdaMART/XGBoost-rank) over annotated candidates, calibrated classifiers for `epcr`, PU-learning (only positives labeled), sequence/protein deep models as frozen feature extractors, GNN over a gene–phenotype–variant knowledge graph, LLM agents for literature triage. **No in-patient training: N = 1.** |
| Evaluation | Rank metrics (top-1, recall@k, MRR), F-max (the official metric — reimplement it), PR-AUC over ROC-AUC (extreme imbalance), calibration (Brier/ECE) because `epcr` is a probability, validated on synthetic probands built by spiking ClinVar pathogenic pairs into public control genomes (GIAB/1000G). |
| Deterministic vs probabilistic | Both, layered: deterministic = variant canonicalization, Mendelian/zygosity logic, phase-based exclusion, set algebra of the scorer; probabilistic = genotype likelihoods, Bayesian causality posterior, phenotype LRs, calibrated ranking. Deterministic layer shrinks the space; probabilistic layer orders what survives. |
| Own DB? | **No new curated database.** Reuse ClinVar / gnomAD v4 / HPO / OMIM / dbNSFP / VEP caches, and build only a thin local analytical store (one DuckDB file + Parquet) that is itself a *derived dataset* and must be deleted within 30 days of close. |

---

## 1. What is the type of the data?

### 1.1 What the rules state (authoritative)

From the rules dump (`raw_hackathon.txt:492-494`):

> File types: genomic data in VCF format; raw sequencing data optionally in BAM/CRAM. Phenotypic data as
> standardized HPO terms.
> Data size: ~85 GB (single-subject dataset).

Track 1 description (`raw_hackathon.txt:74`): *"the child's genomic data (FASTQ + VCF) and a description of their symptoms"*.

So three modalities:

| Modality | Format | Role in the analysis |
|---|---|---|
| Raw reads | FASTQ (gzipped, paired R1/R2), optional aligned BAM/CRAM | Re-calling, SV/CNV detection, low-VAF mosaic scan, manual IGV confirmation |
| Called variants | VCF (GRCh38 / hg38, `chr`-prefixed) | Primary hunting ground: SNV/indel candidate extraction and annotation |
| Phenotype | HPO term list (possibly a Phenopacket JSON) | Drives phenotype-aware prioritization (Exomiser/LIRICAL) and gene-level priors |

### 1.2 What the size implies

85 GB across 11 files for one subject is consistent with **~30× short-read WGS**, not exome:

- 30× WGS ≈ 90–100 Gbp → gzipped FASTQ ≈ 60–80 GB (two files, or lane-split);
- a CRAM at 30× ≈ 15–25 GB; a BAM ≈ 60–90 GB;
- a single-sample WGS VCF ≈ 4–6 M variants ≈ 1–2 GB uncompressed, ~150–250 MB as `.vcf.gz`.

Practical read: FASTQ dominates the 85 GB. **This matters strategically** — WGS (not WES) means non-coding,
deep-intronic and structural second alleles are *in scope*, which is exactly the compound-het trap flagged in
`hackathon-intel.md` §3.

### 1.3 First-hour verification checklist **[verify on data]**

```bash
# inventory
ls -l  # confirm the 11 files and which modalities are actually present

# VCF: reference build, chrom naming, sample id, caller, variant count
bcftools head calls.vcf.gz | head -50          # ##reference, ##contig, ##source, #CHROM line
bcftools query -l calls.vcf.gz                 # sample name — is it literally PROBAND01?
bcftools index -n calls.vcf.gz                 # record count
bcftools stats calls.vcf.gz > stats.txt        # SNV/indel ratio, TSTV, singleton profile

# is it single-sample or a trio? (decides whether phasing is free)
# is it already phased? look for GT with '|' and for PS/HP FORMAT fields
bcftools query -f '[%GT\t%PS\n]' -r chr15 calls.vcf.gz | head

# FASTQ: read length, lane structure, encoding
zcat R1.fastq.gz | head -8
zcat R1.fastq.gz | head -400000 | awk 'NR%4==2{print length($0)}' | sort -n | uniq -c | tail

# BAM/CRAM if present: aligner, sort order, dup marking, reference used
samtools view -H aln.cram | grep -E '^@RG|^@PG|^@HD'
```

Five facts to nail down before any modelling:

1. **Exact `proband_id`** in the VCF vs the `PROBAND01` the scorer demands (they can differ; the scorer only
   accepts `PROBAND01`, matched case-sensitively after `.strip()`).
2. **Chromosome naming** (`chr15` vs `15`) — the scorer does **not** normalize `chrom`; the template uses `chr1`.
3. **Reference build + patch** (GRCh38 with/without alt contigs; which FASTA to use for `bcftools norm`).
4. **Singleton vs trio/duo** — if parents are present, compound-het phasing is solved for free; if not, use
   read-backed phasing (§5.4, §10.2).
5. **Caller and filter status** — a `PASS`-only VCF may already have discarded the hard second allele
   (low-VAF, near-indel, repeat-region calls). Always analyse the *unfiltered* records too.

### 1.4 Phenotype data shape

HPO terms are nodes of a directed acyclic graph (`hp.obo` / `hp.json`, released monthly). Expect something like
`HP:0000252` (Microcephaly), `HP:0001518` (Small for gestational age), `HP:0002664` (Neoplasm),
`HP:0001249` (Intellectual disability) **[verify on data]**. Handle them as a *set of DAG nodes with ancestor
closure*, never as strings: phenotype similarity requires walking the ontology (Resnik/Lin/Phenomizer-style
information-content measures, §7.3).

---

## 2. Can we visualize it? And query it?

Yes to both. Build two separate stacks — an *interactive inspection* stack and an *analytical query* stack —
because they answer different questions.

### 2.1 Query stack (the workhorse)

Pipeline: **VCF → normalize → annotate → columnar → SQL**

```bash
# 1. canonicalize (critical for scorer string-equality matching)
bcftools norm -f GRCh38.fa -m -both -c w calls.vcf.gz -Oz -o norm.vcf.gz
bcftools index -t norm.vcf.gz

# 2. targeted extraction: MVA + SAC/centrosome panel first (minutes, not days)
bcftools view -R mva_panel.bed norm.vcf.gz -Oz -o panel.vcf.gz

# 3. annotate (Ensembl VEP, offline cache + plugins)
vep -i norm.vcf.gz -o annotated.vcf --cache --offline --assembly GRCh38 \
    --vcf --everything --canonical --symbol --hgvs --af_gnomadg \
    --plugin CADD,... --plugin SpliceAI,... --plugin AlphaMissense,... \
    --plugin REVEL,... --plugin dbNSFP,...

# 4. flatten to a columnar table
bcftools +split-vep annotated.vcf -d -f '%CHROM\t%POS\t%REF\t%ALT\t%SYMBOL\t%Consequence\t...\n' \
  > variants.tsv     # → convert to Parquet
```

Then query with **DuckDB** directly over Parquet — zero-server, SQL, fast on millions of rows:

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
| Reads over a candidate locus (the decisive human check) | **IGV** desktop on BAM/CRAM; `igv.js` for a shareable, screenshot-friendly report figure |
| Per-exon / per-base coverage (single-exon deletions) | **mosdepth** + a simple matplotlib/Altair coverage track |
| Sequencing / alignment QC | **FastQC → MultiQC**, `samtools stats`, `bcftools stats` plots |
| Genome-wide CNV / aneuploidy view | Binned depth (mosdepth 10–100 kb) → log2 ratio plot; this is also how you *look for the aneuploidy itself* |
| SV inspection | **samplot** or IGV split-read/discordant-pair view; `svtools`/`AnnotSV` for tabular SV annotation |
| Gene/transcript context, domains | Ensembl / UCSC browser, UniProt feature viewer, AlphaFold structure + PyMOL/py3Dmol for residue mapping |
| Phenotype context | HPO term set vs disease profiles; a simple similarity heatmap makes a strong report figure |

Two visualization payoffs specific to MVA:
1. **A binned-depth karyogram of the proband.** MVA is mosaic aneuploidy in *somatic* cells. Depending on the
   sequenced tissue and mosaic fraction, whole-chromosome copy-number *shifts* may be visible as subtle log2
   deviations (a 20% mosaic trisomy ≈ log2 ratio ~0.14 — small but detectable with enough bins). Finding it is
   not required to win, but it is a striking, defensible report figure and a sanity check on the diagnosis.
2. **IGV panels for the two final alleles.** The report is a tiebreaker (`hackathon-intel.md` §4 Phase 4);
   read-level screenshots of both alleles, plus the phasing evidence, is what a clinical reviewer wants to see.
   **Compliance:** screenshots of patient reads are patient data — they go in the report submitted to organizers,
   **never** into the public GitHub repo (`raw_hackathon.txt` data-resharing clause).

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

### 3.4 Why this drives the whole strategy

Three independent facts converge:
1. The leaked evaluator says the answer is **compound heterozygous** (`hackathon-intel.md` §2.1) → recessive,
   two variants, one gene, one per allele.
2. The public story says care today means *"managing symptoms and fighting cancer cells"* (`raw_hackathon.txt:55`)
   → **active malignancy** → favours the cancer-predisposing subtypes: **BUB1B** ≫ TRIP13 > CEP57 (CEP57
   classically lacks malignancy).
3. Biallelic *complete* BUB1B loss is not viable, so real BUB1B patients are typically **one truncating/null
   allele + one hypomorphic allele** — and hypomorphic alleles are frequently **deep-intronic / splice-altering
   or otherwise not called cleanly**. That is precisely why FASTQ ships alongside the VCF.

**Working hypothesis before touching data: compound het in *BUB1B* (chr15q15.1), one clean LoF + one hard
(splice/intronic/SV/low-VAF) allele.** Fallbacks in order: TRIP13, CEP57, CEP192/CENPE/SMC5, then novel gene.
Note also that *KNL1/CASC5* sits at 15q15.1 next to *BUB1B* — do not let a `chr15` hit auto-assign to *BUB1B*
without checking the transcript.

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
    chrom: str                      # 'chr15'  — chr-prefixed, lowercase 'chr', NOT normalized by the scorer
    pos: int                        # 1-based VCF POS, after `bcftools norm -m -both` left-alignment
    ref: str                        # uppercase
    alt: str                        # uppercase, single allele (multiallelics already split)

Pair = FrozenSet[Variant]           # exactly how the scorer represents a row; |Pair| ∈ {1, 2}
```

Everything downstream keys off `Variant`. One normalization function, one place, unit-tested against a handful
of hand-built indel cases (the indel-representation trap in `hackathon-intel.md` §8.1 is the #1 silent failure).

### 5.2 Storage layer

| Layer | Structure | Why |
|---|---|---|
| Raw callset | `bgzip` + `tabix` (CSI/TBI) VCF | Random access by region in O(log n); the standard everyone expects |
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
  computes). Two candidate variants in the same phase block with *opposite* haplotype assignment = *trans* =
  a valid compound het; same haplotype = *cis* = excluded deterministically. Read-backed phasing only spans
  read/fragment length (~250 bp–1 kb), so most gene-scale pairs come back `unknown` — but every `cis` call is a
  free, certain elimination (SmartPhase reports ~22% of pairs excluded in singletons this way).
- **Coverage arrays / HMM state sequence** for CNV and single-exon deletions: per-base or per-exon depth →
  normalized log2 ratio → HMM segmentation (§7.5).
- **Sparse VAF table** for the mosaic scan: MVA involves mosaicism, so a somatic-style low-VAF second hit is
  plausible; keep `(variant, alt_depth, total_depth)` and test against a binomial/beta-binomial null (§7.4)
  rather than a fixed VAF cutoff.

---

## 6. What open-source models can we use for prediction, and what are their limitations?

Split by job. Nothing here needs training on the proband — all are pretrained or rule-based, which is the only
option at N = 1.

### 6.1 Variant calling / discovery (recover the allele the VCF missed)

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

### 9.3 Technical QC that must pass before any metric is believed

`FastQC/MultiQC` on reads; `samtools stats` + `mosdepth` for coverage (mean, % ≥20×, and *specifically* the
coverage of every exon and splice site of the candidate genes — a "no variant found" conclusion is worthless in
a 5× region); `bcftools stats` (Ti/Tv ≈ 2.0–2.1 for WGS, het/hom ratio, indel size distribution); concordance
of the provided VCF vs your re-called VCF (`hap.py`/`rtg vcfeval` against GIAB for the *method*, and
provided-vs-recalled for *this* sample); contamination/sex checks (`verifyBamID`, `somalier`) — `somalier` also
sanity-checks whether the FASTQ, BAM and VCF really come from the same individual.

### 9.4 Using the oracle without fooling yourself

18 queries = a very small validation set. Treat it as a **held-out test set that you are allowed to query
adaptively**, and record every probe and outcome in the ledger. Two disciplines: (i) never let oracle feedback
silently rewrite the reported pipeline performance — report offline benchmark numbers and oracle outcomes
separately; (ii) keep ≥2 submissions in reserve for indel-representation retries and endgame defense.

---

## 10. Is there a deterministic theory and a probabilistic theory that can be applied to this data?

Both, and the winning design is **layered**: deterministic logic to *shrink and constrain* the space,
probabilistic inference to *order* what survives, decision theory to *choose the next experiment*.

### 10.1 Deterministic layer (exact, no free parameters)

| Deterministic object | Content | Payoff |
|---|---|---|
| **Variant canonicalization** | Left-alignment + parsimony (`bcftools norm -f REF -m -both`) gives a *unique* representation per allele; multiallelic splitting makes identity well-defined | Makes the scorer's string equality safe; eliminates the #1 silent-failure mode |
| **Mendelian / zygosity logic** | AR compound het requires: two distinct rare variants, same gene, both het, **in trans**. Homozygous or hemizygous configurations are excluded by the leaked "compound-heterozygous answer key" | Removes whole classes of hypotheses with certainty |
| **Phase exclusion** | Read-backed phasing (WhatsHap/SmartPhase/HiPhase): any pair proven *in cis* cannot be the compound het | Every `cis` call is a certain elimination (~22% of pairs in singletons) |
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

---

## 12. Remaining unknowns and how to close them

| Unknown | How to resolve | Blocks what |
|---|---|---|
| Exact file inventory (11 files: FASTQ pairs? BAM? CRAM? phenopacket?) | `ls -l` + headers, §1.3 | Compute plan |
| Singleton vs trio/duo | `bcftools query -l` | Whether phasing is free or must be read-backed |
| Exact HPO term list | Read the phenotype file | Exomiser/LIRICAL runs, gene prior, malignancy confirmation |
| Whether the child's malignancy type is stated | Phenotype file + story page | Sharpens BUB1B vs TRIP13; central to Track 2 framing |
| Chromosome naming + reference FASTA/patch | VCF header | Scorer string matching, `bcftools norm` |
| Caller + filter status of the provided VCF | VCF header, `FILTER` distribution | Whether the second allele was filtered out |
| Coverage of BUB1B/TRIP13/CEP57 exons and splice sites | `mosdepth` on the candidate loci | Whether "absent" means absent |
| Whether either candidate allele is already in ClinVar | ClinVar join | Circularity disclosure; near-instant confirmation if yes |
| Whether a mosaic aneuploidy signal is visible in depth/BAF | Binned depth + BAF plots | Diagnostic corroboration + a strong report figure |

### Priority ordering (first 48 hours)

1. Inventory + headers + QC (§1.3) — one hour, prevents every downstream mistake.
2. `bcftools norm` the VCF, then **grep the panel genes** (BUB1B, TRIP13, CEP57, CENPE, CEP192, SMC5, BUB1,
   BUB3, KNL1, PLK4, MAD1L1, MAD2L1, CDC20, TTK/MPS1) and annotate with VEP. The answer is probably here.
3. Parse HPO terms; run Exomiser + LIRICAL genome-wide in parallel (unbiased backbone for the report).
4. Enumerate rare het pairs per gene, compute ACMG points and read-backed phase, rank.
5. Build the local scorer reimplementation + CSV validator **before** the first submission.
6. Only then spend probe S₁.

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
