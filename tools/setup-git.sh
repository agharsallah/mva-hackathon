#!/usr/bin/env sh
# One-time (idempotent) git configuration for this clone. Everything here is
# repo-local (.git/config) and reversible — nothing touches the user's global
# config, and re-running it is a no-op.
#
# Run it after cloning:  sh tools/setup-git.sh
# It also runs automatically from app/package.json's "prepare" script, so a
# `pnpm install` in app/ wires a fresh clone without anyone remembering to.
set -e

git rev-parse --git-dir >/dev/null 2>&1 || {
  echo "setup-git: not inside a git repository" >&2
  exit 1
}
root=$(git rev-parse --show-toplevel)
cd "$root"

set_config() {
  current=$(git config --local --get "$1" 2>/dev/null || true)
  if [ "$current" = "$2" ]; then
    printf 'setup-git: %-24s already %s\n' "$1" "$2"
  else
    git config --local "$1" "$2"
    printf 'setup-git: %-24s set to %s\n' "$1" "$2"
  fi
}

# Hooks. husky owns .husky/_ and points core.hooksPath at it; this is the
# fallback for a clone that has never run `pnpm install`, so a Python-only
# contributor still gets the commit-msg and pre-commit gates.
if [ ! -d .husky/_ ]; then
  set_config core.hooksPath .husky
else
  set_config core.hooksPath .husky/_
fi

# The message template shown in the editor on a bare `git commit`.
set_config commit.template .gitmessage

# `git blame` skips the two formatting-only commits (GitHub does this by file
# name already; this makes the local blame agree with the web one).
set_config blame.ignoreRevsFile .git-blame-ignore-revs

# History stays linear: a `git pull` rebases instead of recording a merge
# commit, matching the zero-merge history the repo has kept so far.
set_config pull.rebase true

# Deleted remote branches stop haunting `git branch -a`.
set_config fetch.prune true

echo "setup-git: done — hooks, commit template, blame-ignore and rebase-pull are configured"
