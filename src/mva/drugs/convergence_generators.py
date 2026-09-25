"""Two generators built from tables that already exist: the graph walk and the phenotype twin.

*Plain words.* Step 10 fixes, before any join, the rule that turns each source into a list
(``docs/iteration4/step-10/README.md``, "The generator rules"). This module is those rules
for two sources, as pure functions over already-read records:

* **walk** (G1): the PrimeKG walk's drugs in score order; the list is the first ``top``
  distinct drugs (by join key) that carry a US label; the universe is every drug the walk
  reached, flagged approved when labelled.
* **twin** (G2): rows of the phenotype twin's intervention table whose
  ``supports_direction`` begins with ``supports``; the drugs are the analogues the row's
  ``analogue_status`` itself calls approved (:func:`approved_analogues`). The universe is
  every approved analogue named by *any* row, plus the other generators' universes.

A check never votes: nothing here reads a screen, a safety table or a mechanism class.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .convergence_tables import DIRECTION_HINTS, GeneratorRow
from .names import base_name

__all__ = [
    "SUPPORTS_PREFIX",
    "WalkCandidate",
    "approved_analogues",
    "twin_rows",
    "twin_universe",
    "walk_rows",
    "walk_universe",
]

#: A twin row votes when its ``supports_direction`` starts with this word. ``hypothesis
#: only``, ``limits``, ``warns`` and ``context`` do not vote.
SUPPORTS_PREFIX = "supports"

_TOKEN = re.compile(r"[a-z][a-z0-9-]*")
_APPROVED_AFTER = re.compile(r"([a-z][a-z0-9-]*) approved\b")
_PARENS = re.compile(r"\([^)]*\)")
_SPLIT = re.compile(r"[/,;+:]| and ")
#: Words that can stand before ``approved`` without naming a drug (``"not approved"``,
#: ``"none approved"``).
_NOT_A_DRUG = frozenset({"not", "no", "none", "is", "are", "be", "but", "also", "as"})


@dataclass(frozen=True)
class WalkCandidate:
    """One drug node the walk reached, with its label lookup already done.

    ``labelled`` is ``None`` when openFDA refused the query (a name it cannot search, e.g. a
    systematic chemical name); such a drug is in the universe as not approved.
    """

    drug_name: str
    drugbank_id: str
    score: float
    rank_all: int
    labelled: bool | None
    application: str
    targets: tuple[str, ...]
    best_path: str


def walk_rows(
    candidates: Sequence[WalkCandidate], top: int, generator: str = "walk"
) -> list[GeneratorRow]:
    """The first ``top`` labelled drugs, distinct by join key, in walk order."""
    out: list[GeneratorRow] = []
    seen: set[str] = set()
    for item in sorted(candidates, key=lambda c: c.rank_all):
        key = base_name(item.drug_name)
        if not item.labelled or key in seen:
            continue
        seen.add(key)
        out.append(
            GeneratorRow(
                generator=generator,
                rank=len(out) + 1,
                drug=key,
                drug_label=item.drug_name,
                approved=True,
                approval_evidence=(
                    f"openFDA label {item.application}"
                    if item.application
                    else "openFDA label, no application number (e.g. a combination product)"
                ),
                score=f"{item.score:.6g}",
                score_name="degree-weighted path count from the disease node (entry 142)",
                direction_hint="none",
                evidence=(
                    f"walk rank {item.rank_all} of all reached drugs; targets reached: "
                    f"{'|'.join(item.targets) or 'none'}; best path: {item.best_path}"
                ),
                source_ids=item.drugbank_id,
            )
        )
        if len(out) >= top:
            break
    return out


def walk_universe(candidates: Iterable[WalkCandidate]) -> dict[str, bool]:
    """Every reached drug by join key; approved when any spelling of it is labelled."""
    out: dict[str, bool] = {}
    for item in candidates:
        key = base_name(item.drug_name)
        out[key] = out.get(key, False) or bool(item.labelled)
    return out


def approved_analogues(analogue: str, status: str) -> list[str]:
    """The drugs a twin row's own ``analogue_status`` calls approved, lower-case.

    Two forms occur, and both are read literally:

    * ``"<drug> approved ..."`` (e.g. ``"dasatinib approved (CML)"``): the word before
      ``approved`` is kept when it is also a word of ``analogue`` - so ``"navitoclax not
      approved"`` and ``"none approved"`` yield nothing (``not``/``none`` are never drugs);
    * ``"approved (...)"`` as the whole status: every name in ``analogue`` is approved;
      names are the pieces of ``analogue`` split on ``/ , ; + :`` with parentheses removed.
    """
    text = status.strip().lower()
    words = set(_TOKEN.findall(analogue.lower()))
    if text.startswith("approved"):
        pieces = [p.strip() for p in _SPLIT.split(_PARENS.sub("", analogue.lower()))]
        return [p for p in pieces if p and _TOKEN.fullmatch(p) and p not in _NOT_A_DRUG]
    found: list[str] = []
    for word in _APPROVED_AFTER.findall(text):
        if word in words and word not in _NOT_A_DRUG and word not in found:
            found.append(word)
    return found


def _direction(value: str) -> str:
    head = value.strip().split(" ")[0]
    return head if head in DIRECTION_HINTS else "none"


def twin_rows(
    interventions: Sequence[Mapping[str, str]], generator: str = "twin"
) -> tuple[list[GeneratorRow], list[dict[str, str]]]:
    """The twin's list, and a record of every row that did not vote and why.

    Ranked by the number of supporting rows naming the drug (more = better), then by the
    best Phenodigm twin rank of those rows' models, then by name.
    """
    votes: dict[str, list[Mapping[str, str]]] = {}
    skipped: list[dict[str, str]] = []
    for row in interventions:
        support = row.get("supports_direction", "").strip().lower()
        names = approved_analogues(
            row.get("nearest_approved_analogue", ""), row.get("analogue_status", "")
        )
        if not support.startswith(SUPPORTS_PREFIX):
            skipped.append(
                {
                    "intervention": row.get("intervention", ""),
                    "reason": f"supports_direction = {support!r}",
                }
            )
            continue
        if not names:
            skipped.append(
                {
                    "intervention": row.get("intervention", ""),
                    "reason": "supports, but its analogue_status names no approved drug",
                }
            )
            continue
        for name in names:
            votes.setdefault(base_name(name), []).append(row)

    def twin_rank(rows: list[Mapping[str, str]]) -> int:
        ranks = [
            int(r["twin_rank_phenodigm"])
            for r in rows
            if r.get("twin_rank_phenodigm", "").isdigit()
        ]
        return min(ranks) if ranks else 10**9

    order = sorted(votes, key=lambda d: (-len(votes[d]), twin_rank(votes[d]), d))
    out: list[GeneratorRow] = []
    for rank, drug in enumerate(order, start=1):
        rows = votes[drug]
        directions = sorted({_direction(r.get("direction", "")) for r in rows} - {"none"})
        out.append(
            GeneratorRow(
                generator=generator,
                rank=rank,
                drug=drug,
                drug_label=drug.lower(),
                approved=True,
                approval_evidence="analogue_status: "
                + " | ".join(sorted({r["analogue_status"] for r in rows})),
                score=str(len(rows)),
                score_name="supporting intervention rows naming the drug (entry 150)",
                direction_hint="|".join(directions) or "none",
                evidence="; ".join(
                    f"{r.get('model', '')}: {r.get('intervention', '')}" for r in rows
                ),
                source_ids="|".join(sorted({f"PMID:{r['pmid']}" for r in rows if r.get("pmid")})),
            )
        )
    return out, skipped


def twin_universe(
    interventions: Sequence[Mapping[str, str]], others: Iterable[Iterable[str]] = ()
) -> dict[str, bool]:
    """Approved analogues named by any row (voting or not), plus every other universe."""
    out: dict[str, bool] = {}
    for row in interventions:
        for name in approved_analogues(
            row.get("nearest_approved_analogue", ""), row.get("analogue_status", "")
        ):
            out[base_name(name)] = True
    for universe in others:
        for drug in universe:
            out[base_name(drug)] = True
    return out
