"""The avoid / caution list: evidence *against* a drug for this child, from any route.

Three sources, each read from a file, never typed as a verdict:

* ``translation`` - a literature route's translation JSON (R3's ``translation.json``): every
  drug mapped from an intervention that carries **harm rows** (it lowers the protein the
  child lacks) is ``avoid``; the reason is the harm row's note and PMID.
* ``do_not`` - a direction table (``ressources/track2/do_not.tsv``): flag ``A1`` (weakens the
  checkpoint further) is ``avoid``, ``A2`` (spindle poison) is ``caution``.
* ``rules`` - a stated rule per drug set, bound to a source file and to the words that file
  must contain (checked at run time, case-insensitive). Used for free-text sources such as
  same-disease patient exposures, where a parser would be a guess. A rule whose words are
  missing from its source is an error, not a skipped rule.

:func:`merge` folds the list into the per-child safety map: each drug takes the class whose
factor is **lowest** among its safety class and its avoid/caution levels. Nothing is ever
upgraded - an absent drug stays ``unassessed``.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mva.drugs.decision_model import drug_key
from mva.drugs.provenance import digest, repo_relative

__all__ = ["AvoidRow", "build", "inputs", "merge"]

LEVELS = ("caution", "avoid")


@dataclass(frozen=True)
class AvoidRow:
    drug: str
    level: str
    reason: str
    source: str
    origin: str

    @property
    def key(self) -> str:
        return drug_key(self.drug)


def _translation(path: Path) -> list[AvoidRow]:
    rows: list[AvoidRow] = []
    for group in json.loads(path.read_text(encoding="utf-8")):
        for harm in group.get("harm_rows", []):
            reason = f"{group['intervention']} lowers BubR1: {harm.get('note', '')}"
            rows.extend(
                AvoidRow(drug["drug_name"], "avoid", reason, f"PMID:{harm['pmid']}",
                         repo_relative(path))
                for drug in group.get("drugs", [])
            )  # fmt: skip
    return rows


def _do_not(path: Path) -> list[AvoidRow]:
    rows = []
    with path.open(encoding="utf-8", newline="") as stream:
        for rec in csv.DictReader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            flags = set((rec.get("flags") or "").split("|"))
            level = "avoid" if "A1" in flags else "caution" if "A2" in flags else None
            if level:
                rows.append(
                    AvoidRow(rec["drug_name"], level, rec["why"], "do-not direction table",
                             repo_relative(path))
                )  # fmt: skip
    return rows


def _rule(rule: Mapping[str, Any]) -> list[AvoidRow]:
    path = Path(rule["source_file"])
    text = path.read_text(encoding="utf-8").lower()
    missing = [w for w in rule["must_contain"] if w.lower() not in text]
    if missing:
        raise ValueError(f"avoid rule for {rule['drugs']}: {path} lacks {missing}")
    if rule["level"] not in LEVELS:
        raise ValueError(f"avoid rule level {rule['level']!r} not in {LEVELS}")
    return [
        AvoidRow(d, rule["level"], rule["reason"], rule["source"], repo_relative(path))
        for d in rule["drugs"]
    ]


def build(spec: Mapping[str, Any]) -> list[AvoidRow]:
    """Every avoid/caution row the config's ``avoid`` block names; missing files are errors."""
    rows: list[AvoidRow] = []
    if spec.get("translation"):
        rows += _translation(Path(spec["translation"]))
    if spec.get("do_not"):
        rows += _do_not(Path(spec["do_not"]))
    for rule in spec.get("rules", []):
        rows += _rule(rule)
    return rows


def inputs(spec: Mapping[str, Any]) -> list[dict[str, str]]:
    """``{file, sha256}`` for every file the avoid list read."""
    paths = [spec.get("translation"), spec.get("do_not")]
    paths += [r["source_file"] for r in spec.get("rules", [])]
    unique = dict.fromkeys(p for p in paths if p)
    return [{"file": repo_relative(Path(p)), "sha256": digest(Path(p))[0]} for p in unique]


def merge(
    safety: Mapping[str, str], rows: Iterable[AvoidRow], factors: Mapping[str, float]
) -> dict[str, str]:
    """Safety map with each avoid/caution level folded in (lowest factor wins)."""
    out = dict(safety)
    for row in rows:
        current = out.get(row.key, "unassessed")
        if factors[row.level] < factors[current]:
            out[row.key] = row.level
    return out
