"""From verified literature rows to approved-drug candidates, with a direction check.

A verified row says "*this* intervention moved *that* effect in *this* model". Three kinds of
intervention translate to a drug differently:

``drug`` / ``diet``  the named substance itself → a ChEMBL molecule by exact name/synonym.
``genetic``, target is a gene   → every ChEMBL mechanism against that gene's human target,
                                 kept only when the drug acts in the **same direction** as the
                                 genetic change (overexpression needs an activator, knockout an
                                 inhibitor). A drug acting the other way is a *mismatch*: it is
                                 recorded, flagged, and never becomes a candidate.
any type, target is a class  → a declared analogue class (e.g. clearing senescent cells →
                              senolytics, promoter methylation → hypomethylating agents),
                              direction-checked the same way, scored lower.

Only interventions whose effect went the **desired** way (``desired``: for a hypomorph,
more protein and fewer senescent cells are good) become candidates. An intervention that
made things worse is kept in the translation log as a harm signal.

``evidence_strength`` is a stated heuristic, not a probability — see :data:`RUBRIC`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .sources import chembl

__all__ = [
    "ACTIVATING",
    "INHIBITING",
    "RUBRIC",
    "candidates",
    "control_recall",
    "direction_check",
    "strength",
    "translate",
]

#: ChEMBL ``action_type`` values that add activity to a target, and those that remove it.
ACTIVATING = frozenset(
    {
        "ACTIVATOR",
        "AGONIST",
        "PARTIAL AGONIST",
        "POSITIVE ALLOSTERIC MODULATOR",
        "POSITIVE MODULATOR",
        "OPENER",
        "STABILISER",
        "RELEASING AGENT",
    }
)
INHIBITING = frozenset(
    {
        "INHIBITOR",
        "ANTAGONIST",
        "NEGATIVE ALLOSTERIC MODULATOR",
        "NEGATIVE MODULATOR",
        "BLOCKER",
        "INVERSE AGONIST",
        "DEGRADER",
        "DISRUPTING AGENT",
        "ANTISENSE INHIBITOR",
        "RNAI INHIBITOR",
        "ALLOSTERIC ANTAGONIST",
    }
)

RUBRIC: dict[str, dict[str, float]] = {
    "model": {
        "human_patient": 1.0,
        "mouse_in_vivo": 0.8,
        "human_cells": 0.6,
        "mouse_cells": 0.5,
        "other_organism": 0.4,
    },
    "directness": {
        "bubr1_level": 1.0,
        "function": 0.9,
        "acetylation": 0.8,
        "aneuploidy": 0.8,
        "lifespan": 0.7,
        "senescence": 0.6,
        "tumour": 0.6,
        "other": 0.6,
    },
    "replication": {"1": 0.6, "2": 0.8, "3+": 1.0},
    "translation": {
        "direct_approved": 1.0,
        "direct_unapproved": 0.3,
        "gene_analogue_approved": 0.6,
        "class_analogue_approved": 0.4,
        "class_analogue_unapproved": 0.2,
    },
}


def direction_check(mode: str, action_type: str) -> str:
    """``match`` / ``mismatch`` / ``unknown`` for a genetic mode against a drug action.

    ``gain`` (overexpression, activation) needs an activating drug; ``loss`` (knockout,
    knockdown, cell removal) needs an inhibiting one. Anything else cannot be judged.
    """
    action = (action_type or "").upper().strip()
    if mode == "gain":
        return (
            "match" if action in ACTIVATING else "mismatch" if action in INHIBITING else "unknown"
        )
    if mode == "loss":
        return (
            "match" if action in INHIBITING else "mismatch" if action in ACTIVATING else "unknown"
        )
    return "unknown"


def _polarity(row: Mapping[str, str], desired: Mapping[str, str]) -> str:
    goal = desired.get(row.get("effect_on", ""))
    direction = row.get("direction", "")
    if not goal or direction == "no_change":
        return "neutral"
    return "benefit" if direction == goal else "harm"


def _spellings(name: str) -> list[str]:
    """``"5-aza-2'-deoxycytidine (decitabine)"`` → the whole string, the head, the bracket.

    A literature row names a compound the way its paper does; ChEMBL knows one of those
    spellings. Trying all three costs at most three cached requests and needs no synonym
    table in the case card.
    """
    head = name.split("(", maxsplit=1)[0].strip()
    inner = name[name.find("(") + 1 : name.rfind(")")].strip() if "(" in name else ""
    return [n for n in dict.fromkeys([name.strip(), head, inner]) if n]


def _lookup(fetcher: Any, name: str) -> dict[str, Any] | None:
    """A ChEMBL molecule by exact preferred name, else exact synonym; highest phase wins."""
    for spelling in _spellings(name):
        found = _lookup_one(fetcher, spelling)
        if found:
            return found
    return None


def _lookup_one(fetcher: Any, name: str) -> dict[str, Any] | None:
    # Synonym first: ChEMBL lists a molecule's preferred name among its synonyms, and the
    # synonym index answers in well under a second where ``pref_name__iexact`` takes ~15.
    for field in ("molecule_synonyms__molecule_synonym__iexact", "pref_name__iexact"):
        payload = fetcher.get_json(
            f"{chembl.BASE}/molecule.json", {field: name, "limit": 20, "format": "json"}
        )
        found = [
            {
                "molecule_chembl_id": m.get("molecule_chembl_id"),
                "pref_name": m.get("pref_name"),
                "max_phase": chembl.phase(m.get("max_phase")),
            }
            for m in (payload or {}).get("molecules", [])
        ]
        if found:
            return max(found, key=lambda m: m["max_phase"] or 0)
    return None


def _gene_drugs(fetcher: Any, symbol: str, mode: str) -> list[dict[str, Any]]:
    """Approved drugs with a ChEMBL mechanism on ``symbol``'s human target, direction-checked."""
    out: list[dict[str, Any]] = []
    for target in chembl.targets_for_gene(fetcher, symbol):
        mechs = chembl.mechanisms_for_target(fetcher, str(target["target_chembl_id"]))
        facts = chembl.molecules(fetcher, [m["molecule_chembl_id"] for m in mechs])
        for mech in mechs:
            mol = facts.get(mech["molecule_chembl_id"], {})
            out.append(
                {
                    "drug_name": str(mol.get("pref_name") or mech["molecule_chembl_id"]).lower(),
                    "molecule_chembl_id": mech["molecule_chembl_id"],
                    "action_type": mech["action_type"],
                    "max_phase": mol.get("max_phase"),
                    "direction_check": direction_check(mode, mech["action_type"]),
                }
            )
    return out


