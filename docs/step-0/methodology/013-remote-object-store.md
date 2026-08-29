# 013 — Querying server-side files from a laptop, without SSH

## Question

The bulk data cannot stay on the local disk. How can it live on the server and still be
worked with remotely, through an API, without logging into the box?

## Finding first

**S3-compatible object storage (MinIO) on the server, queried by DuckDB over HTTP range
requests.** Measured: a query against a five-million-row Parquet transfers **0.2–0.5% of
the file**. Nothing is downloaded whole, nothing is cached locally, and no SSH session is
involved.

The efficiency is conditional, and that is the operationally important part: it comes from
Parquet row-group statistics, which only prune when the data is **sorted by the column you
filter on**. The same lookup moved **24.6% of the file unsorted and 0.6% sorted**.

## Inputs

- `duckdb` with the `httpfs` extension.
- A 5,012,204-row Parquet (18 MB, zstd, 100,000-row row groups) served over a local HTTP
  server instrumented to count bytes returned per `Range` request.
- MinIO (`quay.io/minio/minio:latest`) for the client-code validation.

## Commands run and observed output

### 1. How much does a remote query actually transfer?

An HTTP server that logs the length of every range it serves, with DuckDB querying the
file by URL:

```
file on the 'remote' server: 18 MB, 5,012,204 rows

query                                      downloaded                    time
--------------------------------------------------------------------------------
count(*)                                      0.08 MB  (  0.5% of file)   0.02s
one column, aggregated                        0.07 MB  (  0.4% of file)   1.04s
filter on one gene                            6.31 MB  ( 35.2% of file)   1.04s
rare + damaging, grouped                      0.04 MB  (  0.2% of file)   0.05s
```

`count(*)` reads only the footer. The single-column aggregate reads only that column's
chunks — the other ten columns are never fetched. The grouped filter reads 0.2% because
row-group min/max statistics excluded every group.

The gene filter at 35% is the interesting failure: `symbol` was scattered across all row
groups, so no group could be excluded and nearly the whole column was fetched.

### 2. Sorting is what makes range requests small

The same data rewritten `ORDER BY symbol`, same query:

```
gene filter, UNSORTED file            4.40 MB ( 24.6%)   1.03s
gene filter, SORTED by symbol         0.07 MB (  0.6%)   0.03s
```

**40× less data, 33× faster**, from clustering alone. This is the single highest-leverage
thing that can be done to a file destined for remote querying, and it is why
`mva-warehouse s3-sort` exists.

### 3. The client path, end to end

Against a real MinIO, to validate the code rather than the server:

```
$ uv run mva-warehouse s3-check
target: http://127.0.0.1:9199/mva (key: testkey, secret: set)
note:   S3_USE_SSL=false — credentials travel in clear text …
connected. 0 object(s) in mva:

$ uv run mva-warehouse s3-put build/warehouse/contig_counts.parquet \
      --key profile/contig_counts.parquet
landed: s3://mva/profile/contig_counts.parquet

$ uv run mva-warehouse s3-query "SELECT chrom, n_records FROM
      's3://mva/profile/contig_counts.parquet' ORDER BY n_records DESC LIMIT 5"
 2  388761
 1  383428
 4  339607
```

`s3-ls` and `s3-sort` were exercised the same way. Values match the ingested profile, so
the round trip through object storage altered nothing.

## Two things that bit during this work

1. **`URL_STYLE 'path'` is mandatory for self-hosted S3.** AWS's virtual-host style would
   resolve `bucket.your-server` in DNS, which does not exist. The resulting name-resolution
   error looks nothing like a configuration problem. Set in `objects.connect`.

2. **A `.env` without a trailing newline silently merges the next appended setting.**
   Appending `S3_ENDPOINT=…` to a file ending mid-line produced
   `PGRESULTSCHEMA=resultsS3_ENDPOINT=…`, and the tool correctly reported `S3_ENDPOINT`
   missing while the following lines parsed fine — a confusing half-working state. The
   loader behaved correctly; the lesson is to append with a leading newline, which the
   setup script's output block already does.

## Follow-up: three bugs found standing this up on the real server

The first attempt on `vmi2938918` produced a container that never ran, with **no error
anywhere**. `podman ps -a` showed `Created`, and `podman logs` was empty. The cause chain:

1. **Port 9000 was already in use.** Podman reports a port clash only at container
   *start*, not at create, so `podman run -d` left the container in `Created` and the
   failure surfaced only on an explicit `podman start`:
   `bind: address already in use`.
2. **The script discarded `podman run` output** to `/dev/null`, hiding it.
3. **"Container exists" was treated as success.** A second run with `--port 9002` took the
   "already exists — leaving it alone" branch and printed a `.env` block advertising 9002,
   while the container had been created with 9000 — **ports are fixed at creation**.

Each alone was recoverable; together they produced a confident success message, complete
with credentials, for something that had never started.

Fixes: a port preflight that names the occupying process and proposes a free pair; no
output discarded; the "exists" path checks the container is actually *running* and warns
when its published ports differ from those requested; and a health-check loop that refuses
to print a `.env` block unless `/minio/health/live` answers.

Defaults changed as a result: **API 9012, console 9013** (9000/9001 and 9002/9003 were
both already taken on this server), and
`DATA_DIR` moved to `$HOME/mva-objects` — rootless podman runs the container as the calling
user, so a path outside the home directory is a common cause of a container that dies on
first write.

Also corrected in the client: `listing()` used a malformed `LATERAL` query wrapped in a
bare `except Exception`, which turned a connection failure into an **empty listing** —
indistinguishable from an empty bucket. It now raises with a diagnosis that names the
likely cause, and that is what revealed `S3_ENDPOINT=localhost:9002` pointing at the
laptop rather than the server.

## Security note, unresolved

`S3_USE_SSL=false` sends the access key in clear text. The store will hold patient-derived
data, so before anything is uploaded this needs an SSH tunnel, a TLS reverse proxy, or a
firewall restricted to the team's addresses. `s3-check` prints a warning whenever SSL is
off. **This decision has not been made yet.**

## Conclusion

| File | Where | How it is reached |
|---|---|---|
| FASTQ, CRAM, raw Parquet layers | MinIO on the server | `s3-query`, byte ranges only |
| Typed variant and result tables | PostgreSQL on the server | `pg-query`, pgAdmin |
| Nothing | the laptop | — |

Both are network services on the same box, so a laptop needs only `.env` and no SSH
session. Set up with `tools/setup-object-store.sh`; design notes in
[`docs/reads-storage.md`](../reads-storage.md) and
[`docs/warehouse.md`](../warehouse.md).

**Nothing has been uploaded.** The measurements used a synthetic Parquet and a committed
profile table; the test MinIO and the temporary `.env` entries have been removed, and the
real `.env` restored. VCF ingestion remains held pending review.
