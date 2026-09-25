"""How much working protein two broken alleles make, and what a drug could add.

A recessive disease caused by two damaged copies of one gene is, at bottom, an arithmetic
problem: each copy contributes some fraction of the working protein a healthy copy would, and
the disease appears when the total falls below a threshold. This module makes that arithmetic
explicit and parameterised, so that *every* number in it is a stated assumption a reader can
change rather than a claim hidden in prose.

The model, per allele, is a product of four factors (all fractions of one healthy allele):

``mrna`` × ``protein_per_mrna`` × ``full_length`` × ``specific_activity``

* **mrna** — how much of the message survives. For a **nonsense allele** (a copy with a
  premature stop) this is the share that escapes **nonsense-mediated decay** (NMD, the cell's
  destruction of messages that stop early). For a missense allele it is normally 1.
* **protein_per_mrna** — how much protein a surviving message yields, and how much of it
  survives degradation. This is where an *unstable* missense protein loses ground.
* **full_length** — the share of finished chains that are full length. Without a drug a
  nonsense allele makes none; **readthrough** drugs (which make the ribosome ignore the
  premature stop) raise this.
* **specific_activity** — how well a full-length chain works. A readthrough product carries a
  near-cognate amino acid at the stop, so it is not automatically normal protein; an *inactive*
  missense protein has a low value here with ``protein_per_mrna`` near 1.

Two alleles each cap at 0.5 of the wild-type diploid total, so a healthy person scores 1.0.
Thresholds — "below x % the aneuploidy phenotype appears" — come from published genotypes and
are passed in with their sources; this module never invents one.

Case-agnostic by construction: nothing here names a gene, a patient or a position.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = [
    "Allele",
    "DrugEffect",
    "Scenario",
    "ScenarioResult",
    "Threshold",
    "evaluate",
    "nearest_threshold",
]


@dataclass(frozen=True)
class Allele:
    """One copy of the gene, as four multiplicative fractions of a healthy copy."""

    label: str
    mrna: float
    protein_per_mrna: float
    full_length: float
    specific_activity: float
    basis: str = ""

    def __post_init__(self) -> None:
        for name in ("mrna", "protein_per_mrna", "full_length", "specific_activity"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{self.label}: {name}={value} is outside [0, 1]")

    @property
    def output(self) -> float:
        """This allele's share of the wild-type **diploid** total (0.5 when fully healthy)."""
        return 0.5 * self.mrna * self.protein_per_mrna * self.full_length * self.specific_activity


@dataclass(frozen=True)
class DrugEffect:
    """What a treatment multiplies, expressed on the same four factors.

    Each field *sets* the factor it names rather than scaling it, because that is how the
    measurements are reported: ``nmd_escape_to`` is the surviving-message fraction an NMD
    inhibitor would lift the allele to, ``protein_per_mrna_to`` the level a stabiliser would
    hold the protein at, ``readthrough`` the share of ribosomes reaching the premature stop
    that continue to the real one, and ``product_activity`` how well the resulting chain works.
    """

    label: str
    applies_to: str
    nmd_escape_to: float | None = None
    protein_per_mrna_to: float | None = None
    readthrough: float | None = None
    product_activity: float | None = None
    source: str = ""

    def apply(self, allele: Allele) -> Allele:
        """The allele as this drug leaves it. Alleles it does not target come back unchanged."""
        if allele.label != self.applies_to:
            return allele
        changed = allele
        if self.nmd_escape_to is not None:
            changed = replace(changed, mrna=max(changed.mrna, self.nmd_escape_to))
        if self.protein_per_mrna_to is not None:
            changed = replace(changed, protein_per_mrna=self.protein_per_mrna_to)
        if self.readthrough is not None:
            changed = replace(changed, full_length=self.readthrough)
        if self.product_activity is not None:
            changed = replace(changed, specific_activity=self.product_activity)
        return replace(changed, label=allele.label)


@dataclass(frozen=True)
class Threshold:
    """A published genotype and the protein level it carries, used as a yardstick."""

    label: str
    percent: float
    phenotype: str
    source: str


@dataclass(frozen=True)
class Scenario:
    """A named combination of alleles and (optionally) one treatment."""

    label: str
    alleles: tuple[Allele, ...]
    drug: DrugEffect | None = None
    note: str = ""


@dataclass(frozen=True)
class ScenarioResult:
    """One scenario's arithmetic, kept beside its inputs so a reader can re-derive it."""

    label: str
    per_allele: tuple[tuple[str, float], ...]
    total: float
    drug: str
    gain: float
    note: str

    @property
    def percent(self) -> float:
        return 100.0 * self.total


def evaluate(scenario: Scenario) -> ScenarioResult:
    """Total working protein for one scenario, as a fraction of the wild-type diploid level."""
    treated = tuple(scenario.drug.apply(a) if scenario.drug else a for a in scenario.alleles)
    per_allele = tuple((a.label, a.output) for a in treated)
    total = sum(value for _, value in per_allele)
    baseline = sum(a.output for a in scenario.alleles)
    return ScenarioResult(
        label=scenario.label,
        per_allele=per_allele,
        total=total,
        drug=scenario.drug.label if scenario.drug else "none",
        gain=total - baseline,
        note=scenario.note,
    )


def nearest_threshold(
    result: ScenarioResult, thresholds: tuple[Threshold, ...]
) -> Threshold | None:
    """The published genotype whose protein level is closest to this scenario's total."""
    if not thresholds:
        return None
    return min(thresholds, key=lambda t: abs(t.percent - result.percent))
