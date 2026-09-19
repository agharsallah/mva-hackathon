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
    HAND_MARKER,
    INTERPRETATION_TRAILER,
    coverage_json,
    distribution_json,
    existing_interpretation,
    existing_interpretations,
    histogram_path,
    hpo_sentence,
    interpretation_json,
    render_sections,
)

__all__ = [
    "HAND_MARKER",
    "INTERPRETATION_TRAILER",
    "MODEL_REPORTS_COLUMNS",
    "MODEL_REPORTS_TABLE",
    "REPORT_DIR",
    "Runtime",
    "existing_interpretation",
    "histogram_path",
    "hpo_sentence",
    "model_report_json",
    "render_model_report",
    "report_path",
    "write_markdown",
    "write_reports",
]

#: Bumped when the JSON below changes shape. Version 2 added ``reports_table`` (the warehouse
#: table this run's row lands in — the case's prefix, not a constant) and ``case`` (which
#: illness the report is about).
SCHEMA_VERSION = 2

#: Where a rendered report lands by default. One file per lane, named by the registry key.
#: A run overrides it from ``[paths] reports_dir``, which itself defaults to the case's
#: ``docs/<iteration>/reports``.
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


def report_path(key: str, reports_dir: str | Path = REPORT_DIR) -> str:
    """The Markdown file one lane's report is written to, under the case's reports folder."""
    return f"{reports_dir}/{key}.md"


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
    reports_table: str = "",
    case: Mapping[str, Any] | None = None,
    interpretations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build one lane's report JSON — the single place any of its numbers are computed.

    ``card`` is the registry's model card (``registry.card_with_coverage`` output or the same
    fields as a dict), ``coverage`` a :class:`mva.zoo.types.Coverage`, ``scores`` the lane's
    allele → score mapping, ``model_rank`` a :class:`mva.zoo.rank.ModelRank`, ``hpo_line`` the
    fixed clinical sentence from :func:`mva.zoo.report_sections.hpo_sentence`, and ``runtime``
    what the run cost. ``case`` is :meth:`mva.zoo.workflow_types.Config.case_json` — which
    illness this report is about — so a report never says "iteration 4" because the renderer
    was written for iteration 4.

    ``interpretations`` takes section 6 as **a list of versions** rather than one string: each
    item is a block from :func:`mva.zoo.narrate.interpretation_block` (marker, text, mode,
    model id, citation counts). The first is primary and the rest render under it with their
    own badges — how a generated section 6 and the hand-written one it is compared against
    live in one file without either being lost. Leave it empty and the hand-written
    ``interpretation`` string is used exactly as before.
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
        "reports_table": reports_table or MODEL_REPORTS_TABLE,
        "case": dict(case or {}),
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "sections": {
            "card": dict(card),
            "inputs": coverage_json(coverage),
            "distribution": distribution,
            "confirmed_pair": _confirmed_json(confirmed, table, mode),
            "clinical": {"sentence": hpo_line},
            "interpretation": interpretation_json(
                interpretations,
                marker=f"{HAND_MARKER} {day} | llm:{llm_mode} -->",
                text=interpretation,
                llm_mode=llm_mode,
            ),
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
    case = report.get("case") or {}
    label = str(case.get("label") or case.get("iteration") or "")
    gene = str(case.get("confirmed_gene") or "")
    header = [
        f"# {report.get('model', 'model')} — model report",
        "",
        f"**Case:** {label or '—'}; confirmed pair gene "
        + (f"`{gene}`." if gene else "none declared."),
        "",
        f"**Standing:** generated {report.get('generated_at', '')} by "
        f"`mva.zoo.report.render_model_report` from run `{report.get('run_id', '')}`"
        + (f", catalogue mode `{report.get('mode')}`" if report.get("mode") else "")
        + ".",
        "",
        (
            f"Every number below is a key of "
            f"`{report.get('reports_table', MODEL_REPORTS_TABLE)}.report_json` for this run. "
            f"Section 6 is the only written section."
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

#: ``<schema>.<prefix>_model_reports`` — one row per (model, run); append-only, the rendered
#: Markdown is derivable from ``report_json`` and is therefore not stored twice. The name
#: below is the *default* prefix (``it4``); a run passes its own through
#: :meth:`mva.zoo.workflow_types.Config.table`.
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
    table: str = MODEL_REPORTS_TABLE,
) -> int:
    """Append this run's report JSON rows and record one lineage edge.

    ``schema`` is where the *result* lands (``results``); ``lineage_schema`` is where the
    edge lands (``warehouse``) — see :func:`mva.zoo.rank.write_ranks` for why they are two
    arguments rather than one. ``table`` is the case's own name for the table
    (``<prefix>_model_reports``), so a second case writes beside this one, not over it.
    """
    import json

    from ..warehouse.lineage import ensure_tables, record
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe = safe_identifier(schema)
    safe_table = safe_identifier(table)
    columns = ", ".join(f"{name} {sql}" for name, sql in MODEL_REPORTS_COLUMNS)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{safe_table} ({columns})")
    now = datetime.now(UTC)
    for report in reports:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{safe_table} VALUES (?, ?, ?, ?, ?)",
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
        target_table=table,
        target_rows=len(reports),
        source_kind="table",
        source_ref=source_ref,
        source_version=run_id,
        transform="mva.zoo.report.model_report_json (7-section template, §6 hand-written)",
        tool="mva-zoo",
        notes=f"{len(reports)} lanes",
    )
    return len(reports)


def write_markdown(
    reports: Sequence[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    keep_existing: bool = True,
) -> list[Path]:
    """Render every report to ``<out_dir>/<model>.md`` and return the paths written.

    **Prose already under the section-6 marker is kept** by default. Sections 1-5 and 7 are
    regenerated from the run's JSON on every render, but section 6 is the one slot a human (or
    an LLM) writes into, and a re-render must not silently delete it — the same rule
    :func:`mva.zoo.merge_render.render_merged` already follows for the merged narrative.

    **Every** version is kept, not only the hand-written one: once section 6 can hold a
    generated version beside a hand-written one, a re-render that restored one of them would
    delete the other. The versions are rebuilt from the rendered file's own markers, so a
    chain re-run that knows nothing about ``mva-zoo narrate`` still cannot lose its output.

    ``keep_existing=False`` is for the one caller that has *already read* the file's prose and
    put it into the report's own ``interpretations`` list (``mva-zoo narrate``): re-reading it
    here would push the old versions back over the new one.
    """
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for report in reports:
        path = directory / f"{report.get('model', 'model')}.md"
        kept = existing_interpretations(path) if keep_existing else []
        rendered = report
        if kept:
            sections = dict(report.get("sections", {}))
            sections["interpretation"] = interpretation_json(
                kept,
                marker=str(kept[0].get("marker", "")),
                text=str(kept[0].get("text", "")),
                llm_mode=str(kept[0].get("llm_mode", "none")),
            )
            rendered = {**report, "sections": sections}
        path.write_text(render_model_report(rendered), encoding="utf-8")
        written.append(path)
    return written
