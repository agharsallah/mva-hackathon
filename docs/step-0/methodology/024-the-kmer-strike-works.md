# 024 — The k-mer strike, on the built store

**A step-0 platform entry, so it carries no hypothesis.** It measures the capability the
read store exists to provide, and confirms the query timing
[012](012-read-storage-options.md) extrapolated from a 1M-read sample.

## Question

Does a mapping-free k-mer search over all 1.07 billion reads work, how long does it take,
and does the result look like real sequencing data?

## Finding first

**Yes: 36 reads carry the probe, found in 185.5 seconds — 3.1 minutes — over local disk.**
The count is itself the strongest evidence the store is faithful, because **36 is what the
coverage arithmetic predicts**.

## Inputs

- Store: `/root/mva-staging/reads`, 272 shards, 1,071,835,104 reads (local disk copy).
- Probe: the 31-mer from [012](012-read-storage-options.md),
  `AGAGATAGGAAGCGGGACGAGGAAAGGAACA`, searched forward and reverse-complemented.

## Command run and observed output

```
$ uv run mva-reads scan --root /root/mva-staging/reads --kmer AGAGATAGGAAGCGGGACGAGGAAAGGAACA
  lane 1 read 1 tile 1101 (11957,1000) strand + at 40
  lane 1 read 1 tile 2225 (5810,36072) strand + at 105
  … 32 more …
  lane 4 read 2 tile 1336 (7202,3004) strand + at 60
36 hit(s) in 185.5s over /root/mva-staging/reads
```

## Why 36 is the right answer

A 31-mer falls inside a 149 bp read whenever that read starts at any of
`149 - 31 + 1 = 119` offsets, so the expected number of reads carrying a k-mer from a
single-copy locus is

```
depth x (149 - k + 1) / 149  =  44 x 119 / 149  ~=  35
```

against a mean mapped depth of ~44x ([`data-findings.md`](../../../ideation/data-findings.md) §4).
**Observed 36.** The distribution carries the same signal:

| Lane | Hits |
|---|---|
| 1 | 10 |
| 2 | 7 |
| 3 | 11 |
| 4 | 8 |

Even across all four lanes, present in both R1 and R2, and on both strands — what a real
genomic locus produces when fragments are sequenced from random positions and
orientations. A conversion that dropped, duplicated or corrupted reads could not
reproduce that arithmetic by accident.

The first hit is the first read of the delivery — tile 1101 at (11957, 1000), the read
whose name [012](012-read-storage-options.md) quotes — which is where that probe was
originally taken from.

## Timing, against the prediction

| | Prediction (012, from 1M reads) | Measured (full store) |
|---|---|---|
| Two-strand 31-mer scan | ~3.6 min | **3.1 min** |

The extrapolation held. No row group can be pruned for this query — a k-mer can be in any
read — so the scan reads the whole `sequence` column (~46 GiB) and the time is the cost of
decompressing it. That also means the cost is per *pass*, not per probe.

## Consequence recorded in code: ask everything at once

Since the pass dominates and each extra probe only adds a substring search over bytes
already in memory, **fifty probes in one pass cost far less than fifty passes**. That is
the shape of the real question — *which of these candidate alleles appear in the reads?* —
so `scan` now takes repeated `--kmer` flags or a `--kmers-file`, and a new `count` verb
reports per-probe totals with strand and lane spread:

```bash
uv run mva-reads count --root /root/mva-staging/reads --kmers-file candidates.tsv
```

`count` classifies each probe against the arithmetic above: **absent** (0 reads),
**error-level** (1-2 reads — the rate at which sequencing errors manufacture a k-mer),
or **present**, with a warning when hits fall in only one lane, which suggests an
artefact rather than a locus.

**Not yet measured:** the object-store timing for the same scan, and how the one-pass time
grows with probe count. Both are one command each and belong in the next entry.

## Conclusion

The mapping-free k-mer strike is real and takes minutes, exactly as designed. It answers
*does this sequence exist in the reads, on either strand, and in how many* — with no
aligner and no index build. What it still cannot answer is anything positional; that needs
alignment ([`reads-storage.md`](../reads-storage.md)).
