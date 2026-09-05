#!/usr/bin/env python3
"""Turn a committed, coordinate-free selector spec into the gitignored submission spec.

    uv run python tools/resolve_submission_spec.py \\
        --selectors submissions/track1/iteration-1/spec.selectors.json \\
        --out build/submission/spec.json

Reads ``alleles`` as selectors (see :mod:`mva.warehouse.submission_spec`), resolves each to
one ``(chrom, pos, ref, alt)`` in the warehouse, and writes the spec
:mod:`tools.design_submission` consumes: the same ``rows`` and ``hypotheses``, the alleles
replaced by coordinates. Prints one line per allele **without** the position — the file is
the only place a coordinate lands. With ``--check`` it compares against an existing spec
and reports whether every allele resolved to the same coordinates (again without printing
them), so a rebuilt spec can be proven identical to the one a submission was built from.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mva.warehouse.settings import Postgres
from mva.warehouse.submission_spec import SelectorError, resolve_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--selectors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="the spec to write (gitignored)")
    parser.add_argument(
        "--check",
        type=Path,
        help="an existing spec; report whether every allele resolves to the same coordinates",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = json.loads(args.selectors.read_text(encoding="utf-8"))
    try:
        alleles = resolve_all(Postgres.from_env(), raw["alleles"])
    except SelectorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for name, allele in alleles.items():
        print(f"  {name:<14} chr{allele.chrom}  {allele.ref}>{allele.alt}  (position withheld)")

    spec = {
        "_source": str(args.selectors),
        "alleles": {name: allele.to_json() for name, allele in alleles.items()},
        "rows": raw["rows"],
        "hypotheses": raw["hypotheses"],
    }
    if args.check and args.check.is_file():
        existing = json.loads(args.check.read_text(encoding="utf-8"))["alleles"]
        same = {name: existing.get(name) == allele.to_json() for name, allele in alleles.items()}
        missing = sorted(set(existing) - set(alleles))
        verdict = "identical" if all(same.values()) and not missing else "DIFFERENT"
        print(f"check against {args.check}: {verdict}")
        for name, ok in same.items():
            if not ok:
                print(f"  {name}: differs from the existing spec")
        for name in missing:
            print(f"  {name}: in the existing spec, not among the selectors")
        if verdict != "identical":
            return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}  ({len(alleles)} alleles, {len(raw['rows'])} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
