#!/usr/bin/env python3
"""Stage 3-4 of step 3 — fit the genotype model, then read every allele through it.

The model is fitted on markers whose answer the delivered callset already settled, and then
applied to alleles it has never seen: the ones step 2's two callers found, the 1,199 the
vendor's pipeline never reported, and every ClinVar pathogenic allele of a target or decoy
gene. Nothing in that chain contains an aligner or a caller, which is the whole point — where
this agrees with step 2 the allele has survived a genuinely disjoint instrument, and where it
disagrees, the disagreement is the finding.

**An allele's count is the median over its probes, not the sum.** Summing three probes would
treble the apparent depth and make the model confident about nothing in particular. The
median is also why three probes are designed: a probe killed by another variant this child
carries a few bases away returns zero, and a median of three survives one zero where a mean
would not.

**Probe agreement is computed probe by probe.** H024 asks that all of an allele's probes
agree, and that is only evidence if each one voted separately — pooling first would hide
exactly the disagreement a private neighbouring variant produces.

**Reachability travels with every call.** Entry 093 measured which genes the aligner could
place reads in and which the bait reaches; a genotype in an unreachable gene is reported with
that flag, never silently dropped and never read as a finding.

Usage::

    uv run python tools/fit_it2_genotypes.py
    uv run python tools/fit_it2_genotypes.py --floor 0.99
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.kmer.genotype import (
    CLASSES,
    DEFAULT_FLOOR,
    Fit,
    Genotype,
    dropout,
    fit,
    minimum_count,
    per_probe_agreement,
    posteriors,
)
from mva.warehouse.postgres import ALIAS, attached
from mva.warehouse.settings import Postgres

DEFAULT_OUT = Path("build/it2/step-3")

#: The genotype the delivered callset and step 2's callers spell for each class.
CALLER_CLASS = {
    "0/1": Genotype.HET,
    "1/0": Genotype.HET,
    "0|1": Genotype.HET,
    "1|0": Genotype.HET,
    "1/1": Genotype.HOM_ALT,
    "1|1": Genotype.HOM_ALT,
}

CALLER_SQL = f"""
    SELECT chrom, pos, ref, alt, string_agg(DISTINCT genotype, ',') AS genotypes
    FROM {ALIAS}.results.it2_read_alleles
    GROUP BY chrom, pos, ref, alt
