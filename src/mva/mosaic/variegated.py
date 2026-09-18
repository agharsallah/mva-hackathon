"""Several chromosomes abnormal at once — the case the disease is named for.

Every bound in this package divides by something computed across chromosomes, and
:mod:`~mva.mosaic.simulate` measures each arm against a null built from its own depths. That
makes one chromosome's event unable to move another's threshold *directly* — which would
make the false-positive rate 5 % by construction, an assumption dressed up as a measurement.

What can move it is the pair of constants fitted across the genome: the fold centre and the
beta-binomial over-dispersion. A *variegated* genome is precisely one where several
chromosomes pull on both at once. So each replicate here simulates the whole genome, **refits
those two constants from the simulated autosomes exactly as a real run would**, and scores
every chromosome — injected and untouched alike — against a null built from the refitted
values. The second number this module reports is how often an untouched chromosome is
flagged because the injected ones moved the constants, and that number is the one that says
whether a genome-wide bound survives on a genome like this one.

Kong 2018's discussion names this failure mode and does not measure it. This does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from . import betabinom, moments
from .simulate import _draw, depth_margin
from .tables import AlleleHistogram

__all__ = ["MultiResult", "multi_chromosome"]


@dataclass(frozen=True)
class MultiResult:
    """One multi-chromosome design: what was injected, what was found, what was invented."""

    fraction: float
    affected: tuple[str, ...]
    #: injected chromosomes whose statistic crossed their own null threshold
    recovered: tuple[str, ...]
    #: untouched chromosomes that crossed theirs — the arm that matters for a bound
    false_positives: tuple[str, ...]
    tested: int
    replicate: int
    #: the two constants refitted from this replicate's own simulated genome, which is where
    #: several abnormal chromosomes at once can actually do damage
    centre: float = float("nan")
    rho: float = float("nan")

    @property
    def recall(self) -> float:
        return len(self.recovered) / len(self.affected) if self.affected else float("nan")

    @property
    def false_positive_rate(self) -> float:
        clean = self.tested - len(self.affected)
        return len(self.false_positives) / clean if clean else float("nan")


def multi_chromosome(
    histograms: dict[str, AlleleHistogram],
    *,
    affected: Sequence[str],
    fraction: float,
    rho: float,
    centre: float,
    replicates: int = 50,
    seed: int = 0,
) -> list[MultiResult]:
    """Inject into several chromosomes at once and score every chromosome, injected or not.

    **The coupling being tested is the refit, not the draw.** Each chromosome's null uses its
    own depths, so injecting one chromosome cannot move another's threshold directly. What
    can is the two constants fitted across the genome — the fold centre and the
    over-dispersion — and a *variegated* genome is one where several chromosomes pull on
    both. So every replicate simulates the whole genome, **refits the centre and rho from
    the simulated autosomes exactly as a real run would**, and scores each chromosome against
    a null built from those refitted constants. Without the refit the false-positive arm
    would be 5 % by construction, which is an assumption dressed up as a measurement.
    """
    rng = np.random.default_rng(seed)
    depths = {
        name: np.repeat(histogram.n, histogram.sites.astype(int))
        for name, histogram in histograms.items()
        if histogram.n_sites
    }
    margins = {name: depth_margin(histogram) for name, histogram in histograms.items()}

    results: list[MultiResult] = []
    for replicate in range(replicates):
        drawn = {
            name: _draw(depth, fraction if name in affected else 0.0, centre, rho, rng)
            for name, depth in depths.items()
        }
        pooled_k = np.concatenate(list(drawn.values()))
        pooled_n = np.concatenate([depths[name] for name in drawn])
        refit_centre = float(np.mean(pooled_k / pooled_n))
        refit_rho = betabinom.fit_rho(_histogram_from(pooled_k, pooled_n), p=refit_centre)

        recovered: list[str] = []
        invented: list[str] = []
        for name, alternate in drawn.items():
            unique, counts = margins[name]
            null = moments.fold_moments(
                unique, counts, bands=[(refit_centre, 1.0)], rho=refit_rho, centre=refit_centre
            )
            if not null.usable:
                continue
            observed = float(np.mean(np.abs(alternate / depths[name] - refit_centre)))
            if observed > null.percentile(0.95):
                (recovered if name in affected else invented).append(name)
        results.append(
            MultiResult(
                fraction=fraction,
                affected=tuple(affected),
                recovered=tuple(recovered),
                false_positives=tuple(invented),
                tested=len(depths),
                replicate=replicate,
                centre=refit_centre,
                rho=refit_rho,
            )
        )
    return results


def _histogram_from(k: np.ndarray, n: np.ndarray) -> AlleleHistogram:
    """A simulated genome's draws as the histogram :func:`~mva.mosaic.betabinom.fit_rho` reads."""
    pairs, counts = np.unique(np.stack([k, n], axis=1), axis=0, return_counts=True)
    return AlleleHistogram(
        chrom="simulated",
        arm="",
        k=pairs[:, 0].astype(int),
        n=pairs[:, 1].astype(int),
        sites=counts.astype(float),
    )
