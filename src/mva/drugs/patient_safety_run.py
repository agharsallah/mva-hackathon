"""Running PharmCAT over a callset, and turning its output into a coordinate-free summary.

Split out of the CLI so the orchestration is importable and testable, and so the one place
that touches patient sequence is a named function rather than a command handler.

Two things happen here and nowhere else:

* **the callset is subset to the pharmacogene regions** before PharmCAT sees it. That is a
  speed decision (315 MB of whole-genome VCF versus ~1.5 Mb of PGx intervals) and a
  containment one: every intermediate file lives under the caller's ``work`` directory,
  which is inside ``build/``, which is never committed;
* **PharmCAT is run twice** — once as delivered (absent PGx positions stay no-calls) and
  once with ``--absent-to-ref`` (absent positions are assumed reference). The difference
  between the two runs *is* the uncertainty a variant-only callset leaves behind, and both
  are carried forward so no reader can mistake the assumption for a measurement.

Everything this module returns is a phenotype word or a count. Diplotypes stay in the JSON
files PharmCAT wrote, under ``work``.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import patient_safety_pgx as pgx

#: Padding added either side of each pharmacogene interval when subsetting the callset, so
#: a variant that PharmCAT's own preprocessor left-aligns into the region is not lost.
REGION_PAD = 200

#: The two runs, and the preprocessor flag that distinguishes them.
MODES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("strict", ()),
    ("a2r", ("--absent-to-ref",)),
)


def shell(command: Sequence[str], env: dict[str, str] | None = None, echo: bool = True) -> None:
    """Run a command, failing loudly. Printed so a run's log is its own audit trail."""
    if echo:
        print("  $", " ".join(command))
    subprocess.run(list(command), check=True, env=env)


def write_bare_bed(regions_bed: Path, out: Path, pad: int = REGION_PAD) -> Path:
    """PharmCAT's ``chr``-prefixed regions BED, rewritten for a no-``chr`` callset."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with regions_bed.open() as src, out.open("w") as dst:
        for line in src:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 3:
                continue
            contig, start, end = fields[0], int(fields[1]), int(fields[2])
            dst.write(f"{contig.removeprefix('chr')}\t{max(start - pad, 0)}\t{end + pad}\n")
    return out


def run_pharmcat(work: Path, vcf: str, pharmcat_dir: Path, java_home: str | None = None) -> Path:
    """Subset the callset to the PGx regions, then run PharmCAT both ways. Returns ``work/work``."""
    stage = work / "work"
    stage.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if java_home:
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin:" + env["PATH"]

    bed = write_bare_bed(pharmcat_dir / "pharmcat_regions.bed", stage / "pgx_regions_bare.bed")
    bare = stage / "patient_pgx_bare.vcf.gz"
    chred = stage / "patient_pgx_chr.vcf.gz"
    shell(["bcftools", "view", "-R", str(bed), "-Oz", "-o", str(bare), vcf])
    shell(["bcftools", "index", "-t", str(bare)])
    shell(
        [
            "bcftools",
            "annotate",
            "--rename-chrs",
            str(pharmcat_dir / "pcat" / "chr_rename_map.tsv"),
            "-Oz",
            "-o",
            str(chred),
            str(bare),
        ]
    )
    shell(["bcftools", "index", "-t", str(chred)])

    for mode, extra in MODES:
        shell(
            [
                "uv",
                "run",
                "--with",
                "colorama",
                "--with",
                "pandas",
                "--with",
                "packaging",
                "python",
                str(pharmcat_dir / "pharmcat_vcf_preprocessor"),
                "-vcf",
                str(chred.resolve()),
                "-o",
                str((stage / f"prep_{mode}").resolve()),
                "-bf",
                mode,
                "-G",
                *extra,
            ],
            env=env,
        )
        shell(
            [
                "java",
                "-jar",
                str(pharmcat_dir / "pharmcat.jar"),
                "-vcf",
                str(stage / f"prep_{mode}" / f"{mode}.preprocessed.vcf.bgz"),
                "-o",
                str(stage / f"report_{mode}"),
                "-reporterJson",
            ],
            env=env,
        )
    return stage


def region_variant_counts(vcf: str, spans: dict[str, tuple[str, int, int]]) -> dict[str, int]:
    """PASS variants the callset holds inside each pharmacogene's interval.

    The input of the regional callability proxy: a region the pipeline called variants in
    at close to the genome-wide rate was demonstrably sequenced, so its *absent* PGx
    positions are far more likely true reference than uncallable.
    """
    counts: dict[str, int] = {}
    for gene, (contig, start, end) in spans.items():
        done = subprocess.run(
            ["bcftools", "view", "-H", "-f", "PASS", "-r", f"{contig}:{start + 1}-{end}", vcf],
            capture_output=True,
            text=True,
            check=True,
        )
        counts[gene] = sum(1 for line in done.stdout.splitlines() if line.strip())
    return counts


def pgx_summary(
    work: Path, pharmcat_dir: Path, vcf: str = "", genome_per_kb: float = 0.0
) -> dict[str, Any]:
    """PharmCAT's two runs → one coordinate-free payload: words, counts and callability."""
    stage = work / "work"
    spans = pgx.regions(pharmcat_dir / "pharmcat_regions.bed")
    counts = region_variant_counts(vcf, spans) if vcf else {}
    coverage = pgx.callability(
        positions_vcf=pharmcat_dir / "pharmcat_positions.vcf",
        missing_vcf=stage / "prep_strict" / "strict.missing_pgx_var.vcf",
        bed=pharmcat_dir / "pharmcat_regions.bed",
        region_variants=counts,
        genome_per_kb=genome_per_kb,
    )
    calls = pgx.gene_calls(
        stage / "report_strict" / "strict.phenotype.json",
        stage / "report_a2r" / "a2r.phenotype.json",
        coverage,
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "genome_per_kb": genome_per_kb,
        "genes": {
            gene: {
                "phenotype_observed": call.phenotype if call.observed else "no call",
                "phenotype_with_absent_to_ref": call.phenotype,
                "observed": call.observed,
                "positions_total": call.positions_total,
                "positions_called": call.positions_called,
                "callable_fraction": round(call.callable_fraction, 4),
                "region_kb": round(coverage[gene].region_kb, 1) if gene in coverage else 0.0,
                "region_variants": coverage[gene].region_variants if gene in coverage else 0,
                "density_ratio": (
                    round(coverage[gene].density_ratio, 3) if gene in coverage else 0.0
                ),
                "callability_verdict": call.note,
                "actionable": call.is_actionable,
            }
            for gene, call in calls.items()
        },
        "drug_genes": pgx.drug_genes(stage / "report_strict" / "strict.report.json"),
        "recommendations_observed": pgx.drug_recommendations(
            stage / "report_strict" / "strict.report.json"
        ),
        "recommendations_absent_to_ref": pgx.drug_recommendations(
            stage / "report_a2r" / "a2r.report.json"
        ),
    }
