# 085 — Can 42 Mb of reference be turned into a k-mer bait, and where must the pass run?

**Written:** 2026-09-12, before the pass. **Step:** `step-2` (iteration 2).
**Hypotheses:** none. This entry builds the instrument and measures the machine; the
claims it enables are H021, H022 and H023, filed separately and tested in the entries
that follow. A tool a research step needs is filed under that step (CLAUDE.md), which is
why the new packages are recorded here and not in `docs/step-0/`.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived (step 1) | `targets.tsv` — 404 rows, tiered | `build/it2/step-1/`, entry [084](../../step-1/methodology/084-the-blind-target-set.md) |
| derived (step 1) | `decoys.tsv` — 396 shape-matched genes | same, seed `20260910` |
| public | `ressources/reference/coding_regions.tsv` — the gene model the bait is cut around | Ensembl 116, `tools/build_coding_regions.py` |
| public | GRCh38 no-alt analysis set + hs38d1 decoys | NCBI, sha256 `fb4243eb…`, 872,949,833 B |
| object store | the read store's `manifest.parquet` — shard count and sizes only | `s3://mva/reads` |

**No patient read and no callset record was read by this entry.** The bait is cut from the
public reference; the store was touched only for the shard manifest and the throughput
measurement below. No iteration-1 table was read — `mva-science check --blind iteration2`
is the gate.

## Question

Step 2's plan ([`plan.md`](../../plan.md) §3 step 2) assumes three things it never
measured: that a bait of ~10⁷ k-mers can be built and applied at all, that the pass can
run where the analysis runs, and that the bait's off-target load is small. Each is a
number, and each is cheaper to get wrong now than after a 1.07-billion-read pass.

## 1. The existing instrument does not reach

`mva.reads.scan` compiles its probes into one multi-literal matcher and materialises the
survivors. Both halves are sized for the question it was built for:

| | `scan` (entry [027](../../../step-0/methodology/027-aho-corasick-confirmed.md)) | what step 2 needs |
|---|---|---|
| patterns | 20 measured, 500 capped by the API | ~40,000,000 |
| survivors | "dozens to thousands of reads", materialised | ~12,000,000 |
| engine | Polars `contains_any` (Aho-Corasick/Teddy) over a text column | — |

An automaton over 40 M literals is not the same structure more slowly, and a survivor
relation four orders of magnitude larger is not the same query plan. So the bait needs a
different engine, and `scan` keeps the question it is good at — which is what makes it
usable as the *witness* for H021.

## 2. Where the pass must run — measured, not assumed

The plan left this open. It is now closed by measurement, from this laptop against
`s3://mva/reads`:

| Reading | Wall time | Per shard |
|---|---|---|
| one shard, `sequence` column, single stream | 57.2 s | 57.2 s |
| eight shards, Polars streaming, in parallel | 446.7 s | **55.8 s** |

Parallelism buys nothing: the object-store link saturates at one stream. 272 shards is
therefore **≈ 253 min (4.2 h)** per pass from here, before the k-mer kernel's own CPU
cost, and every re-run costs the same again. The store, Postgres and `mva-reads-api` all
resolve to the same host, where the same pass reads local disk at ~190 MB/s — entry 027's
5.6 minutes.

**Decision, recorded:** the sweep is packaged as one function (`mva.reads.baitjob.run_bait`)
exposed twice — `mva-reads bait` for the laptop and `POST /bait` for the job service — and
the full pass is submitted to the service. This is the **one stage of step 2 that does not
run on the analysis machine**, and it is a stated limitation of that claim rather than a
silent convenience: the bait, the uniqueness filter, alignment, calling, structural
variants, coverage, phasing, every table and every figure stay local. The verb is a thin
runner, so the result is reproducible entirely locally by anyone willing to spend the
4.2 hours.

Two shapes were considered and rejected before adding a verb. `POST /sql` runs read-only
SQL server-side, but `sql_runner` wraps every query in `SELECT * FROM (…) LIMIT ≤ 100 000`
and `SqlRequest` refuses any non-read-only opener, so 12 M survivors can neither be
returned nor written from inside it. Raising the `/scan` probe cap is the first option
section 1 rules out.

## 3. The engine

`mva.kmer`, a new leaf package. Each 31-mer packs into one `uint64` (2 bits per base, 62
of 64 used); forward and reverse-complement spellings are built in the same vectorised
pass and the smaller kept, so one stored integer covers both strands and the
search-both-spellings step disappears. Membership is `np.searchsorted` over a sorted array
behind a 2³⁰-bit prefilter that rejects ~96 % of misses with one memory access. **The
prefilter never decides a hit** — a set bit means *maybe*, every candidate is confirmed
against the array, and a test asserts the answer is identical with the prefilter switched
off.

