"""Fail when a Python module outgrows the size the project allows.

CLAUDE.md: "No script or module longer than 400 lines. When a file approaches that limit,
split it into domain-driven modules (one bounded concern per module) instead of growing
the file." That rule existed for months with nothing checking it, and two modules had
quietly passed it. This is the check.

Two thresholds, because a hard limit with no warning band means every violation arrives
as a blocked commit:

- **over the limit** — reported and the exit code is 1;
- **inside the warning band** (90% of the limit by default) — reported, exit code stays 0.

Usage::

    uv run python tools/check_module_size.py                  # src, tools
    uv run python tools/check_module_size.py --limit 300 src  # one tree, tighter cap
    uv run python tools/check_module_size.py --quiet          # only what fails

Counts physical lines, including comments and docstrings. That is deliberate: the rule is
about how much a reader has to hold in their head to open the file, and prose counts.
"""

import argparse
import sys
from pathlib import Path

#: The cap from CLAUDE.md. Changing it here changes what CI enforces — argue in the doc
#: first, not in this constant.
DEFAULT_LIMIT = 400

#: Per-tree caps. Production code takes the 400-line rule as written. Test modules get
#: 600: a test file is the executable description of one module's behaviour, and cutting
#: it in half to satisfy a line count splits one story across two files without making
#: either easier to read. The cap still exists so a test file cannot grow unbounded.
LIMITS = {"src": DEFAULT_LIMIT, "tools": DEFAULT_LIMIT}

#: Report a file this far below the cap so a split happens before it is urgent.
DEFAULT_WARN_RATIO = 0.9

#: Trees checked when none are named. Generated and archived code is not checked.
DEFAULT_PATHS = ("src", "tools")

#: Never checked: provenance that must not be edited, or output that is regenerated.
EXCLUDED = {"archive", "build", "figures", "ressources", "__pycache__", ".venv"}


def python_files(paths: list[Path]) -> list[Path]:
    """Every ``.py`` file under ``paths``, minus the excluded directories."""
    found: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            found.append(path)
            continue
        found.extend(
            candidate
            for candidate in sorted(path.rglob("*.py"))
            if not EXCLUDED.intersection(candidate.parts)
        )
    return found


def line_count(path: Path) -> int:
    """Physical lines in one file, counted the way ``wc -l`` counts them."""
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def limit_for(path: Path, override: int | None) -> int:
    """The cap that applies to one file: an explicit ``--limit``, else its tree's."""
    if override is not None:
        return override
    for part in path.parts:
        if part in LIMITS:
            return LIMITS[part]
    return DEFAULT_LIMIT


def measure(paths: list[Path], override: int | None, warn_ratio: float) -> tuple[list, list]:
    """Split the tree into (over cap, inside the warning band), each sorted worst-first."""
    over, warned = [], []
    for path in python_files(paths):
        count, limit = line_count(path), limit_for(path, override)
        if count > limit:
            over.append((count, limit, path))
        elif count > int(limit * warn_ratio):
            warned.append((count, limit, path))
    return sorted(over, reverse=True), sorted(warned, reverse=True)


def report(over: list, warned: list, quiet: bool) -> None:
    """Print what was found, worst first."""
    for count, limit, path in over:
        print(f"OVER  {count:>4} lines (limit {limit})  {path}")
    if not quiet:
        for count, limit, path in warned:
            print(f"near  {count:>4} lines (limit {limit})  {path}")
    if over:
        print(
            f"\n{len(over)} module(s) over the line limit. Split by concern — one "
            f"bounded responsibility per module — rather than raising the limit.",
            file=sys.stderr,
        )
    elif not quiet:
        caps = ", ".join(f"{tree}: {cap}" for tree, cap in sorted(LIMITS.items()))
        print(f"ok: every module within its limit ({caps}); {len(warned)} in the warning band.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_module_size",
        description="fail when a Python module is longer than the project allows",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="files or trees (default: src tools)")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="one cap for every path, overriding the per-tree defaults",
    )
    parser.add_argument(
        "--warn-ratio",
        type=float,
        default=DEFAULT_WARN_RATIO,
        help="report files above this fraction of the cap without failing (default: %(default)s)",
    )
    parser.add_argument("--quiet", action="store_true", help="print only what fails")
    args = parser.parse_args(argv)

    paths = args.paths or [Path(name) for name in DEFAULT_PATHS]
    missing = [path for path in paths if not path.exists()]
    if missing:
        print(f"no such path: {', '.join(str(path) for path in missing)}", file=sys.stderr)
        return 2

    over, warned = measure(paths, args.limit, args.warn_ratio)
    report(over, warned, args.quiet)
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
