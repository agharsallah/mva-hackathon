# Step 5 — Recover the second allele from the reads

**Standing:** open, not started as a research step. The read store and the k-mer strike
exist and are timed; no allele recovery has been attempted. Conditional on steps 2–4
leaving a gap. Method: [`../method.md`](../method.md). Last checked 2026-09-04.

---

## The goal

> **Is the missing allele a variant the caller could not emit at all — a structural
> variant, a deep intronic call, or a low-fraction mosaic?**

## Why it matters

- The callset is SNV and indel only. A **structural variant** (a large deletion,
  duplication or rearrangement) simply is not in it.
- A **mosaic** allele present in a minority of cells falls under the caller's threshold.
- If steps 2–4 find only one credible allele, the partner must be a class the VCF cannot
  represent — and the raw reads are the only remaining evidence.
- The read store makes this affordable: one pass over Parquet instead of decompressing
  ~79 GiB of FASTQ per question.

## Already done

- The queryable read store, its provenance and its cost model — step-0 methodology
  [019](../step-0/methodology/019-where-the-read-bytes-come-from.md)–[023](../step-0/methodology/023-the-exact-read-census.md).
- The **k-mer strike** (find a subsequence on either strand in one pass) works, is timed,
  and scales to many probes at once —
  [024](../step-0/methodology/024-the-kmer-strike-works.md),
  [025](../step-0/methodology/025-many-probes-one-pass.md),
  [026](../step-0/methodology/026-multi-literal-matching-needs-aho-corasick.md),
  [027](../step-0/methodology/027-aho-corasick-confirmed.md).
- The BAF karyogram bounds mosaicism at VCF level only —
  [037](../step-0/methodology/037-baf-karyogram.md).

## Remaining

- **A — targeted recovery, funded and local, first.** Stream the reads once against
  candidate-gene k-mers ±50 kb, align that small set to the *full* GRCh38 so foreign reads
  map elsewhere, then per-exon coverage (single-exon deletions), breakpoint calling, and
  evidence shots.
- **B — full re-alignment and re-call. Conditional and unfunded.** Roughly a day and a half
  of local alignment; no compute budget confirmed. Open it only if A leaves a real question.
- Develop the chain against the 200k-read smoke sample first; it runs in seconds. Those
  reads are all from one tile — good for exercising a pipeline, not a quality sample.

## Exit criterion

A verdict on whether a read-level allele exists in the candidate gene — or an explicit
statement that only route A ran, and what it could not see.

## Report artifact

Per-exon coverage over the candidate gene, and breakpoint evidence shots. **Aggregates and
renders only** — never raw patient reads in the repository.

## Tooling this step may need

The k-mer filter generalised into a case-agnostic "targeted read recovery without
alignment" tool; an alignment stage; the coverage plot. Recorded in this step's methodology.

## The record

| | |
|---|---|
| Hypotheses | none recorded yet — [`hypotheses/`](hypotheses/), written by `mva-science export` |
| Tests | none run under this step — entries land in [`methodology/`](methodology/), numbered from 069 |
| Rendered | `figures/science-report.html` |
