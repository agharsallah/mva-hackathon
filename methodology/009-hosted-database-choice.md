# 009 — Choosing a hosted database to sit under DuckDB

## Question

The derived data is on a laptop. We want it on a shared server in a *hosted* database that
the team can reach, run DuckDB operations against, and write DuckDB results back into.
Which server database fits, given DuckDB is embedded and has no server of its own?

## Finding first

**PostgreSQL, with DuckDB kept as the query engine in front of it** — and the two given
different jobs rather than being made to compete:

| Job | Where it goes | Why |
|---|---|---|
| Mutable shared state several people/agents append to (oracle ledger, submissions, run registry, ranking results) | **Postgres tables** | Concurrent writers. Measured below: a DuckDB file cannot do this at all. |
| Big immutable analytical tables (annotated variants) | **Parquet on the server's disk** | 38× smaller and 16× faster than the same rows in Postgres, measured below. |
| Running the analytics and writing results back | **DuckDB**, attached to Postgres | One engine reads both; `CREATE TABLE pg.x AS SELECT …` lands the result in Postgres. |

The optional upgrade, also verified: **DuckLake using that same Postgres as its catalog**,
which adds multi-writer transactions *and* time travel to the Parquet layer. One installed
server covers both roles.

## Inputs

- `duckdb` 1.5.5 CLI (`d8cdaa33fd`) and Python package 1.5.5; extensions `postgres`, `ducklake`.
- `postgres:17` via Docker (PostgreSQL 17.11), disposable, removed after the run.
- Staged Parquet from [008](008-duckdb-warehouse.md).
- A synthetic 5,012,204-row annotated variant table matching the real callset's record
  count and the annotation columns the pipeline will join in.

## Commands run and observed output

### 1. Can DuckDB write results into Postgres? — yes

```
ATTACH 'host=… dbname=mva' AS pg (TYPE postgres);
CREATE TABLE pg.panel_summary AS
  SELECT p.gene, p.n_all, p.n_pass, b."end" - b.start AS span_bp,
         round(p.n_all * 1e6 / (b."end" - b.start), 1) AS variants_per_mb
  FROM read_parquet('…/panel_variant_counts.parquet') p
  JOIN read_parquet('…/mva_panel_grch38.parquet') b ON p.gene = b.name;
→ rows written to postgres: 8
```

Read back through `psql`, with no DuckDB involved, the types had mapped correctly
(`bigint`, `double precision`, `character varying`) and the values were right:
`TP53 1824.6`, `CEP192 1467.4`, `CENPE 1269.6` variants/Mb.

### 2. The single-writer limit is worse than "one writer at a time"

Writer A opens a `.duckdb` file and holds it. Then:

```
=== writer B tries the same file while A holds it ===
rc: 1
IO Error: Could not set lock on file "…/lock.duckdb":
Conflicting lock is held in …/python3.13 (PID 166463).

=== and a READER while A holds it ===
rc: 1
IO Error: Could not set lock on file "…/lock.duckdb": Conflicting lock is held …
```

**A single writer blocks read-only connections too.** One teammate running a long write
makes the warehouse unreadable for everyone else. The same test against Postgres:

```
writer A: connected to postgres and inserted, still holding
=== writer B, concurrently ===  rc: 0 | INSERT 0 1
=== reader C, concurrently ===  rc: 0 | rows: agent-A:probe 1, agent-B:probe 2
```

This is the finding that decides the question. It corrects the softer claim made in
[008](008-duckdb-warehouse.md) and in `docs/warehouse.md`, which said only that DuckDB
takes one writer at a time; readers are excluded as well.

### 3. Storage and speed at the real record count

A synthetic annotated variant table with **5,012,204 rows** (the callset's actual record
count) and 13 columns — `chrom, pos, ref, alt, symbol, consequence, gnomad_af, cadd_phred,
revel, alphamissense, spliceai_max, gt, dp`:

| | Size | Typical candidate-filter query |
|---|---|---|
| Parquet (zstd) | **17 MB** | DuckDB over Parquet: **18 ms** |
| PostgreSQL table | **653 MB** | DuckDB over Postgres (`postgres` ext): **142 ms** |
| | | Postgres native: **287 ms** |

Query: `WHERE gnomad_af < 0.001 AND cadd_phred > 20 AND consequence IN (…) GROUP BY symbol
ORDER BY n DESC LIMIT 10`; best of three warm runs.

**Caveat on the sizes.** The synthetic rows are generated with modulo patterns, so they
compress far better than real annotations will. The 38× ratio is directionally right — a
column store beats a row store on this shape of data — but the absolute 17 MB is optimistic;
budget a few hundred MB for the real annotated table. The Postgres figure is less affected,
since its per-row overhead dominates.

Load time, Parquet → Postgres, was 12.1 s for the 5M rows.

### 4. DuckLake on a Postgres catalog — verified

```
ATTACH 'ducklake:postgres:host=… dbname=lakecat' AS lake (DATA_PATH '…/lakedata/');
CREATE TABLE panel AS SELECT * FROM read_parquet('…/panel_variant_counts.parquet');
→ 8 rows
```

Snapshots are recorded automatically:

