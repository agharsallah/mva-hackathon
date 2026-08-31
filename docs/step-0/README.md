# Step 0 — the platform

**Standing:** the index for step 0. Every page here describes machinery that **exists and
runs**; nothing in this folder is a plan. Direction lives in
[`../roadmap.md`](../roadmap.md), current numbers in
[`../current-state.md`](../current-state.md). Last checked 2026-08-31.

## What step 0 is

Everything done *before* the first unstarted roadmap step (normalize the callset). It is
the platform the causal-variant search runs on top of:

- the delivery fetched, hash-verified and pinned in an object store,
- ingested into Postgres as a lossless anchor table,
- derived tables written back, with lineage and an oracle probe ledger,
- the raw reads converted to a queryable Parquet store, served over HTTP,
- an exploration toolkit that renders the committed data profile.

It contains **no candidate variants and no ranking**. Step 0 answers "can we trust and
query the bytes?", not "which pair is causal?".

```mermaid
flowchart LR
  D[/"the delivery<br/>12 objects · 84.99 GB"/]:::raw
  D --> S[("object store<br/>hash-verified · versioned")]:::good
  S --> W[("Postgres<br/>warehouse · results")]:::good
  S --> R[("read store<br/>1.07B reads · Parquet")]:::good
  R --> A["HTTP API<br/>mva-reads-api"]:::neutral
  W --> L[("lineage + probe ledger")]:::good
  W --> E["exploration toolkit<br/>checks · report"]:::neutral
  L --> NEXT{"step 1 —<br/>normalize the callset"}:::decide
  E --> NEXT
  A --> NEXT
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
  classDef neutral fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef decide fill:#fef9c3,stroke:#ca8a04,color:#713f12
```

> **Legend** — **purple = raw input** as delivered; **green = built and verified**;
> **blue = neutral machinery** that holds no unique state; **yellow = the decision point**
> where step 0 hands off.

## What was built

One row per component. Numbers live in [`../current-state.md`](../current-state.md) and
[`../../ideation/data-findings.md`](../../ideation/data-findings.md); this table only names
the pieces.

| Component | What it does | Code | CLI |
|---|---|---|---|
| Delivery + object store | 12 delivery objects uploaded to MinIO, every hash verified, recorded in the append-only `warehouse.source_files` ledger | `src/mva/warehouse/source.py`, `objects.py`, `integrity.py` | `mva-warehouse source-*`, `s3-*` |
| Profile staging | Committed data profile (`ressources/data-profile/`) parsed from disk and normalised to typed Parquet in `build/warehouse/` (gitignored, regenerable) | `src/mva/io/readers.py`, `src/mva/warehouse/catalog.py`, `stage.py` | `mva-warehouse stage` |
| Postgres warehouse | Staged Parquet ingested into schema `warehouse`; five derivations written to schema `results`; all SQL runs through DuckDB's `postgres` extension, tables addressed `pg.warehouse.<table>` / `pg.results.<table>` | `src/mva/warehouse/postgres.py`, `analysis.py`, `settings.py` | `mva-warehouse pg-check`, `pg-ingest`, `pg-derive`, `pg-list`, `pg-query` |
| Raw VCF layer | The callset staged losslessly (all columns text, round-trip verified) into `warehouse.variants_raw` — run on the server, since gzip cannot be range-requested | `src/mva/warehouse/vcfstage.py` | `mva-warehouse vcf-shape`, `vcf-verify`, `vcf-stage`, `vcf-ingest` |
| Lineage + probe ledger | `warehouse.object_inventory`, `warehouse.data_lineage` (append-only edges), `warehouse.probe_ledger` (oracle budget) | `src/mva/warehouse/lineage.py`, `probes.py` | `mva-warehouse lineage-*`, `probe-*` |
| Read store | All FASTQ reads converted to Parquet shards at `s3://mva/reads/lane=<n>/read=<1|2>/`, verified against the source; k-mer probe scans answered in minutes via Aho-Corasick | `src/mva/reads/` (`convert.py`, `engines.py`, `scan.py`, `verify.py`) | `mva-reads convert`, `verify`, `scan`, `count`, `qc`, `sql`, `status`, `bench` |
| HTTP API | Every `mva-reads` verb over HTTP; long verbs return `202` + a job id, jobs persisted and cancellable; `X-API-Key` auth | `src/mva/reads/api/` (`app.py`, `jobs.py`, `models.py`, `runners.py`) | `mva-reads-api --host 0.0.0.0 --port 8765` |
| Viz API | Warehouse + results tables, parsed `bcftools stats`, read-store aggregates and a reads-API proxy served as JSON for the browser; CORS, disk cache, `{data, cached_at, source}` envelope | `src/mva/viz/` | `mva-viz-api` (port 8900) |
| Viz app | React app rendering the whole data profile — 7 pages, 23 exhibits, honest 3D only where the data is spatial; falls back to labelled fixtures when the API is down | `app/` | `cd app && npm run dev` (port 5173) |