def translate(
    kept: Iterable[Mapping[str, str]],
    fetcher: Any,
    *,
    desired: Mapping[str, str],
    analogues: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """One record per (intervention, type, mode, target) group, with its drug mapping."""
    groups: dict[tuple[str, str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in kept:
        key = (row["intervention"].strip(), row["intervention_type"], row["mode"], row["target"])
        groups[key].append(row)
    out: list[dict[str, Any]] = []
    for (name, kind, mode, target), rows in sorted(groups.items()):
        polarities = [_polarity(r, desired) for r in rows]
        record: dict[str, Any] = {
            "intervention": name,
            "intervention_type": kind,
            "mode": mode,
            "target": target,
            "pmids": sorted({r["pmid"] for r in rows}, key=int),
            "benefit_rows": [r for r, p in zip(rows, polarities, strict=True) if p == "benefit"],
            "harm_rows": [r for r, p in zip(rows, polarities, strict=True) if p == "harm"],
            "drugs": [],
        }
        if kind in ("drug", "diet"):
            approved = False
            for part in (p.strip() for p in name.split(" or ")):
                mol = _lookup(fetcher, part)
                approved = approved or ((mol or {}).get("max_phase") or 0) >= 4
                record["drugs"].append(
                    {
                        "drug_name": _spellings(part)[-1].lower(),
                        "mapping": "direct",
                        "molecule_chembl_id": (mol or {}).get("molecule_chembl_id"),
                        "max_phase": (mol or {}).get("max_phase"),
                        "direction_check": "n/a",
                    }
                )
            # A tool compound that no regulator approved is not a candidate on its own; the
            # approved members of its class are, provided they act the same way on the target.
            if not approved and target in analogues:
                record["drugs"].extend(_class_drugs(fetcher, analogues[target], mode))
        elif target in analogues:
            record["drugs"].extend(_class_drugs(fetcher, analogues[target], mode))
        elif kind == "genetic":
            for drug in _gene_drugs(fetcher, target, mode):
                record["drugs"].append({**drug, "mapping": "gene_analogue"})
        out.append(record)
    return out


def _class_drugs(fetcher: Any, spec: Mapping[str, Any], mode: str) -> list[dict[str, Any]]:
    """The declared approved members of one analogue class, direction-checked against ``mode``."""
    check = "match" if spec["act"] == mode else "mismatch"
    out: list[dict[str, Any]] = []
    for drug in spec["drugs"]:
        mol = _lookup(fetcher, str(drug))
        out.append(
            {
                "drug_name": str(drug),
                "mapping": "class_analogue",
                "class": spec.get("class"),
                "molecule_chembl_id": (mol or {}).get("molecule_chembl_id"),
                "max_phase": (mol or {}).get("max_phase"),
                "direction_check": check,
            }
        )
    return out


def _replication(pmids: Sequence[str]) -> float:
    n = len(set(pmids))
    return RUBRIC["replication"]["3+" if n >= 3 else str(max(n, 1))]


def strength(rows: Sequence[Mapping[str, str]], translation: str) -> float:
    """model × directness × replication × translation, each the best the rows offer."""
    model = max(RUBRIC["model"].get(r["model_system"], 0.0) for r in rows)
    direct = max(RUBRIC["directness"].get(r["effect_on"], 0.0) for r in rows)
    return round(
        model
        * direct
        * _replication([r["pmid"] for r in rows])
        * RUBRIC["translation"][translation],
        3,
    )


def _translation_key(drug: Mapping[str, Any]) -> str:
    approved = (drug.get("max_phase") or 0) >= 4
    mapping = str(drug["mapping"])
    if mapping == "direct":
        return "direct_approved" if approved else "direct_unapproved"
    if mapping == "gene_analogue":
        return "gene_analogue_approved"
    return "class_analogue_approved" if approved else "class_analogue_unapproved"


def candidates(
    mapped: Iterable[Mapping[str, Any]],
    *,
    branch_by_effect: Mapping[str, str],
    control_passed: bool,
    route: str = "R3",
) -> list[dict[str, Any]]:
    """Candidate rows in the plan's pinned columns, best row per (drug, branch)."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for record in mapped:
        rows = record["benefit_rows"]
        if not rows:
            continue
        lead = max(rows, key=lambda r: RUBRIC["directness"].get(r["effect_on"], 0.0))
        branch = branch_by_effect.get(lead["effect_on"], "any")
        for drug in record["drugs"]:
            if drug["direction_check"] == "mismatch":
                continue
            if drug["mapping"] == "gene_analogue" and (drug.get("max_phase") or 0) < 4:
                continue
            key = _translation_key(drug)
            score = strength(rows, key)
            effects = sorted({f"{r['effect_on']}:{r['direction']}" for r in rows})
            row = {
                "drug_name": drug["drug_name"],
                "route": route,
                "branch": branch,
                "evidence_kind": f"literature_{drug['mapping']}",
                "evidence_strength": score,
                "positive_control_passed": str(control_passed).lower(),
                "source": ";".join(f"PMID:{p}" for p in sorted({r["pmid"] for r in rows}, key=int)),
                "notes": (
                    f"{record['intervention']} ({record['intervention_type']}, {record['mode']}, "
                    f"target {record['target']}) → {', '.join(effects)}; "
                    f"model {'/'.join(sorted({r['model_system'] for r in rows}))}; "
                    f"direction check {drug['direction_check']}; "
                    f"ChEMBL {drug.get('molecule_chembl_id') or 'not found'} "
                    f"max_phase {drug.get('max_phase')}; rubric {key}"
                ),
            }
            slot = (row["drug_name"], branch)
            if slot not in best or score > best[slot]["evidence_strength"]:
                best[slot] = row
    return sorted(best.values(), key=lambda r: (-r["evidence_strength"], r["drug_name"]))


def control_recall(
    kept: Iterable[Mapping[str, str]],
    controls: Mapping[str, Sequence[tuple[str, str]]],
    texts: Mapping[str, Any],
) -> dict[str, Any]:
    """Retrieval and extraction recall over the control PMIDs, and whether both are n/n."""
    rows = list(kept)
    per: dict[str, dict[str, bool]] = {}
    for pmid, findings in controls.items():
        allowed = {tuple(f) for f in findings}
        per[pmid] = {
            "retrieved": pmid in texts,
            "extracted": any(
                r["pmid"] == pmid and (r["effect_on"], r["direction"]) in allowed for r in rows
            ),
        }
    n = len(controls)
    got = sum(v["retrieved"] for v in per.values())
    ext = sum(v["extracted"] for v in per.values())
    return {
        "retrieval": f"{got}/{n}",
        "extraction": f"{ext}/{n}",
        "per_pmid": per,
        "passed": got == n and ext == n,
    }
