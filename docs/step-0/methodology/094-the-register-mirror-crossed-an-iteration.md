# 094 — Why did filing step 3's claims write iteration 1's dossiers into iteration 2's folders?

**Written:** 2026-09-13. **Step:** `step-0` (the platform). **Needed by:** `step-3`
(iteration 2) — a cross-step platform fix, filed here and naming the step that surfaced it,
per `CLAUDE.md`.

**Hypotheses:** none. A defect, its cause, its fix and the test that pins it.

## What happened

Step 3 filed its six claims (H024–H029) and ran `uv run mva-science export`, which rebuilds
the committed mirror of the register. The export wrote, among other things:

```
docs/iteration2/step-6/hypotheses/h009-bub1b.md
docs/iteration2/step-8/hypotheses/h010-bub1b.md
docs/iteration2/step-4/hypotheses/h006-bub1b.md
```

H009, H010 and H006 are **iteration-1 claims**. They name the confirmed gene, and they were
about to be committed inside `docs/iteration2/`, whose entire contents are supposed to be
blind until step 6 unblinds. Nothing was committed; the diff was read first.

A second symptom came with it. Every iteration-1 dossier's header line changed:

```diff
-**Step:** [step-6](../README.md) — Which candidate pair does the scorer confirm, and what
-  does each reply tell us that the next submission should exploit?
+**Step:** [step-6](../README.md) — Fused across steps 2-5 and then unblinded, does
+  iteration 2 rediscover iteration 1's pair, and is a second upload informative?
```

An iteration-1 claim was being printed under **iteration 2's** goal.

## Cause

Two places resolved a step slug against the *current* iteration's map instead of the
claim's own. **Slugs restart at `step-1` every iteration** — that is the design
([plan §2](../../iteration2/plan.md), `STEPS_BY_ITERATION`) — so a slug alone does not
identify a step.

| Site | Was | Effect |
|---|---|---|
| `mva.science.export.write` | grouped dossiers by `hypothesis.step` and looped `steps.research_steps()`, writing into `step.folder` of the **current** map | every claim, whatever its iteration, landed in `docs/iteration2/<slug>/` |
| `mva.science.dossier.Dossier.step` | `steps.by_slug(self.hypothesis.step)` — no `iteration=` | the goal line, and the step board's `**Goal.**`, came from the current map |

`Hypothesis.step_record` had already been written correctly — it passes
`iteration=self.filed_under` — and `filed_under` hydrates a row written before the column
existed as `iteration1`. The data was right the whole time; two readers ignored it.

This is why the defect only appeared now. Iteration 2's map was added when step 1 opened,
but until step 3 nobody re-ran `export` with claims from two iterations sharing a slug and
then read the resulting tree.

## The fix

```
src/mva/science/export.py     write() keys by (iteration, slug) and iterates
                              steps.iterations() x steps_for(iteration)
src/mva/science/dossier.py    Dossier.step delegates to hypothesis.step_record
```

Both carry the reason inline, because the rule is not obvious from the type: a slug is not
a key.

## Commands

```
uv run mva-science export
uv run pytest tests/test_science_export.py -q     # 33 passed
```

## Observed, after the fix

| | |
|---|---|
| iteration-1 dossiers under `docs/iteration1/` | 19 files, unchanged but for their generation stamp |
| iteration-2 dossiers under `docs/iteration2/` | H012–H015 (step 1), H016–H023 (step 2), H024–H029 (step 3) |
| BUB1B dossiers anywhere under `docs/iteration2/` | **0** |
| goal line on an iteration-1 dossier | its own iteration's goal |

## The test that pins it

`tests/test_science_export.py` gains two cases:

* an iteration-1 claim with slug `step-1` is written to `iteration1/step-1/hypotheses/`
  and **not** to `iteration2/step-1/hypotheses/`;
* a dossier's `step.goal` equals its own iteration's goal for that slug, and differs from
  the other iteration's — so the assertion would fail if the maps were ever made identical
  and someone re-introduced the shortcut without noticing.

## Assumptions and limitations

* **The blind gate did not and could not catch this.** `tools/check_blind.py` reads the
  `## Inputs` table of *methodology entries*; the register mirror is generated, has no
  such table, and is not scanned. The two are complementary: the gate polices what an
  entry declares it read, this fix polices where a generated file is written. Neither
  replaces reading the diff before committing, which is what actually caught it.
* **Nothing was committed in the wrong place**, so no history needs rewriting. The stray
  directories were removed before the fix was applied and re-exported.
* The generation stamp changes on every export, so all 19 iteration-1 mirrors show a
  one-line diff. That is the mirror doing its job, not a content change.
