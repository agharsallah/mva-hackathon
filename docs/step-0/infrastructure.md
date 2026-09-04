# Infrastructure — the live runbook

**Verified:** 2026-08-29. `pg-check` and `s3-check` both connect; what is provisioned and
how much is in it is in [`current-state.md`](../current-state.md). This page is *how to
operate it*, not what it currently holds.

Two services on one remote VPS:

| | What | Holds |
|---|---|---|
| **PostgreSQL** | client–server database, reached over the network | tables people query and edit — ingested source tables, derived results, the source-file ledger |
| **MinIO** | S3-compatible object store | bulk immutable files — the delivery itself, staged Parquet, anything measured in gigabytes |

DuckDB is the **engine** in both cases and runs inside your own process on your laptop.
Nothing is installed on the server beyond the two services. Why this split rather than a
DuckDB file on a box: [postgres for shared state](notes/postgres-for-shared-state.md).

---

## 1. PostgreSQL

### On the server, once

```bash
./tools/setup-warehouse-server.sh --db mva --user mva
```

Creates the role, the database and two schemas, and prints the `.env` block to paste on
your machine. Idempotent, and pins no version — it reports whatever `SHOW server_version`
says and works with it.

**It finds the database itself.** Three arrangements exist in the wild and guessing wrong
is the difference between "it just worked" and a confusing auth error, so the script tries
each in turn:

| Arrangement | How it connects |
|---|---|
| You said how | `MVA_PSQL_SUPER` is set — always wins |
| **Postgres in a container** | discovers the running container, goes in via `docker exec` / `podman exec` |
| Packaged Postgres | `sudo -u postgres psql`, the Debian/Ubuntu default |

The container case matters because the superuser lives *inside* the container — there is
no local `postgres` OS user to `sudo` to. With several Postgres containers running, name
one: `--docker <container-name>`.

**The port it reports is the published one, not `SHOW port`.** Inside a container Postgres
always answers 5432 regardless of what is mapped on the host, so a `.env` built from that
looks correct and cannot connect. If the container publishes nothing, the script says so
rather than handing you a broken `.env`.

Anything unusual works by naming the connection yourself:

```bash
MVA_PSQL_SUPER="psql 'postgresql://admin:pw@host:5432/postgres'" ./tools/setup-warehouse-server.sh
```

`--no-duckdb` skips installing the DuckDB CLI on the box; it is a convenience for querying
while logged in, not a requirement.

### On your machine

```bash
cp .env.example .env      # then fill in PGPASSWORD

uv run mva-warehouse pg-check     # resolved settings + a live probe
uv run mva-warehouse stage        # profile dir -> typed Parquet
uv run mva-warehouse pg-ingest    # Parquet -> the `warehouse` schema
uv run mva-warehouse pg-derive    # analyses -> the `results` schema
uv run mva-warehouse pg-list      # what is in both schemas
uv run mva-warehouse pg-query 'SELECT * FROM pg.results.panel_gene_density'
```

Then browse it in pgAdmin like any other database.

> **Sharp edge — `pg-query` table names.** The query runs in DuckDB, which reaches Postgres
> through `ATTACH … AS pg`. Tables are therefore addressed **`pg.warehouse.<table>`** and
> **`pg.results.<table>`**, never `warehouse.<table>`. A bare schema name is a "table does
> not exist" error, not a permissions problem.

### Two schemas, and why it matters

```mermaid
flowchart LR
  PQ["staged Parquet<br/><i>on your machine</i>"]:::raw
  PQ -->|pg-ingest<br/>CREATE OR REPLACE| W["schema <b>warehouse</b><br/>ingested source tables"]:::neutral
  W -->|pg-derive<br/>DuckDB computes| R["schema <b>results</b><br/>derived outputs"]:::good
  R --> PROV[("results.derivation_runs<br/><i>appended, never replaced</i>")]:::good
  W -.->|"re-ingest replaces<br/>this schema wholesale"| W
  R -.->|"…and cannot touch<br/>this one"| R
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef neutral fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
```

