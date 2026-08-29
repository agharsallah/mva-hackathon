"""Scoring compound-heterozygote hypotheses so the best pair lands at rank 1.

The scored object is a *pair*, not a variant, because the answer key is a pair and rank
points are awarded for a row whose variant set equals it exactly.

Three signals, deliberately few and each one inspectable — with a single proband and no
training data, a transparent additive score is defensible in the methods write-up in a
way a tuned black box would not be:

* **rarity** — the disease has fewer than 50 known patients worldwide, so a causal allele
  should be effectively absent from gnomAD. This is the strongest single filter.
* **consequence** — loss-of-function outranks missense outranks everything else.
* **gene prior** — MVA is caused by biallelic variants in a small known gene set, and
  saying so explicitly beats burying the assumption in a threshold.

A pair must sit in ONE gene. Two damaging variants in different genes are two unrelated
carrier findings, not a biallelic diagnosis.
"""

from dataclasses import dataclass

from .annotation import Annotator
from .variant import Variant

# Frequency above which a variant is too common to cause an ultra-rare recessive
# disease. Roughly: a carrier rate that would predict far more patients than exist.
RARE_AF = 1e-3


@dataclass(frozen=True)
class RankedPair:
    """A compound-heterozygote hypothesis with the score that ordered it."""

    left: Variant
    right: Variant
    gene: str | None
    score: float


def rank_pairs(
    pairs: list[tuple[Variant, Variant]],
    annotator: Annotator,
    gene_prior: dict[str, float] | None = None,
) -> list[RankedPair]:
    """Score same-gene pairs and return them best-first."""
    gene_prior = gene_prior or {}
    ranked = []

    for left, right in pairs:
        a, b = annotator.annotate(left), annotator.annotate(right)
        if a.gene != b.gene:
            continue

        score = _variant_score(a) + _variant_score(b)
        score *= gene_prior.get(a.gene, 1.0) if a.gene else 1.0
        ranked.append(RankedPair(left, right, a.gene, score))

    return sorted(ranked, key=lambda p: p.score, reverse=True)


def _variant_score(annotation) -> float:
    """Rarity times severity for a single allele."""
    return _rarity(annotation.gnomad_af) * _severity(annotation)


def _rarity(af: float | None) -> float:
    if af is None:
        # Absent from gnomAD is the same evidence as an AF of zero, but we cannot tell
        # it apart from "never looked up", so treat it as mildly favourable.
        return 0.5
    if af >= RARE_AF:
        # Too common for an ultra-rare recessive disease; suppress rather than exclude,
        # so a mistaken frequency lookup cannot silently drop the true answer.
        return 0.05
    return 1.0


def _severity(annotation) -> float:
    if annotation.is_loss_of_function:
        return 1.0
    if annotation.is_protein_altering:
        return 0.6
    if annotation.consequence is None:
        return 0.0
    return 0.1
