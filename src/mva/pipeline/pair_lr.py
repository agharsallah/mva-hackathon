"""Scoring a gene's biallelic hypotheses as a posterior, with nothing filtered out.

A recessive disease needs both copies of a gene disabled, so the object being scored is a
**hypothesis about a gene's two copies**, and there are exactly three shapes it can take:

======================  ==============================================================
shape                   what was observed
======================  ==============================================================
``compound``            two different damaging alleles, one per copy if they are in trans
``homozygous``          one allele on both copies
``single``              one allele on one copy, and nothing on the other
======================  ==============================================================

The third is the one a hard filter throws away, and it is kept here. A gene with one
damaging allele and no partner is *weaker* evidence, not *no* evidence — the partner may be
a call the pipeline never made, in an exon no bait covered, or an allele class no caller
reports. LIRICAL's answer is to degrade the recessive genotype ratio by the fraction of the
required alleles actually seen rather than zeroing it (Robinson 2020), and
:func:`mva.pipeline.genotype_lr.degrade` is that function.

Two rules the scoring follows, both pre-registered:

* **Two different alleles are two observations; one allele on two copies is one.** A
  compound pair multiplies both alleles' lanes. A homozygous call applies its allele's lanes
  once — the second copy adds a broken copy, not a second independent prediction.
* **Correlation groups do not cross alleles.** A missense predictor's opinion about allele A
  and its opinion about allele B are separate observations, so each allele's lanes are
  renamed and re-grouped by side before they are combined.

Phase is decided by :mod:`mva.pipeline.compound_het` and is carried, never used as a filter:
with no parental DNA and no fragment spanning the pair, *unknown* is the honest verdict for
almost every pair in this case, and dropping those pairs would drop the answer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import Enum

from .compound_het import Phase, classify_phase
from .genotype_lr import AlleleEvidence, AlleleLanes, degrade, lanes_for
from .likelihood import Lane, Posterior, combine
from .vcf import Call

#: The prior that a given gene is the causal one, before any evidence. One over the number
#: of protein-coding genes is the uninformative choice and is what makes the posterior
#: comparable across genes; the caller passes the count it actually scored.
DEFAULT_GENE_COUNT = 19_723

#: The lane name the permutation null substitutes. Named once so the null and the scorer
#: cannot drift apart over a string.
PHENOTYPE_LANE = "phenotype"


class Shape(Enum):
    """Which biallelic hypothesis a row carries."""

    COMPOUND = "compound"
    HOMOZYGOUS = "homozygous"
    SINGLE = "single"

    @property
    def alleles_observed(self) -> int:
        """How many of the two required damaged copies this shape accounts for."""
        return 1 if self is Shape.SINGLE else 2


@dataclass(frozen=True)
class ScoredPair:
    """One biallelic hypothesis for one gene, with the arithmetic that produced it."""

    gene: str
    shape: Shape
    phase: Phase
    posterior: Posterior
    left: AlleleLanes
    right: AlleleLanes | None
    #: The ratio after LIRICAL's degradation, which is what ordering uses. Equal to the
    #: posterior's own ratio for every shape but ``single``.
    combined_lr: float
    #: The exponent LIRICAL's degradation applied — the fraction of the two required
    #: alleles actually observed. 1.0 unless the shape is ``single``.
    exponent: float = 1.0
    #: The product of every applied lane **except** the phenotype one, before degradation.
    #: Kept so a permutation null can re-score the whole table by substituting one number
    #: per gene, instead of recomputing every allele's lanes a thousand times.
    lr_without_phenotype: float = 1.0

    def rescored(self, phenotype_lr: float) -> float:
        """What this hypothesis would score if the phenotype lane said ``phenotype_lr``.

        Exact rather than approximate: the degradation is a power, so it distributes over
        the product, and substituting one factor is the same arithmetic run again.
        """
        return (self.lr_without_phenotype * phenotype_lr) ** self.exponent

    @property
    def probability(self) -> float:
        odds = self.posterior.prior_odds * self.combined_lr
        return odds / (1.0 + odds)

    @property
    def unphaseable(self) -> bool:
        """A compound pair with no phase evidence at all — the fifth failure category."""
        return self.shape is Shape.COMPOUND and self.phase is Phase.UNKNOWN


def gene_prior(gene_count: int = DEFAULT_GENE_COUNT) -> float:
    """The uninformative prior that any one gene is causal."""
    if gene_count < 2:
        raise ValueError("a prior over genes needs at least two genes")
    return 1.0 / gene_count


def context_lanes(
    *,
    phenotype_lr: float,
    phenotype_source: str,
    phenotype_rank: int | None,
    network_lr: float = 1.0,
    network_source: str = "",
    inheritance_lr: float = 1.0,
    inheritance_source: str = "",
) -> list[Lane]:
    """The lanes that belong to the **gene** rather than to either allele.

    Three, and the middle one is conditional. The phenotype lane always fires, including for
    a gene the ranker could not place at all — that is its "unranked" bucket, and it is a
    ratio below 1, never zero. The network lane fires **only** for such a gene: it
    subdivides the unranked bucket by who the gene sits beside, rather than offering a
    second opinion about a gene that already has one. That is why the two are not in one
    correlation group even though the network seeds come from the same ranking.
    """
    lanes = [
        Lane(
            PHENOTYPE_LANE,
            phenotype_lr,
            phenotype_source,
            note=f"rank {phenotype_rank}" if phenotype_rank else "no curated phenotype",
        )
    ]
    if phenotype_rank is None and network_lr != 1.0:
        lanes.append(
            Lane(
                "network",
                network_lr,
                network_source,
                note="uncurated gene, scored by proximity to the top-ranked genes",
            )
        )
    if inheritance_lr != 1.0:
        lanes.append(Lane("inheritance", inheritance_lr, inheritance_source))
    return lanes


def score(
    gene: str,
    left: AlleleEvidence,
    right: AlleleEvidence | None,
    *,
    shape: Shape,
    context: Sequence[Lane] = (),
    prior: float,
    source: str,
    left_call: Call | None = None,
    right_call: Call | None = None,
) -> ScoredPair:
    """Score one biallelic hypothesis.

    ``context`` is the evidence that belongs to the gene rather than to either allele — the
    phenotype ranking, a network proximity, an inheritance-mode factor, as
    :func:`context_lanes` builds them. It is passed in rather than computed here so this
    module stays free of any one case's priors.
    """
    left_lanes = lanes_for(left, source=source)
    right_lanes = lanes_for(right, source=source) if right is not None else None
    lanes: list[Lane] = list(context)
    lanes += _sided(left_lanes.lanes, "left")
    if right_lanes is not None and shape is Shape.COMPOUND:
        lanes += _sided(right_lanes.lanes, "right")
    posterior = combine(lanes, prior=prior)
    exponent = min(max(shape.alleles_observed / 2, 0.0), 1.0)
    combined = degrade(posterior.combined_lr, observed=shape.alleles_observed, required=2)
    without = 1.0
    for lane in posterior.applied:
        if lane.name != PHENOTYPE_LANE:
            without *= lane.likelihood_ratio
    phase = _phase(shape, left_call, right_call)
    return ScoredPair(
        gene=gene,
        shape=shape,
        phase=phase,
        posterior=posterior,
        left=left_lanes,
        right=right_lanes if shape is Shape.COMPOUND else None,
        combined_lr=combined,
        exponent=exponent,
        lr_without_phenotype=without,
    )


def best_per_gene(pairs: Iterable[ScoredPair]) -> dict[str, ScoredPair]:
    """The highest-scoring hypothesis for each gene — what a gene-level ranking compares."""
    best: dict[str, ScoredPair] = {}
    for pair in pairs:
        current = best.get(pair.gene)
        if current is None or pair.combined_lr > current.combined_lr:
            best[pair.gene] = pair
    return best


def _sided(lanes: Sequence[Lane], side: str) -> list[Lane]:
    """Rename and re-group one allele's lanes so two alleles never share a group."""
    return [
        replace(
            lane,
            name=f"{side}:{lane.name}",
            group=f"{lane.group}:{side}" if lane.group else "",
        )
        for lane in lanes
    ]


def _phase(shape: Shape, left: Call | None, right: Call | None) -> Phase:
    if shape is Shape.HOMOZYGOUS:
        # Both copies carry it, so both copies are affected. Not a statement about
        # haplotypes, and deliberately not reported as trans.
        return Phase.UNKNOWN
    if shape is Shape.SINGLE or left is None or right is None:
        return Phase.UNKNOWN
    return classify_phase(left, right)
