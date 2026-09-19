"""The zoo's warehouse reads: coverage, one allele's scores, a gene's, and the rankings.

Four tables, all written by :mod:`mva.zoo` and all **coordinate-free by construction** —
the position of every allele stays in ``build/`` (gitignored) and only the ``allele_id``
hash leaves:

* ``<results>.it4_allele_records`` — one row per allele, in every spelling a model reads
  (gene, consequence, HGVS, UniProt). :data:`mva.zoo.types.RECORDS_TABLE`.
* ``<warehouse>.allele_scores`` — the score cache: one row per (model, version, allele).
  :data:`mva.zoo.types.ALLELE_SCORES_TABLE`.
* ``<results>.it4_model_ranks`` — each lane's top pairs plus the confirmed pair's place.
  :data:`mva.zoo.rank.MODEL_RANKS_TABLE`.
* ``<results>.it4_model_reports`` — one report JSON per (model, run).
  :data:`mva.zoo.report.MODEL_REPORTS_TABLE`.

Neither the schema names nor the table names are written here: the tables come from the
run configuration (:class:`Tables`, built in :mod:`mva.viz.api_zoo` from the zoo's TOML)
and the table names from the zoo modules that own the DDL. A different case runs the same
routes by pointing at a different config.

**Every function takes a connection rather than opening one**, exactly like
:mod:`mva.zoo.cache`: the production connection is DuckDB with PostgreSQL attached as
``pg``, so a test can hand in an in-memory DuckDB with ``ATTACH ':memory:' AS pg`` and
exercise this module's real SQL instead of a mock of it. :func:`connect` is the one seam
that opens the real thing.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from ..warehouse.postgres import ALIAS, attached, safe_identifier
from ..warehouse.settings import Postgres
from ..zoo.rank import MODEL_RANKS_TABLE
from ..zoo.registry import ModelCard, card_with_coverage
from ..zoo.report import MODEL_REPORTS_TABLE
from ..zoo.types import ALLELE_SCORES_TABLE, RECORDS_TABLE, Coverage
from ..zoo.workflow_types import DEFAULT_PREFIX, Config

__all__ = [
    "ZOO_TABLES",
    "Tables",
    "connect",
    "coverages",
    "gene_payload",
    "genes_of",
    "models_payload",
    "qualified",
    "record",
    "records_of_gene",
    "rows_of",
    "score_rows",
    "scores_payload",
]

#: The four tables the zoo writes under the default case prefix, named by the modules that
#: own their DDL — never typed here. :meth:`Tables.of` re-derives them for another case.
ZOO_TABLES: tuple[str, ...] = (
    RECORDS_TABLE,
    ALLELE_SCORES_TABLE,
    MODEL_RANKS_TABLE,
    MODEL_REPORTS_TABLE,
)

#: A consequence class the record table left null. Written as a visible word rather than a
#: JSON ``null`` key, because ``by_consequence`` is keyed by string.
UNKNOWN_CONSEQUENCE = "unknown"

#: The record columns that are safe to serve: the whole coordinate-free row. ``built_at``
#: and ``source`` are its own provenance, which is why they are here and not stripped.
RECORD_FIELDS: tuple[str, ...] = (
    "allele_id",
    "gene",
    "transcript",
    "consequence",
    "hgvs_c",
    "hgvs_p",
    "uniprot",
    "is_read_only",
    "af_gnomad",
    "clin_sig",
    "source",
)

#: How many alleles go into one ``IN (...)`` list. Same reason as
#: :data:`mva.zoo.cache.BATCH`: a gene with hundreds of alleles is a few statements rather
#: than one SQL string megabytes long.
CHUNK = 5_000


@dataclass(frozen=True)
class Tables:
    """Where this case's zoo tables live: two tables and four table names.

    Nothing here is a constant of the method. The tables come from the run config's
    ``[run]`` block and the names from its ``[case] table_prefix``, so a second case writes
    ``<prefix>_allele_records`` beside this one rather than over it
    (:meth:`mva.zoo.workflow_types.Config.table`). The defaults are the names the zoo's own
    DDL modules declare, which is what a call with no config gets.
    """

    results: str = "results"
    warehouse: str = "warehouse"
    records: str = RECORDS_TABLE
    scores: str = ALLELE_SCORES_TABLE
    ranks: str = MODEL_RANKS_TABLE
    reports: str = MODEL_REPORTS_TABLE

    @property
    def names(self) -> tuple[str, ...]:
        """The four tables, in the order ``/api/zoo/lineage`` lists them."""
        return (self.records, self.scores, self.ranks, self.reports)

    @classmethod
    def of(cls, config: Config) -> Tables:
        """The tables one run configuration names. The prefix travels; the suffix does not."""
        return cls(
            results=config.schema,
            warehouse=config.warehouse_schema,
            records=config.table(_suffix(RECORDS_TABLE)),
            # The score cache is shared across cases and carries no prefix: its key is
            # (model, version, allele_id), and an allele_id is already case-unique.
            scores=ALLELE_SCORES_TABLE,
            ranks=config.table(_suffix(MODEL_RANKS_TABLE)),
            reports=config.table(_suffix(MODEL_REPORTS_TABLE)),
        )


def _suffix(table: str) -> str:
    """``"it4_model_ranks"`` -> ``"model_ranks"``: the part that is not the case's prefix."""
    return table.removeprefix(f"{DEFAULT_PREFIX}_")