The uniqueness gate reverses the direction KMC and Jellyfish work in. Those build a table
of *every* k-mer in the genome — billions of entries, tens of GB, Linux-only builds. We do
not need that table: we need the occurrence count of the 40 M k-mers we already hold. So
the reference streams past the bait rather than into a new table. That is a smaller
problem, and it is why this stage needs no Linux-only counter and runs on the laptop.

`N` is never silently encoded as `A`: every function returns a validity mask beside its
values, and a window containing an uncalled base has no k-mer.

## 4. Commands

```
uv run python tools/build_reference_genome.py
uv run python tools/build_it2_bait.py
uv run python tools/profile_it2_bait.py
uv run python tools/build_it2_witness.py --sample 120 --seed 20260912
```

## Observed

### The reference

195 contigs, 3,099,922,541 bases. **The 195 is the check**: it is the same contig count
the callset normalization reported in entry
[073](../../../iteration1/step-1/methodology/073-normalization-of-the-candidates.md), so
this build and the delivered callset share a coordinate system. Headers were rewritten to
bare contigs by the same rule `mva.kmer.fasta.rename` applies in memory, so the FASTA on
disk and the k-mers in memory cannot disagree.

### The bait

| Tier | Genes | Padding | Padded bases |
|---|---|---|---|
| `core` | 59 | ±50 kb | 9,606,064 |
| `mechanism-term` | 69 | ±50 kb | 9,789,131 |
| `net` | 268 | ±2 kb | 9,097,805 |
| `decoy` | 396 | ±2 kb | 14,104,047 |
| **merged total** | **792** | | **42,197,689** |

8 of the 800 genes are absent from the gene model and are listed by name in
`build/it2/step-2/summary.json`; they are not baited and step 2 says nothing about them.
`core` and `mechanism-term` share the wide padding because they are together what the plan
calls the core tier, and a structural variant that removes an exon has its breakpoints
deep in the introns around it.

The bait is **1.36 % of the genome**. At the delivery's 44× and 150 bp that predicts
**≈ 12,378,000 recovered reads**, and the pass is judged against 0.5–2× of it
(6,189,000–24,756,000). **39,508,982 canonical 31-mers** were cut in 51 s.

### The uniqueness gate — **failed, at 8.79 % against a < 5 % rule**

2,934,842,387 genome windows scanned in 542 s. **3,470,945 of 39,508,982 bait k-mers
(8.79 %) occur more than once in GRCh38** and were dropped, leaving **36,038,037**.
**0 were never found**, which is the consistency check between the bait and the reference
it was cut from, and it passes exactly.

The gate is pre-registered and it fails. Per the plan's own rule the failure is the
finding, so it is reported as one — and the first thing to say about it is what it does
**not** mean. The repeated k-mers are *dropped*; the bait that goes into the pass is clean
by construction. What 8.79 % measures is how repetitive the chosen regions are, and the
risk the gate stands in for is different from the number it reports: the risk is not that
9 % of k-mers are repetitive, it is that **some particular gene** is so repetitive that
the bait cannot reach it, and a later "no second allele in this gene" would then be a
statement about the reference rather than about the child. An average cannot answer that.

### What the gate was proxying for, measured per gene

`tools/profile_it2_bait.py` re-cuts every gene's intervals and asks how many of its
windows survived the filter. One reference pass, per gene and per tier:

| Tier | Genes | Bases | Windows | Surviving | Lost |
|---|---|---|---|---|---|
| `core` | 59 | 9,606,064 | 9,604,204 | 8,155,048 | 15.09 % |
| `mechanism-term` | 69 | 9,789,131 | 9,787,061 | 8,076,345 | 17.48 % |
| `net` | 268 | 9,097,805 | 9,065,615 | 7,842,394 | 13.49 % |
| `decoy` | 396 | 14,104,047 | 14,049,536 | 12,315,806 | 12.34 % |

These per-tier losses are larger than the global 8.79 % because they count windows **with
multiplicity** while the global figure counts distinct k-mers: one repeated k-mer occupies
many windows. The wide-padded tiers lose most, as expected — ±50 kb reaches into introns
and intergenic sequence, which is far more repetitive than exons.

Per-gene density (surviving k-mers per base), median over all 792 genes = **0.888**:

| Tier | n | Median density | Minimum |
|---|---|---|---|
| `core` | 59 | 0.847 | **0.532** |
| `mechanism-term` | 69 | 0.842 | **0.449** |
| `net` | 268 | 0.891 | 0.048 |
| `decoy` | 396 | 0.905 | 0.002 |

**21 of 792 genes** fall below half the median. **16 are decoys and 5 are `net`; none is
`core` or `mechanism-term`.** They are the classic segmental-duplication families —
TBC1D3, GOLGA6, NBPF, POTE, HNRNPCL, SPDYE, FRG2B, LIMS4 — where a gene has near-identical
copies elsewhere and almost no k-mer of it is unique.

