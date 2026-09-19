"""One report per model, every model the same seven sections.

The point of a fixed template is comparability: the reader who has read one lane's report can
read the next one in thirty seconds, because section 4 is always *the confirmed pair* and
section 7 is always *what this lane cannot do*. The sections themselves live in
:mod:`mva.zoo.report_sections`; this module is the pair of entry points.

    model_report_json(...)   →  a dict: every number, computed once, stored in the warehouse
    render_model_report(...) →  Markdown: prints that dict and computes nothing

Section 6 (*Interpretation*) is the only place prose may enter. In the MVP it is hand-written
and the slot carries a marker naming the author and the date::

    <!-- interpretation: hand-written 2026-09-18 | llm:none -->

A later LLM run replaces the text under that marker and nothing else, which is what makes the
automated half auditable against the hand-written half.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .report_sections import (
    coverage_json,
    distribution_json,
    histogram_path,
    hpo_sentence,
    render_sections,
)

__all__ = [
    "MODEL_REPORTS_COLUMNS",
    "MODEL_REPORTS_TABLE",
    "REPORT_DIR",
    "Runtime",
    "histogram_path",
    "hpo_sentence",
    "model_report_json",
    "render_model_report",
    "report_path",
    "write_reports",
]

#: Bumped when the JSON below changes shape.
SCHEMA_VERSION = 1

#: Where a rendered report lands. One file per lane, named by the registry key.
REPORT_DIR = "docs/iteration4/reports"


@dataclass(frozen=True)
class Runtime:
    """What one lane cost: wall-clock, where it ran, dollars, and what it could not do."""

    seconds: float = 0.0
    venue: str = "laptop"
    dollars: float = 0.0
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelReport:
    """One lane's report: the JSON that holds every number, and the file it renders to."""

    model: str
    version: str
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> str:
        return report_path(self.model)


#: Where the append-only lineage edge lands. Not the schema the *result* lands in:
#: ``results`` holds the tables this module writes, ``warehouse`` holds
#: ``data_lineage``. Passing one schema for both is the bug entry 128 caught on the
#: first real run of the DAG.
LINEAGE_SCHEMA = "warehouse"


def report_path(key: str) -> str:
    """The Markdown file one lane's report is written to."""
    return f"{REPORT_DIR}/{key}.md"


def model_report_json(
    card: Mapping[str, Any],
    coverage: Any,
    scores: Mapping[str, float],
    model_rank: Any,
    hpo_line: str,
    runtime: Runtime | Mapping[str, Any] | None = None,
    *,
    run_id: str = "",
    mode: str = "",
    llm_mode: str = "none",
    interpretation: str = "",
    interpretation_dated: str = "",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build one lane's report JSON — the single place any of its numbers are computed.

    ``card`` is the registry's model card (``registry.card_with_coverage`` output or the same
    fields as a dict), ``coverage`` a :class:`mva.zoo.types.Coverage`, ``scores`` the lane's
    allele → score mapping, ``model_rank`` a :class:`mva.zoo.rank.ModelRank`, ``hpo_line`` the
    fixed clinical sentence from :func:`mva.zoo.report_sections.hpo_sentence`, and ``runtime``
    what the run cost.
    """
    key = str(card.get("key") or card.get("name") or getattr(model_rank, "model", "") or "model")
    confirmed = getattr(model_rank, "confirmed", None)
    table = getattr(model_rank, "table", None)
    marks = _marks(table)
    distribution = distribution_json(scores, marks)
    distribution["figure"] = histogram_path(key)
    cost = runtime if isinstance(runtime, Runtime) else _runtime_from(runtime)
    day = interpretation_dated or datetime.now(UTC).date().isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "model": key,
        "version": str(card.get("version", "")),
        "run_id": run_id,
        "mode": mode,
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "sections": {
            "card": dict(card),
            "inputs": coverage_json(coverage),
            "distribution": distribution,
            "confirmed_pair": _confirmed_json(confirmed, table, mode),
            "clinical": {"sentence": hpo_line},
            "interpretation": {
                "marker": f"<!-- interpretation: hand-written {day} | llm:{llm_mode} -->",
                "text": interpretation,
                "llm_mode": llm_mode,
            },
            "limitations": {
                "licence": card.get("licence", ""),
                "venue": cost.venue,
                "seconds": cost.seconds,
                "dollars": cost.dollars,
                "run_id": run_id,
                "limitations": list(_limitations(card, coverage, table, cost)),
            },
        },
    }


def render_model_report(report: Mapping[str, Any]) -> str:
    """Render one lane's report to Markdown. Prints the JSON; computes nothing."""
    header = [
        f"# {report.get('model', 'model')} — iteration 4 model report",
        "",
        f"**Standing:** generated {report.get('generated_at', '')} by "
        f"`mva.zoo.report.render_model_report` from run `{report.get('run_id', '')}`"
        + (f", catalogue mode `{report.get('mode')}`" if report.get("mode") else "")
        + ".",
        "",
        (
            "Every number below is a key of `results.it4_model_reports.report_json` for this run. "
            "Section 6 is the only written section."
        ),
    ]
    return "\n".join([*header, *render_sections(report), ""])


