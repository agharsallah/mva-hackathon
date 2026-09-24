"""Label-derived adverse effects, read against the patient's own phenotypes — and a base rate.

"Statins cause myopathy" is true of almost every statin label and also of 2,921 other
labels. On its own it says nothing about *this* patient. So every number this module
produces is a rate with a denominator and a comparison:

* **the unit is a label** (one regulatory product label, OnSIDES ``product_label``);
* **a drug matches** when one of its labels carries an adverse effect whose MedDRA id is in
  the patient's mapped set (``ressources/track2/hpo_to_adverse_terms.tsv``);
* **the comparison set** is other approved ingredients matched on *how many distinct
  adverse effects their labels carry* — a proxy for how thoroughly the product was
  studied and how verbose its label is, which is the main confounder of "does this label
  mention muscle injury". Matching on ATC class was rejected because several candidates
  here (nicotinamide, bortezomib, dasatinib) have no class-mate on the shortlist.

The FAERS cross-check is spontaneous reporting: it has a numerator and **no denominator**,
so it can show that a drug–event pair has been reported in children and can never give a
rate. Every FAERS string this module emits says ``reports`` for that reason.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .patient_safety import LabelMatch

#: OnSIDES v3.x CSV files this module reads, by logical name.
ONSIDES_FILES: Mapping[str, str] = {
    "labels": "product_label.csv",
    "effects": "product_adverse_effect.csv",
    "product_to_rxnorm": "product_to_rxnorm.csv",
    "ingredient_to_product": "vocab_rxnorm_ingredient_to_product.csv",
    "ingredient": "vocab_rxnorm_ingredient.csv",
    "meddra": "vocab_meddra_adverse_effect.csv",
}

#: openFDA drug-event endpoint. Public domain, no key needed at this volume.
FAERS_URL = "https://api.fda.gov/drug/event.json"

#: Paediatric filter: onset age 0–17 in years (``patientonsetageunit`` 801 = years).
FAERS_PAEDIATRIC = "patient.patientonsetage:[0+TO+17]+AND+patient.patientonsetageunit:801"


@dataclass(frozen=True)
class LabelUniverse:
    """The OnSIDES tables, opened once, as a DuckDB connection with views in place."""

    root: Path
    sources: tuple[str, ...] = ("US", "EU", "UK", "JP")

    def connect(self) -> object:
        """A DuckDB connection with one view per OnSIDES CSV.

        Every column is read as text: OnSIDES mixes integer ids with ``OMOP…`` string ids
        in the same column, and a typed read fails on the first one.
        """
        import duckdb

        connection = duckdb.connect()
        for name, filename in ONSIDES_FILES.items():
            path = self.root / filename
            connection.sql(
                f"create view {name} as "
                f"select * from read_csv_auto('{path.as_posix()}', all_varchar=true)"
            )
        allowed = ",".join(f"'{s}'" for s in self.sources)
        connection.sql(
            "create view drug_label as "
            "select distinct lower(ing.rxnorm_name) as drug, lab.label_id, lab.source "
            "from labels lab "
            "join product_to_rxnorm p2r on p2r.label_id = lab.label_id "
            "join ingredient_to_product i2p on i2p.product_id = p2r.rxnorm_product_id "
            "join ingredient ing on ing.rxnorm_id = i2p.ingredient_id "
            f"where lab.source in ({allowed})"
        )
        return connection


def label_counts(connection: object, drugs: Sequence[str]) -> dict[str, int]:
    """Drug → number of distinct labels OnSIDES holds for it."""
    wanted = ",".join("'" + d.lower().replace("'", "''") + "'" for d in drugs)
    rows = connection.sql(  # type: ignore[attr-defined]
        f"select drug, count(distinct label_id) n from drug_label "
        f"where drug in ({wanted}) group by 1"
    ).fetchall()
    return {str(drug): int(n) for drug, n in rows}


def matched_labels(
    connection: object, drugs: Sequence[str], meddra_ids: Sequence[str]
) -> dict[str, tuple[int, tuple[str, ...], dict[str, int]]]:
    """Drug → (labels carrying ≥1 mapped effect, the effect names, per-effect label counts)."""
    if not drugs or not meddra_ids:
        return {}
    wanted = ",".join("'" + d.lower().replace("'", "''") + "'" for d in drugs)
    ids = ",".join(f"'{i}'" for i in meddra_ids)
    rows = connection.sql(  # type: ignore[attr-defined]
        f"select dl.drug, m.meddra_name, count(distinct dl.label_id) n "
        f"from drug_label dl "
        f"join effects ae on ae.product_label_id = dl.label_id "
        f"join meddra m on m.meddra_id = ae.effect_meddra_id "
        f"where dl.drug in ({wanted}) and ae.effect_meddra_id in ({ids}) "
        f"group by 1,2"
    ).fetchall()
    any_rows = connection.sql(  # type: ignore[attr-defined]
        f"select dl.drug, count(distinct dl.label_id) n from drug_label dl "
        f"join effects ae on ae.product_label_id = dl.label_id "
        f"where dl.drug in ({wanted}) and ae.effect_meddra_id in ({ids}) group by 1"
    ).fetchall()
    totals = {str(d): int(n) for d, n in any_rows}
    per_effect: dict[str, dict[str, int]] = {}
    for drug, effect, n in rows:
        per_effect.setdefault(str(drug), {})[str(effect)] = int(n)
    return {
        drug: (
            totals.get(drug, 0),
            tuple(sorted(per_effect.get(drug, {}))),
            per_effect.get(drug, {}),
        )
        for drug in totals
    }


def build_matches(
    connection: object, drugs: Sequence[str], meddra_ids: Sequence[str]
) -> dict[str, LabelMatch]:
    """Assemble :class:`LabelMatch` per drug, including drugs OnSIDES does not hold."""
    totals = label_counts(connection, drugs)
    hits = matched_labels(connection, drugs, meddra_ids)
    out: dict[str, LabelMatch] = {}
    for drug in drugs:
        key = drug.lower()
        matched, effects, per_term = hits.get(key, (0, (), {}))
        out[key] = LabelMatch(
            drug=drug,
            labels_total=totals.get(key, 0),
            labels_matched=matched,
            effects=effects,
            per_term=per_term,
        )
    return out


def effect_breadth(connection: object) -> dict[str, int]:
    """Ingredient → how many distinct adverse effects its labels carry. The matching variable."""
    rows = connection.sql(  # type: ignore[attr-defined]
        "select dl.drug, count(distinct ae.effect_meddra_id) n from drug_label dl "
        "join effects ae on ae.product_label_id = dl.label_id group by 1"
    ).fetchall()
    return {str(drug): int(n) for drug, n in rows}


def comparison_set(
    breadth: Mapping[str, int], shortlist: Sequence[str], per_candidate: int = 5
) -> list[str]:
    """Nearest-neighbour match on effect breadth: ``per_candidate`` controls per candidate.

    Deterministic: neighbours are taken in order of \\|breadth difference\\|, ties broken by
    name, so a rerun gives the same comparison set.
    """
    taken = {d.lower() for d in shortlist}
    pool = sorted(k for k in breadth if k not in taken)
    chosen: list[str] = []
    seen: set[str] = set()
    for drug in shortlist:
        target = breadth.get(drug.lower())
        if target is None:
            continue
        ranked = sorted(pool, key=lambda k: (abs(breadth[k] - target), k))
        added = 0
        for candidate in ranked:
            if candidate in seen:
                continue
            chosen.append(candidate)
            seen.add(candidate)
            added += 1
            if added >= per_candidate:
                break
    return chosen


def faers_paediatric(drug: str, reaction: str, pause: float = 0.4) -> int:
    """Count of FAERS reports pairing ``drug`` with ``reaction`` in patients aged 0–17.

    Returns ``-1`` when openFDA answers "no matches" (its 404 for an empty result set),
    so a genuine zero is distinguishable from a failed request by the caller's log.
    """
    query = (
        f'patient.drug.openfda.generic_name:"{urllib.parse.quote(drug)}"'
        f'+AND+patient.reaction.reactionmeddrapt.exact:"{urllib.parse.quote(reaction)}"'
        f"+AND+{FAERS_PAEDIATRIC}"
    )
    url = f"{FAERS_URL}?search={query}&limit=1"
    request = urllib.request.Request(url, headers={"User-Agent": "mva-hackathon/patient-safety"})
    time.sleep(pause)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        return 0 if error.code == 404 else -1
    total = payload.get("meta", {}).get("results", {}).get("total")
    return int(total) if isinstance(total, int) else -1
