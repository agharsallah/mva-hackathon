# Current state — what exists, right now

**Verified:** 2026-08-29, by executed runs (`pg-check`, `s3-check`, `pytest`, live SQL
counts). Recorded in
[`methodology/015`](step-0/methodology/015-step-1-consolidation.md) and
[`methodology/016`](step-0/methodology/016-lineage-backfill-and-probe-ledger.md).

This page owns **repository and infrastructure numbers** — test counts, table counts,
object counts, what is provisioned. **Dataset measurements** (variant counts, coverage,
read counts, panel tallies) are owned by
[`ideation/data-findings.md`](../ideation/data-findings.md) and are linked, never restated.

---

## 1. The data flow

```mermaid
flowchart TB
  PUB[/"the publisher<br/>SageBio/mva-hackathon-2026-data (gated)"/]:::raw
  PUB -->|"source-fetch — streamed on the server,<br/>SHA-256 checked against the publisher"| S3[("<b>MinIO bucket <code>mva</code></b><br/>source/ · 12 objects · 84.99 GB<br/>versioning Enabled · 12/12 hash_verified")]:::good
  S3 -->|"vcf-ingest"| RAW[("<b>warehouse.variants_raw</b><br/>row count = bcftools record count")]:::good
  PROF[/"ressources/data-profile/ + ressources/reference/<br/>committable aggregates and public reference,<br/>HPO tables provenance-manifested"/]:::raw
  PROF -->|"stage → typed Parquet"| BUILD["build/warehouse/*.parquet<br/><i>gitignored, regenerable</i>"]:::neutral
  BUILD -->|"pg-ingest"| WH[("<b>schema warehouse</b><br/>19 tables")]:::good
  RAW --- WH
  WH -->|"pg-derive — DuckDB computes"| RES[("<b>schema results</b><br/>6 tables · 5 runs logged")]:::good
  S3 -.->|"byte-identical convenience mirror"| MIR["~/ubuntu/data/ · 85 GB<br/><i>local, outside git</i>"]:::neutral
  RAW -.-> LIN[("<b>warehouse.data_lineage</b><br/>7 edges · variants_raw ← s3:// + sha256 + version<br/>1 edge per derivation, appended by pg-derive")]:::good
  RES -.-> LIN
  ORACLE[/"the Track 1 oracle<br/>18 submissions, 6 per member"/]:::raw
  ORACLE -.->|"probe-log"| PROBE[("<b>warehouse.probe_ledger</b><br/>0 of 18 spent — budget intact")]:::good
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
  classDef neutral fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
```

> **Legend** — **purple = raw input** as delivered; **green = verified and live** (a live
> probe or a row count was run today); **blue = neutral, regenerable machinery** that
> holds no unique state. Solid arrows are executed pipelines;
> dotted arrows are side relationships, not steps.

### The source-of-truth chain

```
MinIO source/  →  warehouse.variants_raw  →  results.*
   bytes,           lossless all-text        derived tables,
   hash-verified,   anchor                   re-derivable
   versioned
```

Each link is re-derivable from the one before it, and nothing is edited in place. Losing
`results` costs a `pg-derive`; losing `variants_raw` costs a `vcf-ingest`; losing the
bucket costs a re-fetch from the publisher. The rule that keeps this true:
[delivery is immutable](step-0/notes/delivery-is-immutable.md).

---

## 2. What is provisioned

Postgres and MinIO both run on a **remote VPS**, not locally.

| | Value |
|---|---|
| PostgreSQL | 18.4, database `mva`, 1330 MB |
| schema `warehouse` | **27 tables**, counted live 2026-09-03 (was 19 on 2026-08-29). Two of the additions are `hpo_term_ic` and `hpo_gene_scores`, ingested 2026-09-03; the rest — including `hypotheses` and `evidence`, which the row below expected to be absent — arrived from work not recorded on this page |
| `warehouse.variants_raw` | 5,012,204 rows — **exactly** the bcftools record count in `ressources/data-profile/vcf_stats_summary.txt` ([owned by data-findings](../ideation/data-findings.md)) |
| schema `results` | 6 derived tables, 5 runs logged in `derivation_runs` |
| MinIO bucket `mva` | versioning **Enabled** |
| bucket `source/` | 12 objects, 84,985,953,378 bytes (84.99 GB) |
| hash verification | 12/12 `hash_verified=true` — 10 against the publisher's SHA-256, 2 own-upload — **0 mismatches** |
| `warehouse.source_files` | append-only ledger, 14 rows (VCF + `.tbi` uploaded twice, same hash — correct, not drift) |
| `warehouse.data_lineage` | append-only edge list, **37 rows over 29 distinct target tables** as of 2026-09-03 (a re-derived table gets a new edge, never an edit, so rows exceed targets): 2 for `variants_raw` (the original local-path edge and the superseding `s3://mva/source/…` edge carrying the verified sha256 and version), 1 per derivation, 1 per staged reference table, and 1 for the VEP annotation call. The two newest are the HPO tables, each carrying its upstream URL, release and input digest ([step-3/methodology/056](step-3/methodology/056-phenotype-ranking-without-java.md) §7b) |
| `warehouse.probe_ledger` | oracle submissions spent: **0 of 18** — the table exists and is empty because no probe has been spent. Widened in entry 017 with a `hypothesis_ids` column; the widening has **not** been applied to the live table, which is empty |
| `warehouse.hypotheses`, `warehouse.evidence` | **created 2026-09-03** on the first write: 2 hypotheses and 6 evidence rows under step-3 ([step-3/methodology/056](step-3/methodology/056-phenotype-ranking-without-java.md)). No verdict has been committed |

