# 017 — Can the investigation itself be made machine-readable?

## Question

The log up to entry 016 records *what was built* and *what was measured*. It records nothing
about what is **believed**: no claim stated before a test, no statement of what would refute
one, no verdict, no confidence, and no link from a finding to a submission row.

Can the investigation be recorded in tables — so the report and the submission rows are
*generated from* the record rather than transcribed out of it by hand?

This is the last platform entry. It builds machinery, so it belongs to step 0; every entry
from 018 is a test bound to a hypothesis under a research goal.

## Finding first

**Yes, in three append-only tables and one shared renderer.** The register is
`warehouse.hypotheses` and `warehouse.evidence`; `warehouse.probe_ledger` gains one column
tying a spent submission to the claims it tested. `mva-science` is the CLI over them,
`docs/science-register.json` is the committed mirror, and `figures/science-report.html` is
generated from either.

Three rules moved out of a template and into constructors, because a template is advice and
a constructor is a gate:

| Refused at construction | Verified by |
|---|---|
| a hypothesis with no `refuted_by` | `tests/test_science_register.py::test_a_claim_missing_a_required_sentence_is_rejected` |
| an observation with no `source_ref` | `::test_an_observation_with_no_source_is_rejected` |
| a confidence with no stated reason | `::test_a_revision_with_no_reasoning_is_rejected` |

## Inputs

- The existing ledger conventions in `src/mva/warehouse/{probes,lineage,source}.py` —
  `ensure_*(connection, schema)`, three-part `{ALIAS}.{schema}.{table}` names,
  `CREATE TABLE IF NOT EXISTS` over the DDL subset DuckDB and PostgreSQL share, positional
  `?` inserts in DDL column order.
- The renderer in what was `src/mva/explore/{figure,theme,report}.py`.
- The step sequencing in `docs/roadmap.md` §1, transcribed into `src/mva/science/steps.py`.
- The methods-form question numbers transcribed in `ideation/hackathon-intel.md` §9.5.
- No dataset and no database: everything below runs against synthetic fixtures.

## Design decisions, and why

**Steps are code, not rows.** They are few, they change rarely, and a reviewer should see
the whole map in a diff — the same reasoning that puts `analysis.DERIVATIONS` in a module.
Hypotheses and evidence accumulate at runtime and belong in the warehouse; the map they
hang off does not.

**Step 0 takes no hypotheses.** "PostgreSQL is the right database" is a decision with
alternatives, judged by whether it works — not a claim about the patient that evidence can
refute. `Hypothesis.__post_init__` rejects a claim filed under a platform step, so the
distinction is enforced rather than described.

**Revisions, not updates.** Believing something less strongly than last week is a fact about
the investigation. A verdict is a new revision; the tables never emit `UPDATE` or `DELETE`,
asserted by `::test_the_register_never_updates_or_deletes`.

**The weighing suggests and never writes.** `mva-science verdict` accumulates evidence in
log-odds and prints every term; committing takes `--commit` and `--reasoning`. A tool that
silently recorded the number it computed would make every confidence in the register the
tool's opinion rather than a human's. It is a transparent heuristic for triage, **not a
calibrated posterior** — the strengths are human judgments and rows drawn from the same
underlying data are not independent the way the sum treats them. That caveat is printed in
the export, the report, and `docs/method.md`.

**The export refuses coordinates.** The register is the surface where the data transfer
agreement gets broken by accident: writing "chr15:40142000 A>G is causal" as a hypothesis
statement is the natural thing to type, and that sentence is patient data. `export.scan`
reports every leak at once and `export.write` refuses — being told about one leak six times
is how people start deleting the check.

**The renderer was extracted, not copied.** `figure.py`, `theme.py`, `report.css` and
`render()` were already subject-agnostic. They moved to `src/mva/render/`, and
`mva.explore.figure` / `mva.explore.theme` stay as re-export shims so no existing import
path changed.

**The ranking arithmetic is now kept.** `rank_pairs` computed rarity, severity and the gene
prior and discarded the components, which made "why is this pair at rank 1" a question you
answered by re-reading the code. `RankedPair` gained an optional `PairEvidence`; the field
is defaulted, so no existing caller changed.

## Exact commands run

```bash
uv run pytest -q
uv run ruff check src/mva/science src/mva/render tests/test_science_*.py
uv run mva-science steps
uv run mva-explore report ressources/data-profile \
    --title "MVA proband — callset exploration" -o /tmp/after.html
diff <(grep -v 'generated 20' figures/explore-report.html) \
     <(grep -v 'generated 20' /tmp/after.html)
uv run python -c "from mva.science.export import write; print(write([], 'docs'))"
```

## Observed

```
448 passed in 1.81s
All checks passed!
```

| | Before | After |
|---|---|---|
| tests | 305 | **448** |
| test files | 17 | 21 |
| `src/mva` subpackages | 4 | **6** (`render/`, `science/` added) |
| CLI entry points | 2 | **3** (`mva-science`) |
| append-only warehouse tables | 3 | **5** (`hypotheses`, `evidence`) |

The `diff` of the regenerated data-profile report against the committed one produced no
output: **the renderer extraction changed no existing output byte**. The empty register
exports to `docs/step-1/hypotheses/README.md` and `docs/science-register.json`, and renders
to a 29 KB page that says the register is empty rather than rendering blank.

The test count rose by 143, of which 33 are the parametrised source-file walk in
`test_cli_parsers.py` growing with the new modules, and the rest are the four new
`test_science_*.py` files.

One pre-existing test helper was fixed: `_minimal_argv` fed the placeholder `"x"` to every
required flag, which no argument declaring `choices` accepts. It now picks the first valid
choice, so the walk can reach verbs that constrain their flags.

## Conclusions

1. **The investigation is now recordable in the same way the data is.** Provenance answers
   *where did this byte come from*; the register answers *what do we believe, how strongly,
   and on what basis*. Both are append-only, both are queryable, and the report is a
   rendering of them rather than a document someone maintains.
2. **The register is empty, and that is the honest state.** No hypothesis has been proposed
   and no evidence recorded, because step 1 has not run. The report says so explicitly
   rather than rendering a blank page.
3. **The submission is now traceable in both directions.** `dossier.to_row` stamps the
   hypothesis id into `Row.notes`; `dossier.hypothesis_of` reads it back. A row the scorer
   sees can be traced to the claim behind it without a side table.
4. **Nothing here is a scientific result.** This entry records machinery only. The first
   claim about the patient will be entry 018, under `step-1`.