Three ways to read the data, one contract:

1. **Local disk** — `ressources/data-profile/` parsed by `src/mva/io/readers.py`
   (missing value is `None`, nothing coerced on read).
2. **Postgres** — `mva-warehouse pg-query` for warehouse tables; `mva-reads --source <dir>`
   for a local delivery mirror.
3. **HTTP** — `mva-reads-api` for the read store from any machine, no shell on the server.

### Step 0 takes no hypotheses

Step 0 is *machinery*, and that makes it a different kind of step from every one after it.
"PostgreSQL is the right database" is a decision with alternatives, judged by whether it
works — not a claim about the patient that evidence could refute. So:

* its reasoning lives in [`notes/`](notes/) as **decisions**, not as hypotheses;
* its [`methodology/001–027`](methodology/) are **platform records** — what was built and
  what was measured, ending in *Conclusions*;
* the register in `mva-science` **refuses** a hypothesis filed under `step-0`.

From [step 1](../step-1/README.md) on it is the other way round: each step declares one
research goal, every claim under it states what would refute it before it is tested, and
every methodology entry is a test bound to a claim. That loop is
[`../method.md`](../method.md).

## Pages

| Document | Answers |
|---|---|
| [`architecture.md`](architecture.md) | How do the pieces fit? Data flow, seams, sharp edges, extension points. |
| [`infrastructure.md`](infrastructure.md) | How do I operate Postgres and the object store? Setup, verbs, tunnels, credentials. |
| [`data-layers.md`](data-layers.md) | What shape does the data take on the way in? Layer 0 bytes → layer 1 anchor → layer 2 typed tables. |
| [`exploration.md`](exploration.md) | How do I actually *look* at the data? Exhibits, graded checks, one interactive page. |
| [`reads-storage.md`](reads-storage.md) | Where do the raw reads go, and what can you ask of them? **Built** — 1,071,835,104 reads as queryable Parquet. |
| [`reads-api.md`](reads-api.md) | How do I query the store without a shell on the server? Every `mva-reads` verb over HTTP, long jobs handled. |
| [`viz-api.md`](viz-api.md) | How does the browser read the warehouse? Every table and read-store aggregate as JSON — `mva-viz-api`, one origin, disk-cached. |
| [`viz-app.md`](viz-app.md) | How do I *see* the data? The React app — 7 pages, 23 exhibits, 2D + 3D, runs on fixtures when the API is down. |

## Decisions

| Note | Standing |
|---|---|
| [Delivery is immutable](notes/delivery-is-immutable.md) | firm — verified 12/12 hashes |
| [Postgres for shared state](notes/postgres-for-shared-state.md) | firm; Path A deleted 2026-08-29 |
| [The chr-prefix bridge](notes/chr-prefix-bridge.md) | firm — one function, enforced by test |
| [Toolchain choice](notes/toolchain-choice.md) | provisional |

Cross-step decisions — [no patient data](../notes/no-patient-data-in-the-repository.md),
[synthetic fixtures](../notes/synthetic-fixtures.md) — stay in
[`../notes/`](../notes/); they govern every step, not this one.

## Evidence

[`methodology/`](methodology/) — entries 001–029, append-only, one per executed run. 001–006
are first contact with the delivery; 007–017 are the warehouse platform; 018–027 are the
read store and its API; 028–029 are the viz API and the React app.
