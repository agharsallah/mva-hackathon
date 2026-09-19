"""The zoo's ranking table and its lineage: what each lane did with the callset's pairs.

``<results>.it4_model_ranks`` holds, per run and per lane, the top pairs and — always, even
when it fell below the cut — the confirmed pair's row. This module turns that into the
per-lane summary the dashboard draws, and reads ``warehouse.data_lineage`` down to the four
tables the zoo writes.

Two honesty rules are implemented here rather than described elsewhere:

* **A lane that could not score a pair is not credited with an opinion.** ``unscored_pairs``
  is served beside every lane's ``n_ranked``; a percentile quoted without it is a number
  over a population the lane never saw.
* **``skipped_genes`` is reported as unrecorded, not as empty.** :class:`mva.zoo.pairs.PairBuild`
  counts the genes whose heterozygous-call count exceeded the cap, but the rank stage does
  not persist that list, so no query can recover it. The field is therefore ``[]`` with
  ``skipped_genes_recorded: false`` beside it — an absent measurement, never a claim that
  nothing was skipped.

The left/right percentiles of the confirmed pair are *not* columns of this table; they are
computed by the merge step and live in its report JSON. They are filled in from there when
the merged report belongs to the same run, and are ``null`` otherwise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..zoo.registry import ModelCard
from .api_zoo_reads import Tables, qualified, rows_of

__all__ = ["latest_run", "lineage_rows", "rank_runs", "ranks_payload"]

#: The columns served from the rank table. Every one is coordinate-free: a pair is a gene
#: symbol plus two ``allele_id`` hashes (:class:`mva.zoo.pairs.Pair`).
RANK_FIELDS = (
    "run_id",
    "model",
    "gene",
    "left_allele_id",
    "right_allele_id",
    "phase",
    "min_score",
    "max_score",
    '"rank"',
    "n_ranked",
    "percentile",
    "unscored_pairs",
    "is_confirmed",
    "ts",
)

#: The append-only edge list every warehouse writer records into. Shared with
#: ``/api/provenance/lineage``, which serves the whole table rather than the zoo's slice.
LINEAGE_TABLE = "data_lineage"

#: The lineage columns, the same ones ``/api/provenance/lineage`` serves.
LINEAGE_FIELDS = (
    "produced_at",
    "target_schema",
    "target_table",
    "target_rows",
    "source_kind",
    "source_ref",
    "source_version",
    "source_sha256",
    "transform",
    "tool",
    "notes",
)


def rank_runs(connection: Any, tables: Tables) -> list[dict[str, Any]]:
    """Every run present in the rank table, newest first, with its lane and row counts."""
    return rows_of(
        connection,
        "SELECT run_id, count(*) AS rows, count(DISTINCT model) AS models, "
        f"max(ts) AS last_written FROM {qualified(tables.results, tables.ranks)} "
        "GROUP BY run_id ORDER BY last_written DESC",
    )


def latest_run(connection: Any, tables: Tables) -> str | None:
    """The most recently written run id, or ``None`` when no run has been ranked."""
    runs = rank_runs(connection, tables)
    return str(runs[0]["run_id"]) if runs else None


def _rank_rows(connection: Any, tables: Tables, run_id: str) -> list[dict[str, Any]]:
    return rows_of(
        connection,
        f"SELECT {', '.join(RANK_FIELDS)} "
        f"FROM {qualified(tables.results, tables.ranks)} "
        'WHERE run_id = ? ORDER BY model, "rank"',
        [run_id],
    )


def _pick(row: Mapping[str, Any] | None, merged: Mapping[str, Any], key: str) -> Any:
    """The rank table's value, falling back to the merged report's when it has none."""
    value = None if row is None else row.get(key)
    return merged.get(key) if value is None else value


def _confirmed(
    rows: Sequence[Mapping[str, Any]], lane: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """The confirmed pair's place in one lane, or ``None`` when this lane never ranked it.

    ``left_percentile``/``right_percentile`` are the two *alleles'* standings and come from
    the merged report (:mod:`mva.zoo.merge`); the rank table holds the *pair*. A lane that
    ranked no confirmed row still reports the merged report's per-allele percentiles when
    it has them — "this lane scored one half and not the other" is the finding.
    """
    row = next((row for row in rows if row["is_confirmed"]), None)
    merged = (lane or {}).get("confirmed") or {}
    if row is None and not merged:
        return None
    return {
        "gene": (row or {}).get("gene") or merged.get("gene"),
        "rank": _pick(row, merged, "rank"),
        "percentile": _pick(row, merged, "percentile"),
        "left_percentile": merged.get("left_percentile"),
        "right_percentile": merged.get("right_percentile"),
        "min_score": _pick(row, merged, "min_score"),
        "max_score": _pick(row, merged, "max_score"),
        "phase": (row or {}).get("phase"),
        "left_allele_id": (row or {}).get("left_allele_id"),
        "right_allele_id": (row or {}).get("right_allele_id"),
    }


def _top(rows: Sequence[Mapping[str, Any]], limit: int) -> list[dict[str, Any]]:
    """The lane's best pairs, as the table stored them (top N per lane, plus the confirmed)."""
    ordered = sorted(rows, key=lambda row: (row["rank"] is None, row["rank"] or 0))
    return [
        {
            "gene": row["gene"],
            "left_allele_id": row["left_allele_id"],
            "right_allele_id": row["right_allele_id"],
            "phase": row["phase"],
            "rank": row["rank"],
            "percentile": row["percentile"],
            "min_score": row["min_score"],
            "max_score": row["max_score"],
            "is_confirmed": row["is_confirmed"],
        }
        for row in ordered[:limit]
    ]


