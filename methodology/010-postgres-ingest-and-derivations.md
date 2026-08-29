# 010 — Ingesting the profile into hosted PostgreSQL and deriving results there

## Question

With PostgreSQL and pgAdmin already running on the server, can the staged profile be
ingested from a laptop, analysed, and have its **outputs written back into Postgres** —
without installing anything else on the box?

## Finding first

Yes. Fourteen source tables ingested and five derived result tables written back, all
driven from the client with DuckDB as the engine and nothing installed server-side beyond
the PostgreSQL that was already there. The derived numbers reproduce findings established
independently in [003](003-panel-gene-variant-counts.md),
[004](004-sex-and-aneuploidy-from-allele-balance.md) and
[005](005-fastq-structure-and-quality.md), which is the cross-check that the normalisation
and transport altered nothing.

## Inputs

- Server: a stock PostgreSQL container standing in for the real server. **No version is
  pinned anywhere in the tooling or the docs** — the run used whatever `postgres:latest`
  resolved to, which reported `18.6 (Debian 18.6-1.pgdg13+2)`, and the setup script prints
  `SHOW server_version` rather than requiring anything.
- Client: `duckdb` Python package with the `postgres` extension. No Postgres driver.
- Staged Parquet from [008](008-duckdb-warehouse.md) — 14 tables, 4,674 rows, 47 KB.
- Code: `tools/setup-warehouse-server.sh`, `src/mva/warehouse/{settings,postgres,analysis}.py`.

## Commands run and observed output

### 1. Server setup — idempotent, version-agnostic

```
$ MVA_PSQL_SUPER="psql -U postgres" ./tools/setup-warehouse-server.sh \
      --db mva --user mva --password ****
==> Checking the server
    ✓ postgres reachable — 18.6 (Debian 18.6-1.pgdg13+2)
==> Role 'mva'          ✓ created
==> Database 'mva'      ✓ created, owned by mva
==> Schemas: warehouse results
    ✓ warehouse
    ✓ results
```

Re-running it changed nothing and re-printed the `.env` block:

```
==> Role 'mva'      ✓ already existed — password reset to the one supplied
==> Database 'mva'  ✓ already exists
NOTICE:  schema "warehouse" already exists, skipping
```

### 2. Connect

```
$ uv run mva-warehouse pg-check
.env:     /home/abdu/ubuntu/mva-hackathon/.env
target:   mva@localhost:55991/mva (password: set, schemas: warehouse + results)

connected.
  server:  PostgreSQL 18.6 (Debian 18.6-1.pgdg13+2)
  size:    7678 kB
  schemas: public, results, warehouse
```

The `target` line is the redaction test in practice — settings print without the credential.

### 3. Ingest

```
$ uv run mva-warehouse pg-ingest
ingested 14 tables into localhost/mva, schema warehouse
  contig_counts               1,690 rows
  … (14 tables) …
  warehouse_catalog              13 rows
```

Row counts match the staging run in [008](008-duckdb-warehouse.md) exactly.

### 4. Derive — outputs written back into Postgres

```
$ uv run mva-warehouse pg-derive
wrote 5 result tables into schema results
  results.panel_gene_density        8 rows
  results.contig_density           25 rows
  results.allele_balance_flags     24 rows
  results.filter_impact            35 rows
  results.sequencing_yield          4 rows

provenance appended to results.derivation_runs
```

Read back through `psql` — no DuckDB involved:

```
  gene  | n_all | n_pass | n_filtered | span_bp | variants_per_mb | pct_pass
--------+-------+--------+------------+---------+-----------------+----------
 TP53   |   120 |    118 |          2 |   65768 |          1824.6 |     98.3
 CEP192 |   255 |    251 |          4 |  173771 |          1467.4 |     98.4
 CENPE  |   169 |    166 |          3 |  133115 |          1269.6 |     98.2
 SMC5   |   125 |    124 |          1 |  136605 |             915 |     99.2
 BUB1B  |    80 |     76 |          4 |  100154 |           798.8 |       95
 DICER1 |    87 |     87 |          0 |  111783 |           778.3 |      100
 TRIP13 |    12 |      6 |          6 |   66509 |           180.4 |       50
 CEP57  |    13 |     13 |          0 |   87106 |           149.2 |      100
```

**`TRIP13` loses half its records to quality filters** (6 of 12; every other panel gene
keeps ≥95%). That is a new observation from this run, and it is a caution rather than a
result: `TRIP13` is a genuine MVA gene, so a filter dropping half its calls is exactly where
a real variant could be hiding. It is the "caller saw it and suppressed it" case the
strategy brief calls Tier 1.5. Not yet investigated.

The allele-balance derivation reproduces [004](004-sex-and-aneuploidy-from-allele-balance.md):

