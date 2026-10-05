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

Read from `git log`, not invented — the newest 63 commits all pass the gate below (measured
2026-09-02, `tools/check-commit-msg.sh --range 9295687..HEAD`) and follow:

```
<type>(<scope>): <imperative summary, lowercase, no period>

<body: why, not what — paragraphs and/or bullets. Cite measured numbers
where the commit produced one, e.g. "296.89 kB -> 236.44 kB raw".>
```

- `type`: one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`,
  `chore`, `revert`. **Enforced** by the `commit-msg` hook and the CI `commit messages` job,
  both running [`tools/check-commit-msg.sh`](tools/check-commit-msg.sh) — one script, so local
  and CI can never disagree.
- `scope`: the package or app area touched — `app`, `viz`, `compare`, `panel`, `search`,
  `probes`, `callset`, `fixtures`, `src`, `step-0`, etc. Omit it for a repo-wide change
  (`docs: replace the step-0 references with the toolset page`).
- Body explains _why_ and states any number the change produced or changed — per the repo's
  [Results integrity](CLAUDE.md#results-integrity) rule, a number in a commit message must come
  from a real run.
- **Subject**: imperative, lowercase after the colon, no trailing period, blank line before the
  body. Warns over 72 characters (the width `git log --oneline` shows unwrapped), fails over 90.
- No AI-attribution trailers (`Generated with Claude Code`, `Co-Authored-By: Claude ...`) in new
  commits from this tooling wave — a project-level policy, not a repo-wide ban on any trailer
  that already exists in older history. Enforced by the same gate.
- `Merge …`, `Revert "…"`, `fixup!`, `squash!` and `amend!` subjects are exempt: git writes them.

Check a message before you write it, or an existing one after the fact:

```sh
sh tools/check-commit-msg.sh --rev HEAD          # the last commit
sh tools/check-commit-msg.sh --range main..HEAD  # everything a branch adds
sh tools/check-commit-msg.sh --self-test         # the gate's own 11 cases
```

## What enforces what

| Rule                                                                                           | Enforced by                                                                               | Run it locally                                  |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Commit message convention, subject length, no AI trailer                                       | `commit-msg` hook, CI `commit messages` job                                               | `sh tools/check-commit-msg.sh --rev HEAD`       |
| TypeScript compiles (`tsc -b`, strict, `noUnusedLocals`/`noUnusedParameters`)                  | pre-commit hook (blocks), pre-push hook (advisory), CI `app` job                          | `cd app && pnpm run typecheck`                  |
| ESLint (react-hooks, jsx-a11y, import order, repo-local rules)                                 | pre-commit hook (staged files only, `--fix`), pre-push (advisory), CI `app` job           | `cd app && pnpm run lint:strict` (or `lint:fix` to autofix)       |
| Prettier formatting                                                                            | pre-commit hook (staged files only, `--write`), pre-push (advisory), CI `app` job         | `cd app && pnpm run format` (or `format:check`) |
| Production build (`tsc -b && vite build`)                                                      | pre-push hook (advisory), CI `app` job                                                    | `cd app && pnpm run build`                      |
| Bundle size budget                                                                             | CI `app` job (`app/tools/bundle-budget.mjs`)                                              | `cd app && node tools/bundle-budget.mjs`        |
| Dead code (unused files/exports/deps)                                                          | CI `app` job, **report-only** — see `app/knip.json`                                       | `cd app && pnpm exec knip`                      |
| Ruff format (`ruff format`)                                                                    | pre-commit hook (staged `.py` only, rewrites + re-stages), pre-push (advisory), CI `python` job | `uv run ruff format src tests tools`            |
| Ruff lint (30 rule families, line length 100)                                                  | pre-commit hook (staged `.py` only, `--fix`), pre-push (advisory), CI `python` job        | `uv run ruff check src tests tools`             |
| Module size (400 lines in `src`/`tools`, 600 in `tests`)                                       | pre-commit hook (blocks), pre-push (advisory), CI `python` job                           | `uv run python tools/check_module_size.py`      |
| Import layering (no cycles; the leaf packages import no sibling; nothing depends on `mva.viz`) | pre-commit hook (blocks), pre-push (advisory), CI `python` job                           | `uv run lint-imports`                           |
| mypy (strict, with a per-package ratchet)                                                      | pre-commit hook (blocks), pre-push (advisory), CI `python` job                           | `uv run mypy`                                   |
| `uv.lock` matches `pyproject.toml`                                                             | pre-commit hook (blocks), pre-push (advisory), CI `python` job                           | `uv sync --frozen`                              |

`pnpm run check` in `app/` runs typecheck + lint + format:check + test in one command — the same
four gates CI runs (the pre-push hook runs it as an advisory). `tools/check-python.sh` is its counterpart for
the root package: the same six gates, in CI's order, with `--fix` to format and autofix first.
Why each Python rule is set where it is:
[`docs/notes/python-quality-gates.md`](docs/notes/python-quality-gates.md).

## Git hooks (husky)

Hooks live at the **repo root** `.husky/` (not `app/.husky/`) because git resolves
`core.hooksPath` from the top of the working tree, and one hook has to see staged/pushed files
across both projects to decide whether it needs to run at all.

- **commit-msg** — runs [`tools/check-commit-msg.sh`](tools/check-commit-msg.sh) on the message
  being recorded. POSIX `sh`, no node and no uv: a contributor with only one of the two
  toolchains installed still gets the gate. Cheap enough (a few `grep`s) to be unnoticeable.
- **pre-commit** — **the blocking gate.** Each half runs only when the commit stages a file in it:
  - Python (staged `.py`): `ruff format` + `ruff check --fix` on the staged files (re-staged),
    then `tools/check-python.sh` — every CI gate, mypy included. **There is no test step:
    this branch has no test suite.**
  - `app/` (staged `app/` file): `lint-staged` (`app/.lintstagedrc.json`: `eslint --fix` +
    `prettier --write`), `tsc -b`, and the theme/dictionary checks.
  - Gates read the working tree, not the index: unstaged edits in a touched half count.
- **pre-push** — **advisory, never blocks.** Runs `tools/check-python.sh` if the pushed range
  touches `src/`, `tools/`, `pyproject.toml` or `uv.lock`, and `pnpm run check` +
  `pnpm run build` in `app/` if it touches `app/`; a red gate prints a warning and the push goes
  ahead (CI reports the same). Same range logic as before (falls back to running, never to
  skipping). `SKIP_PUSH_CHECKS=1 git push` skips it for one push.

**One-time setup after cloning:** `sh tools/setup-git.sh`. It is idempotent, repo-local
(`.git/config` only, never your global config) and prints what it changed. It wires:

| Setting                 | Value                     | Why                                                              |
| ----------------------- | ------------------------- | ---------------------------------------------------------------- |
| `core.hooksPath`        | `.husky/_`                | hooks fire at all (falls back to `.husky` before husky has run)  |
| `commit.template`       | `.gitmessage`             | the convention is in the editor, not in your memory              |
| `blame.ignoreRevsFile`  | `.git-blame-ignore-revs`  | `git blame` skips the two formatting-only commits                |
| `pull.rebase`           | `true`                    | a `git pull` rebases; history stays linear                       |
| `fetch.prune`           | `true`                    | deleted remote branches stop haunting `git branch -a`            |

`app/package.json`'s `prepare` script runs `husky` and then this script, so `pnpm install` in
`app/` wires a fresh clone automatically. A Python-only contributor who never runs `pnpm install`
runs `sh tools/setup-git.sh` once instead.

## When a gate fails

1. Read the failing step's output — every gate prints what it checked and why it failed.
2. Fix locally with the "Run it locally" command above, or its `--fix`/`--write` variant
   (`pnpm run lint:fix`, `pnpm run format`).
3. Re-run `pnpm run check` in `app/` (or `tools/check-python.sh` for Python) before pushing again.
4. A **knip** finding is a report, not a blocker — it does not fail CI. Triage it, but don't
   feel compelled to fix it in the same change.
5. If a hook is wrong for your change (e.g. it ran when it shouldn't have, or vice versa),
   that's a bug in `.husky/pre-commit` / `.husky/pre-push` — fix the skip logic, don't bypass the
   hook with `--no-verify`.

## History hygiene

The history is **linear — zero merge commits in 152 commits** — and stays that way by rebasing,
not merging:

```sh
git fetch origin
git rebase origin/main        # or just `git pull`, which rebases after tools/setup-git.sh
```

- **One commit, one concern.** A commit that renames a module *and* changes its behavior cannot be
  reverted, bisected, or reviewed as one idea. Split it: `git add -p`.
- **Rewrite your own branch freely, never `main`.** `git rebase -i` and `git commit --amend`
  before pushing a branch is good practice; force-pushing `main` is not, and would break every
  other clone.
- **Formatting-only commits go in [`.git-blame-ignore-revs`](.git-blame-ignore-revs)** so
  `git blame` keeps attributing lines to the change that wrote them. Add a commit there only if it
  changed zero behavior. GitHub reads the file by name; locally, `tools/setup-git.sh` wires it.
- **The convention starts at `9295687`.** Measured 2026-09-02 with
  `sh tools/check-commit-msg.sh --range <sha>..HEAD`: the newest 63 commits pass the gate; the 89
  before them (the ideation and bootstrap phase) do not. They are left alone on purpose:
  rewriting published history to tidy subject lines would invalidate every clone and every SHA
  cited in `docs/*/methodology/`, which is a worse loss than an untidy prologue.

### Branch protection (GitHub side)

The local gates cannot stop a push made with `--no-verify`; CI can, but only if the branch
requires it.

**Not currently active, and not currently possible.** Checked 2026-09-02:
`gh api repos/agharsallah/mva-hackathon/branches/main/protection` answers
`403 — Upgrade to GitHub Pro or make this repository public to enable this feature`. Branch
protection needs the repo to be public or on a paid plan; this one is private on the free tier.
Until that changes, the `commit-msg` and `pre-commit` hooks are the enforcement and CI is the
visible-but-not-blocking backstop — a red `commit messages` job on `main` means a commit got in
around the hook.

When the repo becomes public or upgrades, require the three CI jobs (`app (node)`,
`python (uv)`, `commit messages`), require linear history, and disallow force-pushes:

```sh
gh api -X PUT repos/:owner/:repo/branches/main/protection \
  -F required_status_checks.strict=true \
  -f 'required_status_checks.contexts[]=app (node)' \
  -f 'required_status_checks.contexts[]=python (uv)' \
  -f 'required_status_checks.contexts[]=commit messages' \
  -F enforce_admins=true \
  -F required_linear_history=true \
  -F allow_force_pushes=false \
  -F required_pull_request_reviews=null \
  -F restrictions=null
```

Set the repository's merge button to **squash or rebase only** (Settings → General → Pull
Requests) so a merge commit cannot be introduced from the web UI.

## More

- [`docs/README.md`](docs/README.md) — the doc index: method, dictionary, roadmap, per-step
  detail.
- [`app/README.md`](app/README.md) — the app's architecture, pages, and fixture fallback.
- [`CLAUDE.md`](CLAUDE.md) — the project's working rules (results integrity, methodology
  tracking, writing style) that every contribution — human or agent — follows.
