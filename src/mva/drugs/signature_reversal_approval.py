"""Which compound names are market-approved drugs? ChEMBL phase 4, or an openFDA label.

A connectivity library names tens of thousands of compounds, most of them tool compounds
known only by a research code (``BRD-K…``, ``PD-0325901``). The challenge keeps only
market-approved drugs, evidenced two ways (the same rule as :mod:`mva.drugs.sources.chembl`
and :mod:`mva.drugs.sources.openfda`):

1. **ChEMBL ``max_phase == 4``** — read in bulk (every phase-4 molecule, a few pages), and
   indexed by its preferred name and every synonym except trade names, each folded with
   :func:`mva.drugs.names.base_name`. A trade name is left out because brands are reused
   across molecules and countries.
2. **An openFDA label** for the generic name — asked per name, only for names ChEMBL did
   not already approve and that do not look like a research code (openFDA's anonymous
   quota is 1,000 requests a day; a code name has no US label to find).

The split between the two is recorded per compound (``approval_evidence``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .cache import Fetcher, SourceError
from .names import base_name
from .sources import chembl, openfda

__all__ = [
    "Approval",
    "approve",
    "canonical",
    "chembl_phase4_index",
    "looks_like_code",
    "openfda_labels",
]

#: Research codes, catalogue ids and registry numbers: letters-digits, BRD ids, CAS numbers.
CODE = re.compile(
    r"^(BRD-|LSM-|CID\d|SID\d)|^\d[\d-]*$|^[A-Z]{1,6}[- ]?\d[\w-]*$|^\d+-\d+-\d+$",
)

#: ChEMBL synonym types never used as a join key (brand names collide across molecules).
SKIP_SYNONYMS = frozenset({"TRADE_NAME"})


@dataclass(frozen=True)
class Approval:
    """One compound's approval facts under the two-evidence rule."""

    approved: bool
    evidence: str
    chembl_id: str = ""


def looks_like_code(key: str) -> bool:
    """``BRD-K123…``, ``PD-0325901``, ``R547``, ``38194-50-2`` → True; ``SIROLIMUS`` → False."""
    return bool(CODE.match(key.strip().upper()))


def chembl_phase4_index(fetcher: Fetcher, *, page: int = 1000) -> dict[str, tuple[str, str]]:
    """``base_name`` of every phase-4 molecule's name and synonyms → ``(ChEMBL id, name)``.

    ``name`` is the molecule's own folded preferred name: the canonical join key, so a
    library that spells a drug by its research code (``PLX-4032``) and one that spells it
    by its INN (``VEMURAFENIB``) meet on one key.

    When two molecules share a folded name, the lower ChEMBL id is kept so the index is
    deterministic.
    """
    out: dict[str, tuple[str, str]] = {}
    offset = 0
    while True:
        payload = fetcher.get_json(
            f"{chembl.BASE}/molecule.json",
            {
                "max_phase": 4,
                "limit": page,
                "offset": offset,
                "only": "molecule_chembl_id,pref_name,max_phase,molecule_synonyms",
                "format": "json",
            },
        )
        molecules = (payload or {}).get("molecules", [])
        for row in molecules:
            if chembl.phase(row.get("max_phase")) != 4:
                continue
            ident = str(row.get("molecule_chembl_id") or "")
            preferred = base_name(str(row.get("pref_name") or ""))
            names = [str(row.get("pref_name") or "")]
            names += [
                str(s.get("molecule_synonym") or "")
                for s in row.get("molecule_synonyms") or []
                if s.get("syn_type") not in SKIP_SYNONYMS
            ]
            for name in names:
                key = base_name(name)
                if not key or not preferred:
                    continue
                if key not in out or _chembl_order(ident) < _chembl_order(out[key][0]):
                    out[key] = (ident, preferred)
        if len(molecules) < page:
            break
        offset += page
    return out


def _chembl_order(ident: str) -> int:
    digits = ident.removeprefix("CHEMBL")
    return int(digits) if digits.isdigit() else 1 << 62


def openfda_labels(fetcher: Fetcher, keys: Iterable[str]) -> tuple[dict[str, str], list[str]]:
    """``(key → first application number, keys openFDA could not answer)``.

    A failed lookup (quota, outage) is returned, never read as "no label".
    """
    out: dict[str, str] = {}
    failed: list[str] = []
    for key in sorted(set(keys)):
        # openFDA spells generic names with spaces: AMPHOTERICIN B, not AMPHOTERICIN-B.
        try:
            found = openfda.label(fetcher, key.replace("-", " "))
        except SourceError:
            failed.append(key)
            continue
        if found["has_label"]:
            numbers = found["application_numbers"]
            out[key] = str(numbers[0]) if numbers else "label"
    return out, failed


def canonical(label: str, chembl_index: Mapping[str, tuple[str, str]]) -> str:
    """The join key of one library label: ChEMBL's folded preferred name, else ``base_name``.

    ChEMBL is tried with the label as spelled, then with hyphens read as spaces
    (``AMPHOTERICIN-B`` → ``AMPHOTERICIN B``).
    """
    key = base_name(label)
    for form in (key, base_name(label.replace("-", " "))):
        held = chembl_index.get(form)
        if held:
            return held[1]
    return key


def approve(
    keys: Iterable[str],
    chembl_index: Mapping[str, tuple[str, str]],
    fda: Mapping[str, str],
) -> dict[str, Approval]:
    """The approval record for each canonical key; ChEMBL is read first, openFDA second."""
    out: dict[str, Approval] = {}
    for key in keys:
        parts: list[str] = []
        ident = chembl_index[key][0] if key in chembl_index else ""
        if ident:
            parts.append(f"ChEMBL max_phase 4 ({ident})")
        if key in fda:
            parts.append(f"openFDA {fda[key]}")
        out[key] = Approval(approved=bool(parts), evidence="; ".join(parts), chembl_id=ident)
    return out
