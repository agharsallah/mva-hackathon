#!/usr/bin/env python3
"""Every number step 3's figures and entry quote, pulled once into one file.

The figures read this and nothing else, so a chart cannot drift from the entry beside it,
and ``tools/check_figures_fresh.py`` fails any figure older than this file. That is the
whole reason it exists as a separate stage rather than each renderer querying for itself.

**Aggregates only.** The same constraint as ``GET /api/steps/step-3``: a genotype is a gene,
an ordinal and two counts, and the probe sequences never leave ``build/``. Nothing written
here carries a position, so ``tools/check_coordinates.py`` has nothing to catch even though
this file is gitignored.

Usage::

    uv run python tools/export_it2_step3_analysis.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.viz.steps_it2_step3 import BLOCKS, _contrast
from mva.warehouse.postgres import attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-3/analysis.json")

#: Summaries the run wrote that belong beside the SQL, so the entry has one place to read.
SIDECARS = {
    "probes_summary": "probes-summary.json",
    "counts_summary": "counts-summary.json",
    "genotype_summary": "genotype-summary.json",
    "copynumber_summary": "copynumber-summary.json",
    "mapq_summary": "mapq-summary.json",
    "kernel_check": "kernel-check.json",
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
                # Recorded rather than raised: step 3's stages land one at a time, and a
                # figure whose input is absent is skipped, never drawn empty.
                data[name] = []
                print(f"  {name}: unavailable ({type(error).__name__})")
    if data.get("confirmation"):
        data["contrast"] = _contrast(data["confirmation"])  # type: ignore[arg-type]

    build = args.out.parent
    for key, filename in SIDECARS.items():
        path = build / filename
        if path.is_file():
            data[key] = json.loads(path.read_text(encoding="utf-8"))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")
    filled = [name for name, value in data.items() if value]
    print(f"wrote {args.out}  ({len(filled)} of {len(BLOCKS) + len(SIDECARS) + 1} sections filled)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
