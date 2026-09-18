# 110 — How does a claim get filed under an iteration that is not the current one?

**Written:** 2026-09-18. **Step:** `step-0` (the platform). **Needed by:** `step-1`
(iteration 4) — a cross-step platform fix, filed here and naming the step that needed it,
per `CLAUDE.md`. Settles open item **O4** of [`docs/iteration4/plan.md`](../../iteration4/plan.md) §12.

**Hypotheses:** none. A missing flag, its fix and the test that pins it.

## What was missing

`mva-science hypothesis-add` had no way to name an iteration. `Hypothesis.iteration` exists
(entry 094 added it so a claim resolves its slug against *its own* step map), but the CLI
never set it, so every new claim landed in `steps.ITERATION` — `"iteration2"` — and
`--step` offered only iteration 2's slugs. Iteration 4 runs **beside** iteration 2 with
`ITERATION` unchanged (plan §5c, O8), so its first MVP claim (`P4-1a`) could not be filed.

## Fix

| file | change |
|---|---|
| `src/mva/science/steps.py` | `ITERATION4` declared (seven research steps, all `planned`, `iteration="iteration4"`) and registered in `STEPS_BY_ITERATION`; new `research_slugs_everywhere()` — the union of research slugs across every declared iteration |
| `src/mva/science/cli/parser.py` | `hypothesis-add --iteration {iteration1,iteration2,iteration4}` (default: the current one); `--step` choices come from `research_slugs_everywhere()` |
| `src/mva/science/cli/write.py` | passes `iteration` into `Hypothesis`; the confirmation line prints `iteration/step` |
| `tests/test_zoo_contracts.py` | pins: iteration 4 has seven research steps; the flag parses; a claim filed with `--iteration iteration4 --step step-1` resolves to iteration 4's goal, not iteration 2's |

`Hypothesis.__post_init__` already validates the slug against the claim's own map
(`step_record` → `by_slug(step, iteration=filed_under)`), so a slug that exists in iteration
2 but not in 4 is rejected at construction. `export` and `check` were fixed by 094 to read
`filed_under`, so nothing else changes.

## Commands run

```
uv run python tools/make_it4_fixtures.py
uv run pytest tests/test_zoo_contracts.py tests/test_cli_parsers.py tests/test_science_cli.py -q
uv run mva-science hypothesis-add --help
tools/check-python.sh
```

Observed output is quoted in the commit that carries this entry; the test file is the
reproducible proof.

## Conclusion

O4 is settled: a claim names its iteration at filing time, and iteration 4's steps exist in
the map before any of them runs. No register row was written by this entry.
