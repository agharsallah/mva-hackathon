# `mva.zoo` — the model zoo

**Standing:** re-checked 2026-09-19 against source. Every module below exists, is tested
against `fixtures/it4/` and passes the Python gates; **the whole package has run on the real
callset** — R1-R6, 2026-09-18/19, entries 114-130. Wave 3 added the `[case]` config: the gene, the
docs folder, the table prefix and the clinical term set are configuration, not constants —
what still spells `it4` is inventoried in the decision note below.

Plan: [`docs/iteration4/plan.md`](../../../docs/iteration4/plan.md). Board:
[`docs/iteration4/todo.md`](../../../docs/iteration4/todo.md). Results:
[`docs/iteration4/README.md`](../../../docs/iteration4/README.md). Running it on another case:
[`docs/iteration4/reusability.md`](../../../docs/iteration4/reusability.md).

| module | step | holds |
|---|---|---|
| `case_config.py`, `zoo.example.toml`, `cases/` | wave 3 | `Config` — the `[case]` block (label, iteration, table prefix, confirmed gene + rule, phenotype term set, HPO table) and the `[run]`/`[merge]`/`[llm]`/`[paths]` blocks; path defaults derived from `iteration`; `cases/` holds one TOML per illness. Decision: [`docs/notes/zoo-case-config.md`](../../../docs/notes/zoo-case-config.md) |
| `types.py` | main thread, **pinned** | `AlleleRecord`, `ScoreRow`, `Coverage`, `RemoteJob`, `Adapter` protocol, `allele_id()`, the two table DDLs (`RECORD_COLUMNS`, `ALLELE_SCORES_COLUMNS`), `MODES`, `CATALOGUE_FIELDS` |
| `record.py`, `record_hgvs.py`, `record_write.py` | step 1 | build `AlleleRecord` rows from the warehouse (`results.coding_alleles`, `warehouse.coding_annotations`, `warehouse.it2_insilico_annotations`, `warehouse.it2_read_annotations`) + a VEP HGVS pass; write `results.it4_allele_records` + `build/it4/records.parquet` + lineage row; `--mask-catalogue` |
| `registry.py`, `models.toml`, `models.d/*.toml` | step 2 | one entry per model; card JSON generator; licence manifest |
| `adapters/` | step 3 | one module per lane: `warehouse_column.py` (AlphaMissense, SpliceAI already in the warehouse), `duckdb_lookup.py` (a downloaded table, e.g. ESM1b), `vep_rest.py` (REVEL, catalogue-adjacent) |
| `cache.py` | step 3 | `warehouse.allele_scores`, append-only, no-op on same key, lineage row per run |
| `cli.py` | step 3 | `mva-zoo records|models|coverage|score|scores|narrate [--config <case.toml>]`; `mva-zoo run --config X [--from stage] [--force] [--case-gene G] [--iteration I]` |
| `pairs.py`, `rank.py` | step 4 | pair score = `(min, max)` of the two allele scores over `compound_het` pairs; the confirmed pair's rank and percentile per model |
| `merge.py`, `merge_render.py` | step 6 | agreement matrix (Spearman), RRF with/without catalogue-adjacent lanes, disagreement table |
| `report.py`, `report_stats.py`, `report_sections.py` | step 5 | the seven-section template per model rendered from JSON; §6 marked as the LLM slot; the report JSON carries its `case` and its `reports_table` (`schema_version` 2) |
| `tables.py` | step 2 | a published per-protein score *matrix* (one file per protein, positions as columns) unpivoted into the one long `(accession, change, score)` table a lookup lane joins — a leaf, written in Python because one DuckDB `UNPIVOT` per member measured at ~1,000 per 10 min (entry 119) |
| `adapters/protein_table.py` | step 3 | the lane that joins that table, through the gene-symbol bridge |
| `workflow.py`, `workflow_types.py`, `workflow_stages.py` | step 4 | stages as idempotent functions, the injected `Deps` bundle (warehouse or fixtures, plus its cheap per-stage source `fingerprint`), the run manifest; the run id is the config's sha256 |
| `checkpoint.py`, `checkpoint_state.py` | step 4, opt-A | the resume: one marker per stage (and one per fan-out lane) under `<out_dir>/checkpoints/<run_id>/`, matched on a **content** chain seeded with the effective config; `--from` re-runs from a stage, `--force` drops the markers. Claim `P4-5`, kill test `tests/test_zoo_resume.py` |
| `narrate.py` | step 5, opt-A | LLM interpretation, two modes |

Layering: imports `mva.io`, `mva.pipeline`, `mva.warehouse` only; imported only by `mva.viz`.
Every module ≤ 400 lines (`uv run python tools/check_module_size.py`). Patient coordinates and
sequence windows live only under the case's `build/<prefix>/`; `allele_id` is the only key that
leaves.

**The gene, the disease and the docs folder are not written into this package.** They are the
`[case]` block of the run config; `tests/test_zoo_case_config.py` runs the eight stages on a
second case to prove it. What the case block does *not* reach yet is listed in
[`docs/notes/zoo-case-config.md`](../../../docs/notes/zoo-case-config.md).
