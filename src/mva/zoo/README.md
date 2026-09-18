# `mva.zoo` — the model zoo

**Standing:** package opened 2026-09-18 (iteration 4, wave 0). Only `types.py` is pinned;
every other module is being built against `fixtures/it4/` by a wave-1 agent and is listed
here as its contract, not as delivered code. Re-verify this table when wave 1 lands.

Plan: [`docs/iteration4/plan.md`](../../../docs/iteration4/plan.md). Board:
[`docs/iteration4/todo.md`](../../../docs/iteration4/todo.md).

| module | owner (wave 1) | holds |
|---|---|---|
| `types.py` | main thread, **pinned** | `AlleleRecord`, `ScoreRow`, `Coverage`, `RemoteJob`, `Adapter` protocol, `allele_id()`, the two table DDLs (`RECORD_COLUMNS`, `ALLELE_SCORES_COLUMNS`), `MODES`, `CATALOGUE_FIELDS` |
| `record.py` | agent *record* | build `AlleleRecord` rows from the warehouse (`results.coding_alleles`, `warehouse.coding_annotations`, `warehouse.it2_insilico_annotations`, `warehouse.it2_read_annotations`) + a VEP HGVS pass; write `results.it4_allele_records` + `build/it4/records.parquet` + lineage row; `--mask-catalogue` |
| `registry.py`, `models.toml`, `models.d/*.toml` | agent *registry* | one entry per model; card JSON generator; licence manifest |
| `adapters/` | agent *cache+adapters* | one module per lane: `warehouse_column.py` (AlphaMissense, SpliceAI already in the warehouse), `duckdb_lookup.py` (a downloaded table, e.g. ESM1b), `vep_rest.py` (REVEL, catalogue-adjacent) |
| `cache.py` | agent *cache+adapters* | `warehouse.allele_scores`, append-only, no-op on same key, lineage row per run |
| `cli.py` | agent *cache+adapters* | `mva-zoo score --model X [--mode …] [--records …]`; `mva-zoo run` (wired by *rank+report+merge*) |
| `rank.py` | agent *rank+report+merge* | pair score = `(min, max)` of the two allele scores over `compound_het` pairs; the confirmed pair's rank and percentile per model |
| `merge.py` | agent *rank+report+merge* | agreement matrix (Spearman), RRF with/without catalogue-adjacent lanes, disagreement table |
| `report.py` | agent *rank+report+merge* | the seven-section template per model rendered from JSON; §6 marked as the LLM slot |
| `workflow.py` | agent *rank+report+merge* | stages as idempotent functions, run manifest |
| `narrate.py` | opt-A, not yet | LLM interpretation, two modes |

Layering: imports `mva.io`, `mva.pipeline`, `mva.warehouse` only; imported only by `mva.viz`.
Every module ≤ 400 lines. Patient coordinates and sequence windows live only under
`build/it4/`; `allele_id` is the only key that leaves.
