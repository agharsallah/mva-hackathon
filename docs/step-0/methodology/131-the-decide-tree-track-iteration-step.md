# 131 — Decide becomes a tree: Track ▸ Iteration ▸ Step, generated from the step maps

**Date:** 2026-09-19
**Question:** Entry 126 gave `/steps` an iteration switcher, which made every iteration
*reachable* but left them all behind one page and one address. The user asked for the shape
the work actually has — two tracks, each with its iterations, each with its steps. Can the
navigation be that tree without the step maps being retyped into TypeScript, and can every
step get a page of its own?

_(step-0 platform machinery: a delivery-surface change, not a hypothesis. Per
[`docs/method.md`](../../method.md) step 0 takes no hypotheses. Filed in step 0 because it
re-shapes the shell every step is read through; it serves iterations 1, 2 and 4 of both
tracks.)_

## What was asked for

```
Decide
├── Science
├── Probes
├── Track 1
│   ├── Iteration 1 ▸ Overview · Step 1 · Step 2 · …
│   └── Iteration 2 ▸ Overview · Step 1 · Step 2 · …
├── Track 2
│   ├── Iteration 1
│   └── Iteration 2
└── Submissions
```

> **Legend** — the order is the reader's: the register and the budget first, then the two
> deliverables, then what would be uploaded. Iteration 4 is included as well; it is declared
> and running, and leaving it out would hide work.

## What was in the way

The manifest (`app/src/app/modules/index.ts`) is a static array, because the router, the
header and the journey footer all read it synchronously. The steps are *not* static: they
are declared in `mva.science.steps`, one map per iteration, and the repository's rule is
that declaring a step makes it appear rather than requiring a second edit. Writing ~26 nodes
by hand would have put a copy of every step map into TypeScript, to fall behind the day a
step is added.

## What was changed

**A generator, not a copy.** `tools/gen_steps_nav.py` reads the step maps and writes two
files: the navigation subtree (`app/src/app/modules/steps.generated.ts`, 26 modules) and the
registry of analysis bodies (`app/src/pages/steps/bodies.generated.ts`). Every label, title
and description in them is a field of a `Step` or an iteration's own docstring line —
nothing about a step is written twice. `pnpm steps-nav:check` is in `pnpm check`, so the
tree and the maps cannot drift; both files are in `.prettierignore` for the same reason the
dictionary's output is, and the tool's docstring says so.

**Which steps go where** follows from the `track` field entry 126 added. Track 1 collects
the steps that argue an allele (`track1`) and the ones whose result both submissions quote
(`both`); Track 2 collects the steps that argue a drug. No step appears twice, and a card
that serves both tracks says so. Track 2's iterations have a single step each, so they list
no step children and render that step opened instead — there is nothing to scan past.

**Three new pages, two of them generic.**

| Page | Route | What it carries |
|---|---|---|
| Track overview | `/track1` | one card per declared iteration, from `/api/steps`'s `index`; an undeclared one greyed with the reason |
| Iteration | `/track1/iteration2`, `/track2/iteration1`, … | the track's steps of that iteration, its submission folders and their state, and the blinding checklist scoped to those steps |
| Step | `/track1/iteration1/step-6`, … | the question; every claim **in full** — statement, prediction, refutation condition, verdict; every methodology entry readable verbatim in place; every figure it drew |

The iteration and step pages are one component each for the whole tree: the address carries
the identity (`/track1/iteration2/step-4` parses to exactly the three things a page needs, and
its iteration segment is the same string `?iteration=` takes), and the API carries the rest.
Declaring an iteration is therefore the whole job — the generator adds the routes and these
two pages fill them.

**The analysis pages were not rewritten.** Seven of iteration 2's steps have deep pages with
their tables, nulls and charts; they are now rendered *below* the record on the step's page,
from the generated registry, so one address carries both halves. A step without one says so
instead of looking unfinished.

**The header grew a fourth row**, built by following `parent` rather than by knowing how deep
the tree is — a fifth level would need no change. **Old addresses still work**: `/steps` and
the seven `/steps/step-<n>` redirect, because methodology entries cite them and that log is
append-only. Every *editable* doc and the dictionary's "see it in the app" links were
repointed; the two entries that cite the old paths were left alone by the same rule.

## Commands

```bash
uv run python tools/gen_steps_nav.py          # 26 modules + the bodies registry
uv run python tools/gen_steps_nav.py --check  # now part of `pnpm check`
cd app && pnpm run check
uv run ./tools/check-python.sh
# rendered against the live API, Chromium headless: /track1, /track1/iteration1/step-6,
# /track2/iteration2
```

## Observed output

```
gen_steps_nav: wrote app/src/app/modules/steps.generated.ts (26 modules) and
               app/src/pages/steps/bodies.generated.ts
gen_steps_nav: up to date (26 modules)

app: 45 files, 687 tests passed        (649 before — the 26 new routes are mounted and
                                        axe-checked by the existing per-module suites)
typecheck, lint, format, theme, dictionary, steps-nav: clean
python gate: green
```

Read in a browser:

- `/track1` — four iteration cards; iteration 3 greyed, "no step map, so there is nothing to
  open"; 3 declared, 15/23 steps finished, 63 claims.
- `/track1/iteration1/step-6` — rows read `Science · Probes · Track 1 · Track 2 ·
  Submissions`, then `Track 1 — overview · Iteration 1 · Iteration 2 · Iteration 4`, then
  `Iteration 1 — overview · Step 1 … Step 7`. H009 renders with its prediction, its
  refutation condition and the verdict the oracle's reply settled; entries 074, 076, 082 and
  083 are listed by number and heading, each readable in place.
- `/track2/iteration2` — one step, opened: seven claims, six entries, five figures shown.

## Conclusion

The navigation is now the shape of the work, and it is derived rather than declared twice: a
step added to `mva.science.steps` gets a route, a nav entry, a page and a place in the
reading order with no TypeScript edit at all. Every step of every iteration has a page that
carries its claims in full, its entries verbatim and its figures — including the fifteen
steps that never had a page of any kind.

**Not done, and known:** iteration 4's steps still have no *analysis* bodies (its `todo.md`
wave 3 declares them) and no `/api/zoo/*` routes; their pages render the record alone and say
so. Track 2's iterations show their step in full rather than linking a page of its own,
which is a judgement about one step per iteration and would want revisiting if that changes.
