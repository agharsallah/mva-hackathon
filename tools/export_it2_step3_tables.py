#!/usr/bin/env python3
"""Assemble step 3's warehouse tables from what the stages wrote, and say what is missing.

Four of the six tables are written by the stage that produced them —
``tools/fit_it2_genotypes.py`` writes the genotypes, the calibration and the probe summary,
``tools/measure_it2_copynumber.py`` writes the two copy-number tables. This tool does the
remaining one, checks the set, and refuses to pretend a stage ran when it did not.

``it2_mapq_profile`` is the one written here: stage 0 produced ``mapq.tsv`` before any
schema existed for it, and its columns are already exactly what the warehouse wants.

**A missing table is reported, never created empty.** An empty table and a stage that did
not run look identical in SQL, and only one of them is a result.

Usage::

    uv run python tools/export_it2_step3_tables.py
    uv run mva-warehouse pg-load-it2-step3
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.warehouse.it2_step3_tables import SCHEMAS

DEFAULT_OUT = Path("build/it2/step-3")

#: Table -> the file the stage that produced it wrote, relative to the build directory.
FROM_STAGE: dict[str, str] = {"it2_mapq_profile": "mapq.tsv"}

#: Table -> the tool a reader should run when it is absent.
PRODUCED_BY: dict[str, str] = {
    "it2_mapq_profile": "tools/measure_it2_mapq.py",
    "it2_kmer_probes": "tools/fit_it2_genotypes.py",
    "it2_kmer_calibration": "tools/fit_it2_genotypes.py",
    "it2_kmer_genotypes": "tools/fit_it2_genotypes.py",
    "it2_exon_cn": "tools/measure_it2_copynumber.py",
    "it2_cn_null": "tools/measure_it2_copynumber.py",
}


def rows_in(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    tables = args.out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    for table, source in FROM_STAGE.items():
        origin = args.out / source
        if origin.is_file():
            shutil.copyfile(origin, tables / f"{table}.tsv")

    print(f"{'table':>24} {'rows':>10}")
    missing: list[str] = []
    for table in SCHEMAS:
        path = tables / f"{table}.tsv"
        if not path.is_file():
            missing.append(table)
            print(f"{table:>24} {'-':>10}   (absent — run {PRODUCED_BY[table]})")
            continue
        print(f"{table:>24} {rows_in(path):>10,}")

    print(f"\nwrote {tables}")
    if missing:
        print(f"{len(missing)} of {len(SCHEMAS)} tables are absent; the load will skip them")
    print("next: uv run mva-warehouse pg-load-it2-step3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
