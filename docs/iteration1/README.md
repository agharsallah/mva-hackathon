# Iteration 1 — the research steps behind submission 1

> **Frozen:** 2026-09-09 — this index belongs to iteration 1, whose upload was answered:
> *full match at rank 1: stop+missense (100 rank points, F-max 1.0, threshold 0.9963)*. Do not edit; iteration 2 continues in `docs/iteration2/`.

**Standing:** 2026-09-05. Steps 1–8 as they contributed to
[`submissions/track1/iteration-1/`](../../submissions/track1/iteration-1/README.md). Step 0
(the platform) is not an iteration and stays at [`../step-0/`](../step-0/README.md).

One folder per step; each holds `README.md` (goal, status, exit criterion), `hypotheses/`
(written by `mva-science export`) and `methodology/` (executed tests, numbered globally).

| Step | Goal | Status for submission 1 |
|---|---|---|
| [step-1](step-1/README.md) | one spelling per variant | H008 supported — both alleles SNVs, norm changes no bi-allelic record ([073](step-1/methodology/073-normalization-of-the-candidates.md)) |
| [step-2](step-2/README.md) | rare and damaging, in which gene | H003, H004 supported — genome-wide coding scan leaves BUB1B alone ([069](step-2/methodology/069-layer-2-coding-scan.md), [070](step-2/methodology/070-genome-wide-annotation-and-verdict.md)) |
| [step-3](step-3/README.md) | symptoms agree with the DNA | H002, H005 supported; H001 waits for the oracle ([067](step-3/methodology/067-phenotype-ranking-without-java.md), [071](step-3/methodology/071-phenotype-callset-join.md)) |
| [step-4](step-4/README.md) | nothing hides behind a filter | H006, H007 supported ([072](step-4/methodology/072-genome-wide-suppressed-calls.md)) |
| [step-5](step-5/README.md) | recover an allele from the reads | not needed for submission 1; triggered by the "partner unseen" reply |
| [step-6](step-6/README.md) | spend the oracle budget | v1 designed, rehearsed, not uploaded; H009 `testing` ([074](step-6/methodology/074-submission-v1-design.md)) |
| [step-7](step-7/README.md) | knowledge and literature | three PMIDs as evidence on H009; no separate entry yet |
| [step-8](step-8/README.md) | Track 2 | not started |

When the oracle replies, iteration 2 starts as `docs/iteration2/` (set
`mva.science.steps.ITERATION`) and `submissions/track1/iteration-2/`. This folder is then frozen.