def ranks_payload(
    connection: Any,
    tables: Tables,
    *,
    run_id: str | None = None,
    cards: Mapping[str, ModelCard] | None = None,
    lanes: Mapping[str, Mapping[str, Any]] | None = None,
    lanes_run_id: str | None = None,
    top: int = 10,
) -> dict[str, Any] | None:
    """One run's ranking, lane by lane. ``None`` when the run has no rows at all.

    ``lanes`` is the merged report's per-lane block and is used only when
    ``lanes_run_id`` is the run being served — see below.

    ``pairs_total`` is ``n_ranked + unscored_pairs`` — the widest lane's view of how many
    biallelic pairs the callset offered. Lanes disagree about it only when they disagree
    about what they could score, which is exactly what ``unscored_pairs`` says.
    """
    wanted = run_id or latest_run(connection, tables)
    if wanted is None:
        return None
    rows = _rank_rows(connection, tables, wanted)
    if not rows:
        return None
    # The merged report is one file per output directory, so it may describe another run.
    # Borrowing its percentiles then would be a quietly wrong number, not a missing one.
    borrowed = dict(lanes or {}) if lanes_run_id == wanted else {}

    by_model: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_model.setdefault(str(row["model"]), []).append(row)

    per_model = []
    pairs_total = 0
    for model, lane_rows in sorted(by_model.items()):
        n_ranked = max(int(row["n_ranked"] or 0) for row in lane_rows)
        unscored = max(int(row["unscored_pairs"] or 0) for row in lane_rows)
        pairs_total = max(pairs_total, n_ranked + unscored)
        card = (cards or {}).get(model)
        per_model.append(
            {
                "model": model,
                "catalogue_adjacent": None if card is None else card.catalogue_adjacent,
                "version": None if card is None else card.version,
                "n_ranked": n_ranked,
                "unscored_pairs": unscored,
                "confirmed": _confirmed(lane_rows, borrowed.get(model)),
                "top": _top(lane_rows, top),
            }
        )
    return {
        "run_id": wanted,
        "per_model": per_model,
        "pairs_total": pairs_total,
        "skipped_genes": [],
        # See the module docstring: the cap-skipped genes are counted by the pair builder
        # and never written down, so this is an absent measurement rather than an empty one.
        "skipped_genes_recorded": False,
    }


def lineage_rows(connection: Any, tables: Tables, table: str | None = None) -> list[dict[str, Any]]:
    """``warehouse.data_lineage`` narrowed to the zoo's own tables, newest first."""
    targets = [table] if table else list(tables.names)
    marks = ", ".join("?" for _ in targets)
    return rows_of(
        connection,
        f"SELECT {', '.join(LINEAGE_FIELDS)} "
        f"FROM {qualified(tables.warehouse, LINEAGE_TABLE)} "
        f"WHERE target_table IN ({marks}) ORDER BY produced_at DESC",
        targets,
    )