> **Legend** — **purple = the raw input**; **blue = machinery rebuilt wholesale on every
> ingest**; **green = results worth keeping**, including the provenance log. The dashed
> self-loops are the safety property: `pg-ingest` replaces everything in `warehouse` and
> by construction cannot reach into `results`. Verified — after a re-ingest, every result
> table survived.

`pg-ingest` is a pure function of the Parquet; `pg-derive` is a pure function of the
ingested tables. Nothing is ever edited in place, so a wrong number is fixed by fixing the
input and running again.

Worked example with real output:
[`methodology/010`](methodology/010-postgres-ingest-and-derivations.md).

### Adding an analysis

Derivations are **data, not code** — a record in `src/mva/warehouse/analysis.py`:

```python
Derivation(
    name="panel_gene_density",
    question="Which candidate gene carries the most variation per base sequenced?",
    depends_on=("panel_variant_counts", "mva_panel_grch38"),
    sql=f'''SELECT p.gene, round(p.n_all * 1e6 / (b."end" - b.start), 1) AS variants_per_mb
            FROM {SOURCE}.panel_variant_counts p
            JOIN {SOURCE}.mva_panel_grch38 b ON p.gene = b.name''',
)
```

Append one and the runner, the CLI's `--only` choices, the provenance stamp and the tests
all pick it up unchanged. The SQL runs in **DuckDB**, so it can join, window and aggregate
freely; only the finished table lands in Postgres. Tests assert that every declared
dependency is really selected from and is really a table staging produces, so a typo fails
in a second rather than after a round trip.

---

## 2. The object store — bulk files, queried in place

PostgreSQL holds the tables people query and edit. The **bulk** files go into MinIO on the
same box and are queried *where they sit*: DuckDB's `httpfs` extension fetches byte ranges
over HTTP, and Parquet's footer tells it which ranges it needs, so a `count(*)` over a
5-million-row Parquet downloads under 1% of the file. Nothing is cached locally, nothing is
downloaded whole, and no SSH session is involved. Measurements:
[`methodology/013`](methodology/013-remote-object-store.md).

### On the server, once

```bash
./tools/setup-object-store.sh --bucket mva
```

Publishes the **API on 9012** and the **console on 9013**, data under `~/mva-objects`.
Both defaults exist because of failures worth knowing about:

* **Ports.** MinIO's own defaults 9000/9001 — and 9002/9003 on this box — were already
  taken. Podman reports a port clash only at container *start*, so a collision leaves a
  container stuck in `Created` with an **empty log** and no error anywhere. The script
  checks both ports first and names the process holding one.
* **Data directory.** Rootless podman runs the container as *you*, so a path outside your
  home is a common cause of a container that starts and immediately dies on a write.

Override with `--port` / `--console-port` / `--data-dir`. **A container keeps the ports it
was created with** — re-running with a different `--port` does not change them, and the
script warns rather than printing a `.env` block for a port that was never published.

**Dashboard:** `http://<server>:9013` — always a different port from the API. Its login is
the same credential pair the script prints: MinIO's root user serves both the S3 API and
the console, so `S3_ACCESS_KEY` / `S3_SECRET_KEY` in your `.env` *are* the dashboard
username and password.

If the generated password is lost it is still in the container's environment:

```bash
podman inspect mva-minio --format '{{range .Config.Env}}{{println .}}{{end}}' | grep MINIO_ROOT
```

Or set your own and recreate the container — objects live in `~/mva-objects` on the host,
so they survive:

```bash
podman rm -f mva-minio
./tools/setup-object-store.sh --password 'your-password'
```

### On your machine

```bash
uv run mva-warehouse s3-check          # settings, a live probe, and the console URL
uv run mva-warehouse s3-put <file.parquet> --key raw/variants_raw.parquet
uv run mva-warehouse s3-ls
uv run mva-warehouse s3-query "SELECT count(*) FROM 's3://mva/raw/variants_raw.parquet'"
```

