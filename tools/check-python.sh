#!/usr/bin/env sh
# The whole Python gate, in the order CI runs it. `app/` has `pnpm run check`; this is its
# counterpart for the root package, and the pre-push hook and the CI job both call it, so
# there is exactly one definition of "the Python half is green".
#
#   tools/check-python.sh          # every gate
#   tools/check-python.sh --fix    # format and autofix first, then check
#
# There is no test suite on this branch: the repository was stripped of its previous case
# and nothing new has been built yet. These gates are static analysis only.
set -e

cd "$(dirname "$0")/.."

if [ "${1:-}" = "--fix" ]; then
  echo "==> ruff format"
  uv run ruff format src tools
  echo "==> ruff check --fix"
  uv run ruff check --fix src tools
fi

echo "==> ruff format --check"
uv run ruff format --check src tools

echo "==> ruff check"
uv run ruff check src tools

echo "==> module size"
uv run python tools/check_module_size.py

echo "==> import layering"
uv run lint-imports

echo "==> mypy"
uv run mypy

echo "python gate: green"
