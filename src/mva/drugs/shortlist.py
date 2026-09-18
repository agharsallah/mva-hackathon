"""From a ladder to two tables: the shortlist the report argues, and the do-not table.

The ladder has a row for every approved drug on every direction it touches - hundreds of
rows, most at rung 1. A report cannot argue hundreds of rows, and the plan said which ones it
may argue: **rung 2 or higher**, not already the standard of care for the tumour context (giving
a child the chemotherapy they are already getting is not a repurposing), and not an
anti-direction (a drug the mechanism says would make things worse).

Ordering inside the shortlist is deliberate and printed as ``why``:

0. a curated result (a paper read by a person, on the mechanism) before an automated rung
   alone - an automated rung 5 says the drug is already being tried in the tumour, which is
   a fact about the tumour's trial landscape and not a repurposing this work discovered;
1. the rung, highest first;
2. a curated result for the molecule itself before a same-axis proxy;
3. paediatric evidence (a label section or a study admitting children) before none;
4. more mechanism literature before less - descriptive, and last for that reason.

The do-not table is the other half of the same ladder: every drug carrying an anti-direction
flag, with the card's own status for that anti-direction (``do not`` or ``caution``), and every
standard-of-care drug named so a reader sees they were considered and set aside, not missed.
"""

from __future__ import annotations

from typing import Any

from .mechanism import MechanismCard

__all__ = ["MIN_RUNG", "do_not_table", "shortlist"]

#: A drug below this rung is named in the ladder and never submitted.
MIN_RUNG = 2


def _anti_status(card: MechanismCard) -> dict[str, dict[str, str]]:
    return {
        str(e.get("id")): {"status": str(e.get("status", "")), "name": str(e.get("name", ""))}
        for e in card.raw.get("anti_directions") or []
    }


def _pediatric(row: dict[str, Any]) -> str:
    parts = []
    if row.get("pediatric_label"):
        parts.append("label section 8.4")
    if row.get("pediatric_trial"):
        parts.append("study admitting children")
    return "; ".join(parts) or "none found"


def shortlist(rows: list[dict[str, Any]], card: MechanismCard) -> list[dict[str, Any]]:
    """The rows the report may argue, ranked, with the reason for each rank."""
    anti = _anti_status(card)
    kept = [
        r
        for r in rows
        if int(r["rung"]) >= MIN_RUNG
        and "standard_of_care" not in r["flags"]
        and not any(f in anti for f in r["flags"])
        and r["direction_id"] != "pathway"
    ]
    kept.sort(
        key=lambda r: (
            0 if r.get("curated_rung") else 1,
            -int(r["rung"]),
            0 if r.get("proxy") is False else 1,
            0 if (r.get("pediatric_label") or r.get("pediatric_trial")) else 1,
            -int(r.get("mechanism_hits") or 0),
            r["drug_name"],
        )
    )
    out = []
    for rank, r in enumerate(kept, start=1):
        why = [f"rung {r['rung']}"]
        if r.get("curated_rung"):
            why.append(
                "curated result for the molecule"
                if r.get("proxy") is False
                else "curated result for a same-axis proxy"
            )
        if r.get("trial_in_context"):
            why.append("registered trial in the tumour context")
        if r.get("mechanism_hits"):
            why.append(f"{r['mechanism_hits']} PubMed records with the mechanism")
        out.append(
            {
                "rank": rank,
                "drug_name": r["drug_name"],
                "direction_id": r["direction_id"],
                "rung": r["rung"],
                "verdict": _verdict(r),
                "why": "; ".join(why),
                "pediatric_evidence": _pediatric(r),
                "curated_pmids": r.get("curated_pmids", ()),
                "targets": r.get("targets", ()),
                "flags": r.get("flags", ()),
            }
        )
    return out


def _verdict(r: dict[str, Any]) -> str:
    if not r.get("curated_rung"):
        return "context trial only - not a mechanism finding"
    return "argue" if r.get("approved") else "argue - approval to verify"


def do_not_table(rows: list[dict[str, Any]], card: MechanismCard) -> list[dict[str, Any]]:
    """Every drug set aside, once, with the reason: an anti-direction or the standard of care."""
    anti = _anti_status(card)
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        flags = tuple(r["flags"])
        anti_hits = [f for f in flags if f in anti]
        standard = "standard_of_care" in flags
        if not anti_hits and not standard:
            continue
        name = r["drug_name"]
        if name in seen:
            continue
        if anti_hits:
            first = anti[anti_hits[0]]
            verdict = first["status"] or "do not"
            why = f"{anti_hits[0]}: {first['name']}"
        else:
            verdict = "standard of care"
            why = "already part of the tumour context's treatment; giving it is not a repurposing"
        seen[name] = {
            "rank": None,
            "drug_name": name,
            "direction_id": r["direction_id"],
            "rung": r["rung"],
            "verdict": verdict,
            "why": why,
            "pediatric_evidence": _pediatric(r),
            "curated_pmids": r.get("curated_pmids", ()),
            "targets": r.get("targets", ()),
            "flags": flags,
        }
    order = {"do not": 0, "caution": 1, "standard of care": 2}
    return sorted(seen.values(), key=lambda r: (order.get(r["verdict"], 9), r["drug_name"]))
