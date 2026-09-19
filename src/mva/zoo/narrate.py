"""Section 6 of a model report, written by an LLM that is only ever shown numbers.

Sections 1–5 and 7 of every report are rendered from stored JSON (:mod:`mva.zoo.report`).
Section 6 — *Interpretation* — is the one slot prose may enter, and in the MVP it is written
by hand. This module is the optional automation of that slot, and the whole design is about
keeping it *auditable*:

1. **The input is a list of rows, not a report.** :func:`citable_rows` flattens sections 2–5
   into ``{"id": "cov.missense_variant", "label": …, "text": …}`` rows with stable ids. That
   list, verbatim, is the only case-specific thing in the prompt.
2. **The task is never a ranking.** The prompt says *interpret these numbers*; it forbids
   ranking anything, naming a gene or disease that is not in a row, and adding facts. The
   model is an explainer of arithmetic already done — plan §5 step 5, risk R3.
3. **The gene name reaches the model only through the rows.** It does, via section 4
   (``pair.gene``) and section 5 (``hpo.rank``), because a report that never names the gene
   is not a report. What the model is denied is the *question*: nothing in the prompt asks
   which gene or which pair is the answer.
4. **Every sentence must end in a citation** ``[id]`` to one of those rows, and
   :mod:`mva.zoo.narrate_check` checks it mechanically. That check is ``P4-7``.
5. **Prompt and reply are stored** in ``results.<prefix>_narratives`` with the mode and the
   model id that answered, so the section can be re-checked, re-read and compared between
   modes long after the model behind it has changed.

The two modes live in :mod:`mva.zoo.narrate_modes`; this module never spawns a process or
opens a socket itself, which is what lets every test here run with a fake transport.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .narrate_check import CheckResult, check_narrative
from .narrate_modes import Reply, Transport, build_transport
from .narrate_rows import DEFAULT_MAX_WORDS, build_prompt, citable_rows

__all__ = [
    "NARRATIVES_COLUMNS",
    "NARRATIVES_TABLE",
    "NarrateRun",
    "Narrative",
    "build_prompt",
    "citable_rows",
    "hand_written",
    "interpretation_block",
    "narrate_report",
    "run_narrate",
    "write_narratives",
]


@dataclass(frozen=True)
class Narrative:
    """One generated section 6, with everything needed to audit or reproduce it."""

    model: str
    run_id: str = ""
    mode: str = "none"
    llm_model_id: str = ""
    prompt: str = ""
    reply: str = ""
    text: str = ""
    words: int = 0
    cited_sentences: int = 0
    uncited_sentences: int = 0
    seconds: float = 0.0
    dollars: float = 0.0
    created_at: str = ""
    rows: tuple[dict[str, Any], ...] = ()
    check: CheckResult | None = field(default=None, repr=False)

    @property
    def uncited_rate(self) -> float:
        total = self.cited_sentences + self.uncited_sentences
        return 1.0 if not total else self.uncited_sentences / total

    def marker(self) -> str:
        """The HTML comment that labels the slot in the rendered report.

        A reader (and a re-render) can tell at a glance which of the two paths wrote the
        section, in which mode, and by which model — the badge the plan asks for.
        """
        day = (self.created_at or datetime.now(UTC).isoformat())[:10]
        if self.mode == "hand":
            return f"<!-- interpretation: hand-written {day} | llm:none -->"
        model_id = self.llm_model_id or "unrecorded"
        return (
            f"<!-- interpretation: generated {day} | llm:{self.mode} | model:{model_id} "
            f"| cited {self.cited_sentences}/{self.cited_sentences + self.uncited_sentences} -->"
        )

    def summary(self) -> dict[str, Any]:
        """Plain JSON for a board, an entry or a report — no objects."""
        return {
            "model": self.model,
            "run_id": self.run_id,
            "mode": self.mode,
            "llm_model_id": self.llm_model_id,
            "words": self.words,
            "cited_sentences": self.cited_sentences,
            "uncited_sentences": self.uncited_sentences,
            "uncited_rate": round(self.uncited_rate, 4),
            "seconds": self.seconds,
            "dollars": self.dollars,
            "created_at": self.created_at,
        }


def narrate_report(
    report: Mapping[str, Any],
    *,
    mode: str = "none",
    model: str = "",
    temperature: float = 0.0,
    max_words: int = DEFAULT_MAX_WORDS,
    transport: Transport | None = None,
    run_id: str = "",
) -> Narrative | None:
    """Generate section 6 for one model report. ``None`` when the mode is ``none``.

    ``transport`` overrides the mode's own transport — the seam every test uses, and the seam
    a future provider is added through. The reply is checked before it is returned, so a
    caller never has to remember to check it: the counts on the returned
    :class:`Narrative` *are* the check.
    """
    if transport is None:
        transport = build_transport(mode, model=model, temperature=temperature)
    if transport is None:
        return None
    rows = citable_rows(report)
    prompt = build_prompt(rows, max_words=max_words)
    reply: Reply = transport(prompt)
    result = check_narrative(reply.text, rows, max_words=max_words)
    return Narrative(
        model=str(report.get("model", "")),
        run_id=run_id or str(report.get("run_id", "")),
        mode=getattr(transport, "mode", mode),
        llm_model_id=reply.model_id,
        prompt=prompt,
        reply=reply.text,
        text=reply.text,
        words=result.words,
        cited_sentences=result.cited_sentences,
        uncited_sentences=result.uncited_sentences,
        seconds=reply.seconds,
        dollars=reply.dollars,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        rows=tuple(dict(row) for row in rows),
        check=result,
    )


def hand_written(
    report: Mapping[str, Any], text: str, *, dated: str = "", run_id: str = ""
) -> Narrative:
    """The hand-written section 6 as a :class:`Narrative`, mode ``hand``.

    Generating section 6 must not lose the prose a human wrote: the hand-written version goes
    into ``results.<prefix>_narratives`` as a row of its own, checked by exactly the same
    checker, so "did the automation cite better or worse than the human?" is a query rather
    than an opinion. Its ``prompt`` is empty — there was none — and its ``llm_model_id`` says
    ``human``.
    """
    rows = citable_rows(report)
    result = check_narrative(text, rows)
    return Narrative(
        model=str(report.get("model", "")),
        run_id=run_id or str(report.get("run_id", "")),
        mode="hand",
        llm_model_id="human",
        prompt="",
        reply=text,
        text=text,
        words=result.words,
        cited_sentences=result.cited_sentences,
        uncited_sentences=result.uncited_sentences,
        created_at=(dated or datetime.now(UTC).date().isoformat()),
        rows=tuple(dict(row) for row in rows),
        check=result,
    )


def interpretation_block(narrative: Narrative) -> dict[str, Any]:
    """The ``sections.interpretation`` block a report renders from this narrative.

    The same shape :func:`mva.zoo.report.model_report_json` builds by hand, so the renderer
    does not know — and must not know — which path produced the words.
    """
    return {
        "marker": narrative.marker(),
        "text": narrative.text,
        "llm_mode": narrative.mode,
        "llm_model_id": narrative.llm_model_id,
        "words": narrative.words,
        "cited_sentences": narrative.cited_sentences,
        "uncited_sentences": narrative.uncited_sentences,
    }


# ---------------------------------------------------------------------------------------
# One pass over a case's rendered reports
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NarrateRun:
    """What one ``mva-zoo narrate`` pass produced: the narratives and the files it rewrote."""

    narratives: tuple[Narrative, ...] = ()
    paths: tuple[Path, ...] = ()

    def by_mode(self, mode: str) -> list[Narrative]:
        return [item for item in self.narratives if item.mode == mode]


def run_narrate(
    *,
    json_dir: Path,
    reports_dir: Path,
    settings: Any,
    models: Sequence[str] = (),
    transport: Transport | None = None,
    run_id: str = "",
) -> NarrateRun:
    """Generate section 6 for every stored report JSON, rewrite the Markdown, keep the hand.

    ``json_dir`` is where the run dumped one ``<model>.json`` per lane
    (``<out_dir>/reports``); ``reports_dir`` is where the Markdown lives
    (``docs/<iteration>/reports``). For each lane:

    1. the hand-written section 6 is read out of the rendered file and becomes a ``hand``
       narrative — nothing that was written by a person is discarded;
    2. the LLM is asked for a new one from the lane's rows;
    3. the report JSON's ``sections.interpretation`` is rebuilt with the generated version
       first and the hand-written one under it, and both the JSON and the Markdown are
       rewritten from it.

    Nothing is written to the warehouse here: the caller holds the connection, so this
    function is runnable with no database at all.
    """
    from .report import render_model_report
    from .report_sections import existing_interpretation, interpretation_json

    wanted = set(models)
    narratives: list[Narrative] = []
    paths: list[Path] = []
    for path in sorted(json_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        key = str(payload.get("model") or path.stem)
        if wanted and key not in wanted:
            continue
        markdown = reports_dir / f"{key}.md"
        versions: list[Narrative] = []
        generated = narrate_report(
            payload,
            mode=getattr(settings, "mode", "none"),
            model=getattr(settings, "model", ""),
            temperature=float(getattr(settings, "temperature", 0.0)),
            max_words=int(getattr(settings, "max_words", DEFAULT_MAX_WORDS)),
            transport=transport,
            run_id=run_id,
        )
        if generated is not None:
            versions.append(generated)
        kept = existing_interpretation(markdown)
        if kept:
            versions.append(hand_written(payload, kept, run_id=run_id))
        if not versions:
            continue
        sections = dict(payload.get("sections", {}))
        sections["interpretation"] = interpretation_json(
            [interpretation_block(item) for item in versions],
            marker=versions[0].marker(),
            text=versions[0].text,
            llm_mode=versions[0].mode,
        )
        payload["sections"] = sections
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reports_dir.mkdir(parents=True, exist_ok=True)
        markdown.write_text(render_model_report(payload), encoding="utf-8")
        narratives += versions
        paths += [path, markdown]
    return NarrateRun(tuple(narratives), tuple(paths))


# ---------------------------------------------------------------------------------------
# The warehouse table
# ---------------------------------------------------------------------------------------

#: ``<schema>.<prefix>_narratives`` — one row per (model, run, mode). Append-only: a second
#: mode's narrative is a new row beside the first, never an update, which is what makes the
#: two modes comparable after the fact. The name below is the *default* prefix; a run passes
#: its own through :meth:`mva.zoo.workflow_types.Config.table`.
NARRATIVES_TABLE = "it4_narratives"
NARRATIVES_COLUMNS: tuple[tuple[str, str], ...] = (
    ("model", "VARCHAR"),
    ("run_id", "VARCHAR"),
    ("mode", "VARCHAR"),
    ("llm_model_id", "VARCHAR"),
    ("prompt", "VARCHAR"),
    ("reply", "VARCHAR"),
    ("words", "INTEGER"),
    ("cited_sentences", "INTEGER"),
    ("uncited_sentences", "INTEGER"),
    ("created_at", "TIMESTAMP"),
)

#: Where the append-only lineage edge lands — the shared schema, not the result schema. The
#: same two-argument split :func:`mva.zoo.report.write_reports` explains.
LINEAGE_SCHEMA = "warehouse"


def write_narratives(
    connection: Any,
    schema: str,
    narratives: Sequence[Narrative],
    *,
    run_id: str = "",
    table: str = NARRATIVES_TABLE,
    source_ref: str = "results.it4_model_reports",
    lineage_schema: str = LINEAGE_SCHEMA,
) -> int:
    """Append this run's narratives and record one lineage edge. Returns the rows written.

    ``connection`` is a DuckDB connection with the warehouse attached (the argument, never a
    module-level handle — the same injection every writer in this package takes).
    """
    from ..warehouse.lineage import ensure_tables, record
    from ..warehouse.postgres import ALIAS, safe_identifier

    safe, safe_table = safe_identifier(schema), safe_identifier(table)
    columns = ", ".join(f"{name} {sql}" for name, sql in NARRATIVES_COLUMNS)
    connection.execute(f"CREATE TABLE IF NOT EXISTS {ALIAS}.{safe}.{safe_table} ({columns})")
    placeholders = ", ".join("?" for _ in NARRATIVES_COLUMNS)
    now = datetime.now(UTC)
    modes: list[str] = []
    for item in narratives:
        connection.execute(
            f"INSERT INTO {ALIAS}.{safe}.{safe_table} VALUES ({placeholders})",
            [
                item.model,
                item.run_id or run_id,
                item.mode,
                item.llm_model_id,
                item.prompt,
                item.reply,
                item.words,
                item.cited_sentences,
                item.uncited_sentences,
                now,
            ],
        )
        if item.mode not in modes:
            modes.append(item.mode)
    ensure_tables(connection, lineage_schema)
    record(
        connection,
        lineage_schema,
        target_schema=schema,
        target_table=table,
        target_rows=len(narratives),
        source_kind="table",
        source_ref=source_ref,
        source_version=run_id,
        transform=(
            "mva.zoo.narrate.narrate_report (sections 2-5 rows -> LLM interpretation, "
            "checked by mva.zoo.narrate_check)"
        ),
        tool="mva-zoo narrate",
        notes=f"{len(narratives)} narratives, modes: {', '.join(modes) or 'none'}",
    )
    return len(narratives)
