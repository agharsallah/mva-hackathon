"""The walk's ranking as a table: approved drugs only, every score traceable to its paths.

*Plain words.* The graph walk (:mod:`mva.drugs.graph_walk`) ranks every drug node it can
reach, most of them experimental compounds. The challenge accepts **market-approved** drugs
only, so this module walks the ranking top-down and keeps a drug only when openFDA holds a
current US label for its name (:func:`mva.drugs.sources.openfda.label`, the same check
``drug_candidates.tsv`` uses), until ``keep`` drugs are kept. The label lookup is injected as
a callable, so the rule is testable without a network.

Names are compared through :func:`mva.drugs.names.base_name` everywhere (salt words folded,
upper-cased): the walk's drug names are DrugBank's, the candidate list's are ChEMBL's.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .graph_walk import Path as WalkPath
from .graph_walk import Ranked, WalkResult
from .names import base_name

__all__ = [
    "COLUMNS",
    "PATH_COLUMNS",
    "Kept",
    "candidate_names",
    "keep_approved",
    "path_rows",
    "rows",
    "write_tsv",
]

COLUMNS = (
    "rank",
    "drug_name",
    "drugbank_id",
    "score",
    "paths",
    "paths_direct",
    "paths_ppi",
    "paths_pathway",
    "via_disease_genes",
    "targets_reached",
    "best_path",
    "fda_generic_name",
    "fda_application",
    "walk_rank_all",
    "in_drug_candidates",
    "standard_of_care",
)

PATH_COLUMNS = ("rank", "drug_name", "metapath", "weight", "path")


@dataclass(frozen=True)
class Kept:
    """One approved drug: its walk row, its rank among *all* drugs, and its label."""

    row: Ranked
    rank_all: int
    label: dict[str, Any]


def keep_approved(
    ranking: list[Ranked], label: Callable[[str], dict[str, Any]], keep: int
) -> tuple[list[Kept], int]:
    """The first ``keep`` drugs, in rank order, that ``label`` says carry a US label.

    Returns the kept drugs and how many were checked to find them.
    """
    kept: list[Kept] = []
    checked = 0
    for position, row in enumerate(ranking, start=1):
        if len(kept) >= keep:
            break
        checked += 1
        found = label(base_name(row.drug.name))
        if found.get("has_label"):
            kept.append(Kept(row, position, found))
    return kept, checked


def candidate_names(path: Path) -> set[str]:
    """Every ``drug_name`` in a ``drug_candidates.tsv``, as a base name."""
    with path.open(encoding="utf-8", newline="") as handle:
        return {base_name(r["drug_name"]) for r in csv.DictReader(handle, delimiter="\t")}


def _by_drug(result: WalkResult) -> dict[str, list[WalkPath]]:
    grouped: dict[str, list[WalkPath]] = defaultdict(list)
    for path in result.paths:
        grouped[path.drug].append(path)
    return grouped


def rows(
    result: WalkResult,
    kept: list[Kept],
    *,
    candidates: set[str],
    standard_of_care: Iterable[str],
) -> list[dict[str, Any]]:
    """One TSV row per kept drug, ranked 1..n among the approved."""
    names = result.graph.nodes
    soc = {base_name(d) for d in standard_of_care}
    grouped = _by_drug(result)
    out: list[dict[str, Any]] = []
    for rank, item in enumerate(kept, start=1):
        row = item.row
        via = Counter(names[p.keys[1]].name for p in grouped[row.drug.key])
        name = base_name(row.drug.name)
        out.append(
            {
                "rank": rank,
                "drug_name": row.drug.name,
                "drugbank_id": row.drug.source_id,
                "score": f"{row.score:.6g}",
                "paths": row.paths,
                "paths_direct": row.by_metapath.get("direct", 0),
                "paths_ppi": row.by_metapath.get("ppi", 0),
                "paths_pathway": row.by_metapath.get("pathway", 0),
                "via_disease_genes": "|".join(f"{g}:{n}" for g, n in sorted(via.items())),
                "targets_reached": "|".join(row.targets),
                "best_path": row.best.render(result.graph),
                "fda_generic_name": item.label.get("generic_name", ""),
                "fda_application": "|".join(item.label.get("application_numbers", ())[:3]),
                "walk_rank_all": item.rank_all,
                "in_drug_candidates": str(name in candidates).lower(),
                "standard_of_care": str(name in soc).lower(),
            }
        )
    return out


def path_rows(result: WalkResult, kept: list[Kept], top: int) -> list[dict[str, Any]]:
    """Every path behind the first ``top`` kept drugs: the score, printed as its sum."""
    out: list[dict[str, Any]] = []
    for rank, item in enumerate(kept[:top], start=1):
        out.extend(
            {
                "rank": rank,
                "drug_name": item.row.drug.name,
                "metapath": path.metapath,
                "weight": f"{path.weight:.6g}",
                "path": " > ".join(result.graph.nodes[k].name for k in path.keys),
            }
            for path in result.paths_for(item.row.drug.key)
        )
    return out


def write_tsv(records: list[dict[str, Any]], columns: tuple[str, ...], path: Path) -> int:
    """Write rows as a tab-separated file with a header; returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    return len(records)
