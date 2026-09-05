#!/usr/bin/env python3
"""Put the Track 2 tables into ``warehouse.data_lineage``.

    uv run python tools/record_track2_lineage.py            # append what is missing
    uv run python tools/record_track2_lineage.py --dry-run  # print the edges, write nothing

``ressources/track2/*.tsv`` are built from seven public APIs rather than from the delivered
callset, and each already carries a provenance manifest. This appends the same facts as
lineage edges — ``target_schema = 'track2'``, one row per source — so the Track 2 tables
appear in the one ledger every provenance surface in this project already reads, and
``/api/track2`` can show where each table came from.

The work is :mod:`mva.warehouse.track2_lineage`; this is a thin front for it. It lives in
``mva.warehouse`` and not in ``mva.drugs`` because ``mva.drugs`` sits below the warehouse in
the package layering and may not import it — so the recorder reads the manifests off disk.

Appending is idempotent on ``(target_table, source_kind, source_ref, source_sha256)``:
running it twice appends nothing the second time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mva.warehouse.settings import Postgres
from mva.warehouse.track2_lineage import planned_edges, record_tables


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repository root; the manifests are read from <root>/ressources/track2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the edges that would be appended and touch no database",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    edges = planned_edges(args.root)
    if not edges:
        print("no Track 2 manifests found; nothing to record")
        return 1
    if args.dry_run:
        for edge in edges:
            print(
                f"{edge['target_schema']}.{edge['target_table']}"
                f"  {edge['source_kind']:<11}{edge['source_ref']}"
                f"  {edge['source_version']}"
            )
        print(f"{len(edges)} edge(s) planned; nothing written")
        return 0
    recorded = record_tables(Postgres.from_env(), args.root)
    print(recorded.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
