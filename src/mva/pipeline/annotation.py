"""The functional-annotation port.

The proband VCF carries no annotation worth ranking on: its ``INFO/AF`` is within-sample
(0.5 or 1.0 for a single sample, not a population frequency), there is no consequence
prediction, and the only usable raw field is the dbSNP membership flag — a weak novelty
proxy. Everything the ranker needs therefore comes from outside, through this port.

Keeping it a port rather than a direct VEP call means ranking logic is testable today
against known consequences, and the backend (offline VEP cache, Ensembl REST, a
pre-built table) is a swap rather than a rewrite.
"""

from dataclasses import dataclass
from typing import Protocol

from .variant import Variant

# Sequence Ontology consequences that abolish the protein, in the order VEP ranks them.
LOSS_OF_FUNCTION = frozenset(
    {
        "transcript_ablation",
        "splice_acceptor_variant",
        "splice_donor_variant",
        "stop_gained",
        "frameshift_variant",
        "start_lost",
        "stop_lost",
    }
)

MISSENSE = frozenset(
    {"missense_variant", "inframe_deletion", "inframe_insertion", "protein_altering_variant"}
)


@dataclass(frozen=True)
class Annotation:
    """What the ranker needs to know about one variant."""

    gene: str | None = None
    consequence: str | None = None
    gnomad_af: float | None = None

    @property
    def is_loss_of_function(self) -> bool:
        """True when the consequence abolishes the protein rather than altering it."""
        return self.consequence in LOSS_OF_FUNCTION

    @property
    def is_protein_altering(self) -> bool:
        """True for anything that changes the protein sequence, LoF included."""
        return self.is_loss_of_function or self.consequence in MISSENSE


UNKNOWN = Annotation()


class Annotator(Protocol):
    """Anything that can describe a variant's functional consequence."""

    def annotate(self, variant: Variant) -> Annotation:
        """Describe one variant. Must return :data:`UNKNOWN` rather than raise."""
        ...


class DictAnnotator:
    """A lookup-table annotator — the test fake, and a usable cache in production."""

    def __init__(self, by_variant: dict[Variant, Annotation]):
        self.by_variant = dict(by_variant)

    def annotate(self, variant: Variant) -> Annotation:
        """Look the variant up, falling back to :data:`UNKNOWN`."""
        # An unseen variant is unknown, never an error: a genome-wide run will always
        # reach variants outside any cache, and crashing there would lose the run.
        return self.by_variant.get(variant, UNKNOWN)
