# 132 — What a step says, and what a figure means

**Date:** 2026-09-19
**Question:** Entry 131 gave every step a page carrying its goal, its claims, its
methodology entries and its figures — all of it *derived*. Reading one, the thing missing
was obvious: nothing said what the step **concluded**, why its question belonged where it
was, what the next step does with the answer, or what any of its ninety-odd charts mean. Can
that be added without it becoming prose nobody maintains?

_(step-0 platform machinery: a delivery-surface change and the gate that keeps it true, not
a hypothesis. Per [`docs/method.md`](../../method.md) step 0 takes no hypotheses. Filed in
step 0 because it defines a record artifact every research step now carries; it serves
iterations 1, 2 and 4.)_

## What was observed

Four things about a step cannot be derived from anything the repository already holds:

| Missing | Why no query can produce it |
|---|---|
| what the step concluded | the register has per-claim verdicts; nobody had written the step's own |
| why the question belonged here | the step map has the question, not the argument for asking it there |
| what it inherits, what it hands on | `unblocks` is a dependency edge, not a reason. A journey is not a list: iteration 2's step 4 exists *because* its step 2's filter threw away the thing step 4 had to score, and only prose says so |
| what a figure means | 93 rendered charts; the filesystem knows their filenames and nothing else |

The last one is the sharpest. A chart with no caption is decoration, and the pages were
showing seventy of them with a filename underneath.

## What was changed

**A committed artifact with a gate, not free prose.** `narrative.json` sits beside each
step's README and carries `summary`, `why`, `verdict`, `inherits`, `hands_to`, `figures[]`
and `sources[]`. `mva.viz.steps_narrative` validates it and `/api/steps` serves it, folding
each caption into the figure row it describes so a page needs one list rather than a join.

**Two fields per figure, on purpose.** `reads` is what the chart literally shows — the axes,
what one mark is, the colouring, the ordering — and is checkable against the image by anyone.
`means` is what the chart is evidence *for*, argued from the methodology entry that produced
it, which the caption cites. Keeping them apart is what stops an interpretation being read as
a description.

**`tools/check_step_narrative.py`** is now in the Python gate. It fails when a research step
whose status is `done` or `open` has no narrative; when a required field is empty; when a
source path does not exist; when a figure the step drew has no caption; and when a caption
names a figure the step never drew. A `planned` step is exempt — there is nothing to
summarise about a step that has not run, and inventing one would be worse than the silence.

**Written by three agents, one per iteration, against a worked example.** The contract was
fixed first and `docs/iteration1/step-6/narrative.json` written by hand as the quality bar,
so three writers could not invent three shapes. Each was told the standing rule — never
invent a number, cite what you read, no coordinates — and each verified its own iteration
against the gate before handing back.

**One correction landed from it.** Iteration 1's step 8 (the Track 2 hand-off) still
describes the pair as *inferred, not confirmed*: its files are dated 2026-09-06 and the
oracle's reply is entry 083, dated 2026-09-09. The folder is frozen, so the README was left
alone and the narrative states the chronology instead.

## Commands

```bash
uv run python tools/check_step_narrative.py     # now inside tools/check-python.sh
uv run pytest tests/test_steps_narrative.py -q
cd app && pnpm run check
```

## Observed output

```
step narrative: every step that has run is written up, every figure is read

20 narratives · 93 figure captions · ~17,700 words
  iteration1   6 steps,  4 captions
  iteration2   8 steps, 77 captions
  iteration4   6 steps, 12 captions

python gate: green      2972 passed, 5 skipped   (was 2959)
app: 45 files, 687 tests passed, every gate clean
```

Read in a browser at `/track1/iteration2/step-6`: the page opens with what the step did, then
*Why this step exists here* beside *What it concluded*, then the two joins as chips linking
the steps they name — a platform step, which has no page, renders greyed instead of as a dead
link. Each figure carries **What it shows** and **What it means** with the entry that argues
it.

## What this does not fix

- The narratives are *written*, so they can go stale the way any prose can. The gate checks
  completeness and sourcing, not freshness; a figure re-rendered with different data keeps
  its old caption until someone edits it.
- `confidence` numbers quoted inside a verdict remain what they always were: a stated triage
  heuristic with its arithmetic in the register, never a calibrated probability.
- Two discrepancies surfaced by the writers and deliberately **not** reconciled, because
  each belongs to a document with an owner: iteration 2's step-6 README cites step 5's AUC
  interval as [0.595, 0.672] where step 5's own entry 105 reports [0.593, 0.672]; and
  iteration 4's step-6 README links the `figures/it4/` cross-lane charts that entry 129
  attributes to step 5. Each narrative quotes the document that states the number it uses.
