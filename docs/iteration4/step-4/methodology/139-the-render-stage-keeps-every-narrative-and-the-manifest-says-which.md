# 139 — The render stage keeps every narrative, and the manifest says which

**Written:** 2026-09-20. **Step:** `step-4` (iteration 4), after entry
[135](135-a-resume-that-is-tested-by-killing-the-run.md).
**Hypothesis:** **H067 / `P4-5`** — one more evidence row, no new claim.
**Does not supersede 135**; it records a fault found in the stage 135 measured, and the run
that proves the fix.

## Question

Entry 135's two runs were made with a `render` stage that restored only the **hand-written**
version of section 5. Once an LLM had synthesised one beside it (step 5's work, entry
[137](../../step-5/methodology/137-a-synthesis-that-must-cite-the-lane-it-builds-on.md)), the
next `mva-zoo run` deleted it — a $0.116 model call thrown away by a stage whose whole promise
is that re-running it changes nothing. Does the fixed stage reproduce a two-version page exactly,
and does the manifest then say which method the page actually carries?

## Inputs

| input | role |
|---|---|
| `docs/iteration4/report.md` at `c69fcc0` | a merged report carrying **two** section-5 versions: synthesised (`claude-code`, `claude-opus-5[1m]`, 7/7 cited) and hand-written |
| `build/it4/checkpoints/it4-2962e3117b5c/` | the markers entry 135's runs left |
| `src/mva/zoo/merge_render.existing_narratives` | G3's round trip: every version rebuilt from its own marker |

## What changed

* `render` reads **every** version back with `existing_narratives` and hands the whole list to
  `merge_render.render_merged(…, narratives=…)`. The renderer directly, not
  `merge.render_merged` — that forwarder takes a single narrative and belongs to another group.
  `_existing_narrative` had no caller left and is gone.
* The manifest's `method` is now what the render stage **realised**: `fusion+synthesis` only
  when a synthesised version is on the page, `fusion` otherwise, with the stage's note saying so
  when the two differ. The render checkpoint carries it, so a *restored* run does not fall back
  to the configured value and claim a synthesis it never wrote.
* **Not done, on purpose:** calling `narrate.narrate_merged` from the stage. A billable,
  non-deterministic call inside a resumable stage would run on the first pass and be restored on
  every later one — the same config would stop giving the same page, which is the property
  entry 135 exists to defend. The synthesis stays `mva-zoo narrate --merged`; the manifest
  reports its result.

## Commands

```bash
uv run mva-zoo run --config src/mva/zoo/zoo.example.toml --from render
git diff --stat docs/iteration4/report.md
```

## Observed

```
[it4-2962e3117b5c] normalize             0.203s  restored (39286 records)
[it4-2962e3117b5c] registry_check        0.002s  restored (4 lanes)
[it4-2962e3117b5c] fan_out               0.043s  restored (58480 scores over 4 lanes)
[it4-2962e3117b5c] collect               0.001s  restored (4 coverages)
[it4-2962e3117b5c] rank_per_model        0.435s  restored (63347 pairs, 402 rows, 16 genes skipped)
[it4-2962e3117b5c] report_per_model      0.004s  restored (4 reports)
[it4-2962e3117b5c] merge                 0.002s  restored (RRF rank (free): 20639)
[it4-2962e3117b5c] render                0.002s  docs/iteration4/report.md; method realised as
                                                 'fusion+synthesis' (configured 'fusion')
real 2.29
```

**`git diff --stat docs/iteration4/report.md` printed nothing.** The re-render reproduced the
two-version page byte for byte: §5.1 *Synthesised — mode `claude-code`, model
`claude-opus-5[1m]`, 7/7 sentences cited* and §5.2 *Hand-written*, each under its own marker.
Before the fix the same command deleted §5.1.

Seven stages restored in 0.69 s; only `render` ran, because `--from render` was asked for. It is
a third confirmation of entry 135's resume, on a different code path (`--from`), and the first
one where the stage that re-ran was chosen rather than forced by a change.

The log is `build/it4/a4-run3.log`.

## Verdict

No new claim. **H067 / `P4-5` keeps its evidence**: entry 135's numbers were measured with the
stage as it then stood, and `render` contributed 0.004 s and 0.000 s to those two runs, so the
fix moves nothing in them. It is recorded here rather than folded into 135 because 135 is
committed and the log is append-only.

## Limitations

- **The realised method is read off the page, not off the warehouse.** A page edited by hand to
  carry a synthesised marker would make the manifest say `fusion+synthesis`. The marker is
  written by `narrate` and carries the model id, so the claim is traceable, but it is the page
  that is trusted.
- **Nothing here re-measures the synthesis.** The cited-sentence counts in §5.1 are entry 137's
  measurement, quoted by its badge.
- **§5.2's hand-written text is shorter than the version committed at `e65b405`** (~200 chars
  against 5,043). That truncation happened in another group's renderer before this fix and is
  recoverable from git; it is named here so it is not mistaken for a loss this stage caused.
