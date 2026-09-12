#!/usr/bin/env sh
# The whole Python gate, in the order CI runs it. `app/` has `npm run check`; this is its
# counterpart for the root package, and the pre-push hook and the CI job both call it, so
# there is exactly one definition of "the Python half is green".
#
#   tools/check-python.sh          # every gate
#   tools/check-python.sh --fix    # format and autofix first, then check
#
# Cheap and deterministic gates come before the test suite so a formatting or layering
# mistake fails in seconds rather than after pytest.
set -e

cd "$(dirname "$0")/.."

if [ "${1:-}" = "--fix" ]; then
  echo "==> ruff format"
  uv run ruff format src tests tools
  echo "==> ruff check --fix"
  uv run ruff check --fix src tests tools
fi

echo "==> ruff format --check"
uv run ruff format --check src tests tools

echo "==> ruff check"
uv run ruff check src tests tools

echo "==> module size"
uv run python tools/check_module_size.py

echo "==> import layering"
uv run lint-imports

echo "==> mypy"
uv run mypy

echo "==> coordinate gate"
uv run python tools/check_coordinates.py --quiet

echo "==> blind gate"
uv run python tools/check_blind.py --quiet

echo "==> iteration folders"
uv run python tools/check_iteration.py --quiet

echo "==> pytest"
uv run pytest -q

echo "python gate: green"
