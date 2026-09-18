"""The trial and literature questions, derived from the card rather than typed in.

Both tables answer a fixed *family* of questions whose terms all come off the mechanism
card. Writing the families here, once, keeps the snapshot honest about what it asked: the
query string that produced a row is carried on the row and repeated in the manifest, so a
reader can re-run any single query without reading this module.

**Trials** — two families:

``disease``     ``cond = <card disease, gloss stripped>``. For an ultra-rare syndrome this
                usually returns nothing, and that empty set is the argument for
                repurposing.
``candidate``   for every **approved** candidate: ``intr = <drug name>``,
                ``cond = <card tumour context>``. Only approved drugs, because a phase-1
                compound's trials are not a shorter path to this child.

**Literature** — three families, exactly as the contract fixes them:

``gene``        ``<gene> AND (repurposing OR inhibitor OR aneuploidy)``
``pathway``     ``<pathway head phrase> AND drug``
``direction``   ``<direction name, slash-segments OR'd> AND <disease anchor>``

The third family is the weak one and this module does not hide it: a long descriptive
direction name becomes a long AND-chain that PubMed matches nothing against, and the
snapshot records ``hits: 0`` for it rather than quietly substituting a looser query.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .candidates import Candidate
from .mechanism import MechanismCard
from .sources import clinicaltrials, pubmed

__all__ = ["LiteratureQuery", "TrialQuery", "literature", "literature_queries", "trials"]


#: Words that name a *category* of illness rather than the illness. Every disease name in
#: every ontology ends in one of these, so they carry no search signal: "Mosaic variegated
#: aneuploidy syndrome 1" anchored on "syndrome" would match a third of PubMed.
GENERIC_DISEASE_WORDS = frozenset(
    {"syndrome", "disease", "disorder", "condition", "deficiency", "type", "and"}
)


def _anchor(card: MechanismCard) -> str:
    """The disease in one word: the last alphabetic word that is not a category noun.

    "Mosaic variegated aneuploidy syndrome 1" → ``aneuploidy``. A name made entirely of
    category nouns falls back to the gene symbol, which is always specific.
    """
    words = [w for w in card.disease_query.replace("-", " ").split() if w.isalpha()]
    specific = [w for w in words if w.lower() not in GENERIC_DISEASE_WORDS]
    return specific[-1] if specific else card.gene_symbol


#: The public name of the anchor rule, for the modules that build drug-level queries.
anchor = _anchor


@dataclass(frozen=True)
class TrialQuery:
    """One ClinicalTrials.gov question and what it was asked about."""

    family: str
    label: str
    cond: str | None = None
    intr: str | None = None

    @property
    def text(self) -> str:
        parts = [f"cond={self.cond}" if self.cond else "", f"intr={self.intr}" if self.intr else ""]
        return " ".join(p for p in parts if p)


@dataclass(frozen=True)
class LiteratureQuery:
    """One PubMed question, its family, and the term as sent."""

    family: str
    label: str
    term: str


def trial_queries(card: MechanismCard, approved: list[Candidate]) -> list[TrialQuery]:
    """The trial questions for one card and one approved-candidate list."""
    context = card.tumour_context
    names = sorted({c.drug_name for c in approved if c.drug_name})
    return [
        TrialQuery("disease", card.disease_query, cond=card.disease_query),
        *(TrialQuery("candidate", name, cond=context, intr=name) for name in names),
    ]


def literature_queries(card: MechanismCard) -> list[LiteratureQuery]:
    """The literature questions for one card: one gene, one pathway, one per direction."""
    anchor = _anchor(card)
    out = [
        LiteratureQuery(
            "gene",
            card.gene_symbol,
            f"{card.gene_symbol} AND (repurposing OR inhibitor OR {anchor})",
        )
    ]
    if card.pathway:
        out.append(LiteratureQuery("pathway", card.pathway, f"{card.pathway} AND drug"))
    for direction in card.directions:
        phrase = direction.query_phrase
        if phrase:
            out.append(LiteratureQuery("direction", direction.id, f"{phrase} AND {anchor}"))
    return out


def trials(
    fetcher: Any,
    card: MechanismCard,
    approved: list[Candidate],
    *,
    max_pages: int = 3,
    per_drug_pages: int = 1,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every trial query. Returns ``(rows, query_log)``.

    A study matching two queries appears once per query, tagged with each: the ``query``
    column is what makes the row interpretable, and collapsing it would lose that.
    """
    say = progress or (lambda _line: None)
    asked = trial_queries(card, approved)
    rows: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []
    for index, query in enumerate(asked, start=1):
        pages = max_pages if query.family == "disease" else per_drug_pages
        found = clinicaltrials.studies(fetcher, cond=query.cond, intr=query.intr, max_pages=pages)
        rows.extend({**row, "query": query.text} for row in found)
        log.append(
            {"family": query.family, "label": query.label, "query": query.text, "hits": len(found)}
        )
        if index % 25 == 0 or index == len(asked):
            say(f"  trial queries {index}/{len(asked)}  rows {len(rows)}")
    return rows, log


def literature(
    fetcher: Any,
    card: MechanismCard,
    *,
    retmax: int = 40,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every literature query plus the card's own citations. Returns ``(rows, log)``.

    The card's cited PMIDs are fetched as a fourth family (``card``) so the table carries
    the papers the mechanism was built on alongside the ones the search found — the report
    needs both and they should not live in two places.
    """
    say = progress or (lambda _line: None)
    rows: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []

    for query in literature_queries(card):
        pmids = pubmed.search(fetcher, query.term, retmax=retmax)
        total = pubmed.count(fetcher, query.term)
        rows.extend({**row, "query": query.term} for row in pubmed.summaries(fetcher, pmids))
        log.append(
            {
                "family": query.family,
                "label": query.label,
                "query": query.term,
                "hits": total,
                "kept": len(pmids),
            }
        )
        say(f"  pubmed {query.family}/{query.label}: {total} hits, kept {len(pmids)}")

    cited = list(card.literature_pmids)
    if cited:
        rows.extend({**row, "query": "card citation"} for row in pubmed.summaries(fetcher, cited))
        log.append(
            {
                "family": "card",
                "label": "cited by the mechanism card",
                "query": "card citation",
                "hits": len(cited),
                "kept": len(cited),
            }
        )
    return rows, log
