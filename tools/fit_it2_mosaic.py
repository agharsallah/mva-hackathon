#!/usr/bin/env python3
"""Step 8's measurement: is any chromosome mosaic, and how small an event could we have seen?

Six stages, each independent enough to run alone while the expensive ones are still going:

``constants``  the sample-wide centre and over-dispersion, and the arm-geometry check
``bdev``       fold-over B-deviation and the bias-corrected fraction, per chromosome and arm
``baseline``   the leave-one-chromosome-out depth baseline, and anything that moves it
``models``     the five MAD-seq models per chromosome, by BIC, with Kong's Delta < 10 rule
``limits``     the detection limit per chromosome -- and the same harness run with entry
               037's mean-BAF statistic, which is the only honest way to compare them
``multi``      two and three chromosomes abnormal at once: recovery, and false positives

Every stage writes into ``build/it2/step-8/analysis.json`` under its own key and leaves the
others alone, so a long run can be resumed rather than repeated. ``--stages`` picks them.

Nothing here can write a genomic position: the three warehouse tables it reads were
aggregated to ``(chrom, arm)`` before they were written, so there is no position on the
surface to withhold.

Usage::

    uv run python tools/fit_it2_mosaic.py --stages constants bdev baseline models
    uv run python tools/fit_it2_mosaic.py --stages limits --replicates 200
    uv run python tools/fit_it2_mosaic.py --stages multi --replicates 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))


import it2_step8_common as common
from it2_step8_stages import (
    checkpoint,
    load_analysis,
    stage_baseline,
    stage_bdev,
    stage_constants,
    stage_limits,
    stage_models,
    stage_multi,
    stage_verdicts,
)
from mva.mosaic import madseq

STAGES = ("constants", "bdev", "baseline", "models", "verdicts", "limits", "multi")


def write_tables(analysis: dict[str, Any], out: Path) -> list[Path]:
    """One TSV per exhibit-shaped block, so a figure never re-derives a number."""
    tables = out / "tables"
    written: list[Path] = []
    blocks: dict[str, list[dict[str, Any]]] = {}
    if "bdev" in analysis:
        blocks["it2_mosaic_bdev"] = analysis["bdev"]["whole"]
        blocks["it2_mosaic_bdev_arms"] = analysis["bdev"]["arms"]
        blocks["it2_mosaic_fractions"] = analysis["bdev"]["fractions"]
    if "models" in analysis:
        blocks["it2_mosaic_models"] = analysis["models"]["fits"]
        blocks["it2_mosaic_verdicts"] = analysis["models"]["verdicts"]
    if "multi" in analysis:
        blocks["it2_mosaic_multi"] = analysis["multi"]["designs"]
    if "limits" in analysis:
        blocks["it2_mosaic_limits"] = [
            {
                "chrom": row["chrom"],
                "statistic": row["statistic"],
                "n_sites": row["n_sites"],
                "mean_depth": row["mean_depth"],
                "f80": row["f80"] if row["f80"] is not None else "",
                **{f"power_{key}": value for key, value in row["power"].items()},
            }
            for row in analysis["limits"]["bdev"] + analysis["limits"]["mean_baf"]
        ]
    if "constants" in analysis:
        blocks["it2_mosaic_density"] = analysis["constants"]["density"]
    for name, rows in blocks.items():
        if not rows:
            continue
        # The union of every row's keys, in first-seen order: a block whose rows differ in
        # shape (a power curve that reached f80 beside one that did not) must not lose the
        # columns only some of them carry.
        columns: list[str] = []
        for row in rows:
            columns.extend(key for key in row if key not in columns)
        path = tables / f"{name}.tsv"
        common.write_tsv(path, rows, columns)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=common.DEFAULT_OUT)
    parser.add_argument("--stages", nargs="*", choices=STAGES, default=list(STAGES))
    parser.add_argument(
        "--replicates",
        type=int,
        default=50,
        help="replicates per multi-chromosome design; the limits stage is closed form",
    )
    parser.add_argument(
        "--draws",
        type=int,
        default=0,
        help="null draws per arm for the Bdev test; 0 uses the closed form, above 0 simulates",
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    analysis = load_analysis(args.out)
    sample = common.load()
    print(
        f"loaded: {len(sample.chromosomes)} contigs, "
        f"centre {sample.centre:.5f}, rho {sample.rho:.5f}"
    )

    if "constants" in args.stages:
        analysis["constants"] = stage_constants(sample)
        disagreements = analysis["constants"]["arm_disagreements"]
        print(f"constants: arm geometry disagrees on {len(disagreements) or 'no'} chromosomes")
        checkpoint(analysis, args.out)
    if "bdev" in args.stages:
        analysis["bdev"] = stage_bdev(sample, draws=args.draws)
        flagged = [row["chrom"] for row in analysis["bdev"]["whole"] if row["exceeds_null"]]
        tested = len(analysis["bdev"]["whole"])
        print(f"bdev: {len(flagged)} of {tested} contigs exceed their null: {flagged}")
        checkpoint(analysis, args.out)
    if "baseline" in args.stages:
        analysis["baseline"] = stage_baseline(sample)
        print(
            f"baseline: robust depth {analysis['baseline']['robust']:.2f}x, "
            f"moved by {analysis['baseline']['shifted'] or 'nothing'}"
        )
        checkpoint(analysis, args.out)
    if "models" in args.stages:
        depth_baseline = float(
            analysis.get("baseline", {}).get("robust") or sample.whole_depth("1").mean
        )
        depth_spread = float(
            analysis.get("baseline", {}).get("depth_spread") or madseq.DEFAULT_DEPTH_SD
        )
        analysis["models"] = stage_models(
            sample, depth_baseline=depth_baseline, depth_spread=depth_spread
        )
        calls = [row for row in analysis["models"]["verdicts"] if row["call"] != "normal"]
        print(f"models: {len(calls)} contigs called something other than normal")
        checkpoint(analysis, args.out)
    if "verdicts" in args.stages and "models" not in args.stages:
        analysis["models"] = stage_verdicts(analysis)
        rows = analysis["models"]["verdicts"]
        kinds: dict[str, int] = {}
        for row in rows:
            kinds[row["call"]] = kinds.get(row["call"], 0) + 1
        print(f"verdicts: {kinds}")
        checkpoint(analysis, args.out)
    if "limits" in args.stages:
        analysis["limits"] = stage_limits(sample, replicates=args.replicates)
        checkpoint(analysis, args.out)
    if "multi" in args.stages:
        analysis["multi"] = stage_multi(sample, replicates=args.replicates)
        checkpoint(analysis, args.out)

    common.write_json(args.out / "analysis.json", analysis)
    written = write_tables(analysis, args.out)
    print(f"wrote {args.out / 'analysis.json'} and {len(written)} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
