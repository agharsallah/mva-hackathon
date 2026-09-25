"""The candidate table: every drug any generator named, which ones, and what the checks said.

*Plain words.* After the join (:mod:`mva.drugs.convergence`) and the checks
(:mod:`mva.drugs.checks`, :mod:`mva.drugs.checks_safety`) this module lays the result out
as one row per drug. A **survivor** is a drug named by at least ``k`` generators that no
check fails; a caution never removes a drug, it travels with it.

The ``query_name`` column is the spelling the safety sources are asked about
(:func:`query_names`): the salt-folded join key or a generator's own label, whichever the
label database lists as an ingredient. The join key alone is not always one (DrugBank's
``Pyridoxal phosphate`` folds to ``PYRIDOXAL``), and a label alone is not either
(``Adenosine phosphate`` is listed as ``adenosine``).

Pure: rows in, rows out.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .checks import Check, worst
from .convergence_tables import GeneratorList, GeneratorRow

__all__ = ["CandidateChecks", "candidate_rows", "columns", "query_names", "write_candidates"]

CHECK_IDS = ("k1", "k2", "k3")


@dataclass(frozen=True)
class CandidateChecks:
    """K1-K3 for one drug; ``None`` means the check was not run on this drug."""

    k1: Check | None = None
    k2: Check | None = None
    k3: Check | None = None


def query_names(lists: Sequence[GeneratorList], vocabulary: Collection[str] = ()) -> dict[str, str]:
    """``{drug: the lower-case spelling the safety sources are asked about}``.

    Candidates are the join key and every generator's label for the drug, in ``lists``
    order. The first candidate that is a name in ``vocabulary`` (the label source's own
    ingredient list) wins; with no vocabulary or no match, the first list's label does.
    """
    spellings: dict[str, list[str]] = {}
    for item in lists:
        for drug, row in item.best().items():
            options = spellings.setdefault(drug, [drug.lower()])
            label = row.drug_label.strip().lower()
            if label and label not in options:
                options.append(label)
    known = {v.lower() for v in vocabulary}
    out: dict[str, str] = {}
    for drug, options in spellings.items():
        hit = next((o for o in options if o in known), None)
        out[drug] = hit or (options[1] if len(options) > 1 else options[0])
    return out


def columns(generators: Sequence[str]) -> tuple[str, ...]:
    ranks = tuple(f"rank_{g}" for g in generators)
    checks = tuple(f"{c}_{part}" for c in CHECK_IDS for part in ("status", "reason"))
    return (
        "drug",
        "query_name",
        "n_generators",
        "generators",
        "converging",
        *ranks,
        "direction_hints",
        "approval_evidence",
        *checks,
        "survivor",
        "survivor_reason",
    )


def _hints(rows: Sequence[GeneratorRow]) -> str:
    found = sorted({h for r in rows for h in r.direction_hint.split("|") if h and h != "none"})
    return "|".join(found) or "none"


def candidate_rows(
    lists: Sequence[GeneratorList],
    checks: Mapping[str, CandidateChecks],
    *,
    k: int = 2,
    names: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    """One row per drug named by any list, converging drugs first, then by generator count."""
    best = {item.generator: item.best() for item in lists}
    names = names or query_names(lists)
    drugs = sorted({d for b in best.values() for d in b})
    out: list[dict[str, str]] = []
    for drug in drugs:
        named = [g for g in best if drug in best[g]]
        rows = [best[g][drug] for g in named]
        verdict = checks.get(drug, CandidateChecks())
        record: dict[str, str] = {
            "drug": drug,
            "query_name": names[drug],
            "n_generators": str(len(named)),
            "generators": "|".join(named),
            "converging": "true" if len(named) >= k else "false",
            "direction_hints": _hints(rows),
            "approval_evidence": " | ".join(f"{r.generator}: {r.approval_evidence}" for r in rows),
        }
        for item in lists:
            row = best[item.generator].get(drug)
            record[f"rank_{item.generator}"] = str(row.rank) if row else ""
        ran: list[Check] = []
        for cid in CHECK_IDS:
            check = getattr(verdict, cid)
            record[f"{cid}_status"] = check.status if check else "not run"
            record[f"{cid}_reason"] = check.reason if check else ""
            if check:
                ran.append(check)
        record.update(_survivor(len(named) >= k, verdict, ran))
        out.append(record)
    out.sort(key=lambda r: (r["converging"] != "true", -int(r["n_generators"]), r["drug"]))
    return out


def _survivor(converges: bool, verdict: CandidateChecks, ran: Sequence[Check]) -> dict[str, str]:
    if not converges:
        return {"survivor": "false", "survivor_reason": "named by fewer than k generators"}
    missing = [c for c in CHECK_IDS if getattr(verdict, c) is None]
    if missing:
        return {"survivor": "false", "survivor_reason": "check not run: " + ", ".join(missing)}
    failed = [c for c in CHECK_IDS if getattr(verdict, c).excludes]
    if failed:
        return {"survivor": "false", "survivor_reason": "fails " + ", ".join(failed)}
    level = worst(ran)
    reason = "passes every check" + (" (with a caution)" if level == "caution" else "")
    return {"survivor": "true", "survivor_reason": reason}


def write_candidates(
    rows: Sequence[Mapping[str, str]], generators: Sequence[str], path: Path
) -> int:
    """Write the candidate table; returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns(generators), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