```
 chrom | n_het | mean_vaf | mean_dp | vaf_deviation | balance_call | dp_vs_autosomal
-------+-------+----------+---------+---------------+--------------+-----------------
 Y     |  4301 |   0.3517 |    36.3 |       -0.1483 | flagged      |           0.815
 X     |  4858 |   0.4644 |    41.4 |       -0.0356 | balanced     |            0.93
 20    | 59467 |    0.472 |    45.5 |        -0.028 | balanced     |           1.022
```

Only Y is flagged; every autosome is balanced — the same negative aneuploidy result, now
computed in SQL rather than by eye.

`sequencing_yield` sums to 41.15 + 40.63 + 39.28 + 39.84 = **160.90 Gbases**, matching the
`est_total_gbases` scalar of 160.9 carried in `profile_scalars` from a different source
file. Independent path, same number.

`filter_impact` puts `PASS` at 4,740,790 records (94.58%), consistent with the 5,012,204
total from [001](001-vcf-provenance-and-structure.md).

### 5. The schema separation actually protects results

The design claim is that re-ingesting cannot destroy derived tables. Tested:

```
$ uv run mva-warehouse pg-ingest          # replaces the `warehouse` schema wholesale
$ psql -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='results'"
6 result tables survived
```

And provenance accumulates rather than being overwritten:

```
      derivation      | runs |           latest
----------------------+------+----------------------------
 panel_gene_density   |    2 | 2026-08-29 12:19:02.804066
 allele_balance_flags |    1 | 2026-08-29 12:18:10.049346
```

### 6. Tests

```
$ uv run pytest tests/ -q
186 passed in 3.77s
```

36 are new. None contacts a database: what is unit-tested is what can go wrong *before* a
connection opens — a credential reaching a log, an identifier reaching SQL unvalidated, a
derivation referencing a table ingest never produces.

## Follow-up: Postgres in a container

The first real-server run failed at the first step:

```
$ ./tools/setup-warehouse-server.sh --db mva --user mva
==> Checking the server
cannot reach the postgres superuser role using:
    sudo -u postgres psql -v ON_ERROR_STOP=1 -qtA
```

The server runs Postgres in Docker, so there is no local `postgres` OS user to `sudo` to —
the superuser lives *inside* the container. The script now discovers this rather than
requiring the operator to construct the command. Verified against a containerised Postgres:

```
$ ./tools/setup-warehouse-server.sh --db mva --user mva --password ****
==> Finding the database
    ✓ discovered Postgres container 'mva-pg-docker' via docker
    ✓ postgres reachable — 18.6 (Debian 18.6-1.pgdg13+2)
…
PGHOST=DESKTOP-IRPBBMJ.localdomain
PGPORT=55993
```

**`PGPORT=55993`, not 5432** — which is the substantive part. Inside a container Postgres
answers `SHOW port` with 5432 no matter what is mapped on the host, so the previous code
would have emitted a `.env` that looked right and could not connect. The port now comes
from `docker port <container> 5432/tcp`.

Ambiguity and the unpublished case are both handled:

```
$ ./tools/setup-warehouse-server.sh …
several Postgres containers are running:
    mva-pg-nopub
    mva-pg-docker
Pick one with --docker <name>.
```

```
⚠  Container 'mva-pg-nopub' does not publish port 5432 to the host, so nothing
   outside it can connect yet — not even this server.
```

The full pipeline was then re-run end to end against the container the script had just
configured — `pg-check`, `pg-ingest` (14 tables), `pg-derive` (5 result tables) — all
succeeding.

### The real server: a superuser that is not `postgres`, and a database that does not exist

Container discovery worked on the actual server but the connection still failed:

```
==> Finding the database
    ✓ discovered Postgres container 'postgres_db' via podman
cannot reach the postgres superuser role using:
    podman exec -i postgres_db psql -U abdu -v ON_ERROR_STOP=1 -qtA
```

Read-only probing on the server established what was actually true — the facts the script
had been guessing at:

```
POSTGRES_USER=abdu
POSTGRES_DB=db

  OK    -U abdu -d postgres
  OK    -U abdu -d template1
  fail  -U abdu -d abdu       → FATAL:  database "abdu" does not exist
  fail  -U postgres -d postgres → FATAL:  role "postgres" does not exist
```

Two independent assumptions were wrong at once:

1. **There is no `postgres` role.** The image was built with `POSTGRES_USER=abdu`, so that
   is the superuser and the conventional name does not exist.
2. **`psql -U abdu` with no `-d` opens a database named `abdu`,** which the image creates
   only when `POSTGRES_DB` is unset. Here `POSTGRES_DB=db`, so it does not exist.

