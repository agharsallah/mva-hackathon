# 083 — What did the oracle say to submission 1?

**Step:** step-6   **Hypotheses tested:** H009 (`testing` → **`supported`**, revision 3)
**Written:** 2026-09-09. **Uploaded 2026-09-09** — 1 of 6 spent; the remaining 5 belong to iteration 2 and later, each with its own plan.

## Question

Submission 1 (`submissions/track1/iteration-1/`, built in [074](074-submission-v1-design.md),
rows derived in [082](082-derived-submission-rows.md)) was uploaded to the challenge scorer.
Which row of the pre-committed decode table does the reply land on, and what does that do to
the register?

## Hypothesis and prediction — written before the run (074)

**H009:** the causal pair is the BUB1B stop_gained (ClinVar pathogenic, MVA syndrome 1) with
the gnomAD-absent BUB1B missense, in trans. Predicted reply for the rank-1 row:
`full_match_rank = 1`, `rank_points = 100`, `f_max = 1.0`.

## What would refute it (074)

No full match for that row. A partial match at rank 1: exactly one allele is causal. No
match at all: neither is.

## Observed — the reply, verbatim

```
Submission received ✓
agharsallah (agharsallah)  |  Submission: 1  |  Proband: PROBAND01
Rank points               100.0 / 100
F-max                     1.000
F-max EPCR threshold      0.9963
✅ Full match at rank 1
```

Read against `submissions/track1/iteration-1/decode-table.md`, row 1:
`full match rank 1 · F-max 1.000 · at epcr 0.9963 · prior mass 0.78 · survivors: stop+missense`.
The threshold 0.9963 is the derived anchor epcr of the rank-1 row (082), which confirms the
scorer read the row we think it read. Every other answer key in the hypothesis space is
eliminated: the four alternative pairings, both "partner unseen" keys, and "other gene".

## Verdict

**H009 supported.** The prediction held exactly. The answer key is the BUB1B compound
heterozygote; phase (trans) is settled by the key itself, not by reads, so step 5 is no
longer needed for the partner allele.

## Commands run and what they wrote

```bash
uv run mva-warehouse probe-log --track 1 --type F --by agharsallah \
    --ref "submissions/track1/iteration-1/agharsallah_bub1b-comphet-derived.csv (gitignored; sha256 54854a6e…)" \
    --payload-file submissions/track1/iteration-1/agharsallah_bub1b-comphet-derived.csv \
    --response "Submission 1 | Rank points 100.0/100 | F-max 1.000 | F-max EPCR threshold 0.9963 | Full match at rank 1" \
    --score 100 --rationale "iteration 1 … (074, 082)"
# → logged probe 1 into warehouse.probe_ledger; budget: 1/6 spent, 5 remaining

uv run mva-science probe-link 1 --hypothesis H009 --direction supports --by agharsallah --claim "Oracle reply to submission 1: full match at rank 1 …"
# → recorded 1 oracle observation(s) from probe 1: evidence row 32

uv run mva-science verdict H009 --commit --status supported --by agharsallah --reasoning "…"
# → +1.600 supports 0.80 (the oracle row) → 0.999; suggested 1.00 (7 supporting, 0 refuting, 3 neutral)
# → recorded H009 revision 3: supported at 1.00

uv run mva-science export        # docs/science-register.json, hypotheses/ mirrors
uv run mva-science check         # check passed: 11 hypotheses, 32 evidence rows, no coordinates
uv run mva-science report        # figures/science-report.html — 11 hypotheses, 1/6 probes spent
uv run python tools/new_iteration.py --track track1 --reply "full match at rank 1: stop+missense (100 rank points, F-max 1.0, threshold 0.9963)"
# → iteration 1 frozen (dated banner), docs/iteration2/ + submissions/track1/iteration-2/ scaffolded, ITERATION = "iteration2"
```

The committed confidence is set by the reply, not by the heuristic weighing: the register
had been held at `testing` with no confidence precisely so the weighing could not saturate
on six rows describing the same two alleles ([`method.md`](../../../method.md)). Residual
doubt is only the scorer's own correctness.

## What the reply changes downstream

| Where | Before | After |
|---|---|---|
| `warehouse.probe_ledger` | 0 of 6 | 1 of 6, probe 1 |
| H009 | `testing`, no confidence | `supported` 1.00, revision 3, evidence row 32 |
| `submissions/track1/iteration-1/` | ready | **frozen** 2026-09-09 |
| `submissions/track1/iteration-2/` | — | draft; iteration 2 defines its own plan and steps rather than replaying steps 1–8 |
| Iteration 1's step 5 (raw reads for the partner) | gated on the "partner unseen" reply | not needed for the pair |
| Track 2 (drug repurposing) | on a candidate | on the confirmed BUB1B mechanism |
| Dashboard `/submissions` | 1 iteration, no probe | 2 iterations; audit trail shows probe 1 and the H009 verdict (fixture re-captured) |

## Limitations

- One reply, one bit of information used: the scorer confirms the pair; it says nothing
  about the secondary rows (unscored by design).
- "Confidence 1.00" is the register's cap. It means "the oracle agreed", not "no error is
  possible" — a scorer bug or an answer-key error would be invisible to us.