"""

LABELS = {
    Genotype.HOM_REF: "hom-ref",
    Genotype.HET: "het",
    Genotype.HOM_ALT: "hom-alt",
    Genotype.NO_CALL: "no-call",
}


def per_allele(values: np.ndarray, allele: np.ndarray, alleles: int) -> np.ndarray:
    """Median probe count per allele, rounded to a whole number.

    Median, not sum: see the module docstring. Rounded, because the negative binomial is a
    distribution over *counts* and has zero probability everywhere else — the median of an
    even number of probes is ``x.5``, which makes every class impossible at once. That is
    not hypothetical: 22,475 of these alleles have two surviving probes, and before the
    rounding they came out of the model as a silent "homozygous reference".
    """
    out = np.zeros(alleles, dtype=float)
    order = np.argsort(allele, kind="stable")
    grouped_allele = allele[order]
    grouped_value = values[order].astype(float)
    edges = np.flatnonzero(np.diff(grouped_allele)) + 1
    for chunk, index in zip(
        np.split(grouped_value, edges), grouped_allele[np.concatenate([[0], edges])], strict=True
    ):
        out[index] = float(np.round(np.median(chunk)))
    return out


def load_alleles(out: Path) -> pl.DataFrame:
    return pl.read_csv(out / "alleles.tsv", separator="\t", infer_schema_length=0).with_columns(
        pl.col("allele_index").cast(pl.Int64),
        pl.col("pos").cast(pl.Int64),
        pl.col("probes").cast(pl.Int64),
    )


def caller_genotypes(settings: Postgres) -> dict[tuple[str, int, str, str], str]:
    with attached(settings, read_only=True) as connection:
        rows = connection.execute(CALLER_SQL).fetchall()
    return {(str(c), int(p), str(r), str(a)): str(g) for c, p, r, a, g in rows}


def tiers(out: Path) -> dict[str, tuple[str, bool]]:
    """Gene -> (tier, reachable), from the stage-0 profile."""
    frame = pl.read_csv(out / "mapq.tsv", separator="\t", infer_schema_length=0)
    return {
        row["symbol"]: (row["tier"], row["reachable"] == "True")
        for row in frame.iter_rows(named=True)
    }


def write_calibration(tables: Path, fitted: Fit, floor: float, min_probes: int, fp: float) -> Path:
    """The fitted model and its quality checks, as metric rows the dashboard can render."""
    rows = [
        ("fit", name, float(value), note)
        for name, value, note in (
            ("lambda_per_copy", fitted.lambda_per_copy, "mean alternate count of het markers"),
            ("lambda_from_reference", fitted.lambda_from_reference, "same markers, reference side"),
            ("side_disagreement", fitted.side_disagreement, "relative gap between the two"),
            ("expected_depth", fitted.expected_depth, "2 x lambda; read against 44.08x measured"),
            ("dispersion", fitted.dispersion, "negative-binomial size, MLE at the fitted mean"),
            ("variance_to_mean", fitted.variance_to_mean, "Poisson predicts 1"),
            ("error_rate", fitted.error_rate, "reference counts at hom-alt markers"),
            ("het_markers", fitted.het_markers, "calibration markers, het"),
            ("hom_alt_markers", fitted.hom_alt_markers, "calibration markers, hom-alt"),
            ("dropout_one_copy", dropout(fitted, 1), "P(count=0 | present at one copy)"),
            (
                "minimum_count",
                minimum_count(fitted, false_positive=fp),
                f"alternate count an absent allele reaches with p<{fp}",
            ),
            ("posterior_floor", floor, "a call must reach this"),
            ("minimum_probes", min_probes, "below this, no-call whatever the counts"),
        )
    ]
    path = tables / "it2_kmer_calibration.tsv"
    pl.DataFrame(rows, schema=["stage", "metric", "value", "note"], orient="row").write_csv(
        path, separator="\t"
    )
    return path


def write_probe_summary(tables: Path, frame: pl.DataFrame, minimum_probes: int) -> Path:
    """Probes surviving per gene and allele source, including the alleles that got none."""
    path = tables / "it2_kmer_probes.tsv"
    (
        frame.group_by(["symbol", "origin"])
        .agg(
            pl.len().alias("alleles"),
            pl.col("probes").sum().alias("probes_kept"),
            (pl.col("probes") >= minimum_probes).sum().alias("alleles_fully_probed"),
            (pl.col("probes") == 0).sum().alias("alleles_without_probe"),
        )
        .with_columns(pl.col("probes_kept").alias("probes_designed"))
        .select(
            [
                "symbol",
                "origin",
                "alleles",
                "probes_designed",
                "probes_kept",
                "alleles_fully_probed",
                "alleles_without_probe",
            ]
        )
        .write_csv(path, separator="\t")
    )
    return path


def fit_on_calibration(ref: np.ndarray, alt: np.ndarray, frame: pl.DataFrame, floor: int) -> Fit:
    """Read the model off the markers whose class the delivered callset already settled.

    Only markers with a full probe set are used: a marker typed on one probe carries the
    same weight in the fit as one typed on three and has no way to show disagreement.
    """
    origin = frame["origin"].to_numpy().astype(str)
    usable = frame["probes"].to_numpy() >= floor
    het = (np.char.find(origin, "calibration-het") >= 0) & usable
    hom = (np.char.find(origin, "calibration-hom-alt") >= 0) & usable
    return fit(ref[het], alt[het], ref[hom], alt[hom])


def agreement_per_allele(stored, fitted: Fit, best: np.ndarray, alleles: int) -> np.ndarray:
    """How many of each allele's probes vote for the class the allele was called.

    Probe by probe, because H024's "all probes agree" is only evidence if each one could
    have disagreed — pooling the counts first hides exactly the disagreement a private
    neighbouring variant produces.
    """
    votes, _ = per_probe_agreement(
        stored["ref_fragments"].astype(float), stored["alt_fragments"].astype(float), fitted
    )
    agreeing = np.zeros(alleles, dtype=np.int64)
    for index, vote in zip(stored["allele"], votes, strict=True):
        if int(vote) == int(best[int(index)]):
            agreeing[int(index)] += 1
    return agreeing


def genotype_rows(
    frame: pl.DataFrame,
    ref: np.ndarray,
    alt: np.ndarray,
    called: list[Genotype],
    strength: np.ndarray,
    agreeing: np.ndarray,
    callers: dict[tuple[str, int, str, str], str],
    tier_of: dict[str, tuple[str, bool]],
) -> list[dict[str, object]]:
    """One coordinate-free row per allele: a gene, an ordinal within it, and counts."""
    rows: list[dict[str, object]] = []
    ordinal: dict[str, int] = defaultdict(int)
    probes = frame["probes"].to_numpy()
    for index, row in enumerate(frame.iter_rows(named=True)):
        symbol = str(row["symbol"])
        ordinal[symbol] += 1
        spelled = callers.get((row["chrom"], row["pos"], row["ref"], row["alt"]), "")
        expected = {CALLER_CLASS.get(part) for part in spelled.split(",") if part}
        tier, reachable = tier_of.get(symbol, ("", False))
        rows.append(
            {
                "symbol": symbol,
                "tier": tier,
                "origin": row["origin"],
                "allele_ordinal": ordinal[symbol],
                "novel": "reads-novel" in str(row["origin"]),
                "probes": int(probes[index]),
                "probes_agreeing": int(agreeing[index]),
                "ref_count": round(float(ref[index])),
                "alt_count": round(float(alt[index])),
                "call": LABELS[called[index]],
                "posterior": round(float(strength[index]), 6),
                "caller_genotype": spelled,
                "confirms_caller": bool(expected) and called[index] in expected,
                "reachable": reachable,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--floor", type=float, default=DEFAULT_FLOOR)
    parser.add_argument("--minimum-probes", type=int, default=3)
    parser.add_argument("--false-positive", type=float, default=1e-3)
    args = parser.parse_args(argv)

    counts_file = args.out / "probe-counts.npz"
    if not counts_file.is_file():
        print(f"missing {counts_file} — run tools/run_it2_step3_counts.py first")
        return 1
    settings = Postgres.from_env()
    if settings.missing:
        print("missing settings: " + ", ".join(settings.missing))
        return 1

    stored = np.load(counts_file)
    frame = load_alleles(args.out)
    alleles = frame.height
    ref = per_allele(stored["ref_fragments"], stored["allele"], alleles)
    alt = per_allele(stored["alt_fragments"], stored["allele"], alleles)

    fitted = fit_on_calibration(ref, alt, frame, args.minimum_probes)
    print(json.dumps(fitted.as_dict(), indent=2, sort_keys=True), flush=True)

    weights = posteriors(ref, alt, fitted)
    best = weights.argmax(axis=-1)
    strength = weights.max(axis=-1)
    probes = frame["probes"].to_numpy()
    called = [
        CLASSES[best[i]]
        if (probes[i] >= args.minimum_probes and strength[i] >= args.floor)
        else Genotype.NO_CALL
        for i in range(alleles)
    ]
    agreeing = agreement_per_allele(stored, fitted, best, alleles)

    rows = genotype_rows(
        frame,
        ref,
        alt,
        called,
        strength,
        agreeing,
        caller_genotypes(settings),
        tiers(args.out),
    )
    tables = args.out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    genotypes = pl.DataFrame(rows)
    genotypes.write_csv(tables / "it2_kmer_genotypes.tsv", separator="\t")
    write_calibration(tables, fitted, args.floor, args.minimum_probes, args.false_positive)
    write_probe_summary(tables, frame, args.minimum_probes)

    summary = {
        "alleles": alleles,
        "fit": fitted.as_dict(),
        "calls": {
            label: int((genotypes["call"] == label).sum())
            for label in ("hom-ref", "het", "hom-alt", "no-call")
        },
        "novel_alleles": int(genotypes["novel"].sum()),
        "novel_confirmed": int((genotypes["novel"] & genotypes["confirms_caller"]).sum()),
        "caller_alleles": int((genotypes["caller_genotype"] != "").sum()),
        "caller_confirmed": int(genotypes["confirms_caller"].sum()),
        "floor": args.floor,
        "minimum_probes": args.minimum_probes,
        "minimum_count": minimum_count(fitted, false_positive=args.false_positive),
    }
    (args.out / "genotype-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
