#!/usr/bin/env python3
"""Every number step 6's figures and entries quote, pulled once into one file.

The figures read this and nothing else, so a chart cannot drift from the entry beside it,
and ``tools/check_figures_fresh.py`` fails any figure older than this file. That is the whole
reason it exists as a separate stage rather than each renderer querying for itself.

**No coordinate anywhere.** The same constraint as ``GET /api/steps/step-6``: a pair is a
gene, two consequence classes and two dbSNP identifiers, and a route is a name.

Usage::

    uv run python tools/export_it2_step6_analysis.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.viz.steps_it2_step6 import BLOCKS
from mva.warehouse.postgres import attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-6/analysis.json")

#: The stage summaries that belong beside the SQL: the freeze receipt, the upload arithmetic
#: and the unblinding decision. Unlike the served payload these keep every key — a reviewer
#: reading an entry wants the rows the chart was built from, not the page's subset.
SIDECARS = {
    "fusion": "fusion.json",
    "assessment": "upload-assessment.json",
    "decision": "decision.json",
}


def rows(connection, sql: str) -> list[dict]:
    cursor = connection.execute(sql.replace("{src}", "pg.warehouse").replace("{res}", "pg.results"))
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    data: dict[str, object] = {}
    with attached(settings, read_only=True) as connection:
        for name, sql in BLOCKS.items():
            try:
                data[name] = rows(connection, sql)
            except Exception as error:
                # Recorded rather than raised: a figure whose input is absent is skipped,
                # never drawn empty.
                data[name] = []
                print(f"  {name}: unavailable ({type(error).__name__})")

    build = args.out.parent
    for key, filename in SIDECARS.items():
        path = build / filename
        if path.is_file():
            data[key] = json.loads(path.read_text(encoding="utf-8"))
        else:
            data[key] = {}
            print(f"  {key}: {path} absent")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n", "utf-8")
    filled = [name for name, value in data.items() if value]
    print(f"wrote {args.out} ({len(filled)} of {len(data)} blocks filled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
