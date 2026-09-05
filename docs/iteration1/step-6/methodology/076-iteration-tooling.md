# 076 — Can iteration 1 be rebuilt from the repository alone, and can iteration 2 be opened without hand-work?

**Step:** step-6   **Hypotheses tested:** none — this entry records the **tooling step 6 needed**
(CLAUDE.md: a tool a research step needs is recorded in that step's methodology). No claim
about the patient changes; every run below is a check on the deliverable and its process.
**Written:** 2026-09-05. **Nothing uploaded** — 0 of 6 spent.

## Question

Three weaknesses the iteration-1 review found in the *structure*, not the science:

1. The only record of **which alleles** the CSV holds was `build/submission/spec.json` —
   gitignored, one laptop. Lose it and the submission cannot be rebuilt; a judge cannot see
   why any row is there without seeing coordinates.
2. Nothing checked that an iteration folder **is what its README says** — a PDF older than
   its Markdown, an unanswered methods-form row, a model number left at 1 in iteration 2.
3. Opening iteration 2 meant: bump `ITERATION` in `steps.py`, create eight step folders with
   READMEs, create the submission folder, freeze iteration 1 — all by hand, all easy to
   half-do.

## Method

| Piece | Where | Tested by |
|---|---|---|
| **Selectors.** Each allele is a predicate over a warehouse result table (`gene`, `consequence LIKE`, `is_clinvar_plp`, `gnomad_af IS NULL`, `rsid`) that must match **exactly one** row. Operators are whitelisted, identifiers validated, values bound as parameters. Zero or several matches is an error that names the count, never a position | `src/mva/warehouse/submission_spec.py`, `tools/resolve_submission_spec.py`; the committed `submissions/track1/iteration-1/spec.selectors.json` | `tests/test_warehouse_submission_spec.py` (10, in-memory DuckDB with a `pg` catalog) |
| **Folder gate.** Reads the README's declared state (draft / ready / frozen) and checks what that state promises: deliverables present, PDF and xlsx newer than their sources, form rows 7–18 answered, abstract ≤ 500 words, model number = iteration number, selectors consistent with rows and hypotheses (declared alleles, epcr strictly descending, ≤ 10 rows, no `pos` key), README sha256 matches the CSV when present, frozen folder has no uncommitted change, no `TODO`/`TBD`/`FIXME` | `tools/check_iteration.py`, wired into `tools/check-python.sh` | `tests/test_iteration_tools.py` (6) |
| **Scaffolder.** Freezes iteration *n* (dated `**Frozen:**` banner on the submission README and the docs index), writes `docs/iteration<n+1>/` (index + per-step README and methodology index, goals read from `mva.science.steps`), writes `submissions/<track>/iteration-<n+1>/` (README recording the reply, report skeleton, methods form with the model number bumped, selectors copied), bumps `ITERATION`. Refuses to overwrite; `--dry-run`; `--no-freeze` for a redesign without an upload | `tools/new_iteration.py` | `tests/test_iteration_tools.py` (2, on a throwaway git repository) |
| **Lifecycle page** with the mermaid loop and the commands in order | `submissions/README.md` | — |

## Commands

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-1/spec.selectors.json \
    --out build/submission/spec.json --check build/submission/spec.json
uv run python tools/design_submission.py --spec build/submission/spec.json --out build/submission/track1_submission_v1.csv \
    --decode-md submissions/track1/iteration-1/decode-table.md
uv run python tools/check_iteration.py
uv run python tools/new_iteration.py --track track1 --reply "partial match at rank 1, F-max 0.5" --dry-run
uv run python tools/render_track1_figures.py
tools/check-python.sh
```

## Observed

**Selectors resolve to the same seven coordinates the CSV was built from:**

```
  stop           chr15  T>G  (position withheld)
  missense       chr15  T>G  (position withheld)
  intronA        chr15  A>G  (position withheld)
  intronB        chr15  C>T  (position withheld)
  lztr1_stop     chr22  C>G  (position withheld)
  f5_leiden      chr1  C>T  (position withheld)
  flg_stop       chr1  G>A  (position withheld)
check against build/submission/spec.json: identical
wrote build/submission/spec.json  (7 alleles, 8 rows)
```

Each selector was first counted against the live tables: `coding_candidates` BUB1B
stop_gained 1, BUB1B missense 1, LZTR1 stop_gained P/LP 1, rs6025 1, FLG stop_gained P/LP 1;
`panel_candidates` BUB1B rare intronic 2, of which gnomAD-absent 1 and gnomAD-seen 1. The
designer, rerun on the resolved spec, wrote the same bytes: sha256 `fbc9e750…`, all eight
keys still agreeing with the organisers' scorer.

**Folder gate** on the real tree: `submissions/track1/iteration-1: ready — ok` (after the PDF
was re-rendered; the gate had correctly flagged it as older than `report.md` in between).

**Scaffolder dry run** for a hypothetical "partial match at rank 1" reply: 8 step READMEs,
8 methodology indexes, one docs index, four submission files and the `ITERATION` bump
planned; nothing written. The real run waits for a real reply.

**Decode-table figure:** the PNG was 2200 × 840 with the table in the upper half — the
exhibit's own height was not passed to the PNG writer. Now 2200 × 596, sized to its rows.

**Correction to the previous session's regeneration note:** `figures/track1-report.html` is
the interactive Plotly page written by `tools/render_track1_figures.py`, not a copy of the
Markdown report; a `sed` step that had briefly replaced it is removed and the page
regenerated (48 KB).

**Gates:** `tools/check-python.sh` green after formatting — see the test count in
[`current-state.md`](../../../current-state.md).

## Conclusion

Iteration 1 is reproducible from the repository plus database access, with no coordinate
committed; the folder cannot silently drift from its README; iteration 2 opens with one
command that also freezes iteration 1. The scientific content of submission v1 is untouched
(same CSV bytes, same decode table).

## Next test

The upload, when the user opens it. Then `probe-log`, `probe-link`, and
`tools/new_iteration.py --track track1 --reply '<the decode-table row>'`.
