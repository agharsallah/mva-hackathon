# Step 5 — dictionary terms, draft

**Standing:** drafted 2026-09-18 by the wave-1 *rank + report + merge* agent, against
`fixtures/it4/` only. Not merged: the one dictionary is
[`docs/dictionary.md`](../../dictionary.md) and the wave-3 *docs* agent merges these entries in
dependency order. Nothing here is a result.

Source for every entry: [`docs/iteration4/plan.md`](../plan.md) §5 (step 5),
`src/mva/zoo/report.py`, `report_stats.py`, `report_sections.py`,
`tools/render_it4_figures.py`.

Insert in the order below — each entry only uses words defined above it. They depend on
[step 4's draft](../step-4/terms.draft.md) (percentile, pair score, unscored pair).

---

**report template** — the fixed seven sections every model's report carries, in the same order,
so two models can be compared by reading the same position on two pages.
*Example: `docs/iteration4/reports/alphamissense.md` — 1 model card · 2 inputs and coverage ·
3 score distribution · 4 the confirmed pair · 5 what the clinical terms say · 6 interpretation ·
7 limitations, licence, runtime, cost (`mva.zoo.report_sections.SECTION_TITLES`).*
*Context: a comparability device, not a style choice — the template is what makes "lane A found
it, lane B did not" a one-line diff · source: src/mva/zoo/report_sections.py · related: model
card, coverage · first seen 2026-09-18*

**JSON computes, Markdown prints** — the rule the template obeys: every number is computed once
into a stored JSON document and the renderer only formats it. The renderer performs no
arithmetic at all.
*Example: `model_report_json(...)` produces the numbers and
`results.it4_model_reports.report_json` stores them; `render_model_report(json)` emits the page.
`tests/test_zoo_report.py::test_changing_a_number_in_the_json_changes_the_markdown` asserts the
direction of the dependency.*
*Context: what makes a rendered report auditable — a reader can diff the prose against the row
it came from, and a re-render is byte-identical unless a number changed · source:
src/mva/zoo/report.py · related: report template, lineage · first seen 2026-09-18*

**score distribution (stored histogram)** — the shape of one model's scores over the record set,
stored as bin edges plus counts rather than as the raw scores, so the figure and the report
describe the same distribution by construction.
*Example: 40 bins over `[0.0026, 0.9638]` with their counts, plus the quantile ladder
p01…p99, in `sections.distribution` of the report JSON.*
*Context: `mva.zoo.report_stats.distribution_json`; the figure script reads exactly these
counts, so a figure can never show a distribution the report does not state · source:
src/mva/zoo/report_stats.py · related: report template, JSON computes Markdown prints ·
first seen 2026-09-18*

**marked allele (on a histogram)** — the confirmed pair's two halves drawn as dashed lines on
the lane's score histogram, each labelled with its percentile. A half the lane could not score
is named in an on-figure note rather than omitted.
*Example: `figures/it4/score-histogram-alphamissense.svg` marks the left half at 14.0 % and
notes `not scored by this lane: right`.*
*Context: `tools/render_it4_figures.py::histogram`; the honesty rule of the figure — a missing
mark is stated, never silently absent · source: tools/render_it4_figures.py · related: score
distribution, unscored pair · first seen 2026-09-18*

**interpretation section** — section 6, the only part of a model report written in words rather
than computed. It carries a marker naming who wrote it and when.
*Example: `<!-- interpretation: hand-written 2026-09-18 | llm:none -->` above the paragraph.*
*Context: in the MVP it is hand-written and the marker reserves the slot so a later LLM run
replaces that paragraph and nothing else (plan §5 step 5, opt-A) · source:
src/mva/zoo/report.py · related: report template, LLM mode, citation check ·
first seen 2026-09-18*

**LLM mode** — which large language model, if any, writes the interpretation section: `none`
(the MVP), `claude-code` (a headless `claude -p` call) or `nebius` (open weights through
LiteLLM). The mode is a config key and is recorded on every report it touches.
*Example: `[llm] mode = "none"` in `src/mva/zoo/zoo.example.toml`, which ends up verbatim in
the section-6 marker as `llm:none`.*
*Context: plan decision D7; the mode is stored so an automated paragraph can always be told
apart from a written one · source: src/mva/zoo/zoo.example.toml · related: interpretation
section, citation check · first seen 2026-09-18*

**citation check** — the mechanical test that every sentence of an LLM-written interpretation
points at a row of sections 2–5 of the same report, rather than at the model's training memory.
*Example: plan claim `P4-7` — refuted if either LLM mode's uncited-sentence rate exceeds 10 %.*
*Context: not built in the MVP (section 6 is hand-written, so there is nothing to check yet);
named here because the marker and the section JSON are already shaped for it · source:
docs/iteration4/plan.md · related: interpretation section, LLM mode · first seen 2026-09-18*

**the clinical sentence (section 5)** — one fixed sentence in every model's report giving the
gene's rank against the child's eight HPO terms, followed by whether that model can see the
phenotype at all.
*Example: "Against the child's 8 HPO terms, `BUB1B` ranks #3 of 4812 genes considered
(phenotype score 0.87, term set `with-parental`, `warehouse.hpo_gene_scores`). `alphamissense`
scores the molecular change only and never sees the phenotype, so this line is context for the
reader, not an input to the score above."*
*Context: `mva.zoo.report_stats.hpo_sentence`; this is where the standing two-sources directive
lands in iteration 4 — a genomic result always states what the clinical terms say about it ·
source: src/mva/zoo/report_stats.py · related: HPO, clinical dataset, report template ·
first seen 2026-09-18*

**stated limitation** — section 7's list, assembled from facts the run measured rather than
written by hand: the licence, where it ran, what fraction of the record set it could score, how
many pairs it dropped, and whether it is catalogue-adjacent.
*Example: "Scored 25.0 % of the record set; the unscored remainder is this lane's blind spot and
its pairs are excluded from the ranking, not scored zero."*
*Context: `mva.zoo.report._limitations`; every artifact in this repo states its limitations next
to its result (CLAUDE.md), and here that is generated so it cannot be forgotten · source:
src/mva/zoo/report.py · related: unscored pair, catalogue-adjacent · first seen 2026-09-18*
