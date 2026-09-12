# Step 3 — alignment-free genotype and copy number

**Standing:** opened 2026-09-12 by step 2's handover; **nothing has run.** Revised the same
day, after step 2's completion audit changed two of the things this page hands over — see
§3.9 and §4. Iteration 2, `step-3`.

**Goal** (from `src/mva/science/steps.py`):

> Read without an aligner or a caller, are the discovered alleles at heterozygous
> multiplicity, is every target-gene exon at two copies, and which public ClinVar P/LP
> alleles are present at all?

Design: [`plan.md`](../plan.md) §3 step 3. Tools: [`execution.md`](../execution.md) §3.
Read this page first — it says what step 2 actually produced, which is not in every case
what the plan assumed it would.

---

## 1. Why this step is worth more after step 2 than before it

Step 2 answered its own questions and left two gaps that only step 3 can close.

**The lead pair is unphased.** Read-backed phasing placed neither of the lead gene's two
alleles in any block: they are 10,911 bp apart with four heterozygous variants between them
at ~2.7 kb spacing, against a ~266 bp sequencing fragment. Depth there is 43.7×, so this is
not a coverage failure — it is how densely this child happens to be heterozygous in that
gene. **Step 2 contributes no direct evidence that the two alleles sit on different
copies.** Step 3 cannot phase them either, but it can establish the thing phasing was
wanted for on the way to: that each allele is present at **one** copy rather than two, which
is what a compound heterozygote requires and what a technical artefact would not show.

**Everything step 2 concluded passed through an aligner and a caller.** Both are models with
assumptions — where a read belongs, what a haplotype looks like. Counting k-mers reads the
same bytes with neither. Where the two agree, the allele survives a genuinely disjoint
instrument; where they disagree, the disagreement is the finding.

---

## 2. What step 2 hands over

### Tables (all in `results`, loaded by `mva-warehouse pg-load-it2-step2`)

| Table | Rows | What step 3 uses it for |
|---|---|---|
| `it2_read_alleles` | 131,530 | the alleles to design k-mer probes for |
| `it2_scored_pairs` | 792 | which genes have a rare protein-altering candidate, with bait density, depth and `novel_qualifying` |
| `warehouse.it2_read_annotations` | 1,199 | VEP for the alleles **only the read route saw** — the set step 3 validates (§3.9) |
| `it2_read_pairs` | 792 | the same per gene, unfiltered — the contrast that matters (§4) |
| `it2_exon_depth` | 3,020 | the per-exon depth any copy-number claim is read against |
| `it2_bait_density` | 792 | surviving unique k-mers per base per gene — **carry this beside every per-gene claim** |
| `it2_sv_calls` / `it2_sv_consensus` / `it2_sv_leads` | 18,186 / 10 / 2 | the dosage changes k-mer copy number must confirm or contradict |
| `it2_phase_blocks` | 6,823 | where phase is resolved, and where it is not |
| `it2_bait_qc` | 39 | the funnel, as metric rows |

### Files under `build/it2/step-2/` (gitignored)

| File | What it is |
|---|---|
| `bait.npy` | 36,038,037 uniqueness-filtered canonical 31-mers |
| `baited-reads.parquet` | 15,773,226 reads, 7,886,613 complete pairs |
| `reads/baited_R{1,2}.fastq.gz` | the same as paired FASTQ, bgzip'd |
| `calls/baited.bam` (+ `.bai`) | the alignment, 98.87 % mapped |
| `calls/*.norm.vcf.gz` | both callers, normalised |
| `calls/baited.phased.vcf` | WhatsHap's blocks |
| `bait-profile.tsv`, `bait-recall.json`, `uniqueness-sweep.json`, `analysis.json` | the measurements the entries quote |

### Reusable code

`mva.kmer` (encode, bait, uniqueness, membership, regions) · `mva.reads.bait` / `recover` /
`baitjob` / `client` · `mva.calling` (align, coverage, smallvars, sv, phase, workflow) ·
`mva.warehouse.it2_step2_tables` + `analysis_it2` + `analysis_it2_sv`.

**`mva.kmer` is step 3's engine already.** It packs a k-mer into a `uint64`, canonicalises
strand, and answers membership against a sorted array behind a bitmap. Step 3's probe
counting is the same kernel with a different question: not "is this read in the bait" but
"how many reads contain exactly this k-mer". `mva.reads.scan.counts` already answers that
for up to 500 probes, and step 2 measured what it costs (§6).

