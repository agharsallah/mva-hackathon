#!/usr/bin/env python3
"""Step 7's enrichment pass: from the snapshot tables to a ranked, rung-graded shortlist.

    uv run python tools/track2_enrich.py                # everything, into ressources/track2/
    uv run python tools/track2_enrich.py --skip-live    # re-grade from the tables on disk

The work is :func:`mva.drugs.enrich.run`; this is its command line. Writes, beside the
snapshot's five tables: ``drug_mechanism_literature.tsv``, ``pediatric_trials.tsv``,
``labels.json``, ``evidence_ladder.tsv``, ``shortlist.tsv``, ``do_not.tsv`` and
``decoy_comparison.tsv`` - each with a provenance manifest - plus ``build/track2/analysis.json``
for the methodology entry and the figures. No genomic position exists anywhere in the inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.drugs.enrich import DEFAULT_ANALYSIS, run
from mva.drugs.mechanism import DEFAULT_CARD
from mva.drugs.snapshot import DEFAULT_OUT_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--card", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--refresh", action="store_true", help="bypass the HTTP cache")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="no PubMed / ClinicalTrials.gov / openFDA requests; re-grade from the tables",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        args.card,
        args.dir,
        analysis_path=args.analysis,
        refresh=args.refresh,
        skip_live=args.skip_live,
        progress=print,
    )
    keys = ("rows", "ladder_rows_by_rung", "ladder_drugs_by_max_rung", "pediatric_summary")
    print(json.dumps({k: result.analysis[k] for k in keys}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
