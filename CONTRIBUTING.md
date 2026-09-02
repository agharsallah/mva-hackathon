# Contributing

**Verified:** 2026-09-02 — hooks and CI described here exist and were run manually against
this repo's real history; see `docs/README.md` for what they check and why.

Two projects live in one git repo. Pick the toolchain by which half you touched.

## The two projects

| Project               | Where                           | Toolchain                                                                  | Entry point                                                                                                    |
| --------------------- | ------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Python (the pipeline) | repo root, `src/mva/`, `tests/` | [`uv`](https://docs.astral.sh/uv/) — never `pip`, `venv`, or bare `python` | `uv sync`, `uv run <cmd>`. Scripts: `mva-explore`, `mva-warehouse`, `mva-science`, `mva-reads`, `mva-viz-api`. |
| App (the viewer)      | `app/`                          | `pnpm`                                                                     | `cd app && pnpm install && pnpm run dev` — see [`app/README.md`](app/README.md).                               |

Read [`docs/README.md`](docs/README.md) for the project's domain, method, and roadmap before
changing behavior — this file is only about the mechanics of getting a change in.

## Commit convention

Read from `git log`, not invented — recent history (`feat`/`docs`/`refactor`/`fix`/`chore`/`style`,
122+ commits) consistently follows:

```
<type>(<scope>): <imperative summary, lowercase, no period>

<body: why, not what — paragraphs and/or bullets. Cite measured numbers
where the commit produced one, e.g. "296.89 kB -> 236.44 kB raw".>
```

- `type`: `feat`, `fix`, `docs`, `refactor`, `chore`, `style`, `test`. No hard enforcement (no
  commitlint) — this is observed convention, kept by review.
- `scope`: the package or app area touched — `app`, `viz`, `compare`, `panel`, `search`,
  `probes`, `callset`, `fixtures`, `src`, `step-0`, etc. Omit it for a repo-wide change
  (`docs: replace ~/ubuntu/work references with the warehouse DB and reads/viz API`).
- Body explains _why_ and states any number the change produced or changed — per the repo's
  [Results integrity](CLAUDE.md#results-integrity) rule, a number in a commit message must come
  from a real run.
- No AI-attribution trailers (`Generated with Claude Code`, `Co-Authored-By: Claude ...`) in new
  commits from this tooling wave — a project-level policy, not a repo-wide ban on any trailer
  that already exists in older history.

## What enforces what

| Rule                                                                                           | Enforced by                                                                               | Run it locally                                  |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------- |
| TypeScript compiles (`tsc -b`, strict, `noUnusedLocals`/`noUnusedParameters`)                  | pre-push hook, CI `app` job                                                               | `cd app && pnpm run typecheck`                  |
| ESLint (react-hooks, jsx-a11y, import order, repo-local rules)                                 | pre-commit hook (staged files only, `--fix`), pre-push hook, CI `app` job                 | `cd app && pnpm run lint:strict` (or `lint:fix` to autofix)       |
| Prettier formatting                                                                            | pre-commit hook (staged files only, `--write`), pre-push hook, CI `app` job               | `cd app && pnpm run format` (or `format:check`) |
| Vitest unit/component tests                                                                    | pre-push hook, CI `app` job                                                               | `cd app && pnpm run test`                       |
| Production build (`tsc -b && vite build`)                                                      | pre-push hook, CI `app` job                                                               | `cd app && pnpm run build`                      |
| Bundle size budget                                                                             | CI `app` job (`app/tools/bundle-budget.mjs`)                                              | `cd app && node tools/bundle-budget.mjs`        |
| Dead code (unused files/exports/deps)                                                          | CI `app` job, **report-only** — see `app/knip.json`                                       | `cd app && pnpm exec knip`                      |
| Ruff format (`ruff format`)                                                                    | pre-commit hook (staged `.py` only, rewrites + re-stages), pre-push hook, CI `python` job | `uv run ruff format src tests tools`            |
| Ruff lint (30 rule families, line length 100)                                                  | pre-commit hook (staged `.py` only, `--fix`), pre-push hook, CI `python` job              | `uv run ruff check src tests tools`             |
| Module size (400 lines in `src`/`tools`, 600 in `tests`)                                       | pre-push hook, CI `python` job                                                            | `uv run python tools/check_module_size.py`      |
| Import layering (no cycles; the leaf packages import no sibling; nothing depends on `mva.viz`) | pre-push hook, CI `python` job                                                            | `uv run lint-imports`                           |
| mypy (strict, with a per-package ratchet)                                                      | pre-push hook, CI `python` job                                                            | `uv run mypy`                                   |
| `uv.lock` matches `pyproject.toml`, pytest suite                                               | pre-push hook, CI `python` job                                                            | `uv sync --frozen && uv run pytest`             |

`pnpm run check` in `app/` runs typecheck + lint + format:check + test in one command — the same
four gates the pre-push hook and CI both run. `tools/check-python.sh` is its counterpart for
the root package: the same six gates, in CI's order, with `--fix` to format and autofix first.
Why each Python rule is set where it is:
[`docs/notes/python-quality-gates.md`](docs/notes/python-quality-gates.md).

## Git hooks (husky)

Hooks live at the **repo root** `.husky/` (not `app/.husky/`) because git resolves
`core.hooksPath` from the top of the working tree, and one hook has to see staged/pushed files
across both projects to decide whether it needs to run at all.

- **pre-commit** — runs `ruff format` + `ruff check --fix` on staged `.py` files and
  re-stages them, then `lint-staged` (`app/.lintstagedrc.json`: `eslint --fix` + `prettier
--write` on staged `.ts`/`.tsx`/`.js`/`.mjs`, `prettier --write` on staged `.json`/`.md`, all
  under `app/`) — but only if the commit actually stages a file under `app/`. A Python-only or
  docs-only commit skips it entirely; no node process even starts.
- **pre-push** — runs `tools/check-python.sh` if the pushed range touches `src/`, `tests/`,
  `tools/`, `pyproject.toml` or `uv.lock`, and the full `pnpm run check` + `pnpm run build` in
  `app/` if it touches `app/`. Each half is skipped when untouched. Same skip logic, applied to the diff between each pushed
  ref's old and new SHA (falls back to running the gate, never to skipping it, when that diff is
  ambiguous — e.g. a brand-new branch with no shared history).

**One-time setup after cloning:** hooks only fire once git's `core.hooksPath` points at
`.husky/`. Today that means running `git config core.hooksPath .husky` once per clone (the
lasting fix — adding `"prepare": "husky"` to `app/package.json` so `pnpm install` wires it
automatically — is tracked separately; see the note in the hooks themselves).

## When a gate fails

1. Read the failing step's output — every gate prints what it checked and why it failed.
2. Fix locally with the "Run it locally" command above, or its `--fix`/`--write` variant
   (`pnpm run lint:fix`, `pnpm run format`).
3. Re-run `pnpm run check` in `app/` (or `uv run pytest` for Python) before pushing again.
4. A **knip** finding is a report, not a blocker — it does not fail CI. Triage it, but don't
   feel compelled to fix it in the same change.
5. If a hook is wrong for your change (e.g. it ran when it shouldn't have, or vice versa),
   that's a bug in `.husky/pre-commit` / `.husky/pre-push` — fix the skip logic, don't bypass the
   hook with `--no-verify`.

## More

- [`docs/README.md`](docs/README.md) — the doc index: method, dictionary, roadmap, per-step
  detail.
- [`app/README.md`](app/README.md) — the app's architecture, pages, and fixture fallback.
- [`CLAUDE.md`](CLAUDE.md) — the project's working rules (results integrity, methodology
  tracking, writing style) that every contribution — human or agent — follows.