---

## 3. The assumptions step 3 inherits

Each of these is measured, not assumed, and each has a number.

1. **The target set is an enrichment, not coverage.** Held-out recall@300 = 0.36
   (entry 084). A gene absent from step 2's output is not excluded — it may never have been
   baited.
2. **8.79 % of bait k-mers were dropped as repeated** (085), and no parameter reaches the
   pre-registered 5 % (086): padding bottoms out at 8.38 %, and k = 32, the representation
   ceiling, gives 8.57 %. The genes carrying the load are segmental-duplication families,
   where no k escapes a repeat longer than k.
3. **21 of 792 genes are below half the median bait density, none of them core or
   mechanism-term.** Per-gene density is in `it2_bait_density`; **a "nothing found here"
   without it is not a finding.**
4. **The bait's recall is ≈ 0.905 with a wide interval** ([0.815, 0.974], entry 087). The
   loss concentrates in probes whose alternate k-mer matches several loci, which is a flaw
   in the witness design recorded there: it filtered on the *reference* k-mer's uniqueness
   while the strike searches for the *alternate*. **Step 3 should filter its probes on the
   alternate k-mer's genome-wide count** — it has the machinery
   (`mva.kmer.uniqueness.count_in_genome`) and step 2 did not.
5. **The reference is not byte-identical to the vendor's** (NCBI analysis set, no
   GRC-exclusion masking), so cross-checks against the delivered callset stay on primary
   contigs.
6. **Concordance is untested for indels.** The delivered callset is unnormalised and its
   indels are not comparable without a left-alignment; minimap2's short-read mode is least
   studied exactly there.
7. **The SV consensus is unvalidated.** No HG002 positive control ran. Kosugi 2019's
   type-specific precision is a 2019 GRCh37 prior printed beside each call, not our
   measurement.
8. **Two artefact controls are load-bearing and were earned the hard way** — a 50 bp floor,
   and a requirement that over half an SV's span be baited territory. Without them the
   consensus contained a 13 Mb deletion and a 40 Mb inversion in a living child. Any step-3
   copy-number claim that contradicts an SV call must check which side of those controls the
   call sits on.
9. **1,199 read-derived alleles are annotated but unvalidated, and they now carry the
   candidate counts.** They are calls two read-derived callers made on a baited alignment
   that the vendor's pipeline never reported — 49 of them HIGH impact, 411 missense, 3 with
   a ClinVar pathogenic assertion (entry 090). Six of the ten target genes and eight of the
   ten decoy genes in the lead set reach biallelic **only** because of them, so **every
   biallelic count in step 2 is an upper bound until step 3 checks them.** This is the
   single most valuable thing step 3 can do with its instrument: a k-mer genotype needs
   neither the aligner nor the caller that produced these, so agreement is genuinely
   independent corroboration and disagreement retires the allele.
10. **The read route has no measured discriminating power of its own.** H020 is refuted:
    with every allele scored, targets and decoys carry a biallelic candidate at exactly the
    same rate, 10 of 396 each (p = 0.589). Step 6 weights the read route down accordingly,
    and step 3 must not quietly re-import the assumption that a target-gene finding is worth
    more than a decoy-gene one — **it is not, before the filter.**

---

## 4. The one result step 3 must not repeat

Enumerating biallelic genes **without** a rarity and consequence filter makes the decoys win:

| tier | any two variants | rare + protein-altering |
|---|---|---|
| core | 50.8 % | **5.08 %** |
| mechanism-term | 42.0 % | 1.45 % |
| net | 53.4 % | 2.24 % |
| **decoy** | **57.3 %** | **2.53 %** |
| **targets, all tiers** | 51.0 % | **2.53 %** |

Every person carries roughly two heterozygous differences per gene, so "two variants in one
gene" describes a genome, not a patient. **The discriminating power is in the filter, not in
the symptom-derived gene list** — and once the alleles the vendor never reported are scored
too, the filtered target and decoy rates are **identical**, so the filter is where *all* of
it is. Step 3 genotypes alleles rather than enumerating them, so the same trap takes a
different shape: *a het call is not evidence of anything by itself.* Any step-3 count
compared between targets and decoys must say which filter it used, whether the novel alleles
were included, and must pass the decoy set through the identical rules.

