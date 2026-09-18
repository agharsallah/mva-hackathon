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
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

import it2_step8_common as common
from mva.mosaic import arms, baseline, bdev, madseq, simulate

STAGES = ("constants", "bdev", "baseline", "models", "limits", "multi")

#: The fractions the multi-chromosome designs inject at, and how many chromosomes at once.
MULTI_FRACTIONS = (0.05, 0.10, 0.20)
MULTI_DESIGNS: tuple[tuple[str, ...], ...] = (("7",), ("7", "18"), ("7", "18", "21"))


def _load_analysis(out: Path) -> dict[str, Any]:
    path = out / "analysis.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def stage_constants(sample: common.Sample) -> dict[str, Any]:
    """The two fitted constants, and whether the committed arm geometry matches the data."""
    checks = arms.check(sample.geometry, sample.bins)
    return {
        **sample.constants(),
        "arm_check": [item.as_dict() for item in checks],
        "arm_disagreements": [item.chrom for item in arms.disagreements(checks)],
        "density": sample.density,
    }


def stage_bdev(sample: common.Sample, *, draws: int) -> dict[str, Any]:
    """Every chromosome whole, and every tested arm, against its own simulated null."""
    whole: list[dict[str, Any]] = []
    per_arm: list[dict[str, Any]] = []
    fractions: list[dict[str, Any]] = []
    for index, chrom in enumerate(sample.chromosomes):
        histogram = sample.whole_alleles(chrom)
        result = bdev.bdev(
            histogram, rho=sample.rho, around=sample.centre, draws=draws, seed=common.SEED + index
        )
        whole.append(result.as_dict())
        fractions.append(
            bdev.danfip(
                histogram,
                around=sample.centre,
                rho=sample.rho,
                draws=draws,
                seed=common.SEED + index,
            ).as_dict()
        )
        for offset, arm in enumerate(common.ARMS):
            key = (chrom, arm)
            if key not in sample.alleles:
                continue
            per_arm.append(
                bdev.bdev(
                    sample.alleles[key],
                    rho=sample.rho,
                    around=sample.centre,
                    draws=draws,
                    seed=common.SEED + index * 10 + offset,
                ).as_dict()
            )
    return {"whole": whole, "arms": per_arm, "fractions": fractions, "draws": draws}


def stage_baseline(sample: common.Sample) -> dict[str, Any]:
    """The depth baseline, held out one chromosome at a time.

    Autosomes only. X and Y are hemizygous in this male proband and would drag a median
    that every autosome is then judged against -- which is a different error from the one
    this stage exists to detect, and would mask it.
    """
    depth = {
        chrom: sample.whole_depth(chrom).mean
        for chrom in sample.chromosomes
        if chrom in common.AUTOSOMES
    }
    fitted = baseline.leave_one_out(depth, seed=common.SEED)
    ratios = {chrom: value / fitted.robust for chrom, value in depth.items()}
    sex = {
        chrom: sample.whole_depth(chrom).mean / fitted.robust
        for chrom in ("X", "Y")
        if chrom in sample.chromosomes
    }
    # The spread the depth term is judged against: how much a per-chromosome depth ratio
    # varies across autosomes on this sample. GC content and mappability move it on a
    # perfectly normal genome, so this is the precision floor below which a depth shift is
    # not evidence of anything. Measured, never assumed.
    values = np.array(list(ratios.values()), dtype=float)
    spread = float(np.median(np.abs(values - np.median(values))) * 1.4826)
    return {
        **fitted.as_dict(),
        "per_chromosome_depth": {chrom: round(value, 3) for chrom, value in depth.items()},
        "depth_ratio": {chrom: round(value, 4) for chrom, value in ratios.items()},
        "sex_chromosome_ratio": {chrom: round(value, 4) for chrom, value in sex.items()},
        "depth_spread": round(spread, 5),
        "depth_spread_note": (
            "robust standard deviation (median absolute deviation x 1.4826) of the "
            "per-chromosome depth ratio across autosomes -- the precision floor the "
            "five-model depth term is judged against"
        ),
    }


def stage_models(
    sample: common.Sample, *, depth_baseline: float, depth_spread: float
) -> dict[str, Any]:
    """Five models per chromosome, their BICs, and the verdict Kong's rule allows."""
    fits: list[dict[str, Any]] = []
    verdicts: list[dict[str, Any]] = []
    for chrom in sample.chromosomes:
        alleles = sample.whole_alleles(chrom)
        depth = sample.whole_depth(chrom)
        if not depth.n_sites:
            continue
        fitted = madseq.fit_models(
            alleles,
            depth,
            rho=sample.rho,
            centre=sample.centre,
            baseline_depth=depth_baseline,
            depth_spread=depth_spread,
        )
        fits.extend(fit.as_dict() for fit in fitted)
        verdicts.append(madseq.best(fitted).as_dict())
    return {
        "fits": fits,
        "verdicts": verdicts,
        "baseline_depth": round(depth_baseline, 3),
        "depth_spread": round(depth_spread, 5),
    }