### The delivery itself

The gated delivery lives in the bucket under `source/`, hash-verified and versioned — that
is the project's source of truth, and the rule is
[delivery is immutable](notes/delivery-is-immutable.md). The verbs:

```bash
uv run mva-warehouse source-scan       # inventory the delivery, upload nothing
uv run mva-warehouse source-fetch      # RUN ON THE SERVER: publisher -> bucket, streaming
uv run mva-warehouse source-upload     # hash, upload unchanged, verify, record in the ledger
uv run mva-warehouse source-status     # delivery on disk vs. the ledger
uv run mva-warehouse source-check      # survey the bucket, verify hashes, refresh inventory
```

`source-fetch` streams from the publisher straight into the bucket; `--tee` also writes a
local copy and `--verify` checks each object against the publisher's SHA-256. Evidence:
[`methodology/014`](methodology/014-source-of-truth-and-lineage.md).

### The two append-only ledgers

`warehouse.data_lineage` answers "which bytes produced this table"; `warehouse.probe_ledger`
answers "which of our 6 oracle submissions is spent, by whom, with what content and what
reply". Neither is ever updated or deleted — a correction is a newer row saying what it
supersedes.

```bash
uv run mva-warehouse lineage-list --current    # newest edge per target table
uv run mva-warehouse lineage-repair            # repoint local-path edges at the verified object
uv run mva-warehouse lineage-backfill          # one edge per already-logged derivation run
uv run mva-warehouse probe-budget              # "n/6 spent, m remaining"
uv run mva-warehouse probe-log --by <member> --type S --payload-file <submission.csv> \
    --response '<scorer reply>' --rationale '<what this probe decides>'
uv run mva-warehouse probe-list
```

`pg-derive` records its own lineage edge on every run, so `lineage-backfill` exists only for
runs that predate that; both repair verbs are idempotent and safe to re-run. Evidence:
[`methodology/016`](methodology/016-lineage-backfill-and-probe-ledger.md).

### Sorting is what makes remote queries cheap

Row-group statistics can only skip a group when the filter column is **clustered**. Same
gene lookup, same data: an unsorted file downloaded 4.40 MB in 1.03 s, sorted by symbol
0.07 MB in 0.03 s — 40× less data, 33× faster. So rewrite anything filtered repeatedly:

```bash
uv run mva-warehouse s3-sort raw/variants.parquet --key raw/variants_by_gene.parquet --by symbol
```

---

## 3. Credentials and exposure

`.env` is gitignored; `.env.example` is the committed template, and it declares
`PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSCHEMA PGRESULTSCHEMA MVA_SOURCE_DIR
MVA_STAGING_DIR MVA_HF_REPO` plus the `S3_*` block. Anything exported in the real
environment beats the file, so CI can inject `PGPASSWORD` without a stale `.env`
overriding it. Settings print redacted — `password: set`, never the value — so a settings
object is safe in a log or a traceback.

`S3_ENDPOINT` takes the **published host port** (9012), never MinIO's internal 9000, and
the **server's hostname**. `localhost` is correct only while an SSH tunnel is open *on your
machine*:

```bash
ssh -N -L 9012:localhost:9012 <user>@<server>    # object store, run on YOUR laptop
ssh -N -L 5432:localhost:5432 <user>@<server>    # Postgres, if it should not listen publicly
```

> `s3-check` warns whenever `S3_USE_SSL=false`. For encrypted transport, use the SSH
> tunnel above or put a TLS reverse proxy in front and set `S3_USE_SSL=true`.

## 4. Data handling

Everything on this infrastructure is derived from, or is, the gated delivery. The rule and
its reasoning are in
[no patient data in the repository](../notes/no-patient-data-in-the-repository.md); the
locations are tabulated in the [root README](../../README.md). The server-side consequence:
it must be access-controlled, never public, and wiped on the same 30-day schedule as
everything else.
