# 137 — A synthesis that must cite the lane it builds on

**Written:** 2026-09-20. **Step:** `step-6` (iteration 4). **Run:** A6 of wave 4 (opt-A).
**Hypotheses tested:** H072 (the merge-level sibling of `P4-7`; the plan files no claim for
`fusion+synthesis`, so this one was written for it and filed before the call).

Turns step 6's merge method from `fusion` (deterministic layer, narrative by hand) into
`fusion+synthesis` (deterministic layer, narrative written from the merged rows and checked).
Reads [130](130-a-consensus-of-lanes-that-declined-to-vote.md)'s merged JSON and the four
section 6 texts entry [134](../../step-5/methodology/134-an-llm-that-may-only-explain-the-rows-it-was-given.md)
produced.

## Question

The per-model interpretation (entry 134) had one report to read. A *synthesis* has four, plus
an agreement matrix and two fusions. Does the same discipline — rows with stable ids, a
citation on every sentence, a mechanical check — survive the step up, or does a writer with
more material start joining dots the rows do not join?

## Hypothesis and prediction

*Written before the call.*

| | |
|---|---|
| **Statement** | The merged report's narrative, synthesised in mode `claude-code` from the merged rows, cites every sentence to a row that was sent and names no lane, gene or disease the rows never gave it. |
| **Prediction** | `mva-zoo narrate --merged --mode claude-code`: `mva.zoo.narrate_check` reports `uncited_sentences / sentences <= 0.10`, `unknown_ids == ()` and `new_names == ()` against `mva.zoo.narrate_rows.merged_rows`. |

## What would refute it

> The synthesis leaves more than **10 %** of its sentences without a citation that resolves to
> a merged row, cites an id that was never sent, or names a lane, gene or disease outside the
> rows.

## What the model is shown

The same shape as entry 134, one row set larger: `method`, one `lane.<model>.rank` per lane,
one `rho.<a>.<b>` per off-diagonal cell of the agreement matrix, `rrf.free.rank` and
`rrf.all.rank`, `disagree.n`, and one `interp.<model>` row carrying what each lane's own
section 6 already says. The rule block adds one line to the per-model one: *rows whose id
starts with `interp.` are what a lane already said; build on them, but cite the lane*.

A lane that abstained reads "has no rank for the confirmed pair: it scored only one of its two
alleles" — never a null. The distinction between abstention and a bad verdict is the whole
finding of entry 130, and it must not be something the writer has to infer.

## Inputs

| input | rows | role |
|---|---|---|
| `build/it4/merged.json` | 4 lanes, 6 off-diagonal ρ cells, 2 fusions, 90 disagreements | the deterministic layer, run `it4-2962e3117b5c` |
| `build/it4/reports/*.json` | 4 | each lane's own section 6, as the `interp.<model>` rows |
| Claude Code CLI | 2.1.278, model `claude-opus-5[1m]` | the `claude-code` transport |

**18 citable rows**: `method`, four `lane.<model>.rank`, six `rho.<a>.<b>`, `rrf.free.rank`,
`rrf.all.rank`, `disagree.n`, four `interp.<model>`.

## Commands

```bash
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --merged --mode claude-code --dry-run
uv run mva-zoo narrate --config src/mva/zoo/zoo.example.toml --merged --mode claude-code
```

## Observed

One call, 20.1 s, **$0.116**.

| | |
|---|---|
| sentences | 7 |
| sentences whose citation resolves to a row that was sent | **7** |
| uncited rate | **0.00** (bar: 0.10) |
| ids cited that were never sent | **0** |
| lane, gene or disease names outside the rows | **0** |
| words | 195 (budget 200) |

Re-checked from the rendered file against a freshly built row list — the checker needs only
the reply and the rows:

```bash
uv run python - <<'EOF'
import json, pathlib
from mva.zoo.narrate_check import check_narrative
from mva.zoo.narrate_rows import merged_rows
merged = json.loads(pathlib.Path("build/it4/merged.json").read_text())
readings = {}
for p in sorted(pathlib.Path("build/it4/reports").glob("*.json")):
    d = json.loads(p.read_text())
    if d["sections"]["interpretation"].get("text"):
        readings[d["model"]] = d["sections"]["interpretation"]["text"]
body = pathlib.Path("docs/iteration4/report.md").read_text()
body = body.split("### 5.1", 1)[1].split("-->", 1)[1].split("### 5.2", 1)[0].strip()
print(check_narrative(body, merged_rows(merged, readings), max_words=200).summary())
EOF
```

