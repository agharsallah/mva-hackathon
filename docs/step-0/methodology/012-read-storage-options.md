# 012 — How to normalise and store 1.08 billion reads, and in what

## Question

What is the best way to normalise the FASTQ raw reads into a queryable format, and which
type of database should hold them?

## Finding first

**DuckDB over Parquet, not PostgreSQL.** Measured on this dataset: a normalised columnar
layout is **64 GB for all 1,079,858,785 reads — smaller than the 82 GB source** — and a
two-strand 31-mer scan across every read extrapolates to **~3.6 minutes**. PostgreSQL is
the wrong shape by roughly 6× (~378 GB, estimated).

**This corrects [011](011-duckdb-fidelity-and-ingestion-gates.md)**, which said reads
"would be roughly 0.4 TB in a row store" and left the impression that storing them was
impractical. That figure was right *for a row store* and is the Postgres number here; it
was wrong as a general claim, because a column store with zstd lands at 64 GB. The
recommendation against Postgres stands and is now quantified; the recommendation against
storing reads *at all* does not.

**Relational normalisation is not where the win is.** Sequence and quality are 97% of the
bytes; every field of the read name combined is 3%.

## Inputs

- `WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz` (10,467,073,561 bytes; 138,245,967
  reads), 1,000,000 reads sampled from the head.
- `duckdb` Python package; Parquet with zstd.

## Commands run and observed output

### 1. What the reads look like

```
@A01973:164:HGWCNDSX7:1:1101:11957:1000 1:N:0:GTGACGGAGC+NGGACCGCCA
   instrument A01973   run 164   flowcell HGWCNDSX7
   lane 1   tile 1101   x 11957   y 1000   read 1   filtered N   control 0   index …

   read length : 149, uniform
   alphabet    : ACGNT
```

```
=== quality alphabet ===
   distinct quality chars: 4
      '#'  Q2     0.0%
      ','  Q11    2.8%
      ':'  Q25    4.5%
      'F'  Q37   92.8%
```

**Four-level quality binning** (NovaSeq RTA3). This single fact drives the storage result:
the quality string, nominally as large as the sequence, compresses 10× because it is nearly
constant.

### 2. Size of a normalised columnar layout

Ten columns — `lane, tile, x, y, read_num, is_filtered, control, index_pair, sequence,
quality` — written to Parquet with zstd:

```
                              per 1M reads   all 1.08B reads
source .fastq.gz                     76 MB             82 GB
normalized parquet                   60 MB             64 GB
```

Parquet is **smaller than the delivered gzip**, because it separates sequence from quality
before compressing and the two have very different entropy; gzip sees them interleaved.

### 3. Where the bytes go — the result that settles the design

```
column           compressed   share   uncompressed   ratio
sequence            42.7 MB   71.8%       153.0 MB    3.6x
quality             15.0 MB   25.2%       153.0 MB   10.2x
x                    1.6 MB    2.7%         1.6 MB    1.0x
y                    0.1 MB    0.1%         0.1 MB    1.4x
index_pair           0.1 MB    0.1%         0.8 MB    9.9x
tile, read_num, lane, control, is_filtered   ~0
TOTAL               59.4 MB
```

Cardinality within the file confirms what is redundant:

```
   index_pair      220 distinct
   control           1 distinct
   is_filtered       1 distinct
   lane              1 distinct
   read_num          1 distinct
   tile              7 distinct
```

So `instrument`, `run`, `flowcell`, `lane`, `read_num`, `control` and `index_pair` are
constant or near-constant per file and belong in a one-row dimension table — but doing so
saves ~3% of storage. Normalise for clarity and correct mate joins, not for space.

Sequence at 42.7 bytes per 149 bp read is close to the ~37 bytes a 2-bit packing would
give *before* compression, so bit-packing buys perhaps 15% and costs a decode on every
query. Real DNA carries close to 2 bits per base; there is little left to remove.

### 4. Query performance

```
probe 31-mer: AGAGATAGGAAGCGGGACGAGGAAAGGAACA
  exact substring scan       hits=1    143 ms over 1M reads  -> ~2.6 min over all 1.08B
  with reverse complement    hits=1    200 ms over 1M reads  -> ~3.6 min over all 1.08B

  aggregate QC grouped by tile          90 ms over 1M reads
```

A both-strand k-mer scan over every read in ~3.6 minutes is the "mapping-free k-mer strike"
from the strategy brief, expressed as SQL with no aligner and no index build.

### 5. PostgreSQL, estimated

```
~350 B/row (149 sequence + 149 quality + 20 fields + 24 B tuple header + alignment)
1,079,858,785 rows -> ~378 GB uncompressed
```

An estimate, not a measurement: no read data was loaded into PostgreSQL. It is consistent
with the row-store overhead measured directly in
[009](009-hosted-database-choice.md) (5,012,204 rows at 653 MB vs 17 MB as Parquet).

## The limit no storage choice removes

A raw read carries no genomic coordinate. "Which reads cover *BUB1B* exon 3?" and "what is
the depth at chr15:40,161,000?" are unanswerable from normalised FASTQ in any database,
because the position is not in the data — it is computed by **alignment**. The output of
that, a coordinate-sorted CRAM with an index (typically 20–25 GB at this depth), is the
queryable read store for positional questions, and no relational schema substitutes for it.

## Conclusion

Choose by the question:

| Question | Store | Cost |
|---|---|---|
| Does this allele appear anywhere in the reads? | **Parquet + DuckDB** | 64 GB, ~3.6 min/scan |
| What covers this genomic position? | **align → CRAM + index** | 20–25 GB, ms range queries |
| Run quality per lane/tile/cycle | **aggregates in PostgreSQL** | kilobytes |
| Repeated k-mer lookups at ms latency | k-mer index | only once a scan proves too slow |

They coexist; all are derived from the FASTQ, which stays untouched. PostgreSQL should hold
read *aggregates*, never read *payloads*.

Design and proposed schema: [`docs/reads-storage.md`](../reads-storage.md).

**Nothing was ingested.** One million reads were parsed into a scratch Parquet outside the
repository for measurement, and deleted afterwards. The full read store is not built, and
the VCF ingestion remains held pending review as instructed.
