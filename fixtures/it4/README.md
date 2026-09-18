# `fixtures/it4/` — synthetic zoo fixtures

**Standing:** written 2026-09-18 by `tools/make_it4_fixtures.py` (seed 4); regenerate with
`uv run python tools/make_it4_fixtures.py`. **No patient data**: every position is on
chromosome 1 below 1,000,000, every allele, gene name and score is invented. Same rule as
[`../../tests/fixtures/README.md`](../../tests/fixtures/README.md).

| file | rows | shape | used by |
|---|---|---|---|
| `records.tsv` | 200 | `AlleleRecord` fields + the coordinate columns the real `build/it4/records.parquet` carries | every wave-1 agent |
| `scores/<lane>.tsv` | 50 each | `allele_id, model, version, score` — one per MVP lane (alphamissense, esm1b, spliceai, revel) | cache + adapters, rank, merge |
| `pairs.tsv` | 20 | `gene, allele_id_left, allele_id_right, phase, is_confirmed` — one pair flagged confirmed | rank, report, merge |

Column contracts are `src/mva/zoo/types.py`. Ten synthetic genes (`GENEA`–`GENEJ`), five
consequence classes weighted like a real coding callset, every 40th record `is_read_only`.