@contextmanager
def connect(settings: Postgres) -> Iterator[Any]:
    """A read-only DuckDB connection with the warehouse attached as ``pg``.

    The one seam a test replaces: monkeypatching this yields an in-memory database to
    every route without any route knowing.
    """
    with attached(settings, read_only=True) as connection:
        yield connection


def qualified(schema: str, table: str) -> str:
    return f"{ALIAS}.{safe_identifier(schema)}.{safe_identifier(table)}"


def rows_of(connection: Any, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    """One statement, as JSON-safe dicts. ``queries.access.rows`` over a live connection."""
    from .queries.access import rows as as_dicts

    return as_dicts(connection, sql, list(params or []))


def _chunks(values: Sequence[str]) -> Iterator[Sequence[str]]:
    for start in range(0, len(values), CHUNK):
        yield values[start : start + CHUNK]


def _aux(value: Any) -> dict[str, Any]:
    """The ``aux`` column is JSON text. An unreadable value is shown, never dropped."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {"_unparsed": str(value)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


# ---------------------------------------------------------------------------------------
# Coverage — how much of the record set each lane could actually score
# ---------------------------------------------------------------------------------------


def coverages(connection: Any, tables: Tables) -> dict[str, Coverage]:
    """Per model, how many records it scored, in total and per consequence class.

    Two aggregates rather than one per model: the totals of the record table, and the
    scored count per (model, consequence). A model absent from the second is absent from
    the result — a lane that never ran has *no* coverage, which is a different statement
    from a coverage of zero.
    """
    records = qualified(tables.results, tables.records)
    scores = qualified(tables.warehouse, tables.scores)
    totals = {
        str(row["consequence"]): int(row["total"])
        for row in rows_of(
            connection,
            f"SELECT coalesce(consequence, '{UNKNOWN_CONSEQUENCE}') AS consequence, "
            f"count(DISTINCT allele_id) AS total FROM {records} GROUP BY 1",
        )
    }
    scored: dict[str, dict[str, int]] = {}
    for row in rows_of(
        connection,
        f"SELECT s.model AS model, "
        f"coalesce(r.consequence, '{UNKNOWN_CONSEQUENCE}') AS consequence, "
        f"count(DISTINCT s.allele_id) AS scored "
        f"FROM {scores} s JOIN {records} r ON r.allele_id = s.allele_id "
        f"WHERE s.score IS NOT NULL GROUP BY 1, 2",
    ):
        scored.setdefault(str(row["model"]), {})[str(row["consequence"])] = int(row["scored"])

    total_all = sum(totals.values())
    return {
        model: Coverage(
            model=model,
            scored=sum(by_class.values()),
            total=total_all,
            by_consequence={
                consequence: (by_class.get(consequence, 0), total)
                for consequence, total in sorted(totals.items())
            },
        )
        for model, by_class in scored.items()
    }


def models_payload(
    connection: Any, cards: Mapping[str, ModelCard], tables: Tables
) -> list[dict[str, Any]]:
    """Every declared model card, with the coverage it actually reached.

    ``coverage`` is **null** for a lane with no row in the score cache: declared, never
    run. :func:`mva.zoo.registry.card_with_coverage` builds the shape, so the API and the
    step-5 report cannot drift apart.
    """
    measured = coverages(connection, tables)
    return [
        card_with_coverage(card, measured[key])
        if key in measured
        else {**card.as_dict(), "coverage": None}
        for key, card in sorted(cards.items())
    ]


# ---------------------------------------------------------------------------------------
# Records and scores
# ---------------------------------------------------------------------------------------


def record(connection: Any, tables: Tables, allele_id: str) -> dict[str, Any] | None:
    """One allele's coordinate-free record, or ``None`` when the table does not know it."""
    found = rows_of(
        connection,
        f"SELECT {', '.join(RECORD_FIELDS)} FROM {qualified(tables.results, tables.records)} "
        "WHERE allele_id = ? ORDER BY built_at DESC LIMIT 1",
        [allele_id],
    )
    return found[0] if found else None


def records_of_gene(connection: Any, tables: Tables, gene: str, limit: int) -> list[dict]:
    """Every record of one gene symbol, newest first. Case-insensitive on the symbol."""
    return rows_of(
        connection,
        f"SELECT {', '.join(RECORD_FIELDS)} FROM {qualified(tables.results, tables.records)} "
        "WHERE upper(gene) = ? ORDER BY allele_id LIMIT ?",
        [gene.upper(), limit],
    )


def genes_of(connection: Any, tables: Tables, allele_ids: Sequence[str]) -> dict[str, str]:
    """``allele_id`` → gene symbol, for the ids a payload already holds.

    The merged report's disagreement table names alleles, not genes; this is the join that
    lets the page say *which gene* two lanes disagree about without the merge step having
    to store the symbol twice.
    """
    table = qualified(tables.results, tables.records)
    found: dict[str, str] = {}
    for chunk in _chunks(list(dict.fromkeys(allele_ids))):
        marks = ", ".join("?" for _ in chunk)
        for row in rows_of(
            connection,
            f"SELECT allele_id, gene FROM {table} WHERE allele_id IN ({marks})",
            list(chunk),
        ):
            if row["gene"]:
                found[str(row["allele_id"])] = str(row["gene"])
    return found


def score_rows(
    connection: Any, tables: Tables, allele_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """The score cache for a set of alleles, grouped by ``allele_id``.

    :func:`mva.zoo.cache.read` is the sibling of this query and is what the *workflow*
    uses; it omits ``ts``, which this API contract carries (a page has to be able to say
    when a lane last spoke). So the columns are selected here, in the same chunked shape.
    """
    table = qualified(tables.warehouse, tables.scores)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in _chunks(list(dict.fromkeys(allele_ids))):
        marks = ", ".join("?" for _ in chunk)
        for row in rows_of(
            connection,
            "SELECT allele_id, model, version, score, aux, digest, venue, licence, run_id, ts "
            f"FROM {table} WHERE allele_id IN ({marks}) ORDER BY model, ts",
            list(chunk),
        ):
            grouped.setdefault(str(row["allele_id"]), []).append(
                {
                    "model": row["model"],
                    "version": row["version"],
                    "score": row["score"],
                    "aux": _aux(row["aux"]),
                    "digest": row["digest"],
                    "venue": row["venue"],
                    "licence": row["licence"],
                    "run_id": row["run_id"],
                    "ts": row["ts"],
                }
            )
    return grouped


def scores_payload(connection: Any, tables: Tables, allele_id: str) -> dict[str, Any] | None:
    """One allele: its record and every lane's verdict on it. ``None`` = unknown allele.

    An allele with a record but no score is not an error — it is a lane blind spot, and
    ``rows`` is then empty.
    """
    found = record(connection, tables, allele_id)
    rows = score_rows(connection, tables, [allele_id]).get(allele_id, [])
    if found is None and not rows:
        return None
    return {"allele_id": allele_id, "record": found, "rows": rows}


def gene_payload(connection: Any, tables: Tables, gene: str, limit: int) -> dict[str, Any] | None:
    """Every record of one gene with every lane's row. ``None`` = no record of that gene.

    Case-agnostic by construction: the symbol is the request parameter, so this route
    serves the confirmed gene and any other gene with the same code.
    """
    records = records_of_gene(connection, tables, gene, limit)
    if not records:
        return None
    by_allele = score_rows(connection, tables, [str(row["allele_id"]) for row in records])
    rows = [{**row, "rows": by_allele.get(str(row["allele_id"]), [])} for row in records]
    models = sorted({str(score["model"]) for entry in by_allele.values() for score in entry})
    return {
        "gene": str(records[0]["gene"] or gene.upper()),
        "records": rows,
        "models": models,
        "scored_records": sum(1 for row in rows if row["rows"]),
    }
