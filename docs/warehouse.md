# The warehouse: derived tables in DuckDB, on a box you already have

The [exploration toolkit](exploration.md) reads the profile tables straight off disk, which
is right while the numbers are still being argued about on one laptop. This is the other
half: one **typed**, columnar copy of those derived tables on a machine the team shares,
queryable in SQL.

## First, the thing that surprises everyone

**DuckDB is not a server.** It is a library that runs inside your process, with the whole
database in one file — the same arrangement as SQLite, but column-oriented. There is no
daemon, no listening port, no `CREATE USER`, and nothing to "expose".

This is worth stating plainly because it inverts the usual instinct. With Postgres you
install a service, open a port, create accounts, and *then* send data. With DuckDB there is
no step 1–3. "The database on the server" means precisely one thing: a `.duckdb` file on
that server's disk.

```mermaid
flowchart LR
  subgraph CS["Client–server database (Postgres, MySQL)"]
    direction LR
    A1[your script]:::neutral -->|TCP :5432| D1[(daemon<br/>owns the data)]:::neutral
    D1 --> F1[(data files)]:::neutral
  end
  subgraph EM["Embedded database (DuckDB, SQLite)"]
    direction LR
    A2["your process<br/><i>the database is a library inside it</i>"]:::good --> F2[(one .duckdb file)]:::good
  end
  CS ~~~ EM
  classDef neutral fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
```

> **Legend** — **blue = neutral machinery** you would have to install, secure and keep
> patched; **green = the goal**, a single file with no service behind it. The absent arrow
> in the green box is the point: there is no network hop, so there is no port to expose and
> no second thing to authenticate.

The consequence is a *security* one, and it is why this design was chosen: the access
control on the warehouse is the box's own SSH access. There is no second surface.

The trade-off is sharper than "one writer at a time", and it is worth stating precisely
because it is measured rather than assumed. The lock is a **file** lock, and it excludes
*readers too*:

```
# while one process holds the .duckdb file open:
$ duckdb profile.duckdb -c "INSERT INTO ledger VALUES ('B','y');"
IO Error: Could not set lock on file "…/profile.duckdb":
Conflicting lock is held in …/python3.13 (PID 166463).

$ duckdb -readonly profile.duckdb -c "SELECT count(*) FROM ledger;"
IO Error: Could not set lock on file "…/profile.duckdb": Conflicting lock is held …
```

