# Shared mutable state goes in Postgres, not a DuckDB file

**Standing:** settled. What remains open is whether to *retire* the superseded file-warehouse
verbs — see Consequences.

The first warehouse was a `.duckdb` file on a box, reached over SSH. It was chosen for a
real reason: DuckDB is embedded, so there is no daemon, no listening port, no accounts, and
the access control is the box's own SSH. One surface instead of two.

It does not survive contact with a team. DuckDB's file lock excludes **readers as well as
writers**, so one teammate running a long write makes the warehouse unreadable for everyone
else — measured, not assumed
([`methodology/008`](../../methodology/008-duckdb-warehouse.md)). For a single-owner store
rebuilt wholesale that is fine. For an oracle probe ledger, a submissions table or a run
registry — state that is *edited* rather than rebuilt — it is disqualifying.

The split is by what the data **is**, not by which engine is preferred:

| | Where | Why |
|---|---|---|
| Mutable shared state — ledger, submissions, run registry, results | **Postgres tables** | concurrent readers and writers, which DuckDB cannot give at all |
| Big immutable derived tables | **Parquet**, in the object store | measured 17 MB vs 653 MB and 18 ms vs 287 ms on the full callset |
| Running the analytics, writing results back | **DuckDB over both** | one engine; it attaches to Postgres and writes natively |

Every claim was executed against a real PostgreSQL and DuckDB rather than read off
documentation. The measurements, the rejected options (MotherDuck, ClickHouse, `pg_duckdb`,
MySQL, SQLite) and the caveats on the synthetic sizing are in
[`methodology/009`](../../methodology/009-hosted-database-choice.md); the working ingest is
[`methodology/010`](../../methodology/010-postgres-ingest-and-derivations.md).

Nothing depends on a particular Postgres release. The setup script prints
`SHOW server_version` and works with whatever the server has.

## Consequences

The pipeline shape did not change — DuckDB is still the engine, and derivations are still
plain SQL. Only the destination moved.

Two warehouse stories now live in one CLI. The file verbs (`preflight`, `stage`, `local`,
`provision`, `push`, `load`, `ship`, `query`) and their modules (`remote.py`, `catalog.py`,
`analysis.py`) are kept in-tree, and **`stage.py` is still live** because `pg-ingest`
consumes its Parquet. Retiring the rest is an open decision, not a done one. The archived
document describing that path is
[`archive/duckdb-file-warehouse.md`](../../archive/duckdb-file-warehouse.md).

If the *variant* tables ever need versioning and time travel, point DuckLake at the same
Postgres as its catalog rather than installing a second server. Not needed yet.