def stage_limits(sample: common.Sample, *, replicates: int) -> dict[str, Any]:
    """The detection limit per chromosome, for the fold-over statistic and for 037's.

    Both statistics see the same draws from the same depths at the same seed, so the only
    difference between the two curves is the line that computes the number.
    """
    folded: list[dict[str, Any]] = []
    mean: list[dict[str, Any]] = []
    for index, chrom in enumerate(sample.chromosomes):
        histogram = sample.whole_alleles(chrom)
        if not histogram.n_sites:
            continue
        seed = common.SEED + index
        started = time.perf_counter()
        folded.append(
            simulate.power_curve(
                histogram,
                rho=sample.rho,
                centre=sample.centre,
                replicates=replicates,
                seed=seed,
            ).as_dict()
        )
        mean.append(
            simulate.power_curve(
                histogram,
                rho=sample.rho,
                centre=sample.centre,
                replicates=replicates,
                seed=seed,
                statistic=simulate.mean_statistic,
                name="mean_baf",
            ).as_dict()
        )
        print(
            f"  chr{chrom:<3} {histogram.n_sites:>9,} sites  "
            f"f80 bdev={folded[-1]['f80']}  mean={mean[-1]['f80']}  "
            f"({time.perf_counter() - started:.1f}s)",
            flush=True,
        )
    return {"bdev": folded, "mean_baf": mean, "replicates": replicates, "grid": list(simulate.GRID)}


def stage_multi(sample: common.Sample, *, replicates: int) -> dict[str, Any]:
    """Two and three chromosomes abnormal at once — recovery, and what gets invented."""
    histograms = {
        chrom: sample.whole_alleles(chrom)
        for chrom in sample.chromosomes
        if chrom in common.AUTOSOMES and sample.whole_alleles(chrom).n_sites
    }
    designs: list[dict[str, Any]] = []
    for fraction in MULTI_FRACTIONS:
        for design in MULTI_DESIGNS:
            started = time.perf_counter()
            results = simulate.multi_chromosome(
                histograms,
                affected=design,
                fraction=fraction,
                rho=sample.rho,
                centre=sample.centre,
                replicates=replicates,
                seed=common.SEED + len(design) * 100 + int(fraction * 1000),
            )
            recall = sum(item.recall for item in results) / len(results)
            false_rate = sum(item.false_positive_rate for item in results) / len(results)
            designs.append(
                {
                    "fraction": fraction,
                    "affected": list(design),
                    "n_affected": len(design),
                    "recall": round(recall, 4),
                    "false_positive_rate": round(false_rate, 4),
                    "replicates": replicates,
                    "chromosomes_tested": results[0].tested,
                    "seconds": round(time.perf_counter() - started, 1),
                }
            )
            print(
                f"  f={fraction:<6} {len(design)} affected  recall={recall:.2f}  "
                f"false positives={false_rate:.3f}  ({designs[-1]['seconds']}s)",
                flush=True,
            )
    return {"designs": designs, "replicates": replicates}


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
        "--replicates", type=int, default=200, help="simulation draws per point (limits, multi)"
    )
    parser.add_argument(
        "--draws", type=int, default=200, help="null draws per arm for the Bdev test"
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    analysis = _load_analysis(args.out)
    sample = common.load()
    print(
        f"loaded: {len(sample.chromosomes)} contigs, "
        f"centre {sample.centre:.5f}, rho {sample.rho:.5f}"
    )

    if "constants" in args.stages:
        analysis["constants"] = stage_constants(sample)
        disagreements = analysis["constants"]["arm_disagreements"]
        print(f"constants: arm geometry disagrees on {len(disagreements) or 'no'} chromosomes")
    if "bdev" in args.stages:
        analysis["bdev"] = stage_bdev(sample, draws=args.draws)
        flagged = [row["chrom"] for row in analysis["bdev"]["whole"] if row["exceeds_null"]]
        tested = len(analysis["bdev"]["whole"])
        print(f"bdev: {len(flagged)} of {tested} contigs exceed their null: {flagged}")
    if "baseline" in args.stages:
        analysis["baseline"] = stage_baseline(sample)
        print(
            f"baseline: robust depth {analysis['baseline']['robust']:.2f}x, "
            f"moved by {analysis['baseline']['shifted'] or 'nothing'}"
        )
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
    if "limits" in args.stages:
        analysis["limits"] = stage_limits(sample, replicates=args.replicates)
    if "multi" in args.stages:
        analysis["multi"] = stage_multi(sample, replicates=args.replicates)

    common.write_json(args.out / "analysis.json", analysis)
    written = write_tables(analysis, args.out)
    print(f"wrote {args.out / 'analysis.json'} and {len(written)} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
