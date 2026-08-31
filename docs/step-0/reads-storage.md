# The read store — 1.07 billion reads, queryable

**Standing:** built and verified 2026-08-31. 272 shards, 63.03 GiB, in `s3://mva/reads/`.
Every number here comes from the run recorded in
[`methodology/023`](methodology/023-the-exact-read-census.md). The design study this page
used to hold is superseded; its reasoning survives in
[`methodology/012`](methodology/012-read-storage-options.md).

The delivered FASTQ are gzip: to ask anything of them you decompress 79 GiB and scan. They
are now also **sharded columnar Parquet**, which answers questions in seconds without
moving most of the bytes. The FASTQ are untouched — this is a derived copy, rebuildable at
any time.

## What exists

| | |
|---|---|
| Location | `s3://mva/reads/` |
| Reads | **1,071,835,104** — counted, not estimated |
| Size | **63.03 GiB** Parquet, from **78.9 GiB** of source gzip |
| Shards | **272**, ~4M reads each |
| Built in | 61.2 minutes, oxbow engine, 8 parallel jobs |

**The columnar copy is smaller than the delivered gzip** — because sequence and quality
have very different entropy and Parquet compresses them separately, where gzip sees them
interleaved.

```
s3://mva/reads/lane=<1..4>/read=<1|2>/part-<NNNN>.parquet   the reads
s3://mva/reads/runs.parquet                                  8 rows: one per source file
s3://mva/reads/manifest.parquet                              272 rows: one per shard
```

`lane` and `read` live in the **directory names** (hive partitioning), so a query about
one lane never opens the other three. Within a shard, rows are grouped 200,000 at a time
(a **row group**), each carrying the min/max of every column so a reader can skip blocks
it cannot need.

## The schema, and what is deliberately absent

| Column | Type | Why |
|---|---|---|
| `tile`, `x`, `y` | `USMALLINT`, `UINTEGER` | flowcell position — **the mate key** |
| `is_filtered` | `BOOLEAN` | the machine's own quality flag |
| `index_pair` | `VARCHAR` | library barcode |
| `sequence`, `quality` | `VARCHAR` | the payload — 97% of the bytes |

**The read name is not stored.** Everything constant per file — instrument, run, flowcell,
lane, read number, control — is one row in `runs`, and the name is reconstructed from
columns when needed (`RunFacts.rebuild_name`). `(lane, tile, x, y)` is shared by a read and
its mate, so pairing is a join rather than a stored string.

## Asking it things

```bash
uv run mva-reads scan --kmer AGAGATAGGAAGCGGGACGAGGAAAGGAACA   # both strands
uv run mva-reads qc                                            # per-lane quality
uv run mva-reads sql "SELECT lane, count(*) FROM reads GROUP BY lane"
uv run mva-reads status                                        # what the store holds
```

`scan --kmer` is the **mapping-free k-mer strike**: does this exact sequence appear in the
raw reads, forward or reverse-complemented? It answers from the reads themselves, with no
aligner and no index build — the check that a variant call is really supported by data.

## What this store cannot do

**A raw read has no genomic coordinate.** The FASTQ says a 149-base string came off tile
1101 at (11957, 1000); it does not say it came from chromosome 15. So these are
unanswerable here, at any speed:

* "Which reads cover *BUB1B* exon 3?"
* "What is the depth at a given position?"
* "Is this variant supported on both strands *at that locus*?"

Answering those needs **alignment** — placing each read on the reference — producing a
coordinate-sorted BAM/CRAM with an index. That is a different store, and this one does not
replace it. What this store does is the sequence question: *does this string exist in the
reads, and how often*.

## Cost of a full scan, and where to run it

A k-mer scan reads the `sequence` column of every row: **no row group can be pruned**, so
it moves tens of gigabytes. Run it on the server, where the object store is on the same
box. From a laptop the link was measured at 6.4 MiB/s, which makes a full scan hours
rather than minutes.

The fix for laptop-side scanning is a **per-shard k-mer sketch** — a small presence filter
per shard so a rare k-mer opens only the few shards that could contain it. Not built;
it is the next thing worth building here.

## Rebuilding it

```bash
uv run mva-reads convert --source s3 --engine oxbow --jobs 8
uv run mva-reads verify --source s3 --expected-total 1071835104
```

`verify` re-counts every shard against the manifest, checks R1 equals R2 in each lane, and
reproduces the **first and last record of every source file byte-for-byte** — the last one
being reachable only by decompressing the whole object, which is what proves a conversion
ran to the true end of its stream.

Engine choice and its measurements: [`methodology/022`](methodology/022-engine-bakeoff-on-the-delivery.md).
Why the row group size is a memory budget: [`methodology/021`](methodology/021-the-row-group-is-a-memory-budget.md).

## Data handling

Reads are patient data and the `index_pair` barcode is library identity. Nothing from this
store is committed: the repository holds code, counts and aggregates only, per
[no patient data in the repository](../notes/no-patient-data-in-the-repository.md).