```
snapshot_id | changes
          0 | {schemas_created=[main]}
          1 | {tables_created=[main.panel], inlined_insert=[1]}
          2 | {inlined_insert=[1]}
```

Time travel works — `SELECT count(*) FROM lake.panel AT (VERSION => 1)` returned **8**
while the current table held **9**. Concurrent writers work: writer A held a connection and
inserted, writer B inserted from a separate process and succeeded (`rc: 0`), final count 11.

## Options considered and rejected

| Option | Why not |
|---|---|
| **MotherDuck** (hosted DuckDB) | Uploads the data to a third party. For patient-derived tables under the challenge's data agreement that is the wrong default, independent of its technical merits. |
| **ClickHouse** | Genuinely fast for analytics, but heavier to operate and a poor fit for a small mutable ledger. DuckDB over Parquet already answers in 18 ms; there is no performance problem to solve. |
| **`pg_duckdb`** (DuckDB embedded *inside* Postgres) | Interesting, and would collapse the two engines into one. Rejected for this timeline: it is a newer extension and adds a failure mode to the one component that must stay boring. |
| **MySQL / MariaDB** | No advantage over Postgres here, weaker analytical SQL, and DuckDB's Postgres integration is the better-supported path. |
| **SQLite on the server** | Same single-writer problem as DuckDB, without DuckDB's analytical speed. |

## Conclusion

Install **PostgreSQL** on the box. Give it the mutable, shared, small things — the oracle
probe ledger, submissions, run metadata, ranking outputs — where its concurrency is the
whole point. Leave the big immutable variant tables as Parquet on the same box, where they
are 38× smaller and 16× faster. Use **DuckDB as the engine over both**, writing results back
with `CREATE TABLE pg.… AS SELECT …`.

If a versioned, auditable variant store is wanted, point **DuckLake** at the same Postgres
as its catalog — verified working, with time travel and concurrent writers — rather than
installing a second server.

All figures above are from executed runs against a real PostgreSQL 17.11 and the real
DuckDB 1.5.5 CLI. The Postgres container was disposable and has been removed; **no hosted
database has yet been provisioned on an actual server.**

## Addendum — provisioning against a container-hosted Postgres (2026-08-29)

**Question.** The user's Postgres is not a system service but a Podman container
(`docker.io/pgvector/pgvector:0.8.6-pg18`, container `postgres_db`, publishing
`0.0.0.0:5432->5432/tcp`). Does `tools/setup-warehouse-server.sh` work against it?

**Blocker found.** The script's precondition hardcoded `command -v psql`. There is no
`psql` on the container *host* — it lives inside the container — so the script aborted
before ever trying `MVA_PSQL_SUPER`. Fixed by checking `${PSQL_SUPER[0]}`, the first token
of whatever client was configured, so a `podman exec` / `docker exec` / `ssh` wrapper
passes the check.

**Inputs.** A throwaway container of the *same image* the user runs, started locally:

```bash
docker run -d --name mva_pg_test -e POSTGRES_PASSWORD=testpw \
  -p 55432:5432 docker.io/pgvector/pgvector:0.8.6-pg18
```

**Commands run.**

```bash
MVA_PSQL_SUPER="docker exec -i mva_pg_test psql -U postgres" \
  bash tools/setup-warehouse-server.sh --password testsecret --no-duckdb    # twice
env PGHOST=127.0.0.1 PGPORT=55432 PGDATABASE=mva PGUSER=mva PGPASSWORD=testsecret \
  uv run mva-warehouse pg-check
```

**Observed output.** First run: `postgres reachable — 18.6 (Debian 18.6-1.pgdg12+2)`,
role `mva` created, database `mva` created owned by `mva`, schemas `warehouse` and
`results` created. Second run was idempotent — role "already existed — password reset to
the one supplied", database "already exists", schemas emitted `NOTICE: … already exists,
skipping`. `pg-check` from outside the container over the published port:

```
connected.
  server:  PostgreSQL 18.6 (Debian 18.6-1.pgdg12+2)
  size:    7662 kB
  schemas: public, results, warehouse
```

**Two caveats in the printed `.env` block**, both consequences of the script running
*outside* the database's namespace:

- `PGHOST` is filled from the host's `hostname -f` (here `DESKTOP-IRPBBMJ.localdomain`).
  For a container published on the local machine it must be edited to `localhost`.
- `PGPORT` comes from `SHOW port`, which is the port *inside* the container (5432), not
  the published one. Correct only when the publish mapping is 1:1 — which it is for the
  user's `5432->5432`, but was not for the test's `55432->5432`.

**Conclusion.** The container path works and needs no server-side `postgresql.conf` or
`pg_hba.conf` edits: the official image already listens on `*` and ships a `host all all
all scram-sha-256` rule, and Podman's port publish is the network exposure. Only the two
`.env` fields above need hand-editing after the script prints its block.

`--no-duckdb` is the right flag here — the DuckDB CLI would install onto the container
host, where it is not wanted; the client already drives DuckDB from this repo.

The test container was removed after the run. **The user's own `postgres_db` container has
not been provisioned by this session** — the commands above were executed only against the
throwaway.
