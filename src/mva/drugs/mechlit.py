"""How much has been written about each approved drug *and* this mechanism?

The snapshot's literature stage asks about the gene, the pathway and each direction. It never
asks about a drug. Yet the first question a panel asks of a candidate is whether anyone has
put the drug and the mechanism in one paper - and the honest answer for most of 359 approved
drugs is *nobody*, which is exactly what a repurposing report needs to show rather than hide.

Two PubMed questions per drug, both derived from the card and never typed:

``mechanism``   ``"<drug>" AND (<gene> OR <protein> OR "<pathway head>" OR <disease anchor>)``
``context``     ``"<drug>" AND <tumour context>``

The count is the number of PubMed records matching; a handful of PMIDs is kept so a reader can
open them. A count is **not** evidence for a rung - a drug can be mentioned beside a mechanism
in a hundred papers that argue against it - so the ladder prints the count in its own column
and the rung is decided elsewhere. Step 5 measured that literature volume is a poor ranker
(ρ = 0.024 against a hit count, methodology 105); this table is descriptive on purpose.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .mechanism import MechanismCard
from .queries import anchor
from .sources import pubmed

__all__ = ["FAMILIES", "context_term", "mechanism_term", "survey"]

#: The two question families, in the order the table is written.
FAMILIES = ("mechanism", "context")


def _protein_short(card: MechanismCard) -> str:
    """``"BubR1 (mitotic checkpoint ...)"`` → ``BubR1``. The head before any bracket."""
    text = card.protein.strip()
    return text.split("(")[0].strip() if text else ""


def mechanism_term(card: MechanismCard) -> str:
    """The mechanism half of the query, as an OR-group PubMed can translate itself."""
    parts = [card.gene_symbol]
    protein = _protein_short(card)
    if protein and protein.upper() != card.gene_symbol.upper():
        parts.append(protein)
    if card.pathway:
        parts.append(f'"{card.pathway}"')
    parts.append(anchor(card))
    return "(" + " OR ".join(dict.fromkeys(parts)) + ")"


def context_term(card: MechanismCard) -> str | None:
    """The tumour context as a searchable word, or ``None`` when the card names none."""
    return card.tumour_context or None


def _terms(card: MechanismCard) -> list[tuple[str, str]]:
    out = [("mechanism", mechanism_term(card))]
    context = context_term(card)
    if context:
        out.append(("context", context))
    return out


def survey(
    fetcher: Any,
    card: MechanismCard,
    drug_names: Iterable[str],
    *,
    retmax: int = 10,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One row per drug per family. Returns ``(rows, log)``.

    ``drug_names`` are already folded to their base name by the caller, so a drug with five
    salts is asked about once. Two requests per row (a count and a short id list); a warm
    cache makes both free.
    """
    say = progress or (lambda _line: None)
    names = list(dict.fromkeys(drug_names))
    terms = _terms(card)
    rows: list[dict[str, Any]] = []
    for index, name in enumerate(names, start=1):
        for family, body in terms:
            term = f'"{name}" AND {body}'
            hits = pubmed.count(fetcher, term)
            pmids = pubmed.search(fetcher, term, retmax=retmax) if hits else []
            rows.append(
                {
                    "drug_name": name,
                    "family": family,
                    "term": term,
                    "hits": hits,
                    "pmids": tuple(pmids),
                }
            )
        if index % 25 == 0 or index == len(names):
            say(f"  mechanism literature {index}/{len(names)} drugs")
    log = [
        {"family": family, "term_body": body, "drugs": len(names), "requests_per_drug": 2}
        for family, body in terms
    ]
    return rows, log
