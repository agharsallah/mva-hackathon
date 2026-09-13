# 095 — Can an allele be spelled both ways, and does a new counting kernel count what it claims?

**Written:** 2026-09-13. **Step:** `step-3` (iteration 2). **Hypotheses:** none — this entry
builds and validates the two instruments the step's claims are then tested with. The claims
themselves (H024–H029) were filed before it ran and are settled in
[096](096-the-alleles-at-their-multiplicity.md).

**Supersedes nothing.**

## Why this ran

Step 3 asks what the reads say when neither an aligner nor a caller is consulted. Answering
that needs two things the repository did not have.

1. **A way to spell an allele.** Write the 31 letters around a variant twice — as the
   reference has them, as the allele has them — and the two k-mers differ only by the
   variant. Counting each in the reads says how many copies carry it. FastGT (Pajuste 2017)
   is the direct precedent for exactly this use.
2. **A way to count.** `mva.kmer.membership` answers *is this k-mer in the set* — a boolean,
   which was all step 2 needed because it was selecting reads. A genotype is not a boolean:
   one copy puts a k-mer into about half the reads covering it, two into nearly all, none
   into a few from sequencing error. Those differ only in *how many*.
   `mva.reads.scan.counts` does count, but through a multi-literal string matcher validated
   at 20 literals and capped in practice around 500. Step 3 designs hundreds of thousands.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| public | GRCh38 analysis set | `build/reference/GRCh38.provenance.json`, sha256 `a7a41737…` |
| public | ClinVar GRCh38 VCF, `##fileDate` **2026-08-29** | `build/it2/step-3/clinvar-baited.provenance.json` |
| derived | `results.it2_read_alleles` — every allele step 2's two callers emitted | entry 088 |
| derived | `warehouse.it2_read_annotations` — the 1,199 the delivered callset never reported | entry 090 |
| raw | `warehouse.variants_raw` — the delivered callset, for calibration markers only | the delivered VCF |
| derived | `build/it2/step-2/baited-reads.parquet` — 15,773,226 reads, 7,886,613 complete pairs | entry 087 |
| derived | `build/it2/step-2/baited-regions.bed` | entry 088 |
| clinical | indirectly: the genes come from step 1's target set, ranked from the eight HPO terms | [084](../../step-1/methodology/084-the-blind-target-set.md) |

No iteration-1 candidate table was opened. **`warehouse.clinvar_panel` was deliberately not
used**: it holds iteration 1's eighteen-gene panel, and reading it would import that gene
list into a blind step. ClinVar was re-fetched over step 2's own baited intervals instead.

## Commands

```
uv run python tools/build_reference_data.py clinvar \
    --bed build/it2/step-2/baited-regions.bed --out build/it2/step-3/clinvar-baited.tsv
uv run python tools/build_it2_probes.py
uv run python tools/run_it2_step3_counts.py
uv run python tools/check_it2_kernel.py
```

## Observed — the probes

164,044 distinct alleles from four sources: 75,733 from step 2's callers (the 1,199
vendor-unreported among them, tagged rather than fetched twice), 88,754 ClinVar pathogenic
or likely-pathogenic alleles of the 792 target and decoy genes, and 20,000 calibration
markers drawn from inside the baited intervals with seed 20260913.

| | |
|---|---|
| probe pairs designed | 439,851 |
| **probe pairs kept after the uniqueness pass** | **381,510** |
| distinct probe k-mers | 763,020 |
| alleles with all three probes | 95,372 |
| alleles with none | 15,525 |

What the filters removed, and why each matters:

| Dropped | Pairs | What it was |
|---|---|---|
| `ref_equals_alt` | 52,230 | a window whose two spellings coincide — an indel inside a repeat, where the alternate reads exactly as the reference does. Not a probe that failed; not a probe |
| **`alt_kmer_occurs_in_reference`** | **37,306** | the alternate spelling already exists somewhere in GRCh38, so reads from *that* place would be counted as this allele being present |
| `ref_kmer_not_unique` | 21,035 | the reference side collects reads from elsewhere, inflating the denominator |
| `window_off_contig_or_n` | 51 | ran off the contig, or spanned a base the machine could not call |

