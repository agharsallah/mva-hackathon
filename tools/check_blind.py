#!/usr/bin/env python3
"""Fail when a blind iteration's methodology entry reads something it must not.

Iteration 2 re-derives the case from the raw reads, the VCF and the eight HPO terms as if
no candidate were known. The blinding is procedural, not secret, and
:mod:`mva.science.blind` is the machine that audits it: every entry must carry an
``## Inputs`` section, and none may name an iteration-1 candidate table before the
unblinding entry exists.

**Why this is a separate tool from** ``mva-science check --blind``. That verb checks two
different things at once: the register (does every settled claim have an evidence row, has
a coordinate leaked into it) and the entries. The register half needs the warehouse; the
entry half needs only the filesystem. Splitting them is what lets the entry half join
``tools/check-python.sh`` and run in CI, on a laptop with no database, and in the pre-push
hook — which matters, because this gate was red for a day while every gate CI runs was
green, and nothing connected the two.

The register half still runs under ``uv run mva-science check --blind iteration2`` and
needs a warehouse connection.

Usage::

    uv run python tools/check_blind.py
    uv run python tools/check_blind.py --iteration iteration2 --quiet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.science import blind
from mva.science.steps import ITERATION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", type=Path, default=Path("docs"), help="where the step folders are"
    )
    parser.add_argument("--iteration", default=ITERATION)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = blind.check(args.root, args.iteration)
    if not report.entries and not args.quiet:
        print(f"blind gate: no {args.iteration} entries yet")
        return 0
    for problem in report.problems:
        print(f"  {problem}")
    if report.problems:
        print(
            f"blind gate: {len(report.problems)} problem(s) in {args.iteration}",
            file=sys.stderr,
        )
        return 1
    if not args.quiet:
        state = "still blind" if report.blind else f"unblinded by {report.unblinded_by}"
        print(
            f"blind gate: {len(report.entries)} {args.iteration} entries, "
            f"every one declaring its inputs — {state}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