Both probes connect: `uv run mva-warehouse pg-check`, `uv run mva-warehouse s3-check`.

The `variants_raw` count matching bcftools independently is the cross-check that transport
and typing altered nothing — the two numbers were produced by different tools reading the
same bytes.

### Two copies that are *not* state

| | What | Why it is safe to lose |
|---|---|---|
| `~/ubuntu/data/` | byte-identical 85 GB local mirror of the delivery | convenience only; the bucket is the source of truth |
| `build/warehouse/` | staged Parquet | gitignored, regenerable in under a second, fully redundant with Postgres |

---

## 3. What runs today

```bash
uv run pytest -q                            # 448 passed, no services needed
uv run mva-explore report ressources/data-profile
uv run mva-science steps                    # the research goals, needs no database
uv run mva-science report --from docs/science-register.json
uv run mva-warehouse stage                  # profile dir -> build/warehouse/*.parquet
uv run mva-warehouse pg-check
```

| | Verbs | Notes |
|---|---|---|
| `mva-explore` | 4 — `report`, `checks`, `locus`, `export` | reads the committed profile; `locus` reads a real VCF |
| `mva-warehouse` | 26 — `stage`, `pg-*` (5), `vcf-*` (4), `s3-*` (5), `source-*` (5), `lineage-*` (3), `probe-*` (3) | measured from `mva-warehouse --help` |
| `mva-science` | 12 — `steps`, `board`, `show`, `hypothesis-*` (2), `evidence-*` (2), `verdict`, `probe-link`, `check`, `export`, `report` | measured from `mva-science --help`; `steps` and `report --from` need no database |

The **448 tests are hermetic**: synthetic fixtures only, no dataset, no Postgres, no MinIO.
A green suite says nothing about whether the infrastructure is up — that is what `pg-check`
and `s3-check` are for. 21 test files.

---

## 4. Repository layout

`src/mva/` is six subpackages:

| Package | Concern | Modules |
|---|---|---|
| `pipeline/` | the causal-variant pipeline | `variant`, `vcf`, `compound_het`, `annotation`, `ranking`, `scorer`, `submission` |
| `render/` | the shared report shell and palette | `theme`, `figure`, `report` + `report.css` |
| `explore/` | the data-profile report | `profile`, `checks`, `report`, `cli`, `views/` (callset, karyotype, locus, overview, panel, quality, reads); `theme` and `figure` are re-export shims over `render/` |
| `science/` | the research record | `steps`, `hypothesis`, `evidence`, `dossier`, `record`, `export`, `report`, `cli`, `views/` (loop, board, ledger, submission, methods) |
| `io/` | file parsing shared by all | `readers` |
| `warehouse/` | storage and infrastructure | `settings`, `catalog`, `stage`, `postgres`, `analysis`, `objects`, `source`, `integrity`, `lineage`, `probes`, `vcfstage`, `cli`, `cli_ledger`, `cli_objects`, `cli_source`, `cli_vcf` |

Dependencies run one way, and **nothing may use `science/`**:

```
render/     <-  explore/ , science/
io/         <-  explore/ , science/ , warehouse/
pipeline/   <-  explore/ , science/ , warehouse/
warehouse/  <-  science/
```

`pipeline/` uses none of them. A change to a chart can never affect a submission, and a
change to the research record can never affect the pipeline that feeds it. The map with
seam guarantees is [`step-0/architecture.md`](step-0/architecture.md).

---

## 5. Known gaps

Stated here so they are not discovered later. Sequencing is in [`roadmap.md`](roadmap.md).

| Gap | What is actually wrong | Consequence |
|---|---|---|
| **Staged Parquet is single-homed** | `build/warehouse/` exists only on one laptop | regenerable, so not data loss — but it is an undeclared dependency of `pg-ingest` |
| **Layer 2 not built** | `variants` / `genotypes` / `variant_info` are designed only | see [`data-layers.md`](step-0/data-layers.md) |
| **No real annotator** | `annotation.py` is a port with a lookup fake behind it | the critical path for ranking — see [the note](notes/annotation-as-a-port.md) |
| **The research register is empty** | no hypothesis proposed, no evidence recorded, no probe spent | not a defect — step 1 has not run. The machinery is built and tested; nothing has been claimed. See [`method.md`](method.md) |
| **`clinvar_panel` has no source digest** | its lineage edge names a ClinVar release but does not identify the bytes; the scratch VCF cannot be shown to be the download that produced the committed extract | the extract is reproducible from the release but not *provably* the same bytes. Left empty rather than guessed — see [step-3/methodology/056](step-3/methodology/056-phenotype-ranking-without-java.md) §7b |
| **The register tables are not in the database** | `warehouse.hypotheses` and `warehouse.evidence` are defined in code and covered by tests, but no connection has been made since | they appear on first write, like every other ledger. Until then `mva-science board` against a live database will create them |
