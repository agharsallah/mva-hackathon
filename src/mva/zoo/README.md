# `mva.zoo` — the model zoo

**Standing:** wave 1 landed 2026-09-18 — every module below exists, is tested against
`fixtures/it4/` and passes the Python gates. No module has run on real data yet (wave 2).

Plan: [`docs/iteration4/plan.md`](../../../docs/iteration4/plan.md). Board:
[`docs/iteration4/todo.md`](../../../docs/iteration4/todo.md).

| module | step | holds |
|---|---|---|
| `types.py` | main thread, **pinned** | `AlleleRecord`, `ScoreRow`, `Coverage`, `RemoteJob`, `Adapter` protocol, `allele_id()`, the two table DDLs (`RECORD_COLUMNS`, `ALLELE_SCORES_COLUMNS`), `MODES`, `CATALOGUE_FIELDS` |
| `record.py`, `record_hgvs.py`, `record_write.py` | step 1 | build `AlleleRecord` rows from the warehouse (`results.coding_alleles`, `warehouse.coding_annotations`, `warehouse.it2_insilico_annotations`, `warehouse.it2_read_annotations`) + a VEP HGVS pass; write `results.it4_allele_records` + `build/it4/records.parquet` + lineage row; `--mask-catalogue` |
| `registry.py`, `models.toml`, `models.d/*.toml` | step 2 | one entry per model; card JSON generator; licence manifest |
| `adapters/` | step 3 | one module per lane: `warehouse_column.py` (AlphaMissense, SpliceAI already in the warehouse), `duckdb_lookup.py` (a downloaded table, e.g. ESM1b), `vep_rest.py` (REVEL, catalogue-adjacent) |
| `cache.py` | step 3 | `warehouse.allele_scores`, append-only, no-op on same key, lineage row per run |
| `cli.py` | step 3 | `mva-zoo score --model X [--mode …] [--records …]`; `mva-zoo run` (wired by *rank+report+merge*) |
| `pairs.py`, `rank.py` | step 4 | pair score = `(min, max)` of the two allele scores over `compound_het` pairs; the confirmed pair's rank and percentile per model |
| `merge.py`, `merge_render.py` | step 6 | agreement matrix (Spearman), RRF with/without catalogue-adjacent lanes, disagreement table |
| `report.py`, `report_stats.py`, `report_sections.py` | step 5 | the seven-section template per model rendered from JSON; §6 marked as the LLM slot |
| `workflow.py`, `workflow_types.py`, `workflow_stages.py`, `zoo.example.toml` | step 4 | stages as idempotent functions, run manifest |
| `narrate.py` | opt-A, not yet | LLM interpretation, two modes |

Layering: imports `mva.io`, `mva.pipeline`, `mva.warehouse` only; imported only by `mva.viz`.
Every module ≤ 400 lines. Patient coordinates and sequence windows live only under
`build/it4/`; `allele_id` is the only key that leaves.
