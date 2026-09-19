# 126 — Every iteration on the steps page, and the figures it drew served rather than named

**Date:** 2026-09-19
**Question:** The repository holds four research iterations, ~75 rendered figures and 60
methodology entries. How much of that was reachable from the dashboard, and what had to be
built so that none of it is invisible?

_(step-0 platform machinery: this entry records a defect in the delivery surface, its cause
and the fix, not a hypothesis. Per [`docs/method.md`](../../method.md) step 0 takes no
hypotheses. Filed in step 0 rather than under a research step because the fault was in the
page every step is read through — it names the steps it serves: iteration 1, 2 and 4,
steps 0–8.)_

## What was observed

Three read-only inventories were taken (app surface, `docs/` record, `submissions/` +
result data). Measured against the running API, four gaps:

| # | Gap | Evidence |
|---|---|---|
| 1 | `/steps` showed **one** iteration. `app/src/pages/Steps.tsx` called `useSteps()` with no argument, so it always asked for `mva.science.steps.ITERATION` (`iteration2`). Iteration 1 — the route whose submission was uploaded and answered *full match at rank 1* — and iteration 4 had no surface at all, although `GET /api/steps?iteration=` had served them since it was written. The hook's own docstring already said "which is what every page but the iteration switcher wants"; that switcher did not exist. | `grep -rn "useSteps(" app/src` → one call site, no argument |
| 2 | Figures were **named, not shown**. `/api/steps` returned `figures: string[]` — bare filenames — and `StepCard` printed them comma-joined. No route served the bytes: `submissions.py` serves only `figures/<track>/*.png` at the top level, so the ~70 files under `figures/track1/iteration2/step-*/` were reachable only from a filesystem. | `curl /api/steps` → `"figures": ["recall-at-n.png", …]`; no `/figure/` route under `/api/steps` in the OpenAPI document |
| 3 | Two steps read as having **drawn nothing** when they had. `_figures()` looked only in `figures/track1/<iteration>/<slug>/`. Iteration 2's step 7 renders into `figures/track2/` (`tools/render_track2_figures.py`) and iteration 1 predates the per-step convention entirely (`figures/track1/*.png`), so both returned `[]`. | `/api/steps?iteration=iteration1` → every step `"figures": []`, while `figures/track1/` holds three PNGs cited by entries 070, 071 and 074/076 |
| 4 | Iteration 1's **statuses were stale**. The step map carried `open` for steps 2–4 and `planned` for step 6, while each step's own README records *exit criterion met 2026-09-05* and, for step 6, *uploaded 2026-09-09 and answered: full match at rank 1, 100 rank points, F-max 1.0* (entry [083](../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)). | `docs/iteration1/step-{2,3,4,6}/README.md` **Standing:** lines vs `src/mva/science/step_maps/iteration1.py` |

A fifth, smaller one: the `decide` nav group had grown to twelve sibling tabs, seven of them
one iteration's step pages, so `Step 4` read as a peer of `Submissions` rather than a detail
of `Steps`.

## What was changed

**The step map gained two declared fields** (`src/mva/science/step.py`):

