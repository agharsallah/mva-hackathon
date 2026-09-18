#!/usr/bin/env python3
"""What step 8 reads out of the warehouse, and the two sample-wide constants it fits first.

Three tables and one reference table arrive here as histograms; everything downstream is
arithmetic over them. Nothing in this module or below it ever sees a genomic position: the
derivations aggregated them away, which is why the step's outputs can be published at all.

**Two constants are fitted once for the whole sample and then held fixed**, because both
are properties of the assay rather than of any chromosome:

``centre``  the B-allele fraction a balanced heterozygous site actually shows. Reference
            reads map slightly more readily than alternate ones, so it is a little below
            0.5 -- entry 037 measured 0.4954-0.4984 per autosome -- and folding around 0.5
            would turn that constant offset into a constant deviation everywhere.
``rho``     the beta-binomial over-dispersion. Fitted on the pooled autosomal histogram and
            never per arm: a genuinely mosaic arm is exactly an arm with inflated spread,
            so fitting its own null would absorb the signal it is being tested for.

Both are reported beside every result that uses them.

**The autosomal pool excludes the centromeric rows and the sex chromosomes.** Pericentromeric
repeats are where allele balance is least trustworthy and X and Y are hemizygous in this
male proband, so including either would fit a null that describes neither the autosome arms
nor itself.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.io.writers import write_json, write_tsv
from mva.mosaic import bdev as bdev_module
from mva.mosaic import betabinom
from mva.mosaic.tables import (
    AlleleHistogram,
    DepthHistogram,
    allele_histograms,
    depth_histograms,
    pool,
    pool_depth,
)
from mva.viz.queries.access import fetch
from mva.warehouse.postgres import ALIAS
from mva.warehouse.settings import Postgres

__all__ = [
    "ARMS",
    "AUTOSOMES",
    "DEFAULT_OUT",
    "SEED",
    "Sample",
    "load",
    "rows",
    "settings",
    "write_json",
    "write_tsv",
]

DEFAULT_OUT = Path("build/it2/step-8")

#: Fixed so a re-run reproduces every interval. The date step 8 opened.
SEED = 20260918

#: The two arms a result is reported for. ``cen`` and ``unplaced`` rows are loaded and
#: carried, never silently merged into a neighbour, but they are not tested.
ARMS = ("p", "q")

AUTOSOMES = tuple(str(number) for number in range(1, 23))


def settings() -> Postgres:
    return Postgres.from_env()


def rows(sql: str) -> list[dict[str, Any]]:
    return fetch(settings(), sql)


class Sample:
    """Every histogram this sample offers, plus the two constants fitted across it."""

    def __init__(
        self,
        alleles: dict[tuple[str, str], AlleleHistogram],
        depths: dict[tuple[str, str], DepthHistogram],
        density: list[dict[str, Any]],
        geometry: list[dict[str, Any]],
        bins: dict[str, list[int]],
    ) -> None:
        self.alleles = alleles
        self.depths = depths
        self.density = density
        self.geometry = {str(row["chrom"]): row for row in geometry}
        self.bins = bins
        self.autosomal = pool(
            [
                histogram
                for (chrom, arm), histogram in alleles.items()
                if chrom in AUTOSOMES and arm in ARMS
            ],
            chrom="autosomes",
            arm="",
        )
        self.centre = bdev_module.centre(self.autosomal)
        self.rho = betabinom.fit_rho(self.autosomal, p=self.centre)

    @property
    def chromosomes(self) -> list[str]:
        """Every contig with at least one tested arm, in the order a karyogram is read."""
        found = {chrom for chrom, arm in self.alleles if arm in ARMS}
        found |= {chrom for chrom, arm in self.depths if arm in ARMS}
        ordered = [*AUTOSOMES, "X", "Y"]
        return [chrom for chrom in ordered if chrom in found]

    def allele_arms(self, chrom: str) -> list[AlleleHistogram]:
        return [self.alleles[(chrom, arm)] for arm in ARMS if (chrom, arm) in self.alleles]

    def whole_alleles(self, chrom: str) -> AlleleHistogram:
        """The chromosome's two arms added together — exact, because counts add."""
        return pool(self.allele_arms(chrom), chrom=chrom, arm="")

    def whole_depth(self, chrom: str) -> DepthHistogram:
        present = [self.depths[(chrom, arm)] for arm in ARMS if (chrom, arm) in self.depths]
        return pool_depth(present, chrom=chrom, arm="")

    def constants(self) -> dict[str, Any]:
        return {
            "centre": round(self.centre, 5),
            "rho": round(self.rho, 6),
            "autosomal_het_sites": self.autosomal.n_sites,
            "autosomal_mean_depth": round(self.autosomal.mean_depth, 2),
            "seed": SEED,
            "arms_tested": list(ARMS),
            "note": (
                "centre and rho are fitted once on the pooled autosomal p and q arms and held "
                "fixed for every chromosome; centromeric rows, X and Y are excluded from that "
                "pool because neither describes a balanced autosome arm."
            ),
        }


def load() -> Sample:
    """Read the three step-8 tables, the arm geometry and the karyogram bins."""
    alleles = allele_histograms(
        rows(f"SELECT chrom, arm, k, n, sites FROM {ALIAS}.results.it2_mosaic_sites")
    )
    depths = depth_histograms(
        rows(f"SELECT chrom, arm, depth, sites FROM {ALIAS}.results.it2_mosaic_depth")
    )
    density = rows(
        f"""SELECT chrom, arm, het_sites, pass_sites, arm_bp, acrocentric,
                   het_per_mb, het_share
            FROM {ALIAS}.results.it2_mosaic_density"""
    )
    geometry = rows(
        f"""SELECT chrom, chrom_length, cen_start, cen_end, acrocentric
            FROM {ALIAS}.warehouse.cytoband_arms"""
    )
    bins: dict[str, list[int]] = {}
    for row in rows(f"SELECT chrom, mb FROM {ALIAS}.results.baf_bins ORDER BY chrom, mb"):
        bins.setdefault(str(row["chrom"]), []).append(int(row["mb"]))
    return Sample(alleles, depths, density, geometry, bins)
