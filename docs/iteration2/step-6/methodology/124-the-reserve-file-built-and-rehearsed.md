# 124 — The reserve file: submission 2 built, rehearsed, and not uploaded

**Written:** 2026-09-19. **Step:** `step-6` (iteration 2).
**Hypotheses:** **H044** — re-tested on the built file; one evidence row added.

**Supersedes nothing.** [109](109-what-the-mirror-found.md) computed the expected information
gain of a second upload from the *plan* of a file; this entry builds the file the organisers
would receive, grades it byte-for-byte with two scorers, and reads its decode table. It is
the step's hand-over to `submissions/track1/iteration-2/`.

## Hypothesis and prediction

- **H044** — a second Track 1 upload is not informative. *Predicted:* the built file's decode
  table has one row, the prior entropy is 0 bits and the expected information gain is 0 bits;
  both scorers return full match at rank 1, 100 rank points, F-max 1.0 for the only key.

## What would refute it

- A decode table with more than one row, or an expected information gain above 0 bits. Either
  would mean a live hypothesis the file could still separate, and the plan's §6 rule would then
  make the upload worth spending.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| derived | `results.coding_candidates` — five selectors (two `BUB1B` alleles, `LZTR1`, `F5`, `FLG`) | `submissions/track1/iteration-2/spec.selectors.json` |
| register | H009's suggested confidence, 0.9993, as the rank-1 epcr | `docs/science-register.json` |
| clinical | the eight HPO terms — through step 1's target set, which the fused ranking read | [084](../../step-1/methodology/084-the-blind-target-set.md) |
| organisers | `evaluation.py`, the published scorer, for the cross-check | `ressources/hackathon-rules/rare-diseas-repo/evaluation.py` |

The alternative pairings iteration 1 carried at ranks 2–5 (the two rare intronic `BUB1B`
alleles) are **not** in this file: the reply to submission 1 eliminated them
([083](../../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)). The three
secondary rows keep iteration 1's rule (ClinVar P/LP, gnomAD < 0.02, dominant or
risk-factor genes) — they are free under the scorer and are the qualitative-review content.

## Commands

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-2/spec.selectors.json --out build/submission/spec.json --record-lineage
uv run python tools/design_submission.py --spec build/submission/spec.json \
    --out build/submission/agharsallah_bub1b-comphet-replication.csv \
    --decode-md submissions/track1/iteration-2/decode-table.md
shasum -a 256 build/submission/agharsallah_bub1b-comphet-replication.csv
```

## Observed

- 5 alleles resolved, each to exactly one row; 4 rows written (1 primary pair, 3 secondary);
  1,814 bytes, LF, template header, `PROBAND01`.
- epcr ladder, derived: rank 1 **0.9993** (H009's suggested confidence); secondaries 0.4996,
  0.02498, 0.01499 — every value strictly descending, none typed. `derivation.md` prints the arithmetic.
- rehearsal, our replica: `rank_points 100.0 · f_max 1.0 · threshold 0.9993 · full_match_rank 1`.
- cross-check, organisers' `evaluation.py`: **agree** on every exposed field.
- decode table: **one row** — survivors `stop+missense`, prior mass 1.00.
- prior entropy **0.000 bits**, expected posterior **0.000 bits**, expected information gain
  **0.000 bits** (the tool prints `-0.000`, a floating-point sign on zero).
- sha256 `325205a8abdf53d0dca12080cf29633b27d882316517bc8a4620da0b7afab359`.
- lineage: 3 edges appended to `warehouse.data_lineage` (`target_schema = submissions`), for
  the selector table, the selector file by digest and the clinical document by digest.

## Assumptions, limitations and quality checks

- The hypothesis space is a single point *because the oracle said so*; this file cannot test
  the pair again, only re-score it. That is the content of H044, now measured on real bytes.
- A prior of 1.00 on the anchor is the register's arithmetic taken to its end (seven supporting
  rows including the oracle reply, none refuting). It is still a triage heuristic, and the
  epcr inherits the caveat.
- Secondary rows below the hit cannot lower F-max and earn no points; they are here for the
  qualitative review, chosen by a stated rule, and their facts are quoted from the table.
- The folder gate (`tools/check_iteration.py`) and the coordinate gate run on the result; the
  CSV stays under `build/` and is never committed.

## Verdict

**H044 — supported, unchanged (0.90).** The file that would be uploaded teaches nothing:
one decode row, 0.000 bits. Built and rehearsed so the reserve is real, **not uploaded**;
5 of 6 slots remain. The timing of any upload is the user's call.
