"""Reading route tables and safety flags into the decision engine; nothing else.

**Candidate tables** carry the columns pinned by the iteration-5 plan (:data:`COLUMNS`).
Validation refuses, with the file and line, a missing column, a branch outside
:data:`~mva.drugs.decision_model.BRANCHES` or an ``evidence_strength`` outside [0, 1].
``positive_control_passed`` reads ``true/yes/1/passed`` as passed, ``false/no/0/failed`` as
failed and anything else (empty, ``unknown``, ``na``) as unknown - never as passed.

**Safety tables** are either iteration 4's ``candidate_safety.tsv`` (a ``drug`` column and
the ``combined_flag`` sentence) or any table with ``drug``/``drug_name`` and a
``safety_class`` column already in :data:`~mva.drugs.decision_model.SAFETY_CLASSES`. A drug
absent from the table is ``unassessed`` downstream - absence of a flag is not safety.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

from mva.drugs.decision_model import BRANCHES, SAFETY_CLASSES, EvidenceRow, drug_key
from mva.drugs.provenance import repo_relative

__all__ = ["COLUMNS", "parse_control", "read_candidates", "read_safety", "read_tsv", "safety_class"]

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
        out[drug_key(name)] = klass
    return out
