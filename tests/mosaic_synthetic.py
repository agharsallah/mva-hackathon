"""Synthetic histograms for the mosaic tests — a forward model, not fixtures on disk.

Every mosaic test needs the same thing: an arm's worth of heterozygous calls with a known
cell fraction injected, so that what comes back can be compared against what went in. The
builders live here rather than in each test module because a second copy of a forward model
is a second chance for the model under test and the model generating the data to drift
apart, and then the suite would be asserting that a bug is reproducible.

Nothing here touches the network, the warehouse or any patient file.
"""

from __future__ import annotations

import numpy as np

from mva.mosaic import betabinom, models
from mva.mosaic.tables import AlleleHistogram, DepthHistogram

DEPTH = 44
RHO = 0.02
CENTRE = 0.5


def tally(k: np.ndarray, n: np.ndarray, *, chrom: str = "1", arm: str = "q") -> AlleleHistogram:
    """Turn per-site draws into the ``(k, n) -> count`` histogram the package reads."""
    pairs: dict[tuple[int, int], float] = {}
    for alternate, total in zip(k, n, strict=True):
        key = (int(alternate), int(total))
        pairs[key] = pairs.get(key, 0.0) + 1.0
    keys = sorted(pairs)
    return AlleleHistogram(
        chrom=chrom,
        arm=arm,
        k=np.array([key[0] for key in keys], dtype=int),
        n=np.array([key[1] for key in keys], dtype=int),
        sites=np.array([pairs[key] for key in keys], dtype=float),
    )


def arm(
    sites: int = 5000,
    *,
    fraction: float = 0.0,
    model: str = "mitotic_trisomy",
    tract: float = 0.0,
    depth: int = DEPTH,
    rho: float = RHO,
    centre: float = CENTRE,
    seed: int = 1,
    chrom: str = "1",
) -> AlleleHistogram:
    """One simulated arm: ``fraction`` zero is the null, above it the model's bands."""
    rng = np.random.default_rng(seed)
    totals = np.full(sites, depth, dtype=int)
    spec = models.by_name(model)
    bands = models.bands_for(spec, fraction, centre, tract)
    weights = np.array([band.weight for band in bands], dtype=float)
    chosen = rng.choice(len(bands), size=sites, p=weights / weights.sum())
    drawn = np.empty(sites, dtype=int)
    for index, band in enumerate(bands):
        mask = chosen == index
        if mask.any():
            drawn[mask] = betabinom.sample(totals[mask], band.centre, rho, rng)
    return tally(drawn, totals, chrom=chrom)


def depths(
    mean: float = float(DEPTH),
    *,
    sites: int = 50_000,
    dispersion: float = 50.0,
    seed: int = 2,
    chrom: str = "1",
    arm_name: str = "q",
) -> DepthHistogram:
    """A negative-binomial depth histogram at a known mean."""
    rng = np.random.default_rng(seed)
    probability = dispersion / (dispersion + mean)
    draws = rng.negative_binomial(dispersion, probability, size=sites)
    draws = draws[draws > 0]
    values, counts = np.unique(draws, return_counts=True)
    return DepthHistogram(chrom, arm_name, values, counts.astype(float))