The old code passed no `-d` at all, so even the correct superuser failed. Superuser and
maintenance database are now probed **as pairs**, with candidates drawn from the
container's own `POSTGRES_USER` / `POSTGRES_DB` plus `postgres` and `template1`.

**The deeper defect was the error handling, not the guess.** The probe ran under
`>/dev/null 2>&1`, so the operator got a dead end instead of `FATAL: database "abdu" does
not exist` — which names the problem outright. Failures now print every pair tried with its
real error.

Verified against stubs replicating the server exactly (role `abdu`, no `postgres` role,
databases `postgres`/`template1`/`db`, port published) — no containers involved, since a
local container proves nothing about that host:

```
    ✓ discovered Postgres container 'postgres_db' via podman
    ✓ superuser 'abdu', maintenance database 'postgres'
    ✓ postgres reachable — 18.4 (Debian 18.4-1.pgdg12+1)
==> Role 'mva'       ✓ created
==> Database 'mva'   ✓ created, owned by mva
==> Schemas          ✓ warehouse  ✓ results
PGPORT=5432
```

Re-running was a no-op. The failure path was exercised too, and now lists all six
attempted pairs with the actual psql error against each.

### A second bug, caught in that work

`set -o pipefail` plus `docker port` aborted the script silently. `docker port` exits
non-zero when nothing is published, so the pipeline assigning `PUBLISHED_PORT` failed and
`set -e` killed the run at exactly the moment it was trying to *detect and explain* that
situation — exit code 1, no message. Fixed with a `|| true` on that pipeline, with a comment
saying why it is load-bearing.

## Bug this run caught

**A lazy relation outlived its connection.** `pg-query` raised
`ConnectionException: Connection has already been closed` — DuckDB's `sql()` returns a
relation evaluated only when consumed, and the `attached` context manager had closed the
connection by then. Fixed by materialising inside the block and returning a `Result` that
carries its own rows.

## Conclusion

The hosted path works end-to-end and needs nothing on the server but the PostgreSQL already
installed. Ingest is a pure function of the staged Parquet; derivations are a pure function
of the ingested tables; the two live in separate schemas so neither can destroy the other.

One follow-up worth taking: `TRIP13`'s 50% filter rate.

## Confirmed on the real server

Run against `vmi2938918.contaboserver.net` (PostgreSQL 18.4, in a Podman container) with
the credentials the setup script produced.

```
$ uv run mva-warehouse pg-check
target:   mva@vmi2938918.contaboserver.net:5432/mva (password: set, …)
connected.
  server:  PostgreSQL 18.4 (Debian 18.4-1.pgdg12+1)
  schemas: public, results, warehouse

$ uv run mva-warehouse pg-ingest     → 14 tables      real 0m4.4s
$ uv run mva-warehouse pg-derive     → 5 result tables real 0m4.7s
```

**Independent verification.** SSH to the box is not reachable from the client (port 22
blocked; 5432 open), so rather than take DuckDB's word for it, PostgreSQL's own statistics
view was asked what it physically holds:

```
table                                    rows (per Postgres)   on disk
results.allele_balance_flags                              24   16 kB
results.panel_gene_density                                 8   16 kB
…
warehouse.contig_counts                                1,690   152 kB
warehouse.vcf_header_lines                             2,621   320 kB

20 tables physically present in PostgreSQL
```

Row counts match the ingest report exactly, and the types survived the trip —
`results.panel_gene_density` stores `bigint` and `double precision`, not text.

**Cross-checks against earlier methodology, computed server-side:**

| Check | Warehouse says | Established | Agree |
|---|---|---|---|
| Lane yields summed vs `est_total_gbases` | 160.9 | 160.9 ([005](005-fastq-structure-and-quality.md)) | ✓ |
| FILTER counts summed vs `total_records` | 5,012,204 | 5,012,204 ([001](001-vcf-provenance-and-structure.md)) | ✓ |
| Chromosomes flagged for allele imbalance | Y only; 23 balanced incl. X | no visible aneuploidy, male ([004](004-sex-and-aneuploidy-from-allele-balance.md)) | ✓ |
| Panel gene counts | unchanged | [003](003-panel-gene-variant-counts.md) | ✓ |

Two independent paths through different source files agree on 160.9 and 5,012,204, which
is the evidence that normalisation, transport and ingest altered nothing.

**The safety property holds in production.** A re-ingest — which replaces the `warehouse`
schema wholesale — left all six result tables intact:

```
$ uv run mva-warehouse pg-ingest
$ SELECT count(*) FROM information_schema.tables WHERE table_schema='results'
  → 6
```

`TRIP13` at 50% pass rate reproduces on the real server and remains the open follow-up.

The warehouse is live and browsable in pgAdmin.
