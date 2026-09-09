# Step 6 — Spend the oracle budget

**Standing:** submission v1 designed and rehearsed 2026-09-05 ([074](methodology/074-submission-v1-design.md)), its rows re-derived from data 2026-09-09 ([082](methodology/082-derived-submission-rows.md)); H009 `testing`. **0 of 6 submissions spent** (`mva-warehouse probe-budget`,
2026-09-04). The builder and the offline replica exist; nothing has been uploaded.
Method: [`../method.md`](../../method.md). Last checked 2026-09-04.

---

## The goal

> **Which candidate pair does the scorer confirm, and what does each reply tell us that
> the next submission should exploit?**

## Why it matters

- The **oracle** (the challenge's grading endpoint) is the only window onto the answer key.
- The budget is **6 submissions in total**, not 18. Each one is a measurement to be
  designed before it is spent.
- A reply returns `rank_points`, `f_max`, `full_match_rank` and `partial_match_rank` — enough
  to decode *which* of a submitted set matched, if the set was designed to be decodable.
- Matching is **exact string equality** on `(chrom, pos, ref, alt)`. A correct answer spelled
  differently scores zero, which is why step 1 gates this step.

## Already done

- The probe payload builder — step-0 methodology
  [046](../../step-0/methodology/046-probe-builder.md), `src/mva/viz/probebuild.py`, surfaced
  at `/probes` and `/api/probe/build`.
- The **local scorer replica** — [`../notes/local-scorer-replica.md`](../../notes/local-scorer-replica.md),
  `src/mva/pipeline/scorer.py` — so a CSV can be graded offline first.
- The probe ledger: `mva-warehouse probe-log`, `probe-list`, `probe-budget`. Currently 0/6.

## The gate — no upload until all four hold

1. The callset is **normalized** (step 1).
2. The **hypotheses are filed**, each with a prediction and a refutation condition.
3. The CSV is **rehearsed byte-for-byte on the local scorer replica** via the payload builder.
4. **≥ 2 independent methods agree** on the candidate.

The date is decided when the step opens, not now. **Reserve rule:** at least **1 of the 6**
is held to the freeze, for an indel-representation retry or a leaderboard defence. An
alternate spelling costs a *row*, not a submission — exhaust rows first.

```bash
uv run mva-warehouse probe-budget
uv run mva-warehouse probe-log --by <member> --type S \
    --payload-file build/probe_s1.csv --response '<what the scorer replied>' \
    --rationale '<why this probe, and what each reply would mean>'
uv run mva-science probe-link
```

## Remaining

The probe designer: hypothesis space as a bitmask, every candidate probe simulated against
the replica, submit the one with the highest expected information gain. Then decode, and
log every spend as evidence against the hypothesis it tested.

## Exit criterion

A confirmed pair at rank 1 in the final submission, and every reply logged as evidence.

## Report artifact

The verified decode table, and a per-probe entropy-reduction chart — the flagship
innovation exhibit.

## Tooling this step may need

The information-gain probe designer and the decode-table verifier. Recorded in this step's
methodology.

## The record

| | |
|---|---|
| Hypotheses | H009 (`testing`) — [`hypotheses/`](hypotheses/) |
| Tests | [074](methodology/074-submission-v1-design.md) — design and rehearsal; the upload is the next test |
| Rendered | `figures/science-report.html` |
