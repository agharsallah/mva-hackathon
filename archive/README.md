# Archive — superseded documents, kept for provenance

These files are **not current**. They record what was thought at the time, which is why
they are kept: a decision only makes sense against the reasoning it replaced.

Rules, from [`CLAUDE.md`](../CLAUDE.md):

- Never edited, apart from the one-line banner at the top saying what superseded them.
- Never cited as current. Numbers here may be wrong, and several are.
- Never deleted.

Current documentation lives in [`docs/`](../docs/) — start at
[`docs/README.md`](../docs/README.md). Measured facts live in
[`ideation/data-findings.md`](../ideation/data-findings.md).

| File | What it was | Superseded by |
|---|---|---|
| [`draft0.md`](draft0.md) | the first eleven open questions, before any data was opened | [`archive/draft0-answers.md`](draft0-answers.md), then the live docs |
| [`draft0-answers.md`](draft0-answers.md) | 1,400-line answer sweep across all eleven questions | [`docs/decisions.md`](../docs/decisions.md) (§0.1 matrix), [`docs/roadmap.md`](../docs/roadmap.md) (§12.2 still-open) |
| [`data-inventory.md`](data-inventory.md) | asset register written *before* the files were opened | [`ressources/hackathon-rules/README.md`](../ressources/hackathon-rules/README.md) (bucket A), [`ideation/data-findings.md`](../ideation/data-findings.md) (bucket B, measured) |
| [`ingestion-plan.md`](ingestion-plan.md) | ingestion proposal, "awaiting review, nothing ingested" | [`docs/data-layers.md`](../docs/data-layers.md); layers 0–1 are now live |
| [`hackathon-intel-exploration.md`](hackathon-intel-exploration.md) | §12 of the intelligence brief: the exploration plan | [`methodology/001`–`006`](../methodology/), which executed it |
| [`duckdb-file-warehouse.md`](duckdb-file-warehouse.md) | the embedded-DuckDB file-on-a-box warehouse | [`docs/infrastructure.md`](../docs/infrastructure.md) (Postgres + MinIO) |

Two files were **deleted** rather than archived, because they contained no project content:
`ideation/draft-0.1-data-structure.md` (a generic pangenome-infrastructure essay about a
different system, referencing an unreferenced `image.png`) and that `image.png`.
