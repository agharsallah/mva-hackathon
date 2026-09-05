# `mva.report` — the Track-1 report's figures, from aggregates only

**Standing:** 2026-09-05 — first version, built for the Track-1 submission report
([`submissions/track1/iteration-1/report.md`](../../../submissions/track1/iteration-1/report.md)).

The report needs figures that read the *results* of the pipeline — the filtering funnel,
the genome-wide gene table against the phenotype ranking, the decode table of the
submission — and every one of them must be committable. So this package reads **counts and
per-gene rows** from the warehouse's result schema, never a coordinate, and hands them to
the shared exhibit unit in [`mva.render`](../render/README.md).

| Module | Holds |
|---|---|
| `data.py` | The three queries: funnel counts, `gene_biallelic` rows (gene names and counts, no positions), and the decode table built from a submission spec through `mva.pipeline.probe_design`. |
| `figures.py` | One `Exhibit` per figure, each with its caption and `**Legend**` line, in the repository palette. |

Entry point: `uv run python tools/render_track1_figures.py` writes
`figures/track1/*.png` (static, for the Markdown report) and `figures/track1-report.html`
(interactive, one page). Layering: imports `render`, `pipeline` and `warehouse`; nothing
imports it except the tool.