**So the gate fails on the average and the risk it guards against is absent from the genes
step 2 reasons about.** Every core and mechanism-term gene retains at least 45 % of the
median bait density. Recorded decision: the pass proceeds on the filtered bait, the
failure is reported as a limitation rather than waved away, and **every per-gene claim
step 2 makes carries that gene's bait density beside it** — which is strictly more
informative than the gate would have been had it passed.

### A correction the profiling forces on H020

H020 predicts the decoy set yields fewer biallelic candidates per gene than the target
set. The decoys were drawn (entry 084) matched on **coding length and exon count** — not
on repetitiveness, which nobody had measured yet. They are now known to differ from the
targets in a way that touches exactly what H020 counts: the decoy set carries 16 of the 21
bait-starved genes, against 5 in the target set. A gene the bait cannot reach yields no
candidates for a reason that has nothing to do with whether symptoms nominated it, so
H020 could be "supported" by bait reachability alone.

**Pre-registered now, before the pass returns:** H020 is reported **twice** — over all
genes, and restricted to genes above half the median bait density (776 of 792). The
restricted comparison is the primary one; if the two disagree, the disagreement is the
result. This is a limitation of the step-1 decoy design discovered by step 2, and it is
filed here rather than corrected silently in the draw.

### Genes the bait cannot reach at all

8 of the 800 are absent from the gene model and were never baited: **H19, HELLPAR, HYMAI,
KCNQ1OT1, MEG3, RMRP, RNU4ATAC, RNU5B-1**. All eight are non-coding RNA genes, and their
absence is structural rather than accidental: `coding_regions.tsv` is built from coding
sequence, so a gene that encodes no protein has no interval to pad. This is a **named
blind spot**, not a rounding error — **RNU4ATAC** is itself a recessive disease gene
(Roifman and MOPD1 syndromes), which is precisely the kind of gene this design would miss.
Step 4's genome-wide ranking over the callset is the safety net, and the report says so.

## Assumptions and limitations

1. **The reference is not byte-identical to the vendor's.** The delivery names a no-alt
   analysis set plus hs38d1 that is additionally GRC-exclusion masked; NCBI's analysis set
   has the same primary assembly and the same decoys without that masking. Concordance
   against the delivered callset (H022) is therefore restricted to primary contigs, and
   the difference is written into `build/reference/GRCh38.provenance.json`.
2. **The stride is a pre-registered trade, not a free optimisation.** Testing every 16th
   offset of a read costs ~15× less than testing all 120 and can miss a read that overlaps
   the bait by fewer than `k + stride − 1` bases. That loss is measured by H021 before any
   absence is interpreted, and a unit test demonstrates the failure mode on a toy store so
   it is visible rather than theoretical.
3. **The target set is an enrichment, not coverage** — step 1's measured recall@300 is
   0.36 (entry 084). A gene absent from the bait is not excluded by step 2; it is not
   baited. The genome-wide safety net is step 4.
4. **The expected-recovery arithmetic assumes uniform depth.** 44× is a genome-wide mean;
   GC-extreme and repetitive intervals will sit below it. The 0.5–2× gate is wide enough
   to absorb that, and per-exon depth (stage 9) is where it is actually measured.
5. **The decoys double the pass** and are cut with identical rules on purpose. A null that
   went through a different pipeline would measure the pipeline, not the route H020 is
   about.

## Validation

- 28 unit tests on `mva.kmer` and 21 on the sweep and recovery, all on toy sequences and a
  miniature store built with the real hive layout and companion tables: canonical form is
  strand-agnostic, a substitution in the middle of a read still matches, a read of `N`
  never matches, chunk boundaries do not lose a window, the prefilter changes nothing, and
  a mate is written to the line its pair occupies in the other file.
- The uniqueness pass asserts `unseen == 0`: every bait k-mer was cut from the same
  reference it scans, so a k-mer the pass never finds means the two disagree.
- H021 is the external check, and it is the one that matters: the old strike finds the
  reads carrying a known alternate allele, and the bait must have kept them.

## Verdict on the gates

| Gate | Rule | Observed | |
|---|---|---|---|
| reference agrees with the callset | contig count matches entry 073 | 195 = 195 | **pass** |
| bait cut | printed before the pass | 42,197,689 bases, 39,508,982 k-mers | **pass** |
| `unseen` k-mers | must be 0 | 0 | **pass** |
| off-target | < 5 % | **8.79 %** | **fail — reported, and re-measured per gene** |
| no core gene bait-starved | (added after the failure) | 0 of 128 core + mechanism-term | **pass** |

## What this hands to the next entry

`build/it2/step-2/bait.npy` (36,038,037 uniqueness-filtered k-mers), `bait-profile.tsv`
(per-gene density, to be carried beside every per-gene claim), `witness-probes.tsv`, and
the funnel gate to judge the pass against: **12.4 M reads expected, 6.2–24.8 M accepted.**