- `track` — `track1` | `track2` | `both`, read off each step's own goal. `both` is a step
  whose result both submissions quote (iteration 2's step 8, the mosaic bound), not a hedge.
  Validated in `__post_init__` against `TRACKS`, like `status` and `kind`.
- `figures` — repository-relative paths a step drew **outside** the convention directory.
  This is what closes gap 3 without a special case in the route: the step declares its own
  files, and `figure_rows()` merges the convention directory with the declaration.

**Two routes** (`src/mva/viz/steps.py`, helpers in the new `src/mva/viz/steps_artifacts.py`):

| Route | Serves |
|---|---|
| `GET /api/steps/{iteration}/{slug}/figure/{name}` | the figure's bytes, with the right media type |
| `GET /api/steps/{iteration}/{slug}/entry/{name}` | one methodology entry, verbatim |

Neither reads the register, so neither waits on a database to hand back a PNG. **The
whitelist is the validation:** `name` is looked up in the rows the payload publishes (for a
figure) or in the entries the blind gate walked (for an entry). There is no path arithmetic,
so a traversal is simply not a match — checked below.

**The payload gained** `track` per step; `number`, `title` and `url` per methodology entry
(the title read from the entry's own `#` heading, not composed from the filename); figures as
objects with a URL; `submissions` (the folders this iteration fed, with the `state` the
folder gate itself parses); and `index` — every iteration counted, including one that has
docs but no step map, so the journey does not read 1 → 2 → 4 with the gap unexplained.

**Iteration 1's statuses** were corrected to what its own step READMEs record: steps 2, 3, 4
and 6 `done`, step 8 `open`. Steps 1, 5 and 7 were already right.

**The app**: an iteration switcher and a four-card iteration strip on `/steps` (`?iteration=`
in the address, so one link cites one iteration); figures shown as a thumbnail grid into the
existing lightbox, interactive HTML renders as a link; methodology entries readable inline;
a `parent` field in the module manifest and a third header row, which takes `decide` from
twelve tabs to five.

## Commands

```bash
# the four iterations, as the API now answers them
uv run mva-viz-api --port 8901 &
curl -s "http://127.0.0.1:8901/api/steps?iteration=iteration1" | python3 -c "..."

# the new routes
curl -s -o /dev/null -w '%{http_code} %{content_type} %{size_download}\n' \
  "http://127.0.0.1:8901/api/steps/iteration2/step-1/figure/recall-at-n.png"
curl -s "http://127.0.0.1:8901/api/steps/iteration2/step-1/entry/084-the-blind-target-set.md"
curl -s -o /dev/null -w '%{http_code}\n' \
  "http://127.0.0.1:8901/api/steps/iteration2/step-1/figure/..%2F..%2Fetc%2Fpasswd"

# fixtures re-captured for all three declared iterations, then re-blessed
uv run python -c "…mva.viz.steps.payload(Postgres.from_env(), it)…"   # -> app/src/fixtures/data/steps*.json
cd app && pnpm run check
uv run ./tools/check-python.sh
```

## Observed output

```
== iteration1   (was: every step 0 figures)
  step-2 track1 done  figs 2   entries 2
  step-3 track1 done  figs 1   entries 2
  step-6 track1 done  figs 1   entries 4
== iteration2
  step-7 track2 done  figs 5   entries 6      (was: figs 0)
  step-8 both   done  figs 21  entries 6
== iteration4   (was: not reachable from the app at all)
  step-1 track1 done  figs 0   entries 1
  step-3 track1 open  figs 0   entries 1

200 image/png 140331
{"data":{"entry":"084-the-blind-target-set.md","number":"084","title":"Which genes do the child's symptoms alone nominate?", …
404                      # the traversal attempt

iteration1 declared=True  4/8 done  claims 11  submissions track1 frozen · track2 draft
iteration2 declared=True  8/8 done  claims 47  submissions track1 ready  · track2 draft
iteration3 declared=False 0/0       claims 0   submissions none
iteration4 declared=True  2/7 done  claims 4   submissions none

python gate: green          (2954 passed, 5 skipped)
app: 45 files, 649 tests passed; typecheck, lint, format, theme, dictionary clean
```

Rendered and read in a browser against the live API (Chromium headless, `/steps`,
`/steps?iteration=iteration4`): no console error; step 1's four figures render from the API;
entry 084 opens verbatim in place.

## Conclusion

Every declared iteration, every step of it, every methodology entry it wrote and every figure
it drew is now reachable from one page, and the three sources behind them — the step map, the
register, the filesystem — remain the only places any of it is written down. Two facts the
repository already held were wrong on the page rather than missing from it: iteration 1's
step statuses, and the claim that steps 7 and iteration 1 had drawn no figures. Both are
corrected at the source, not at the view.

**Not done, and known:** iteration 4 has no step detail pages (its `todo.md` wave 3 declares
them); the `terms.draft.md` files under `docs/iteration4/step-*/` are still not merged into
the dictionary; `docs/iteration4/README.md` still reads "no step has run" while its own step
READMEs record three that have. Those are the next gaps, and they belong to iteration 4.
