# 019 — Where do the FASTQ bytes come from, and can they be read straight out of the store?

**A step-0 platform entry, so it carries no hypothesis** — same note as
[018](018-fastq-conversion-engine-choice.md).

## Question

The first attempt to benchmark on the server failed:

```
$ uv run mva-reads bench --source ~/mva-objects/mva/source/ --reads 2000000
cutting 2,000,000-read sample from WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz …
gzip: /root/mva-objects/mva/source/WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz is a directory -- ignored
  pipe: FAILED — IndexError: list index out of range
  oxbow: FAILED — IndexError: list index out of range
  polars_bio: FAILED — IndexError: list index out of range
```

Two questions fell out of it. What is that directory? And if the delivery exists only
inside the object store, can it be converted from there without first copying 84 GB back
onto the disk?

## Finding first

**`~/mva-objects/` is MinIO's own storage backend, not a folder of files.** MinIO stores
each object as a **directory** containing `xl.meta` (its metadata) plus one `part.N` per
multipart chunk. So `…/source/WGS_….fastq.gz` is a directory that *looks* like the
delivery and cannot be read as it. Reading or writing a store's data directory directly is
never supported — it is the store's private bookkeeping, and a multipart object is not
even byte-identical to the file that was uploaded without reassembling its parts in order.

**The delivery can be converted straight from the object store, at full speed.** Measured
on 500,000 synthetic reads, converting from a range-request HTTP URL is as fast as
converting from a local file:

| Source | Engine | Throughput |
|---|---|---|
| local file | oxbow | 355,902 reads/s |
| **HTTP URL, range requests** | **oxbow** | **426,666 reads/s** |
| non-seekable stream | pipe | 48,699 reads/s |

The two oxbow numbers differ by less than run-to-run noise: **reading over the network is
not the bottleneck** — on the server the object store is on the same box, so this path
costs effectively nothing versus a local copy, and needs no second copy of 84 GB on disk.

## What was actually wrong in the code

The `IndexError` was a bug in error reporting, not in parsing. Three fixes:

1. **Directory entries were accepted as files.** `discover()` matched on the filename
   pattern alone, so a MinIO object directory passed the filter and reached the parser.
   Source resolution now moved to `src/mva/reads/source.py`, which requires a real file
   and **recognises MinIO's layout by shape**, reporting it in full:

   ```
   /root/mva-objects/mva/source looks like MinIO's internal storage, not a delivery.
     Every object there is a *directory* of parts — 'WGS_….fastq.gz' is one — so nothing
     can read it as a FASTQ.
     Use the delivery as it was downloaded, or read the bucket over the S3 API:
       mva-reads convert --source s3
     Never read or write MinIO's data directory directly; it is the store's own bookkeeping.
   ```

2. **`peek()` diagnosed nothing.** It read a first record and indexed into it. Not-gzip,
   not-FASTQ, and a read name that is not the Illumina 8-field form are now each named at
   the cheapest possible moment, with the offending line quoted.

3. **Seekability was an unstated requirement.** oxbow and polars-bio both need to seek, so
   neither can take a pipe; only the shell pipeline can. Each now says so and names the
   engine that copes, instead of a `pyo3` panic (`"File or stream is not seekable."`).

## How the object-store path works

`--source s3` (or `s3://bucket/prefix`) lists the FASTQ objects and gives each one a
**presigned HTTPS URL**, which oxbow opens through fsspec with range requests.

The obvious alternative, `s3fs`, was rejected on a dependency conflict: it pulls
`aiobotocore`, which pins `botocore` to narrow ranges incompatible with the `boto3` the
warehouse already uses (`uv` reported the conflict across every `aiobotocore` release).
A presigned URL needs no S3 library at all — only HTTP.

**A presigned URL is a bearer credential.** It grants read access to exactly one object
until it expires (12 hours here). Never log one, commit one, or paste one anywhere shared.

## Verification

`tests/test_reads_store.py` covers each failure mode that produced the server error: the
MinIO directory layout, an empty directory, a missing directory, not-gzip, gzip-that-is-
not-FASTQ, an unparseable read name, and each engine's refusal of a non-seekable stream.

The remote path is tested against a **range-capable** localhost HTTP server written for
the purpose. This mattered more than expected: Python's stock `http.server` does *not*
implement `Range`, and fsspec silently falls back to re-reading from the beginning — the
first version of the test passed while proving nothing, taking 33 s for 5,000 reads.
With range support it takes 6 s and exercises the real behaviour.

## Conclusion

Convert from whichever exists, in this order:

1. **The delivery on disk**, if a real copy is still there — `--source <dir>`.
2. **The object store**, otherwise — `--source s3`, same speed, no second copy.

Never `~/mva-objects/`. Still to be measured on the delivery itself: the engine bake-off
on a real `.fastq.gz`, which is what authorises the full conversion.
