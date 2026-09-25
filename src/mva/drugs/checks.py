"""The checks that filter converging drugs: direction (K1) and a contrary screen (K3).

*Plain words.* A **check** only removes or cautions; it never proposes a drug (that is a
generator's job, :mod:`mva.drugs.convergence_generators`). Every check returns a
:class:`Check` - ``pass``, ``caution`` (kept, with a reason a reader must see) or ``fail``
(not a survivor) - and every rule is a frozen dataclass whose :meth:`as_manifest` is written
into the output's provenance, so the rule a table was filtered by is on disk beside it.

* **K1 direction** (:class:`K1Rule`). A *checkpoint-kinase inhibitor* - an annotated MOA
  (mechanism of action) of Mps1/TTK or Aurora kinase inhibition, the class entry 151
  measured as *less* effective in high-aneuploidy lines - fails. A *spindle poison*
  (tubulin / microtubule binder) is a caution, not an exclusion. The MOA text is the Drug
  Repurposing Hub's annotation (the field entry 151 used to define the class); a drug the
  Hub does not annotate is a caution (``unannotated``), and a target list that includes a
  checkpoint kinase without the MOA saying so is a caution (polypharmacology), never a fail.
* **K3 contrary screen** (:class:`K3Rule`). Where a screen measures a drug on the contrast
  its proposed direction maps to, the drug fails when the effect points the other way:
  Cliff's delta below 0 *and* the one-sided p in that opposite direction below ``alpha``.
  A drug with no measurable direction, or not measured, passes as ``not applicable``.

Pure: no I/O. The safety check (K2) lives in :mod:`mva.drugs.checks_safety`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

__all__ = [
    "Check",
    "K1Rule",
    "K3Rule",
    "Measurement",
    "k1",
    "k3",
    "worst",
]

Status = Literal["pass", "caution", "fail"]
_ORDER: dict[str, int] = {"pass": 0, "caution": 1, "fail": 2}


@dataclass(frozen=True)
class Check:
    """One check's verdict on one drug."""

    status: Status
    reason: str

    @property
    def excludes(self) -> bool:
        return self.status == "fail"


def worst(checks: Iterable[Check]) -> Status:
    """The most severe status among ``checks`` (``pass`` when there are none)."""
    status: Status = "pass"
    for check in checks:
        if _ORDER[check.status] > _ORDER[status]:
            status = check.status
    return status


@dataclass(frozen=True)
class K1Rule:
    """The do-not and caution classes, as MOA phrases and target symbols (case-blind)."""

    do_not_moa: tuple[str, ...] = (
        "MONOPOLAR SPINDLE 1 KINASE INHIBITOR",
        "AURORA KINASE INHIBITOR",
        "TTK INHIBITOR",
        "MPS1 INHIBITOR",
    )
    caution_moa: tuple[str, ...] = (
        "TUBULIN POLYMERIZATION INHIBITOR",
        "TUBULIN INHIBITOR",
        "MICROTUBULE INHIBITOR",
        "MICROTUBULE STABILIZING AGENT",
        "MICROTUBULE STIMULANT",
    )
    checkpoint_targets: tuple[str, ...] = ("TTK", "AURKA", "AURKB", "AURKC")
    moa_source: str = "Drug Repurposing Hub MOA field (PRISM compound annotation)"
    source_entry: str = (
        "entry 151: 33 of 34 Mps1/Aurora inhibitors less effective in aneuploid lines"
    )

    def as_manifest(self) -> dict[str, Any]:
        out = asdict(self)
        out["rule"] = (
            "fail when the annotated MOA contains a do_not_moa phrase; caution when it "
            "contains a caution_moa phrase (spindle poison), when the drug has no MOA "
            "annotation, or when its annotated targets include a checkpoint_targets symbol "
            "the MOA does not name; pass otherwise"
        )
        return out


def _contains(text: str, phrases: Sequence[str]) -> list[str]:
    upper = text.upper()
    return [p for p in phrases if p.upper() in upper]


def k1(moa: str | None, targets: Iterable[str] = (), rule: K1Rule | None = None) -> Check:
    """K1 for one drug from its MOA text and its annotated targets."""
    rule = rule or K1Rule()
    hit = _contains(moa or "", rule.do_not_moa)
    if hit:
        return Check("fail", f"checkpoint-kinase inhibitor: MOA '{moa}'")
    reasons: list[str] = []
    poison = _contains(moa or "", rule.caution_moa)
    if poison:
        reasons.append(f"spindle poison (caution, not an exclusion): MOA '{moa}'")
    if not (moa or "").strip():
        reasons.append("unannotated: no MOA in the annotation source")
    wanted = {t.upper() for t in rule.checkpoint_targets}
    off = sorted({t.strip().upper() for t in targets if t.strip()} & wanted)
    if off:
        reasons.append("annotated targets include " + ", ".join(off) + " (polypharmacology)")
    if reasons:
        return Check("caution", "; ".join(reasons))
    return Check("pass", f"MOA '{moa}' is in no do-not class")


@dataclass(frozen=True)
class Measurement:
    """One screen contrast for one drug. ``delta > 0`` means the in-group is more sensitive.

    ``p_opposite`` is the one-sided p that the in-group is *less* sensitive.
    """

    contrast: str
    delta: float
    p_opposite: float
    note: str = ""


@dataclass(frozen=True)
class K3Rule:
    """Which contrast each direction is proposed on, and the contrary threshold."""

    direction_contrasts: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    alpha: float = 0.05

    def contrasts_for(self, directions: Iterable[str]) -> tuple[str, ...]:
        out: list[str] = []
        for direction in directions:
            for contrast in self.direction_contrasts.get(direction, ()):
                if contrast not in out:
                    out.append(contrast)
        return tuple(out)

    def as_manifest(self) -> dict[str, Any]:
        return {
            "direction_contrasts": {k: list(v) for k, v in self.direction_contrasts.items()},
            "alpha": self.alpha,
            "rule": (
                "fail when, on a contrast the drug's direction maps to, Cliff's delta < 0 and "
                "the one-sided p that the in-group is LESS sensitive < alpha; pass (not "
                "applicable) when no direction maps to a contrast or the drug is not measured"
            ),
        }


def k3(directions: Iterable[str], measurements: Sequence[Measurement], rule: K3Rule) -> Check:
    """K3 for one drug: contrary on any mapped contrast fails it."""
    wanted = rule.contrasts_for(directions)
    if not wanted:
        return Check("pass", "not applicable: no proposed direction maps to a screen contrast")
    seen = [m for m in measurements if m.contrast in wanted]
    if not seen:
        return Check("pass", "not applicable: not measured on " + ", ".join(wanted))
    contrary = [m for m in seen if m.delta < 0 and m.p_opposite < rule.alpha]
    shown = "; ".join(f"{m.contrast} delta {m.delta:+.3f} p_opp {m.p_opposite:.3g}" for m in seen)
    if contrary:
        return Check("fail", "contrary: " + shown)
    return Check("pass", "not contrary: " + shown)
