"""The Track 2 surface: the mechanism, the drug evidence behind it, and where it came from.

Track 2 asks a different question from Track 1 — *which market-approved drug acts on the
mechanism the alleles imply* — and it is answered from public sources rather than from the
callset: seven APIs, five committed TSVs, a provenance manifest each. This route is those
files assembled into one object a page can render, with the same discipline the rest of the
API keeps: the manifests' own words for how each table was built, the warehouse ledger for
what it rests on, and the research register for what was claimed before any of it ran.

**One request, the whole surface.** ``catalog``, ``targets``, ``candidates``, ``trials``,
``literature``, ``pathways``, ``summary``, ``lineage``, ``register``, ``linked_iterations``
and ``strategy`` come back together. The tables are a few hundred kilobytes of text and the
page cross-filters them — a candidate against its target, a target against its pathway — so
paginating them would only move the joins into the browser's request waterfall.

**Cached, because the database is the cost.** Parsing the TSVs is milliseconds; the lineage
walk is a round trip to a hosted PostgreSQL. One entry under the key ``track2`` holds the
whole payload and ``?refresh=true`` rebuilds it, exactly like ``/api/submissions``.

**The lineage degrades rather than fails.** With no credentials, ``lineage.available`` is
false and the sources are the manifests' own claims — which is what the recorded edges were
written from anyway, so the page loses the *confirmation*, not the content.

**Track 2 carries no patient data at all.** Every row is a gene symbol, a drug name, a
trial id or a citation, derived from public APIs. The one link to the case is the mechanism
card, which is coordinate-free by rule: it names the gene, the protein and the variant
classes, never a position.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ..warehouse.settings import Postgres
from . import submissions_audit, submissions_lineage, submissions_reader, track2_lineage
from . import track2_reader as reader
from .cache import Cache
from .response import Envelope, cached

#: Cache key for the whole payload. Named rather than derived: the route takes no parameter.
CACHE_KEY = "track2"

#: Everything the payload was assembled from, for the envelope's ``source`` line.
SOURCE = (
    "ressources/track2/*.tsv + *.provenance.json + mechanism.json + snapshot.json, "
    "warehouse.data_lineage, docs/science-register.json, submissions/*/iteration-*/"
)

#: The step whose claims this page shows. Track 2 is step 8 of the roadmap.
STEP = "step-8"

#: How Track 2 reaches its final suggestion, as the step's README states it. Static because
#: it is a *plan*, not a measurement: nothing in the data can tell you that the ranking is
#: open or that the merge waits on the last oracle reply. ``status`` is one of ``done``,
#: ``open`` (workable now) and ``waiting`` (blocked on something outside Track 2).
STRATEGY: list[dict[str, Any]] = [
    {
        "id": "handoff",
        "title": "Hand-off from Track 1",
        "status": "done",
        "detail": (
            "The mechanism card (ressources/track2/mechanism.json, version 2) is written "
            "from the iteration-1 research record: the gene, the protein, the two allele "
            "classes, the pathway, and four repurposing directions with seed targets. "
            "Coordinate-free by rule — it names consequences, never positions."
        ),
        "depends_on": [],
    },
    {
        "id": "snapshot",
        "title": "Evidence snapshot from public sources",
        "status": "done",
        "detail": (
            "mva-drugs snapshot expands the card's seed targets through Reactome, then "
            "queries Open Targets, ChEMBL, DGIdb, openFDA, ClinicalTrials.gov and PubMed "
            "for every target. Five TSVs, a provenance manifest each, and lineage edges "
            "under target_schema 'track2'."
        ),
        "depends_on": ["handoff"],
    },
    {
        "id": "ranking",
        "title": "Ranking and a hypothesis per candidate drug",
        "status": "open",
        "detail": (
            "3,766 drug-target rows are evidence, not an answer. Each candidate that "
            "survives the approved filter needs a scored, cited path from the allele to "
            "its target, and a registered claim with its refutation condition before it "
            "is argued."
        ),
        "depends_on": ["snapshot"],
    },
    {
        "id": "report",
        "title": "Report structured along methods-form Q14",
        "status": "open",
        "detail": (
            "Loss- versus gain-of-function, the pathway, the downstream consequence, and "
            "the drug x mechanism evidence table with a pathway diagram from the allele "
            "to each intervention point."
        ),
        "depends_on": ["ranking"],
    },
    {
        "id": "verdicts",
        "title": "Verdicts on H010 and H011",
        "status": "waiting",
        "detail": (
            "The mechanism rests on an inferred trans pair. Confidence is not committed "
            "on any Track 2 claim until step 6's oracle reply confirms the pair — a "
            "mechanism argued from an unconfirmed allele is a guess dressed as rigour."
        ),
        "depends_on": ["snapshot"],
    },
    {
        "id": "merge",
        "title": "Merge every Track 1 iteration into one final suggestion",
        "status": "waiting",
        "detail": (
            "Each oracle reply revises the card (a new version and a history entry, never "
            "an edit) and the snapshot is re-run. The final suggestion is produced once, "
            "after the last reply: all iterations' evidence merged, the ranking re-run on "
            "the confirmed pair, the report written from that merged state."
        ),
        "depends_on": ["verdicts", "report"],
    },
]


def linked_iterations(cited: list[str], root: Path) -> list[dict[str, Any]]:
    """The Track 1 iterations whose claims the card was written from.

    The link is the **hypotheses**, not a hard-coded folder name: an iteration is linked
    when the claims it argues intersect the ones the card cites, so iteration 2's reply
    links itself as soon as its folder exists. Only the identifying fields are returned —
    a page that wants the full iteration asks ``/api/submissions`` for it.
    """
    wanted = set(cited)
    linked = []
    for folder in submissions_reader.iteration_folders(root):
        iteration = submissions_reader.read(folder, root)
        shared = sorted(wanted.intersection(iteration["hypotheses"]))
        if not shared:
            continue
        linked.append(
            {
                "track": iteration["track"],
                "number": iteration["number"],
                "folder": iteration["folder"],
                "state": iteration["state"],
                "standing": iteration["standing"],
                "hypotheses": shared,
            }
        )
    return linked


def payload(settings: Postgres, root: Path | None = None) -> dict[str, Any]:
    """The whole Track 2 surface. One ledger read; everything else is disk."""
    base = (root or reader.DEFAULT_ROOT).resolve()
    rows, catalog = reader.tables(base)
    mechanism = reader.card(base)
    ledger = submissions_lineage.read_ledger(settings)
    cited = reader.cited_hypotheses(reader.card_text(base))
    return {
        "card": mechanism,
        "catalog": catalog,
        "targets": rows["targets"],
        "pathways": rows["pathways"],
        "candidates": rows["drug_candidates"],
        "trials": rows["trials"],
        "literature": rows["literature"],
        "summary": reader.summary(base),
        "lineage": track2_lineage.build(ledger, base),
        "register": reader.register(submissions_audit.read_register(base), STEP),
        "linked_iterations": linked_iterations(cited, base),
        "strategy": STRATEGY,
    }


def add_routes(api: APIRouter, settings: Postgres, cache: Cache, root: Path | None = None) -> None:
    """Register the Track 2 route on the warehouse router."""
    base = (root or reader.DEFAULT_ROOT).resolve()

    @api.get(
        "/track2",
        response_model=Envelope,
        tags=["track2"],
        summary="the mechanism card, the drug evidence snapshot, and its provenance",
    )
    def track2(refresh: bool = False) -> dict:
        """Everything Track 2 has: the mechanism, the evidence, and where it came from.

        ``card`` is ``ressources/track2/mechanism.json`` verbatim — the hand-off from
        Track 1, revised and never edited, so ``history`` is the record of every revision.

        ``catalog`` documents each table in plain English: what every column means, how the
        table was built (the manifest's own ``method``), and which API replies at which
        digest it was built from. ``columns[].description`` is **null** for a column the
        dictionary does not know, rendered as a visible gap rather than a guess.

        The five table blocks are the rows themselves, typed by the catalogue's rule. An
        empty field means **unknown**: ``max_phase`` null is "no source stated one" and
        ``fda_label`` empty is "never checked", neither of which is a zero or a false.

        ``lineage.available`` is **false** on a checkout with no database; ``sources`` is
        then the manifests' own claims and ``edges`` is empty. When it is true, ``edges``
        also carries the walk back through the Track 1 iteration to the callset object.

        ``register`` is the step-8 claims as filed: statement, prediction and refutation
        condition. ``confidence`` is **null** wherever none has been committed, which is
        every Track 2 claim until the oracle confirms the pair.

        ``strategy`` is a static plan, not a measurement — see :data:`STRATEGY`.
        """
        entry = cache.get_or_build(CACHE_KEY, lambda: payload(settings, base), refresh)
        return cached(entry, SOURCE)
