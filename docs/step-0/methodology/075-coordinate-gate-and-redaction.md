# 075 — Does the tree hold a patient coordinate, and does the rehearsal survive the organisers' own scorer?

**A step-0 platform entry (cross-step fix), so it carries no hypothesis.** Named for step 6
(the submission) and for every step that writes a doc. **Written:** 2026-09-05, from the runs
quoted below. Step 0 closed at 068; this entry is the kind of cross-step fix
[`CLAUDE.md`](../../../CLAUDE.md) still routes here.

## Question

Two checks the iteration-1 review asked for and nothing in the repository performed:

1. The rules say no patient genomic position may appear outside `build/`. `mva-science
   check` enforces it for the register; nothing scanned the docs, the tests or the tools. Is
   the tree clean?
2. The rehearsal in [074](../../iteration1/step-6/methodology/074-submission-v1-design.md)
   graded the CSV with `mva.pipeline.scorer`, our transcription of the published
   `evaluation.py`. A transcription proves it agrees with itself. Does the organisers' own
   code, run on the same bytes, return the same five numbers for every answer key?

## Method

- `tools/check_coordinates.py` — three rules over every tracked or untracked-but-not-ignored
  text file: a Track-1 CSV data row with a 7+-digit position; any position named in the
  gitignored `build/submission/spec.json` (when present); any 8-digit number strictly inside
  the candidate gene's public span when it stands beside its chromosome. Public reference
  tables (`ressources/`), `archive/` and SVGs are skipped; synthetic examples are listed with
  a reason in `tools/coordinate_allowlist.txt`. Wired into `tools/check-python.sh` before
  pytest. Tests: `tests/test_check_coordinates.py` (10, one of which scans the real tree).
- `mva.pipeline.scorer_reference` — loads the organisers' `evaluation.py` by path
  (`ressources/hackathon-rules/rare-diseas-repo/`), grades a written CSV with
  `load_submission` + `score_proband`, and compares the five exposed fields to the replica.
  `tools/design_submission.py` runs it after every build and exits non-zero on a
  disagreement. Tests: `tests/test_scorer_reference.py` (7, hand-derived expectations).

## Commands

```bash
uv run python tools/check_coordinates.py                 # first run: 11 findings; after triage and redaction: clean
uv run mva-warehouse pg-query "SELECT pos FROM pg.warehouse.variants_raw WHERE chrom='15' AND pos IN (<the 6 allowlisted test/example positions>)"
uv run python tools/design_submission.py --spec build/submission/spec.json \
    --out build/submission/track1_submission_v1.csv --decode-md submissions/track1/iteration-1/decode-table.md
uv run pytest -q tests/test_check_coordinates.py tests/test_scorer_reference.py
tools/check-python.sh
```

## Observed

**Coordinate gate, first run** (spec present, so rule 2 was live):

| Finding | Files | Triage |
|---|---|---|
| **both candidate positions, verbatim** | `docs/step-0/methodology/050-pair-comparator.md` lines 142 (a pasted CSV row) and 148 (the staged pair) | **a real leak**, committed 2026-09-03 and pushed to the private `origin/main`. Redacted in the working tree to `<pos-1>` / `<pos-2>` with a dated banner at the top of 050 naming this entry. The append-only rule yields to the no-coordinates rule; nothing else in 050 changed. **Git history still holds the bytes** — rewriting it is the user's decision |
| public gene-model coordinates | `060` (BUB1B and PAK6 spans from Ensembl), reference TSVs | allowlisted / `ressources/` skipped |
| synthetic positions | `040` (two VEP REST example alleles), `tests/` fixtures, `CONTRIBUTING.md`, `017` | verified **0 rows** in `warehouse.variants_raw` for every one of them, then allowlisted with the reason |

Second run: `coordinate gate: clean`. The gate now runs in `tools/check-python.sh`.

**Cross-check against the organisers' scorer**, same CSV bytes (sha256 `fbc9e750…`,
unchanged by the rebuild):

```
cross-check against the organisers' scorer (ressources/hackathon-rules/rare-diseas-repo/evaluation.py):
  stop+missense                agree
  stop+intronA                 agree
  stop+intronB                 agree
  missense+intronA             agree
  missense+intronB             agree
  stop+unseen                  agree
  missense+unseen              agree
  neither (other gene)         agree
```

All eight keys: identical `full_match_rank`, `partial_match_rank`, `rank_points`, `f_max`,
`f_max_threshold`. The decode table and the 1.455-bit expected gain of 074 are therefore
properties of the published scorer, not of our transcription. One hand-derived expectation
in the new test was wrong on first writing — a key whose partner sits in the secondary row
peaks F-max at 0.667 once that row is admitted, not at 0.5 — and the organisers' code
corrected the author, which is the point of the check.

**Review corrections landed with this entry** (no run changed a result):

- Report §6 said the two alleles are "9 exons apart"; VEP places them in exons 17/23 and
  23/23 of the MANE transcript — six exons apart. Corrected in the report; evidence row 25
  (append-only) is superseded by a new neutral row citing this entry.
- Methods form Q7 carried a note-to-self in the team-name field; now the username only.
- `CLAUDE.md`, `roadmap.md`, `docs/README.md`, `current-state.md` and `toolset.md` still
  described steps 1–4 as unrun and the docs layout as `docs/step-<n>/`; refreshed to the
  `docs/<iteration>/step-<n>/` layout and the 2026-09-05 statuses.

**Gates:** `tools/check-python.sh` green — ruff, module size, layering, mypy, coordinate gate,
1,668 tests (1,650 before this entry).

## Conclusion

The tree is coordinate-free and now stays so mechanically. The rehearsal that gates the
first upload is confirmed by the organisers' own code on every key in the hypothesis space.
Open: whether to rewrite `origin/main` history for the two positions in 050's past
revisions — the repository is private today; it becomes a judged artifact when its URL is
submitted.