Two of the twenty lead genes, `PWWP4` (4.6× mean depth) and `GTF2IRD2` (5.3×), sit far below
the 44× median and were already flagged as k-mer-repetitive. Step 3 should expect to retire
them, and if it does not, that is itself a result.

---

## 5. Claims to file before step 3 runs

From `plan.md` §3 step 3, to be filed with `mva-science hypothesis-add` **before** the run.
The register allocates ids in filing order; the next free id is **H024**.

| Plan label | Claim | Refuted by |
|---|---|---|
| H017 (plan) | every step-2 heterozygous call in the target set is called het by the fitted negative-binomial model at posterior ≥ 0.95, with all ≥ 3 probes agreeing | one is not — re-examined as mosaic, private neighbour, or artefact |
| H018 (plan) | at least one ClinVar P/LP allele of a target gene is present at het multiplicity above the fitted error threshold | none — the pair, if any, is novel on both sides |
| H019 (plan) | no target-gene exon (or pooled gene) falls below the 2.5th percentile of a 1,000-exon null copy-number band | one does — a deletion candidate for step 6 |

Two additions step 2's results argue for, not in the plan:

| Suggested | Claim | Why step 2 makes it worth filing |
|---|---|---|
| new | both alleles of the lead pair are at **one-copy** multiplicity (posterior ≥ 0.95), not two | phasing failed (§1); single-copy dosage on both is the strongest statement left about the pair, and a caller artefact would not produce it |
| new | genes below half the median bait density yield **no** confident k-mer genotype | it makes the reachability limit falsifiable rather than a caveat; the 21 genes are named in `it2_bait_density` |
| new | **at least 80 % of the 1,199 alleles the delivered callset never reported are confirmed at the same multiplicity by k-mer genotype** | refuted by fewer, in which case every biallelic count step 2 reported is revised downward and the read route's own false-positive rate becomes a number rather than a caveat (§3.9). This is the claim with the most leverage in the whole step |

---

## 6. What step 2 learned about running things, which step 3 should not relearn

| Lesson | Number | Consequence for step 3 |
|---|---|---|
| The full-store pass belongs beside the data | 55.8 s/shard from the laptop against 50.8 min for all 272 shards server-side | use `POST /bait` or `POST /count`; do not stream the store to the laptop |
| Saturating cores takes the shared service down | three restarts mid-scan | keep `workers` ≤ 4 and probes ≤ 20 per strike (entry 027's measured size) |
| Long polls get cut, jobs survive | three `RemoteProtocolError`s | `mva.reads.client` polls in 25 s waits and can attach to a running job with `--job` |
| The laptop swaps before it runs out of disk | minimap2 paged to 0.3 GB with swap at 24.9/26.6 GB | bound tool memory explicitly; `-I 1G --split-prefix` for minimap2 |
| Contig spelling is a silent joiner | one join returned 0 rows and looked like a clean negative | `mva.pipeline.variant` owns both directions; the step-2 loader now refuses a mixed load |
| Alignment is the hour, everything else is minutes | 63 min | `run_it2_step2_calling.py --realign` forces it; by default an indexed BAM is reused |

---

## 7. How to start

```bash
# 1. read, in order
docs/iteration2/step-2/methodology/085-the-bait-and-where-it-runs.md
docs/iteration2/step-2/methodology/086-can-the-off-target-gate-be-reached.md
docs/iteration2/step-2/methodology/087-the-pass-and-what-it-recovered.md
docs/iteration2/step-2/methodology/088-the-alleles-the-reads-carry.md

# 2. file the claims before running anything
uv run mva-science hypothesis-add --step step-3 --statement … --prediction … --refuted-by …

# 3. the tables are already there
uv run mva-warehouse pg-query "SELECT * FROM pg.results.it2_scored_pairs LIMIT 5"
```

The next methodology entry is **089**. Step 3's folder is this one; its entries go in
`methodology/`.

---

## 8. What step 3 hands on

Step 6 fuses four routes and weights each by its **measured** error rate. Step 2's
contribution to that weight is the decoy false-lead rate (§4) and the bait recall
(0.905, wide). Step 3 owes the same: a genotype posterior per call and a copy-number null
band, both measured on this sample, so the fusion weights a route by what it demonstrably
does rather than by how modern its method sounds.
