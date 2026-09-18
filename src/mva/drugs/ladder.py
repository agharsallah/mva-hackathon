"""The evidence ladder: one drug, one direction, one rung - and every test behind the rung.

Rigor is 35 % of the Track 2 score, and the plan pre-registered how it is earned: every
candidate is placed on a rung *before* it is argued, and the rung is printed in the evidence
table. The rungs, read off the card so another case can restate them:

    5  approved for a related indication, with paediatric use
    4  clinical trial in a related indication
    3  in-vivo model of aneuploidy or checkpoint deficiency
    2  cell model in aneuploid or checkpoint-deficient cells
    1  mechanism only - named, never submitted

Two kinds of test feed the rung and they are kept apart in the row:

* **automated** - approval (ChEMBL phase 4, Open Targets APPROVAL, DGIdb flag), an openFDA
  label and its paediatric section, a registered trial in the tumour context, a registered
  trial admitting children, and the mechanism-literature counts. These are the same for a
  decoy card, which is what makes the specificity control possible.
* **curated** - one PMID per row in ``evidence.tsv``, read by a person, placed on rung 2 or 3
  with the model named. ``proxy`` marks a result for a same-axis compound rather than the
  approved molecule, and the flag travels with the rung.

The rung is the higher of the two, and the row prints both so a reader can see which one is
carrying it. A drug that only the curated table names (chloroquine sits on no target the
sources drug) still gets a row, because the ladder is about evidence, not about which API
happened to list the molecule; its ``flags`` say ``curated_only``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .mechanism import MechanismCard
from .names import base_name

__all__ = ["DEFAULT_RUNGS", "LadderInputs", "assign", "rung_label"]

#: Used when a card states no ``evidence_ladder`` block.
DEFAULT_RUNGS: dict[int, str] = {
    5: "approved for a related indication, with paediatric use",
    4: "clinical trial in a related indication",
    3: "in-vivo model of aneuploidy or checkpoint deficiency",
    2: "cell model in aneuploid or checkpoint-deficient cells",
    1: "mechanism only",
}

#: The direction id given to a drug that attaches only through pathway-expansion targets.
PATHWAY_DIRECTION = "pathway"


@dataclass
class LadderInputs:
    """Everything the assignment reads, already parsed into rows."""

    card: MechanismCard
    candidates: list[dict[str, Any]]
    trials: list[dict[str, Any]]
    mechlit: list[dict[str, Any]] = field(default_factory=list)
    pediatric: list[dict[str, Any]] = field(default_factory=list)
    #: base name → the openFDA label answer (``has_label``, ``pediatric_use``).
    labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)


def rung_label(card: MechanismCard, rung: int) -> str:
    block = card.raw.get("evidence_ladder") or {}
    for entry in block.get("rungs") or []:
        if int(entry.get("rung", 0)) == rung:
            return str(entry.get("label", ""))
    return DEFAULT_RUNGS.get(rung, "")


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _split(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if str(v))
    text = str(value or "")
    return tuple(part for part in text.split("|") if part)


def _context_drugs(trials: list[dict[str, Any]], context: str | None) -> set[str]:
    """Base names with a trial row found by the *candidate* query in the tumour context."""
    if not context:
        return set()
    prefix = f"cond={context} intr="
    found: set[str] = set()
    for row in trials:
        query = str(row.get("query", ""))
        if query.startswith(prefix):
            found.add(base_name(query[len(prefix) :]))
    return found


def _anti_patterns(card: MechanismCard) -> list[tuple[str, re.Pattern[str]]]:
    out = []
    for entry in card.raw.get("anti_directions") or []:
        pattern = entry.get("moa_pattern")
        if pattern:
            out.append((str(entry.get("id", "A?")), re.compile(pattern, re.IGNORECASE)))
    return out


def _standard_of_care(card: MechanismCard) -> set[str]:
    block = (card.raw.get("case") or {}).get("context_standard_of_care") or {}
    return {base_name(d) for d in block.get("drugs") or []}


def _blank(curated_only: bool = False) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "targets": set(),
        "directions": set(),
        "action_types": set(),
        "moa": [],
        "fda_label": False,
    }
    if curated_only:
        entry["curated_only"] = True
    return entry


def _fold(inputs: LadderInputs) -> dict[str, dict[str, Any]]:
    """Approved candidates and curated rows, folded to one entry per base name."""
    drugs: dict[str, dict[str, Any]] = {}
    for row in inputs.candidates:
        if not _truthy(row.get("approved")):
            continue
        entry = drugs.setdefault(base_name(str(row["drug_name"])), _blank())
        entry["targets"].add(str(row["target_symbol"]))
        entry["directions"].update(_split(row.get("direction_ids")))
        if row.get("action_type"):
            entry["action_types"].add(str(row["action_type"]))
        if row.get("interaction_or_moa"):
            entry["moa"].append(str(row["interaction_or_moa"]))
        entry["fda_label"] = entry["fda_label"] or _truthy(row.get("fda_label"))
    for row in inputs.evidence:
        name, direction = base_name(str(row["drug_name"])), str(row["direction_id"])
        entry = drugs.setdefault(name, _blank(curated_only=True))
        if row.get("target"):
            entry["targets"].add(str(row["target"]))
        entry["directions"].add(direction)
    return drugs


def _flags(
    name: str,
    entry: dict[str, Any],
    anti: list[tuple[str, re.Pattern[str]]],
    standard: set[str],
    approved: bool,
) -> tuple[str, ...]:
    flags: list[str] = []
    haystack = " ".join([*entry["action_types"], *entry["moa"]])
    flags.extend(anti_id for anti_id, pattern in anti if pattern.search(haystack))
    if name in standard:
        flags.append("standard_of_care")
    if entry.get("curated_only"):
        flags.append("curated_only")
    if not approved:
        flags.append("approval_unverified")
    return tuple(flags)


def assign(inputs: LadderInputs) -> list[dict[str, Any]]:
    """One row per (drug, direction), highest rung first, then by name."""
    card = inputs.card
    anti = _anti_patterns(card)
    standard = _standard_of_care(card)
    context_drugs = _context_drugs(inputs.trials, card.tumour_context)
    pediatric_drugs = {base_name(str(r.get("drug_name", ""))) for r in inputs.pediatric}
    hits: dict[tuple[str, str], int] = {
        (base_name(str(r["drug_name"])), str(r["family"])): int(r.get("hits") or 0)
        for r in inputs.mechlit
    }
    curated: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in inputs.evidence:
        curated[(base_name(str(row["drug_name"])), str(row["direction_id"]))].append(row)

    out: list[dict[str, Any]] = []
    for name, entry in _fold(inputs).items():
        label = inputs.labels.get(name) or {}
        approved = (not entry.get("curated_only")) or bool(label.get("has_label"))
        pediatric_label = bool(label.get("pediatric_use"))
        in_context = name in context_drugs
        pediatric_trial = name in pediatric_drugs
        automated = 4 if in_context else 1
        if approved and in_context and (pediatric_label or pediatric_trial):
            automated = 5
        base = {
            "drug_name": name,
            "automated_rung": automated,
            "approved": approved,
            "fda_label": bool(entry["fda_label"] or label.get("has_label")),
            "pediatric_label": pediatric_label,
            "trial_in_context": in_context,
            "pediatric_trial": pediatric_trial,
            "mechanism_hits": hits.get((name, "mechanism"), 0),
            "context_hits": hits.get((name, "context"), 0),
            "targets": tuple(sorted(entry["targets"])),
            "action_types": tuple(sorted(entry["action_types"])),
            "flags": _flags(name, entry, anti, standard, approved),
        }
        for direction in sorted(entry["directions"]) or [PATHWAY_DIRECTION]:
            rows = curated.get((name, direction), [])
            curated_rung = max((int(r["rung"]) for r in rows), default=0)
            rung = max(automated, curated_rung)
            out.append(
                base
                | {
                    "direction_id": direction,
                    "rung": rung,
                    "rung_label": rung_label(card, rung),
                    "curated_rung": curated_rung or None,
                    "curated_pmids": tuple(dict.fromkeys(str(r["pmid"]) for r in rows)),
                    "proxy": any(_truthy(r.get("proxy")) for r in rows) if rows else None,
                }
            )
    out.sort(
        key=lambda r: (
            -int(r["rung"]),
            -(r["curated_rung"] or 0),
            r["drug_name"],
            r["direction_id"],
        )
    )
    return out
