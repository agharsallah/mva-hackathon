"""Which of the child's own alleles the literature has already described.

**The direction of this join is the design decision.** The obvious catalogue is
per-gene — "every published allele of BUB1B" — and it is close to useless here, because a
gene's famous alleles are somebody else's alleles. The question that carries information
is the reverse one: *take the alleles this child actually carries, and ask the literature
whether any of them has been written about.* That has a complete denominator (every allele
in a scored pair), it is answerable at dbSNP resolution, and a zero is meaningful.

Two independent instruments answer it, and they are kept apart on purpose:

``literature``
    LitVar 2.0, keyed on rsID. Counts publications per allele.
``clinical``
    the child's own k-mer genotypes of the **public ClinVar pathogenic / likely-pathogenic
    catalogue**, produced by step 3 with no aligner and no caller. This one says
    *present in this child*, which LitVar cannot.

An allele with a publication count is a *described* allele; an allele called het or
hom-alt against the ClinVar catalogue is a *carried* pathogenic allele. Only the second
is evidence about the child, and the row keeps them in separate columns so a reader can
never mistake one for the other.

Case-agnostic: this module is given rows and a fetcher. It knows no gene, no disease and
no coordinate.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..drugs.cache import Fetcher
from . import sources

__all__ = ["NOT_ASKED", "AlleleRow", "CatalogueSummary", "build", "summarise"]

#: ``pmid_count`` for an allele the literature index was never asked about — either it
#: carries no dbSNP identifier, or the caller ran with ``ask_literature=False``.
NOT_ASKED = -1


@dataclass(frozen=True)
class AlleleRow:
    """One allele of one gene, as the catalogue reports it.

    ``rsid`` empty means the allele has no dbSNP identifier at all, which is not a
    missing value but a finding: an allele nobody has ever catalogued cannot be looked up
    in a literature index keyed on that catalogue. Those rows are counted as
    ``unqueryable`` and never silently dropped.
    """

    gene: str
    rsid: str
    consequence_class: str
    #: Publications LitVar holds for this exact variant. :data:`NOT_ASKED` when it was
    #: not, or could not be, asked.
    pmid_count: int = NOT_ASKED
    top_pmid: str = ""
    #: ClinVar significance as the annotation pass recorded it, empty when unknown.
    clin_sig: str = ""
    #: The child's own multiplicity for this allele where step 3 typed it.
    child_call: str = ""
    child_posterior: float = 0.0
    is_target: bool = False
    is_decoy: bool = False
    in_top_leaders: bool = False

    @property
    def queryable(self) -> bool:
        """Whether a literature index keyed on dbSNP could answer about this allele."""
        return bool(self.rsid)

    @property
    def described(self) -> bool:
        """At least one publication mentions this exact variant."""
        return self.pmid_count > 0

    @property
    def carried_pathogenic(self) -> bool:
        """A ClinVar pathogenic / likely-pathogenic allele the child actually carries."""
        return self.child_call in ("het", "hom-alt") and "athogenic" in self.clin_sig


@dataclass
class CatalogueSummary:
    """The three numbers a coverage claim needs, and the reason all three are printed."""

    alleles: int = 0
    queryable: int = 0
    described: int = 0
    carried_pathogenic: int = 0
    genes: int = 0
    per_gene_described: dict[str, int] = field(default_factory=dict)

    @property
    def unqueryable(self) -> int:
        """Alleles with no dbSNP identifier — the band a coverage figure must draw."""
        return self.alleles - self.queryable


def build(
    fetcher: Fetcher,
    alleles: Sequence[dict[str, Any]],
    *,
    ask_literature: bool = True,
) -> list[AlleleRow]:
    """One :class:`AlleleRow` per input allele, with LitVar asked once per distinct rsID.

    ``alleles`` rows carry ``gene``, ``rsid``, ``consequence_class`` and whatever of
    ``clin_sig`` / ``child_call`` / ``child_posterior`` / the membership flags the caller
    could resolve in SQL. Rows are returned in input order so the caller's own ordering
    survives; LitVar is asked **once per distinct rsID**, not once per row, because the
    same variant reaches the table through every pair it belongs to.
    """
    counts: dict[str, tuple[int, str]] = {}
    if ask_literature:
        for rsid in _distinct_rsids(alleles):
            pmids = sources.publications_for_rsid(fetcher, rsid)
            counts[rsid] = (len(pmids), pmids[0] if pmids else "")
    rows = []
    for allele in alleles:
        rsid = str(allele.get("rsid") or "").strip()
        # -1 is "not asked", and it is the only honest value for an allele with no dbSNP
        # identifier: LitVar could not have been asked about it, so 0 would read as
        # "asked, and nobody has published", which is a different statement.
        found, top = counts.get(rsid, (NOT_ASKED, ""))
        rows.append(
            AlleleRow(
                gene=str(allele.get("gene") or ""),
                rsid=rsid,
                consequence_class=str(allele.get("consequence_class") or ""),
                pmid_count=found,
                top_pmid=top,
                clin_sig=str(allele.get("clin_sig") or ""),
                child_call=str(allele.get("child_call") or ""),
                child_posterior=float(allele.get("child_posterior") or 0.0),
                is_target=bool(allele.get("is_target")),
                is_decoy=bool(allele.get("is_decoy")),
                in_top_leaders=bool(allele.get("in_top_leaders")),
            )
        )
    return rows


def summarise(rows: Iterable[AlleleRow]) -> CatalogueSummary:
    """Roll the rows up into the coverage numbers, with nothing hidden in a ratio.

    A single "coverage" percentage would conflate two very different absences — an allele
    nobody indexed and an allele indexed but never written about — so the summary keeps
    ``alleles``, ``queryable`` and ``described`` as three separate counts and derives
    :attr:`CatalogueSummary.unqueryable` from the first two.
    """
    summary = CatalogueSummary()
    genes: set[str] = set()
    for row in rows:
        summary.alleles += 1
        genes.add(row.gene)
        if row.queryable:
            summary.queryable += 1
        if row.described:
            summary.described += 1
            summary.per_gene_described[row.gene] = summary.per_gene_described.get(row.gene, 0) + 1
        if row.carried_pathogenic:
            summary.carried_pathogenic += 1
    summary.genes = len(genes)
    return summary


def _distinct_rsids(alleles: Sequence[dict[str, Any]]) -> list[str]:
    """The distinct, non-empty rsIDs of the input, in first-seen order."""
    seen: dict[str, None] = {}
    for allele in alleles:
        rsid = str(allele.get("rsid") or "").strip()
        if rsid:
            seen.setdefault(rsid, None)
    return list(seen)
