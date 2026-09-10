"""The mode-of-inheritance factor, and why a family history of loss is evidence.

The clinical document lists a *parental* feature — recurrent spontaneous abortion — and
says in its own notes that it "should be treated as part of the phenotypic input, not
merely as background". Scoring the proband's symptoms against it pulls
recurrent-miscarriage genes into the top ranks (entry 067), which is the wrong use of it.
This module is the right one: recurrent loss in the parents of an affected child raises
the weight of **recessive** genes whose biallelic genotype is lethal before birth or
causes early loss, and lowers the weight of dominant-only genes, which a healthy carrier
parent pair would not explain.

The factors are small on purpose and **fixed before any score is seen**. They are a
pre-registered prior, not a fitted weight, and every ranking that uses one is reported
again with the factor removed so a reader can see exactly what it moved.

A leaf module: it takes inheritance facts as rows and gives back a number. Nothing here
reads a database, a file, or the case.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

#: How the annotation files spell the modes this factor distinguishes.
AUTOSOMAL_RECESSIVE = "HP:0000007"
X_LINKED_RECESSIVE = "HP:0001419"
AUTOSOMAL_DOMINANT = "HP:0000006"
X_LINKED_DOMINANT = "HP:0001423"

RECESSIVE_TERMS = frozenset({AUTOSOMAL_RECESSIVE, X_LINKED_RECESSIVE})
DOMINANT_TERMS = frozenset({AUTOSOMAL_DOMINANT, X_LINKED_DOMINANT})

#: Terms that record loss before or around birth — what a recurrent-miscarriage history in
#: the parents would predict for a gene whose biallelic genotype the fetus cannot survive.
PRENATAL_LOSS_TERMS = frozenset(
    {
        "HP:0003826",  # Stillbirth
        "HP:0005268",  # Miscarriage
        "HP:0032468",  # History of stillbirth
        "HP:0032479",  # Preimplantation lethality
        "HP:0200067",  # Recurrent spontaneous abortion
        "HP:5210273",  # Maternal history of recurrent miscarriage
    }
)

#: The three factors, pre-registered. Small on purpose: this is a prior a clinician would
#: hold before seeing any data, and a large factor would let it decide the ranking.
RECESSIVE_WITH_LOSS = 1.5
RECESSIVE = 1.0
DOMINANT_ONLY = 0.5
UNKNOWN = 1.0


@dataclass(frozen=True)
class GeneInheritance:
    """What the curated diseases of one gene say about how it is inherited."""

    symbol: str
    modes: frozenset[str] = frozenset()
    #: Terms curated against the gene's diseases, used only to look for prenatal loss.
    disease_terms: frozenset[str] = frozenset()

    @property
    def recessive(self) -> bool:
        return bool(self.modes & RECESSIVE_TERMS)

    @property
    def dominant_only(self) -> bool:
        return bool(self.modes & DOMINANT_TERMS) and not self.recessive

    @property
    def prenatal_loss(self) -> bool:
        """Whether any curated disease of this gene records loss before or around birth."""
        return bool(self.disease_terms & PRENATAL_LOSS_TERMS)

    @property
    def known(self) -> bool:
        return bool(self.modes)


def factor(gene: GeneInheritance, *, family_history_of_loss: bool = True) -> float:
    """The multiplier this gene's inheritance earns.

    ``family_history_of_loss`` is the switch the report is required to flip: with it off,
    every gene gets 1.0 and the ranking is the one the factor never touched. That is how
    the claim "the prior did not decide this" is shown rather than asserted.
    """
    if not family_history_of_loss or not gene.known:
        return UNKNOWN
    if gene.recessive:
        return RECESSIVE_WITH_LOSS if gene.prenatal_loss else RECESSIVE
    return DOMINANT_ONLY if gene.dominant_only else UNKNOWN


def explain(gene: GeneInheritance, *, family_history_of_loss: bool = True) -> str:
    """One sentence for the evidence register — the factor, and the reason for it."""
    value = factor(gene, family_history_of_loss=family_history_of_loss)
    if not family_history_of_loss:
        return f"{gene.symbol}: x1.0 — the inheritance prior is switched off for this run"
    if not gene.known:
        return f"{gene.symbol}: x1.0 — no curated mode of inheritance, so no prior is applied"
    if gene.recessive and gene.prenatal_loss:
        return (
            f"{gene.symbol}: x{value} — recessive, and a curated disease records loss "
            "before or around birth, which is what the parents' history would predict"
        )
    if gene.recessive:
        return f"{gene.symbol}: x{value} — recessive, with no curated prenatal loss"
    if gene.dominant_only:
        return (
            f"{gene.symbol}: x{value} — dominant only, which a healthy carrier parent "
            "pair would not explain"
        )
    return f"{gene.symbol}: x{value} — mode of inheritance carries no signal here"


def factors(
    genes: Iterable[GeneInheritance], *, family_history_of_loss: bool = True
) -> dict[str, float]:
    """The factor per gene symbol — the form the pair ranker consumes."""
    return {
        gene.symbol: factor(gene, family_history_of_loss=family_history_of_loss) for gene in genes
    }
