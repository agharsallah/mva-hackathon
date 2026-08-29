# 014 — The delivery as a source of truth, with lineage

## Question

Get the delivered data into MinIO and PostgreSQL **unchanged**, so there is a source of
truth that cannot drift, with enough metadata and lineage to answer later which bytes
produced which result.

## Finding first

All 12 delivered files are in object storage, **84.99 GB**, and every one of the 10 that
the publisher hashes matches its published SHA-256. The bucket carries versioning, so no
upload can destroy an earlier one. PostgreSQL holds three records of it — an append-only
upload ledger, a current object inventory enriched with the delivery's naming convention,
and an append-only lineage edge list.

## Inputs

- Source dataset: `SageBio/mva-hackathon-2026-data` (gated), commit `f534cb0c`.
- Object store: MinIO on the server, bucket `mva`, versioning **Enabled**.
- PostgreSQL on the same server, schema `warehouse`.

## What was done

### 1. Fetched from the publisher, not copied from a laptop

The delivery was already on a workstation, but uploading it would have taken **8.7 hours**
at the 2.7 MB/s measured on the 300 MB VCF. Downloading it again *on the server* is faster
and is better provenance — the bytes come from the source rather than from a copy — because
the publisher's own SHA-256 makes the result checkable.

Those hashes are committed at
[`ressources/data-profile/hf_lfs_sha256.tsv`](../ressources/data-profile/hf_lfs_sha256.tsv),
read out of the `huggingface_hub` download cache. One subtlety: **only Git-LFS objects
carry a SHA-256.** Small non-LFS files record a 40-character git blob SHA-1 — a different
algorithm over different bytes — so comparing them would produce a false mismatch. They are
excluded from the table rather than reported as failures.

### 2. Verification

```
$ uv run mva-warehouse source-check
  Challenge_Clinical_Phenotype_1.docx               document          0.00 GB         ok
  WGS_EX2312012_HGWCNDSX7.vcf.gz                    variants          0.32 GB         ok
  WGS_EX2312012_HGWCNDSX7.vcf.gz.tbi                variant_index     0.00 GB         ok
  WGS_EX2312012_HGWCNDSX7_S16_L001_R1_001.fastq.gz  reads            10.47 GB  L1 R1  ok
  … (8 FASTQ) …

  12 objects, 84.99 GB
  12 hash-verified against the publisher
```

Independently, every hash in the ledger was compared with the published table:

```
10 match the publisher, 0 mismatch, 2 without a published hash
```

The reference is deliberately the **publisher's** hash, not our own upload record.
Comparing our record against our record confirms nothing.

### 3. Metadata enrichment

The delivery's filenames encode facts that would otherwise be re-parsed ad hoc:
`WGS_EX2312012_HGWCNDSX7_S16_L003_R2_001.fastq.gz` → sample `WGS_EX2312012`, flowcell
`HGWCNDSX7`, lane 3, read 2. `source_objects` carries these as columns, plus a `mate_key`
that pairs R1 with R2:

```
mate_key      files   gb      mates
HGWCNDSX7:L1      2   21.50   R1+R2
HGWCNDSX7:L2      2   21.29   R1+R2
HGWCNDSX7:L3      2   20.82   R1+R2
HGWCNDSX7:L4      2   21.06   R1+R2
```

Four complete lanes, both mates present in each — a completeness check that falls out of
the enrichment for free.

### 4. The three tables, and why they differ

| Table | Shape | Why |
|---|---|---|
| `source_files` | **append-only** | The upload history. A file uploaded twice has two rows; the VCF and its index do, having been sent from the workstation and then re-fetched on the server. Both MinIO versions still exist. |
| `source_objects` | **replaced** | Current bucket state. History would duplicate the ledger and could then disagree with it. |
| `data_lineage` | **append-only** | Which inputs produced which table, how, and how many rows. A derived table with no lineage row is one nobody can vouch for. |

### 5. Raw ingest into PostgreSQL

`warehouse.variants_raw`: one row per VCF data line, **every field from the file as text**,
nothing parsed, nothing filtered — non-PASS records included, because a suppressed allele is
exactly what this case may turn on. Only `line_no` is typed, and it is our own bookkeeping
rather than file data.

Verified on a 5,000-record smoke load before the full run:

```
line_no  chrom  pos    ref  alt    qual    filter  format          sample_call
1        1      13273  G    C      385.77  MQ40    GT:AD:DP:GQ:PL  1/1:0,13:13:39:414,39,0
```

Byte-identical to the first record of the file. Column types: `line_no bigint`, all ten
file columns `character varying`.

## Two things worth recording

**A gzip cannot be range-requested.** Reading the VCF object directly from MinIO means
transferring all 315 MB, so `read_csv('s3://…vcf.gz')` from a laptop timed out at 115 s
while `count(*)` on a *Parquet* object of similar size moves 0.5% of the file. Columnar
formats are remotely queryable; compressed text is not. The ingest is therefore documented
to run on the server, where the object store is local.

**A right-anchored filename regex.** The first parser split
`WGS_EX2312012_HGWCNDSX7_S16_L003_R2_001.fastq.gz` from the left and matched nothing,
because the sample identifier itself contains an underscore. Anchoring on the fixed
`_S<n>_L<lane>_R<read>_001` suffix and taking the flowcell as the last remaining segment
handles it. Unrecognised names yield nulls rather than guesses — a wrong lane silently
attached to a read is worse than a missing one.

## Conclusion

The delivery is preserved unchanged and independently verified, with versioning against
accidental overwrite and lineage from each derived table back to the exact object and
version it came from. Nothing has been transformed: `variants_raw` is the file, in rows.

Typed layers — `variants` split per ALT allele, `genotypes`, `variant_info` — are derived
from this and can be rebuilt at will. Structure proposed in
[`docs/ingestion-plan.md`](../docs/ingestion-plan.md); not yet built.
