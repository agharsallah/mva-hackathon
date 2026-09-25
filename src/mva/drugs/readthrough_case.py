"""The case card for route R1: every published number this route puts into an arithmetic.

The generic modules (:mod:`~mva.drugs.readthrough`, :mod:`~mva.drugs.readthrough_context`,
:mod:`~mva.drugs.readthrough_dosage`) know nothing about any gene. This module is where the
BubR1/MVA case enters, and **every constant carries the PMID it came from** so that a reader
can check it and a second case can be written by replacing this one file.

Three groups of numbers:

* **Thresholds** — how much BubR1 a mouse or a cell needs. These are the yardsticks the dosage
  scenarios are read against.
* **Allele factors** — what each of the child's two copies contributes, taken from measurements
  on *other* people's BUB1B alleles, never from the child (nothing has been measured in the
  child beyond the DNA).
* **Scenarios** — the named combinations, including the treated ones, whose only drug-derived
  input is the readthrough fraction this route predicted and controlled.

Nothing here is a recommendation, and no number is a measurement in this child.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from mva.drugs.readthrough_dosage import Allele, DrugEffect, Scenario, Threshold

__all__ = [
    "BENCHMARK_PANEL",
    "DOSAGE_PARAMETERS",
    "THRESHOLDS",
    "best_readthrough",
    "scenarios",
]

#: The PTC contexts held out of the fit before anything was predicted for this child. Chosen
#: from the readthrough literature (the alleles other papers benchmark on), not from any model
#: output. ``CFTR_Y1092X`` is reachable by two different stops, so the loader splits it.
BENCHMARK_PANEL = frozenset(
    {
        "CFTR_G542X",
        "CFTR_W1282X",
        "CFTR_R1162X",
        "CFTR_R553X",
        "CFTR_G550X",
        "CFTR_Y1092X(tag)",
        "CFTR_Y1092X(taa)",
        "TP53_R213X",
        "DMD_R1051X",
        "DMD_R3381X",
        "USH2A_R626X",
        "PTEN_R130X",
        "BUB1B_R114X",
        "CEP57_R339X",
    }
)

#: Published BubR1 levels and what they produce. Percent of the wild-type **diploid** level.
THRESHOLDS: tuple[Threshold, ...] = (
    Threshold("wild type", 100.0, "healthy", "reference"),
    Threshold(
        "heterozygous carrier (mouse +/-, +/X753)",
        50.0,
        "viable; reduced lifespan, sarcopenia, 18 % splenocyte aneuploidy for +/X753",
        "PMID:31738183; PMID:23300461",
    ),
    Threshold(
        "segregation-fidelity cliff, upper lip (human cells, ~13 %)",
        13.0,
        "virtually no impact on chromosome segregation fidelity",
        "PMID:20516114 (doxycycline-titratable BUBR1 shRNA HeLa)",
    ),
    Threshold(
        "mouse hypomorph H/H (~10 %)",
        10.0,
        "viable, progeroid: dwarfism, sarcopenia, cataracts, 15 % splenocyte aneuploidy",
        "PMID:15208629, quantified in PMID:23300461 and PMID:31738183",
    ),
    Threshold(
        "segregation-fidelity cliff, lower lip (human cells, ~6 %)",
        6.0,
        "chromosome mis-segregation in the majority of cells",
        "PMID:20516114",
    ),
    Threshold(
        "mouse -/H (~4-5 %)",
        4.5,
        "dies at or near P1 of respiratory failure",
        "PMID:23300461 (4 %); PMID:31738183 (5 %)",
    ),
    Threshold("mouse null (0 %)", 0.0, "dies before E3.5", "PMID:15208629"),
)

#: The missense allele's protein output, as a fraction of one healthy allele. Human MVA patient
#: cells show full-length mutant BUBR1 **2-6 fold** below wild type (PMID 20516114); the base
#: case takes the middle of that range and the two ends are run as their own scenarios.
MISSENSE_LEVEL = {
    "optimistic (2-fold down)": 0.50,
    "base (4-fold down)": 0.25,
    "pessimistic (6-fold down)": 0.17,
}

#: Share of the stop allele's message that survives nonsense-mediated decay. No measurement
#: exists for this child; in patient cells the 386X transcript was undetectable and the 731X
#: allele's transcript absent (PMID 20516114), and the mouse X753 allele's transcript matched a
#: null allele (PMID 31738183). 0.10 is therefore a **generous** upper reading of "undetectable".
NMD_ESCAPE = 0.10

#: What a full NMD blockade would lift that to. NMD inhibitors are preclinical and NMD is
#: essential (Smg1-null mice are embryonic lethal, PMID 20566848), so this is an upper bound on
#: a hypothetical, not a dose.
NMD_INHIBITED = 1.0

#: How well a readthrough product works. Readthrough inserts a near-cognate amino acid at the
#: stop, so the chain is full length but not wild type. Nothing is measured for this position;
#: 0.5 is a stated guess and the sensitivity scenarios run 1.0.
PRODUCT_ACTIVITY = 0.5

DOSAGE_PARAMETERS: dict[str, Any] = {
    "nmd_escape": NMD_ESCAPE,
    "nmd_escape_under_inhibition": NMD_INHIBITED,
    "readthrough_product_activity": PRODUCT_ACTIVITY,
    "missense_protein_levels": MISSENSE_LEVEL,
    "missense_specific_activity_when_unstable": 1.0,
    "missense_specific_activity_when_inactive": 0.10,
    "model": "per allele, 0.5 x mrna x protein_per_mrna x full_length x specific_activity",
}


def _stop_allele(readthrough: float = 0.0, *, escape: float = NMD_ESCAPE) -> Allele:
    return Allele(
        label="stop",
        mrna=escape,
        protein_per_mrna=1.0,
        full_length=readthrough,
        specific_activity=PRODUCT_ACTIVITY if readthrough else 1.0,
        basis="NMD-competent premature stop; no full-length protein without a readthrough agent",
    )


def _missense(level: float, *, activity: float = 1.0) -> Allele:
    return Allele(
        label="missense",
        mrna=1.0,
        protein_per_mrna=level,
        full_length=1.0,
        specific_activity=activity,
        basis="transcript normal (PMID 20516114); the loss is protein abundance or function",
    )


def best_readthrough(path: Path, *, controlled_only: bool = True) -> dict[str, float]:
    """The predicted readthrough per drug, as a fraction, from this route's own table.

    By default only drugs whose positive control passed are returned, so a number that is not
    interpretable cannot silently enter a dosage scenario. ``Untreated`` is the dataset's
    no-drug column and is never a treatment.
    """
    out: dict[str, float] = {}
    if not path.is_file():
        return out
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row["predicted_readthrough"] or row["drug_name"] == "Untreated":
                continue
            if controlled_only and row["control_passed"] != "true":
                continue
            out[row["drug_name"]] = float(row["predicted_readthrough"]) / 100.0
    return out


def scenarios(facts: dict[str, Any], predicted: dict[str, float]) -> list[Scenario]:
    """Every dosage scenario, untreated first, then the treated ones this route can price."""
    base = MISSENSE_LEVEL["base (4-fold down)"]
    out = [
        Scenario(
            "wild type",
            (_missense(1.0), _missense(1.0)),
            note="reference: two healthy copies",
        ),
        Scenario(
            "one healthy copy (a parent)",
            (_missense(1.0), _stop_allele()),
            note="the carrier state; the yardstick a treated child would have to approach",
        ),
    ]
    for label, level in MISSENSE_LEVEL.items():
        out.append(
            Scenario(
                f"child now, missense unstable, {label}",
                (_stop_allele(), _missense(level)),
                note=(
                    "untreated; the stop allele contributes nothing because its message is "
                    "destroyed"
                ),
            )
        )
    out.append(
        Scenario(
            "child now, missense inactive",
            (_stop_allele(), _missense(1.0, activity=0.10)),
            note=(
                "the other branch: enough protein, but it does not work. Specific activity is a "
                "placeholder, not a measurement"
            ),
        )
    )
    for drug, fraction in sorted(predicted.items(), key=lambda item: -item[1]):
        out.append(
            Scenario(
                f"child + {drug} (readthrough only)",
                (_stop_allele(), _missense(base)),
                drug=DrugEffect(
                    drug,
                    applies_to="stop",
                    readthrough=fraction,
                    product_activity=PRODUCT_ACTIVITY,
                    source="this route's model, controlled on the declared benchmark panel",
                ),
                note=f"the stop allele's message is still {100 * NMD_ESCAPE:.0f}% present at most",
            )
        )
    fraction = predicted.get("DAP", 0.0)
    out.append(
        Scenario(
            "child + DAP + complete NMD blockade (upper bound, not a dose)",
            (_stop_allele(), _missense(base)),
            drug=DrugEffect(
                "DAP + NMD inhibition",
                applies_to="stop",
                nmd_escape_to=NMD_INHIBITED,
                readthrough=fraction,
                product_activity=PRODUCT_ACTIVITY,
                source=(
                    "readthrough from this route's model; the NMD term is a hypothetical ceiling"
                ),
            ),
            note=(
                "every assumption at its most generous, to see the ceiling of the stop-allele route"
            ),
        )
    )
    out.append(
        Scenario(
            "child + a perfect readthrough agent (ceiling)",
            (_stop_allele(), _missense(base)),
            drug=DrugEffect(
                "hypothetical: full transcript, best measured readthrough, wild-type product",
                applies_to="stop",
                nmd_escape_to=NMD_INHIBITED,
                readthrough=max(predicted.values(), default=0.0),
                product_activity=1.0,
                source="arithmetic ceiling, not any real agent",
            ),
            note="not achievable; it bounds what the stop allele could ever be worth",
        )
    )
    out.append(
        Scenario(
            "child + a 2-fold stabilisation of the missense protein",
            (_stop_allele(), _missense(base)),
            drug=DrugEffect(
                "missense-stabilising (the branch this route's arithmetic favours)",
                applies_to="missense",
                protein_per_mrna_to=min(2 * base, 1.0),
                source=(
                    "direction from PMID 24825348 (NAD+/SIRT2 raises BubR1 in vivo); the factor is "
                    "a target, not a measured effect"
                ),
            ),
            note=(
                "modelled by doubling the missense allele's protein: see the entry, not a measured "
                "drug effect"
            ),
        )
    )
    _ = facts
    return out
