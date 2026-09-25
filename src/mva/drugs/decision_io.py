"""Reading route tables and safety flags into the decision engine; nothing else.

**Candidate tables** carry the columns pinned by the iteration-5 plan (:data:`COLUMNS`).
Validation refuses, with the file and line, a missing column, a branch outside
:data:`~mva.drugs.decision_model.BRANCHES` or an ``evidence_strength`` outside [0, 1].
``positive_control_passed`` reads ``true/yes/1/passed`` as passed, ``false/no/0/failed`` as
failed, ``n/a``/``na``/``not applicable`` as not_applicable (the row is a published fact, not
the output of a controlled method) and anything else (empty, ``unknown``) as unknown - never
as passed.

**Safety tables** are either iteration 4's ``candidate_safety.tsv`` (a ``drug`` column and
the ``combined_flag`` sentence) or any table with ``drug``/``drug_name`` and a
``safety_class`` column already in :data:`~mva.drugs.decision_model.SAFETY_CLASSES`. A drug
absent from the table is ``unassessed`` downstream - absence of a flag is not safety - and so
is an 'unflagged' drug whose ``labels_total`` is 0 (no label: the phenotype source was silent).

**Aliases.** A route may name a class (``proteasome inhibition (MG132 as the tool; ...)``).
:func:`expand_aliases` turns such a row into one row per named member at a stated weight
(config ``aliases``), so class evidence meets the same molecule named by another route.
"""

from __future__ import annotations

import csv
import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path

from mva.drugs.decision_model import BRANCHES, SAFETY_CLASSES, EvidenceRow, drug_key
from mva.drugs.provenance import repo_relative

__all__ = [
    "COLUMNS",
    "expand_aliases",
    "parse_control",
    "read_candidates",
    "read_safety",
    "read_tsv",
    "safety_class",
]

#: The pinned candidate-table schema (``docs/iteration5/plan.md``, "Contracts").
COLUMNS = (
    "drug_name",
    "route",
    "branch",
    "evidence_kind",
    "evidence_strength",
    "positive_control_passed",
    "source",
    "notes",
)

_PASSED = {"true", "yes", "1", "passed", "pass"}
_FAILED = {"false", "no", "0", "failed", "fail"}
_NA = {"n/a", "na", "not applicable", "not_applicable"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    """One TSV as string rows. The repo's writers never quote, so neither does the reader."""
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE))


def parse_control(text: str) -> str:
    """``passed`` / ``failed`` / ``unknown``."""
    word = text.strip().lower()
    if word in _PASSED:
        return "passed"
    if word in _FAILED:
        return "failed"
    if word in _NA:
        return "not_applicable"
    return "unknown"


def read_candidates(paths: Sequence[Path]) -> list[EvidenceRow]:
    """Every row of every candidate table, validated against the pinned schema."""
    rows: list[EvidenceRow] = []
    for path in paths:
        records = read_tsv(path)
        header = set(records[0]) if records else set(_header(path))
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            raise ValueError(f"{path}: missing pinned column(s) {missing}")
        for line, rec in enumerate(records, start=2):
            where = f"{path}:{line}"
            branch = rec["branch"].strip()
            if branch not in BRANCHES:
                raise ValueError(f"{where}: branch {branch!r} not in {BRANCHES}")
            strength = float(rec["evidence_strength"])
            if not 0.0 <= strength <= 1.0:
                raise ValueError(f"{where}: evidence_strength {strength} outside [0, 1]")
            if not rec["drug_name"].strip():
                raise ValueError(f"{where}: empty drug_name")
            rows.append(
                EvidenceRow(
                    drug_name=rec["drug_name"].strip(),
                    route=rec["route"].strip(),
                    branch=branch,
                    evidence_kind=rec["evidence_kind"].strip(),
                    evidence_strength=strength,
                    control=parse_control(rec["positive_control_passed"]),
                    source=rec["source"].strip(),
                    notes=(rec.get("notes") or "").strip(),
                    origin=repo_relative(path),
                )
            )
    return rows


def expand_aliases(
    rows: Sequence[EvidenceRow],
    aliases: Mapping[str, Mapping[str, float]],
    drop_kinds: Sequence[str] = (),
) -> tuple[list[EvidenceRow], list[tuple[EvidenceRow, str]]]:
    """``(kept rows, dropped rows with reason)``: class rows expanded, control rows dropped.

    ``aliases`` maps a raw ``drug_name`` (matched by :func:`drug_key`) to ``{member: weight}``;
    each member row carries ``evidence_strength x weight`` and says where it came from.
    """
    table = {drug_key(name): members for name, members in aliases.items()}
    drop = {kind.strip().lower() for kind in drop_kinds}
    kept: list[EvidenceRow] = []
    dropped: list[tuple[EvidenceRow, str]] = []
    for row in rows:
        if row.evidence_kind.strip().lower() in drop:
            dropped.append((row, f"evidence_kind '{row.evidence_kind}' is a control row"))
            continue
        members = table.get(drug_key(row.drug_name))
        if not members:
            kept.append(row)
            continue
        for member, weight in members.items():
            note = f"via class row '{row.drug_name}' x {weight}"
            kept.append(
                dataclasses.replace(
                    row,
                    drug_name=member,
                    evidence_strength=row.evidence_strength * float(weight),
                    notes=f"{note}; {row.notes}" if row.notes else note,
                )
            )
    return kept, dropped


def _header(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as stream:
        return stream.readline().rstrip("\n").split("\t")


def safety_class(combined_flag: str) -> str:
    """Iteration 4's ``combined_flag`` sentence -> a safety class."""
    text = combined_flag.strip().lower()
    if text.startswith("both"):
        return "both_flag"
    if text.startswith("genome"):
        return "genome_flag"
    if text.startswith("phenotype"):
        return "phenotype_flag"
    if text.startswith("unflagged"):
        return "unflagged"
    return "unassessed"


def read_safety(path: Path | None) -> dict[str, str]:
    """Drug key -> safety class. ``None`` (no table) gives an empty map: all unassessed."""
    if path is None:
        return {}
    out: dict[str, str] = {}
    for rec in read_tsv(path):
        name = rec.get("drug") or rec.get("drug_name") or ""
        if not name.strip():
            continue
        if "safety_class" in rec:
            klass = rec["safety_class"].strip()
            if klass not in SAFETY_CLASSES:
                raise ValueError(f"{path}: unknown safety_class {klass!r} for {name!r}")
        else:
            klass = safety_class(rec.get("combined_flag", ""))
            if klass == "unflagged" and rec.get("labels_total", "").strip() == "0":
                klass = "unassessed"  # no label exists, so the phenotype source was silent
        out[drug_key(name)] = klass
    return out