So one teammate running a long write makes the warehouse **unreadable** for everyone else,
not merely unwritable. For a single-owner, rebuild-from-Parquet store like this one that is
fine — the file is derived, and `load` rewrites it wholesale. For anything several people
or agents append to concurrently it is disqualifying, and the answer is a hosted database
rather than a workaround. See [When you outgrow this](#when-you-outgrow-this).

## The pipeline

```mermaid
flowchart TB
  P[/"profile directory<br/>ressources/data-profile/*.tsv|.bed|.txt"/]:::raw
  P --> S{{"<b>stage</b><br/>sniff shape → normalise → type"}}:::decide
  S --> Q["build/warehouse/*.parquet<br/><i>typed, columnar, 47 KB</i>"]:::good
  Q --> L{{"<b>local</b><br/>rehearsal build"}}:::decide
  L --> LD[("build/warehouse/profile.duckdb<br/>schema proven before shipping")]:::good
  Q -->|"<b>push</b> — rsync over ssh"| R["box:~/warehouse/parquet/"]:::neutral
  V{{"<b>provision</b><br/>pinned duckdb binary"}}:::decide --> R
  R -->|"<b>load</b> — CREATE OR REPLACE"| DB[("box:~/warehouse/profile.duckdb")]:::good
  DB -->|"<b>query</b> — readonly over ssh"| OUT[/"answers"/]:::good
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef decide fill:#fef9c3,stroke:#ca8a04,color:#713f12
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
  classDef neutral fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
```

> **Legend** — **purple = the raw input** (files as delivered by the shell pipelines);
> **yellow = a step that makes a decision** (what shape is this file, what type is this
> column, does this box already have the binary); **blue = neutral transport**;
> **green = the queryable result**. Every arrow is a separate CLI verb, so a failure is
> debugged one step at a time rather than as one opaque pipeline.

## What to run

```bash
export MVA_WAREHOUSE_HOST=user@your-box     # or an alias from ~/.ssh/config

uv run mva-warehouse preflight              # what does the box have? changes nothing
uv run mva-warehouse stage                  # profile dir → typed Parquet, no network
uv run mva-warehouse local                  # rehearsal: build the .duckdb here first
uv run mva-warehouse ship                   # stage + provision + push + load
uv run mva-warehouse query 'SELECT * FROM warehouse_catalog'
```

`--dry-run` on any networked verb prints the exact commands instead of running them. Read
them before the first real run; they are short.

## Why each step is its own verb

`ship` is the everyday command, but it is a composition, not a monolith. When a deployment
fails you want to know *which* of four independent things broke — the box lacked `unzip`,
the transfer was interrupted, a Parquet was malformed — and each of those is one verb you
can rerun in isolation. `preflight` in particular uploads nothing and changes nothing, so a
failure there costs nothing to retry.

`local` earns its place for a different reason: it builds exactly the schema the remote
load will build, on your machine, before a byte leaves it. If the types are wrong you find
out in one second rather than after a transfer.

## What staging actually fixes

The delivered TSVs are not rectangular, and handing them to a CSV reader unmodified gives
either a parse error or a silently truncated table. Three specific hazards:

| Hazard | Example | What staging does |
|---|---|---|
| No header row | `vcf_contig_counts.tsv` starts with a record | Column names declared in `catalog.OVERRIDES`; the first line stays a record |
| Rollup lines glued under the table | `est_raw_coverage_x  51.9` beneath 8 full-width rows | Collected into one `profile_scalars` table instead of being dropped or read as a short row |
| `##` sections, not one table | `vcf_filter_gt_counts.tsv` holds two blocks | Flattened to long form: `(section, label, count)` |

And one that is not a parse error but a usability tax: a header cell like
`pct_in_0.40_0.60` is legal in a TSV and legal in Parquet, but in SQL the dots read as
qualifiers, so every query touching it would need double quotes forever. It is folded once,
at staging, to `pct_in_0_40_0_60`.

**Types come from DuckDB's own CSV sniffer**, not from a hand-rolled guesser. That is
deliberate: it means the staging step and an analyst typing `read_csv` themselves can never
disagree about what a column is.

## Adding a new case

Nothing in the module knows about this proband. `catalog.discover` sniffs whatever
directory it is given and infers each file's shape from its suffix and first line, so a
different N-of-1 case is a different `--profile` argument. Only files whose shape *cannot*
be read off the file itself — a headerless table has no way to announce its own column
names — need an entry in `OVERRIDES`. Adding a case means adding overrides; it never means
editing the sniffer.

## Data handling

The warehouse holds **derived tables only** — counts, coverage summaries, panel intervals,
checksums. No reads, no genotypes, no patient variant records. It is a derived dataset in
the sense the challenge rules use, and is deleted with everything else within 30 days of
close. `build/` and `*.duckdb` are gitignored so the file is never committed by reflex; the
repository carries the recipe, and `mva-warehouse stage` rebuilds the output in under a
second.

If patient-level tables are ever staged, the same rules that govern the VCF apply to the
box: it must be access-controlled, never public, and wiped on the same schedule.

## When you outgrow this

The file-on-a-box design holds for as long as the warehouse has one owner and is rebuilt
rather than edited. Two things break it: **concurrent writers** (the lock above), and
**mutable shared state** — an oracle probe ledger, a submissions table, a run registry —
which by definition is edited rather than rebuilt.

At that point install **PostgreSQL** on the same box and split the work by what the data
*is*, not by which engine you prefer:

| | Where | Why |
|---|---|---|
| Mutable shared state — ledger, submissions, run registry, results | **Postgres tables** | Concurrent readers and writers, which DuckDB cannot give at all |
| Big immutable derived tables — annotated variants | **Parquet on disk** | Measured at 5,012,204 rows: 17 MB vs 653 MB, and 18 ms vs 287 ms |
| Running the analytics, and writing results back | **DuckDB over both** | One engine; results land in Postgres directly |

DuckDB attaches to Postgres and writes to it natively, so nothing about the pipeline
changes shape:

```sql
INSTALL postgres; LOAD postgres;
ATTACH 'host=box dbname=mva user=… password=…' AS pg (TYPE postgres);

CREATE TABLE pg.panel_summary AS
  SELECT p.gene, p.n_all, b."end" - b.start AS span_bp
  FROM read_parquet('parquet/panel_variant_counts.parquet') p
  JOIN read_parquet('parquet/mva_panel_grch38.parquet') b ON p.gene = b.name;
```

If the *variant* tables also need to be versioned and auditable — a real want for a
scientific submission — point **DuckLake** at that same Postgres as its catalog instead of
installing a second server. It keeps the data as Parquet, adds multi-writer transactions,
and records a snapshot per change:

```sql
ATTACH 'ducklake:postgres:host=box dbname=lakecat …' AS lake (DATA_PATH 'lake/');
SELECT count(*) FROM lake.panel AT (VERSION => 1);   -- the table as it was, before
```

Every claim in this section was executed against a real PostgreSQL and DuckDB rather than
read off documentation. The numbers, the options rejected (MotherDuck, ClickHouse,
`pg_duckdb`, MySQL, SQLite) and the caveats on the synthetic sizing are in
[`methodology/009`](../methodology/009-hosted-database-choice.md), which records the exact
versions the run used. Nothing here depends on a particular Postgres release — use whatever
the server has.

## The hosted path, step by step

This is the route to use when the warehouse is shared: PostgreSQL holds the tables, and
DuckDB stays the engine. It needs **nothing installed on the server** beyond the PostgreSQL
already running there — the client connects over the network.

### 1. On the server, once

```bash
./tools/setup-warehouse-server.sh --db mva --user mva
```

Creates the role, the database and two schemas, and prints the `.env` block to paste on
your machine. It is idempotent — safe to re-run — and pins no version: it reports whatever
`SHOW server_version` says and works with it. If `sudo -u postgres psql` is not how you
reach the superuser, override it:

```bash
MVA_PSQL_SUPER="psql 'postgresql://admin:pw@host:5432/postgres'"   ./tools/setup-warehouse-server.sh
```

Add `--no-duckdb` to skip installing the DuckDB CLI on the box; it is a convenience for
querying while logged in, not a requirement.

### 2. On your machine

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

> **Legend** — **purple = the raw input**; **blue = machinery that is rebuilt wholesale on
> every ingest**; **green = results worth keeping**, including the provenance log. The
> dashed self-loops are the safety property: `pg-ingest` replaces everything in
> `warehouse`, and by construction cannot reach into `results`. Verified — after a
> re-ingest, all six result tables survived.

`pg-ingest` is a pure function of the Parquet; `pg-derive` is a pure function of the
ingested tables. Nothing is ever edited in place, so a wrong number is fixed by fixing the
input and running again.

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

### Credentials

`.env` is gitignored; `.env.example` is the committed template. Anything exported in the
real environment beats the file, so CI can inject `PGPASSWORD` without a stale `.env`
overriding it. Settings print redacted — `password: set`, never the value — so a settings
object is safe in a log or a traceback.

If the server should not accept connections from the internet, leave `listen_addresses`
alone and tunnel instead:

```bash
ssh -L 5432:localhost:5432 user@server     # then PGHOST=localhost in .env
```

Worked example with real output: [`methodology/010`](../methodology/010-postgres-ingest-and-derivations.md).
