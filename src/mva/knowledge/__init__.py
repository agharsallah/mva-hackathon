"""What published knowledge says about a candidate set — and whether that is worth anything.

Four questions, four modules, and the fourth exists because the first three are easy to
fool yourself with:

:mod:`~mva.knowledge.sources`
    thin adapters over LitVar 2.0, PubTator 3.0 and (through
    :mod:`mva.drugs.sources.pubmed`) NCBI E-utilities. Fetching, caching, politeness and
    provenance all belong to :class:`mva.drugs.cache.Fetcher`; these are parsers.
:mod:`~mva.knowledge.catalogue`
    *has anyone published about the alleles this sample actually carries?* Keyed on dbSNP
    identifiers, with an honest denominator: an allele with no identifier is counted as
    unqueryable rather than as unpublished.
:mod:`~mva.knowledge.anchors`
    *does any single paper discuss a candidate gene alongside several of the patient's
    clinical features?* Derived by script from a gene list and a term list — never a
    hand-written reading list, which in a blind design is a leak wearing a citation.
:mod:`~mva.knowledge.protein`
    *does a missense allele land in an annotated domain, in a region the structure model
    is confident about?* InterPro plus AlphaFold DB, no protein language model and no new
    dependency.
:mod:`~mva.knowledge.baselines`
    *does any of the above order anything that a raw publication count does not?* A
    literature route that reproduces citation volume has measured fame, not biology, and
    this module is what makes that statement falsifiable rather than rhetorical.

The package is **case-agnostic**: no gene, no disease, no coordinate is written anywhere
in it. It takes a gene list, a term list and a set of allele identifiers, and it returns
sourced rows. Point it at another case and the same code answers that one.
"""

from .baselines import Agreement, RouteWeight, agreement, weigh
from .catalogue import AlleleRow, CatalogueSummary
from .protein import Domain, ProteinContext, ResidueVerdict

__all__ = [
    "Agreement",
    "AlleleRow",
    "CatalogueSummary",
    "Domain",
    "ProteinContext",
    "ResidueVerdict",
    "RouteWeight",
    "agreement",
    "weigh",
]