def _marks(table: Any) -> list[dict[str, Any]]:
    confirmed = getattr(table, "confirmed", None)
    if confirmed is None:
        return []
    return [
        {"allele_id": confirmed.left_id, "role": "left"},
        {"allele_id": confirmed.right_id, "role": "right"},
    ]


def _confirmed_json(confirmed: Any, table: Any, mode: str) -> dict[str, Any]:
    if confirmed is None:
        return {
            "gene": None,
            "rank": None,
            "n_ranked": getattr(table, "n_ranked", 0),
            "percentile": None,
            "left_percentile": None,
            "right_percentile": None,
            "mode": mode,
        }
    return {
        "gene": confirmed.gene,
        "rank": confirmed.rank,
        "n_ranked": confirmed.n_ranked,
        "percentile": confirmed.percentile,
        "left_percentile": confirmed.left_percentile,
        "right_percentile": confirmed.right_percentile,
        "min_score": confirmed.min_score,
        "max_score": confirmed.max_score,
        "mode": mode,
    }


def _runtime_from(value: Mapping[str, Any] | None) -> Runtime:
    if not value:
        return Runtime()
    return Runtime(
        seconds=float(value.get("seconds", 0.0) or 0.0),
        venue=str(value.get("venue", "laptop")),
        dollars=float(value.get("dollars", 0.0) or 0.0),
        limitations=tuple(value.get("limitations", ()) or ()),
    )


def _limitations(card: Mapping[str, Any], coverage: Any, table: Any, cost: Runtime) -> list[str]:
    """The stated caveats of one lane — assembled from facts, never from opinion."""
    out = list(cost.limitations)
    if card.get("catalogue_adjacent"):
        out.append(
            "Catalogue-adjacent: this model's training data included ClinVar, so it may be "
            "recalling a published verdict rather than predicting one. The consensus rank is "
            "reported with and without this lane."
        )
    fraction = coverage_json(coverage).get("fraction")
    if isinstance(fraction, float) and fraction < 1.0:
        out.append(
            f"Scored {fraction:.1%} of the record set; the unscored remainder is this lane's "
            f"blind spot and its pairs are excluded from the ranking, not scored zero."
        )
    unscored = getattr(table, "unscored_pairs", 0)
    if unscored:
        out.append(f"{unscored} biallelic pairs had an unscored half and left this ranking.")
    if not cost.dollars:
        out.append(f"Ran on `{cost.venue}` at zero marginal cost.")
    return out


# ---------------------------------------------------------------------------------------
# The warehouse table
# ---------------------------------------------------------------------------------------

#: ``results.it4_model_reports`` — one row per (model, run); append-only, the rendered
#: Markdown is derivable from ``report_json`` and is therefore not stored twice.
MODEL_REPORTS_TABLE = "it4_model_reports"
MODEL_REPORTS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("model", "VARCHAR"),
    ("version", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("report_json", "VARCHAR"),
    ("rendered_at", "TIMESTAMP"),
)


def write_reports(
    connection: Any,
    schema: str,
    reports: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    source_ref: str = "results.it4_model_ranks + warehouse.allele_scores",
    lineage_schema: str = LINEAGE_SCHEMA,
) -> int:
    """Append this run's report JSON rows and record one lineage edge.

    ``schema`` is where the *result* lands (``results``); ``lineage_schema`` is where the
    edge lands (``warehouse``) — see :func:`mva.zoo.rank.write_ranks` for why they are two
    arguments rather than one.
    """
    import json

    from ..warehouse.lineage import ensure_tables, record
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    columns = ", ".join(f"{name} {sql}" for name, sql in MODEL_REPORTS_COLUMNS)
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{MODEL_REPORTS_TABLE} ({columns})"
    )
    now = datetime.now(UTC)
    for report in reports:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{MODEL_REPORTS_TABLE} VALUES (?, ?, ?, ?, ?)",
            [
                report.get("model", ""),
                report.get("version", ""),
                run_id,
                json.dumps(report, sort_keys=True, default=str),
                now,
            ],
        )
    ensure_tables(connection, lineage_schema)
    record(
        connection,
        lineage_schema,
        target_schema=schema,
        target_table=MODEL_REPORTS_TABLE,
        target_rows=len(reports),
        source_kind="table",
        source_ref=source_ref,
        source_version=run_id,
        transform="mva.zoo.report.model_report_json (7-section template, §6 hand-written)",
        tool="mva-zoo",
        notes=f"{len(reports)} lanes",
    )
    return len(reports)


def write_markdown(reports: Sequence[Mapping[str, Any]], out_dir: str | Path) -> list[Path]:
    """Render every report to ``<out_dir>/<model>.md`` and return the paths written."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for report in reports:
        path = directory / f"{report.get('model', 'model')}.md"
        path.write_text(render_model_report(report), encoding="utf-8")
        written.append(path)
    return written
