# Iteration 4 — the model zoo

**Standing:** 2026-09-19 — steps 1 and 2 are **done**, step 3 is **open**, steps 4-7 are
`planned`. Four claims are filed (H058-H060, H062): two supported, one refuted, one undecided
by its own terms. Iteration 2 stays the current iteration (`ITERATION = "iteration2"`);
iteration 4 runs beside it, which is why the dashboard's `/steps` page reaches it through
`?iteration=iteration4` rather than showing it by default.

_(Previously, and wrongly, this page said "no step has run; no claim is filed" while its own
step READMEs recorded three runs. Corrected 2026-09-19 — see
[`../step-0/methodology/126-every-iteration-on-the-steps-page.md`](../step-0/methodology/126-every-iteration-on-the-steps-page.md).)_

**Plan:** [`plan.md`](plan.md) — every credible open variant-effect model run under one
contract (record → adapter → cache → rank → template → merge), with lineage, and a merged
report no single model produces. **Board:** [`todo.md`](todo.md) — what is done, what is next,
by wave. Iteration 3 was a draft, absorbed here as step 1; it is not declared.

## Steps

Read them on the dashboard at `/steps?iteration=iteration4`, which carries each step's goal,
its claims with their verdicts, and its methodology entries in full. These steps have **no
detail pages** of their own yet — `todo.md` wave 3 declares them — so the journey page is the
whole surface for now.

| step | goal (one question) | folder | status | entry | verdicts |
|---|---|---|---|---|---|
| 1 | one normalized allele record every model class can read | [`step-1/`](step-1/README.md) | **done** | [114](step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) | H058 supported |
| 2 | which open models are credible, runnable, licensed; their coverage | [`step-2/`](step-2/README.md) | **done** | [119](step-2/methodology/119-four-lanes-fetched-licensed-and-joined.md) | H059 supported, H060 refuted |
| 3 | one batch inference API, one cache with provenance | [`step-3/`](step-3/README.md) | **open** | [122](step-3/methodology/122-every-lane-scored-once-and-only-once.md) | H062 undecided by its own terms |
| 4 | a checkpointed DAG from one command, costed | [`step-4/`](step-4/README.md) | planned | — | — |
| 5 | one report template per model | [`step-5/`](step-5/README.md) | planned | — | — |
| 6 | do the models agree; the merged report | [`step-6/`](step-6/README.md) | planned | — | — |
| 7 | Track 2: graph walk vs GNN over PrimeKG, against a decoy | [`step-7/`](step-7/README.md) | planned | — | — |

Every step here feeds **Track 1** except step 7, which feeds Track 2; the step map declares
that (`track=`) and `/steps` shows it as a badge on each card.

Methodology numbering continues globally. Iteration 4's entries so far are **114**, **119**
and **122** — not a contiguous block, because iteration 2's steps 7 and 8 were running beside
this one and the numbers are handed out in filing order across every step.

## Code

`src/mva/zoo/` ([README](../../src/mva/zoo/README.md)); contracts in `types.py`; synthetic
fixtures in [`fixtures/it4/`](../../fixtures/it4/README.md). Track 2's engine lives in
`src/mva/drugs/graph_walk.py`.
