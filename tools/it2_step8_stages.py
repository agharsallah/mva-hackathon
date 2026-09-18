#!/usr/bin/env python3
"""Step 8's six stages, each independent enough to run while the slow ones are still going.

Separated from ``tools/fit_it2_mosaic.py`` so that file is the driver -- arguments, order,
checkpointing -- and this one is what each stage actually measures. The split is also what
keeps both under the size gate.

Every stage writes into ``build/it2/step-8/analysis.json`` under its own key and leaves the
others alone, so a long run can be resumed rather than repeated. ``verdicts`` is the one that
reads rather than measures: the five-model stage is an hour of nested optimisation and the
rule for reading its output changed twice after it had run, so re-deciding is a separate verb
from re-fitting.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

import it2_step8_common as common
from mva.mosaic import arms, baseline, bdev, madseq, simulate, variegated
from mva.mosaic import verdict as verdict_module

#: The fractions the multi-chromosome designs inject at, and how many contigs at once.
MULTI_FRACTIONS = (0.05, 0.10, 0.20)
MULTI_DESIGNS: tuple[tuple[str, ...], ...] = (("7",), ("7", "18"), ("7", "18", "21"))


def load_analysis(out: Path) -> dict[str, Any]:
    path = out / "analysis.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def checkpoint(analysis: dict[str, Any], out: Path) -> None:
    """Merge this run's stages into the file on disk, and write after every stage.

    Two failures this prevents, both met in practice. A crash in the last stage used to throw
    away the first four, which turns a resumable run into a repeated one -- and the resume
    path is the whole reason each stage writes under its own key.

    And a long run holds the document it loaded at *start*. While the models stage was
    fitting, a second process re-decided the verdicts from its output and wrote them; the
    first process would then have finished its next stage and written its hour-old copy back
    over them. Merging rather than overwriting means a stage only ever claims its own key,
    which is what "independent stages" was supposed to mean all along.
    """
    on_disk = load_analysis(out)
    on_disk.update(analysis)
    common.write_json(out / "analysis.json", on_disk)


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
        started = time.perf_counter()
        fitted = madseq.fit_models(
            alleles,
            depth,
            rho=sample.rho,
            centre=sample.centre,
            baseline_depth=depth_baseline,
            depth_spread=depth_spread,
        )
        fits.extend(fit.as_dict() for fit in fitted)
        verdict = verdict_module.best(fitted)
        verdicts.append(verdict.as_dict())
        # Per contig, because this stage is the slow one -- five nested fits over tens of
        # thousands of rows each -- and a run with no output is a run nobody can tell from
        # a hang.
        print(
            f"  chr{chrom:<3} {alleles.n_sites:>9,} sites  {verdict.call:<22} "
            f"dBIC={verdict.delta_bic:>8.1f}  noise={verdict.noise_share:.4f}  "
            f"({time.perf_counter() - started:.0f}s)",
            flush=True,
        )
    return {
        "fits": fits,
        "verdicts": verdicts,
        "baseline_depth": round(depth_baseline, 3),
        "depth_spread": round(depth_spread, 5),
    }


def stage_verdicts(analysis: dict[str, Any]) -> dict[str, Any]:
    """Re-decide the verdicts from fits already on disk, without refitting anything.

    The five-model stage is an hour of nested optimisation and the rule for reading its
    output changed twice after it had run — once for the noise gate, once for the degeneracy
    one. Re-fitting to apply a new rule would be re-measuring to re-interpret, which is the
    thing an append-only record exists to prevent. This reads ``models.fits``, rebuilds the
    fits and asks :func:`mva.mosaic.verdict.best` again.
    """
    stored = (analysis.get("models") or {}).get("fits") or []
    if not stored:
        raise SystemExit("no fits on disk: run --stages models first")
    by_chrom: dict[str, list[madseq.ModelFit]] = {}
    for row in stored:
        by_chrom.setdefault(str(row["chrom"]), []).append(
            madseq.ModelFit(
                chrom=str(row["chrom"]),
                model=str(row["model"]),
                fraction=float(row["fraction"]),
                tract=float(row["tract"]),
                rho=float(row.get("rho", float("nan"))),
                noise_share=float(row.get("noise_share", 0.0)),
                depth_dispersion=float(row["depth_dispersion"]),
                allele_log_likelihood=float(row["log_likelihood"])
                - float(row.get("depth_log_likelihood", 0.0)),
                depth_log_likelihood=float(row.get("depth_log_likelihood", 0.0)),
                parameters=int(row["parameters"]),
                observations=int(row["observations"]),
            )
        )
    verdicts = [verdict_module.best(tuple(fits)).as_dict() for fits in by_chrom.values()]
    analysis["models"]["verdicts"] = verdicts
    return analysis["models"]


def stage_limits(sample: common.Sample, *, replicates: int) -> dict[str, Any]:
    """The detection limit per chromosome, for the fold-over statistic and for 037's.

    Both statistics are evaluated on the same depth margin under the same over-dispersion,
    so the only difference between the two curves is the quantity being averaged. 037's is
    scored two-sided, which is the generous reading of it: a mosaic gain could have moved a
    mean either way and that entry would have reported either.
    """
    folded: list[dict[str, Any]] = []
    mean: list[dict[str, Any]] = []
    for chrom in sample.chromosomes:
        histogram = sample.whole_alleles(chrom)
        if not histogram.n_sites:
            continue
        folded.append(
            simulate.power_curve(histogram, rho=sample.rho, centre=sample.centre).as_dict()
        )
        mean.append(
            simulate.power_curve(
                histogram, rho=sample.rho, centre=sample.centre, name="mean_baf"
            ).as_dict()
        )
        print(
            f"  chr{chrom:<3} {histogram.n_sites:>9,} sites  "
            f"f80 bdev={folded[-1]['f80']}  mean={mean[-1]['f80']}",
            flush=True,
        )
    return {
        "bdev": folded,
        "mean_baf": mean,
        # Zero draws: both curves are computed in closed form. The column stays so a reader
        # of the table can see that, rather than having to know it.
        "replicates": 0,
        "grid": list(simulate.GRID),
    }


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
            results = variegated.multi_chromosome(
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
            centres = [item.centre for item in results]
            rhos = [item.rho for item in results]
            designs.append(
                {
                    "fraction": fraction,
                    "affected": list(design),
                    "n_affected": len(design),
                    "recall": round(recall, 4),
                    "false_positive_rate": round(false_rate, 4),
                    "replicates": replicates,
                    "chromosomes_tested": results[0].tested,
                    # What the injected chromosomes did to the two constants a real run
                    # would have fitted -- the mechanism behind any false positive here.
                    "refit_centre": round(float(np.mean(centres)), 5),
                    "refit_rho": round(float(np.mean(rhos)), 5),
                    "seconds": round(time.perf_counter() - started, 1),
                }
            )
            print(
                f"  f={fraction:<6} {len(design)} affected  recall={recall:.2f}  "
                f"false positives={false_rate:.3f}  ({designs[-1]['seconds']}s)",
                flush=True,
            )
    return {"designs": designs, "replicates": replicates}