**The 37,306 are the correction step 2 earned.** Its witness set filtered the *reference*
k-mer's uniqueness while the strike searched for the *alternate*, and its recall loss
concentrated exactly there ([087](../../step-2/methodology/087-the-pass-and-what-it-recovered.md)).
8.5 % of designed pairs would have been read as present wherever their other locus was
covered. They are dropped here because the alternate is the spelling being counted.

## Observed — the count

One pass over the 15,773,226 recovered reads, every window of every read, no stride.

| | |
|---|---|
| windows scanned | **1,876,842,047** |
| wall time | **765 s** on the laptop |
| raw probe occurrences | 11,499,330 |
| observations after collapsing read pairs to fragments | 11,154,903 |
| **raw-to-fragment ratio** | **1.0309** |
| probe k-mers never observed | 295,503 of 684,914 |

The ratio is the number the design was arguing about. R1 and R2 are two reads of one
molecule and overlap at a ~266 bp fragment against 2 × 150 bp of read, so a probe in the
overlap would be counted twice for one piece of DNA. **It happens to 3.1 % of observations**
— small, and now measured rather than assumed or ignored.

The 295,503 silent k-mers are mostly alternate spellings of ClinVar alleles this child does
not carry. That is the expected answer, not a failure: most published pathogenic alleles are
absent from most people.

## The gate: does the kernel count what it claims?

`mva.kmer.count` is new, and every number in step 3 rests on it. Stage 2's pre-registered
gate is agreement with the engine step 0 already validated — the multi-literal matcher
behind `mva.reads.scan` ([027](../../../step-0/methodology/027-aho-corasick-confirmed.md)).
The two share no code and no representation: one searches 64-bit integers in a sorted array,
the other searches text, and they solve the two-strand problem differently (one canonical
k-mer against a sequence plus its reverse complement).

```json
{"agree": true, "disagreements": [], "probes": 20, "reads": 2000000,
 "kernel_total": 38, "strike_total": 38, "probes_with_no_hit": 11, "seed": 20260913}
```

**Exact agreement on all 20 probes.** Eleven of them were carried by no read, which is part
of the check: two methods agreeing on zero is weaker evidence than two methods agreeing on
38, and both were observed.

## Assumptions, limitations and quality checks

* **Stride is absent here, on purpose.** `mva.kmer.membership.hits` samples every 16th
  window and stays exact, because a read overlapping the bait by ≥ 46 bases hits *some*
  sampled window. A sampled count is not a count: a probe occurring once in a read is seen
  by exactly one window and sampling would miss it fifteen times in sixteen.
* **The fragment collapse is exact to about 28 pairs in 11 million.** Each
  `(fragment, probe)` pair is packed into one `uint64` — the flowcell coordinate hashed to
  43 bits, the probe index in 21 — so two different fragments collide with probability about
  2⁻⁴³. Recorded rather than presented as exact. More probe k-mers than the packing holds is
  refused rather than wrapped, because wrapping would mix two probes' counts and read as a
  genotype rather than as an error.
* **Indel probes use the idea, not the published numbers.** FastGT validated SNVs only
  (Methods p. 7). The anchor base VCF repeats on both sides of an indel is read off the
  strings rather than assumed, so a window must reach the first differing base on *both*
  haplotypes; 52,230 windows that could not are refused.
* **Calibration markers come from inside the baited intervals.** The bait recovers 0.905 of
  the reads carrying a known allele (087). Drawing calibration and probe counts from the
  same recovery makes that factor common to both sides of the ratio the model fits, so it
  cancels. A genome-wide calibration set would read every allele as ~10 % under-covered.
* **ClinVar is a public catalogue and says nothing about this child.** It is admitted by the
  blind protocol for exactly that reason, and was fetched fresh over the baited intervals
  rather than reused from iteration 1's panel table.
* **No sequence leaves `build/`.** Probe k-mers are patient sequence — an alternate k-mer
  spells a base this child carries. They live in `probes.npz`; the committed tables carry a
  gene, an ordinal and counts. `tools/check_coordinates.py` passes.

## What this hands to the next entry

381,510 probe pairs over 164,044 alleles, their counts in 15.8 million reads collapsed to
one observation per molecule, and a kernel that has been shown to agree exactly with an
independently validated instrument. [096](096-the-alleles-at-their-multiplicity.md) fits the
genotype model on them and settles H024, H025, H027, H028 and H029.
