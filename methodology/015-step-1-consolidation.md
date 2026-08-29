# 015 — Is the repository coherent enough to build phase 2 on?

## Question

Before starting phase 2 (layer 2, the annotator, the FASTQ path), take a checkpoint: is the
data actually under verified control, does the code match what the docs claim, and is the
documentation trustworthy enough to build on?

## Finding first

Yes, with five gaps left deliberately open. The delivery is in object storage with
**12/12 objects hash-verified against the publisher and 0 mismatches**; the ingested
callset's row count **matches the independent bcftools record count exactly**; the test
suite passes hermetically at **285 tests**. The documentation was consolidated: one index,
one owner per number, one note per decision, and an `archive/` for what the work has moved
past.

## Inputs

Three audits run 2026-08-29 against this repository at commit `80fcc41`:

1. **Docs audit** — every markdown file outside `.venv`, read for stale claims, duplicated
   numbers and missing owners.
2. **Code audit** — `src/mva/` against what the docs describe.
3. **Live infrastructure audit** — the remote VPS, probed rather than assumed.

Environment: the project venv (`uv`, Python 3.13); `mva-warehouse` and `mva-explore` from
`src/`; PostgreSQL 18.4 and MinIO on the remote VPS.

## What was verified live

| Command | Observed |
|---|---|
| `uv run mva-warehouse pg-check` | connects; PostgreSQL 18.4, database `mva`, 1330 MB |
| `uv run mva-warehouse s3-check` | connects; bucket `mva`, versioning **Enabled** |
| row count on `warehouse.variants_raw` | **5,012,204** |
| the same number in `ressources/data-profile/vcf_stats_summary.txt` (bcftools) | **5,012,204** — identical |
| object survey under `source/` | **12 objects, 84,985,953,378 bytes (84.99 GB)** |
| hash verification | **12/12 `hash_verified=true`** — 10 against the publisher's SHA-256, 2 own-upload — **0 mismatches** |
| `warehouse.source_files` | 14 rows for 12 objects; the VCF and its `.tbi` appear twice with the **same hash** |
| schema counts | `warehouse` 18 tables; `results` 6 tables, 5 runs in `derivation_runs` |
| `uv run pytest -q` | **285 passed**, 3.7 s, no services needed |
| `uv run mva-warehouse --help` | **27** verbs |
| `uv run mva-explore --help` | **4** verbs |

The row-count agreement is the load-bearing check. bcftools counted records in the
compressed VCF; Postgres counted rows after an independent transport and load. Two tools,
two paths, same number — so neither transport nor typing lost or duplicated a record.

The ledger having 14 rows for 12 objects is **correct, not drift**: `source_files` is
append-only, so a file uploaded twice produces two events. Both rows carry the same hash,
which is what makes them a re-upload rather than a change.

## What was changed

### Code (landed before this entry)

| Change | Why |
|---|---|
| Fixed a shadowed duplicate `do_fetch` in `cli_source.py` | the second definition shadowed the streaming implementation, so `--tee` and `--verify` were silently dead. `source-fetch` is now the streaming implementation and both flags work |
| `explore/readers.py` → `io/readers.py` | it parses file shapes and knows nothing about charts; `warehouse/` needs it too |
| Seven modules → `pipeline/` | `variant`, `vcf`, `compound_het`, `annotation`, `ranking`, `scorer`, `submission` moved off the package top level, leaving four bounded subpackages: `pipeline/`, `explore/`, `io/`, `warehouse/` |
| New settings keys in `.env.example` | `MVA_SOURCE_DIR`, `MVA_STAGING_DIR`, `MVA_HF_REPO` |
| Tests **209 → 285** | the moves and the fix came with coverage |

### Documentation (this pass)

| Change | Result |
|---|---|
| Created `docs/current-state.md` | the missing anchor page: what is provisioned, what runs, the layout, the gaps. Owns repo and infra numbers |
| Created `archive/` | `draft0.md`, `draft0-answers.md`, `data-inventory.md`, `ingestion-plan.md`, `hackathon-intel.md` §12, and the DuckDB-file warehouse doc, each with a banner naming its successor |
| Split `docs/warehouse.md` (434 lines, three topics) | rationale → `archive/duckdb-file-warehouse.md`; the live runbook → `docs/infrastructure.md`; the file deleted |
| Extracted live content before archiving | challenge documents → `ressources/hackathon-rules/README.md`; the §0.1 matrix → `docs/decisions.md`; §12.2 still-open → `docs/roadmap.md`; the layer-2 schema → `docs/data-layers.md` |
| Created `docs/decisions.md` + three new notes | `postgres-for-shared-state`, `delivery-is-immutable`, `chr-prefix-bridge` — the last had been restated in five places with no owner |
| Deduplicated measured numbers | dataset numbers now have one owner (`ideation/data-findings.md`) and are linked elsewhere; the audit had found some restated in up to 11 files |
| Rewrote `README.md` and `docs/README.md` | front door and single index; deleted a stale layout tree (wrong view names, missing eight warehouse modules) and a hardcoded test count |
| Added `Standing:` / `Verified:` lines | every live doc outside `methodology/` and `archive/` |
| Deleted `ideation/draft-0.1-data-structure.md` and `image.png` | a generic essay about a different system; `grep` confirmed the image was referenced only by that file |

No `.py` file, test, or `.env*` was touched in the documentation pass. `pytest` was re-run
afterwards and still reports 285 passed.

## Gaps deliberately left open

Recorded rather than fixed, so phase 2 starts from a known position.

| Gap | State |
|---|---|
| **Lineage** | `warehouse.data_lineage` holds **1 row**, pointing at a *local* path, with an **empty sha256**, and no edges for the 5 derivations. "Which bytes produced this result" is not answerable from the database |
| **Staged Parquet** | single-homed in local `build/warehouse/`. Regenerable, so not data loss, but an undeclared dependency of `pg-ingest` |
| **Path A** | the DuckDB-file-over-SSH verbs are superseded but still in the CLI; `stage.py` is still live because `pg-ingest` consumes its Parquet. Retirement is an open decision |
| **Probe ledger** | nothing records which oracle submission was spent, by whom, with what content. The budget is 18 |

## Conclusion

**Step-1 checkpoint passed: the data is under verified control and the documentation is
consolidated.** The chain from delivered bytes to derived results is hash-verified at the
source, row-count-verified at the ingest, and re-derivable at every hop; the code matches
what the docs now say about it. Phase 2 can be built on this.

The five gaps above are the honest cost of that conclusion. None blocks phase 2, and two —
the lineage edges and the probe ledger — must close before the final report, because both
are things the report will need to claim.

Sequencing for the phase-2 work: [`docs/roadmap.md`](../docs/roadmap.md) §2.