### What the synthesis said that no single lane's report could

The seven sentences reach the same conclusion entry 130 reached by hand, from the rows alone:

- three lanes returned **no rank**, each having scored one of the pair's two alleles, and a
  pair with an unscored half is dropped rather than scored zero
  `[lane.alphamissense.rank][lane.esm1b.rank][lane.revel.rank]`;
- one lane saw both halves, at 11,980 of 50,696, 23.63 % from the top `[lane.spliceai.rank]`;
- so both fused positions — 20,639 of 52,012 without the catalogue-adjacent lane, 21,497 of
  52,219 with it, **at the same fused score** — rest on that single lane
  `[method][rrf.free.rank][rrf.all.rank][lane.revel.rank]`;
- the lanes largely do not track each other (+0.580 at best, +0.021 at worst)
  `[rho.*]`, and 90 alleles sit in one lane's top 1 % and another's bottom half
  `[disagree.n]`;
- **"the consensus here is one opinion plus three abstentions"**, and it cannot show
  agreement, cannot read silence as harmlessness, and does not establish that anything causes
  anything `[method][interp.spliceai][interp.revel]`.

The last sentence is the one worth noting: it is a *judgement about the merge*, built from the
lanes' own readings and cited to them, and it is the same judgement the hand-written §5 makes.
Two independent writers, the same rows, the same conclusion.

### The marker round trip, and an incident that proves the storage earns its keep

The first render wrote the synthesised version under an ``<!-- interpretation: … -->`` marker
— the per-model slot's name, not the merged report's ``<!-- narrative: … -->``. The next
re-render looked for narrative markers, found only the hand-written one, and **wrote the file
without the synthesised version**.

It was recovered from ``results.it4_narratives`` — model ``merged``, mode ``claude-code``,
195 words, 7/7 — without a second call to the model and without a second $0.116. That is the
whole argument for storing prompt and reply rather than only the rendered page, and it was
tested by accident within an hour of the table existing.

Both halves are now fixed: :meth:`mva.zoo.narrate.Narrative.marker` takes the slot's name
(``narrative`` renders *synthesised*), and :func:`mva.zoo.merge_render.existing_narratives`
reads **every** version back out of the rendered file, each rebuilt from its own marker — the
same round trip :func:`mva.zoo.report_sections.existing_interpretations` does for section 6.

## Verdict

**H072 — supported.** Seven of seven sentences cite a row that was sent; no invented id, no
lane, gene or disease outside the rows, inside the word budget. The refutation condition was
not met.

## Limitations

- **One call, one mode, not reproducible.** As in entry 134: `claude -p` has no temperature
  flag. `nebius` **was not run: no key**.
- **A synthesis cites rows, not reasoning.** "One opinion plus three abstentions" is a correct
  reading of the rows it cites, but the checker only proves it points at them.
- **`interp.<model>` rows carry their own `[cov.*]` citations.** Those ids are not merged rows;
  had the model copied a lane's sentence verbatim, its citations would have failed to resolve
  and the check would have caught it. It did not copy one.
- **`fusion+synthesis` is not yet the configured method.** `[merge] method` is still `fusion`;
  the synthesis is produced by `mva-zoo narrate --merged`, and the run manifest therefore still
  records `fusion`. Wiring the method key to skip the hand-written fallback is a change to the
  workflow's render stage, which another agent owns this wave — the exact request is in
  `build/it4/agents/g3-narrate.md`.
- **A `mva-zoo run` still deletes the synthesised §5.** Its render stage restores only the
  hand-written narrative (`workflow_stages._existing_narrative`). The one-line fix is filed in
  the same status file; until it lands, a chain re-run is followed by
  `uv run mva-zoo narrate --merged --mode none`.

## Outputs

| artifact | where |
|---|---|
| the merged report, §5 in two versions | [`../../report.md`](../../report.md) |
| the synthesis, prompt and reply included | `results.it4_narratives` (model `merged`) |
| the run log | `build/it4/a6-synthesis.log` (not tracked) |
