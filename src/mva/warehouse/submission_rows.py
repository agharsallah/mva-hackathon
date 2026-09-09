"""Derive every non-coordinate field of a submission row from the warehouse.

A selector says *which* allele a row holds (:mod:`mva.warehouse.submission_spec`). This
module says everything else about the row — and refuses to let a human type it:

* **facts** — gene, consequence, zygosity, filter, depth, allele fraction, gnomAD frequency,
  ClinVar significance, dbSNP id — are read from the selector's own result table, with the
  same ``WHERE`` clause, so a note can only quote what the table holds;
* **score** — one allele's rarity × severity, from :mod:`mva.pipeline.ranking`, the
  heuristic the methods form already defends; a pair scores the sum of its alleles;
* **epcr** — the rank-1 row takes the register's suggested confidence for the hypothesis it
  tests (the *anchor*); every other primary row shares the remaining mass in proportion to
  its pair score; secondary rows sit below the lowest primary, ordered by allele score;
* **notes** — a fixed template over the facts, plus an optional free-text ``rationale``
  that may contain **no digit**, so a number can only reach the organisers from a table;
* **priors** — a hypothesis whose alleles are all in the callset takes the mass of the row
  that names them; only a hypothesis naming an ``_unknown`` allele may *declare* a prior,
  because "the partner is a variant we cannot see" is not something a table can measure.

Every number comes out with its arithmetic (:attr:`Derivation.lines`), so the derivation
can be printed, committed coordinate-free next to the selectors, and argued with. The
weighing the anchor comes from is a transparent triage heuristic, not a calibrated
posterior; the epcr inherits that caveat and the rendering says so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .submission_facts import AlleleFacts

__all__ = [
    "EPCR_DIGITS",
    "SECONDARY_SHARE",
    "UNKNOWN_PREFIX",
    "Derivation",
    "DerivationError",
    "DerivedRow",
    "derive",
]

UNKNOWN_PREFIX = "_unknown"
#: Significant digits an epcr is rounded to before the distinctness check.
EPCR_DIGITS = 4
#: A secondary row's ceiling relative to the lowest primary: half of it, so no secondary
#: can overtake a primary whatever its allele score.
SECONDARY_SHARE = 0.5
#: A number a human typed: a digit that does not continue an identifier such as BUB1B or rs6025.
DIGIT = re.compile(r"(?<![A-Za-z0-9])\d")


class DerivationError(ValueError):
    """The spec asks for something the data cannot support."""


@dataclass(frozen=True)
class DerivedRow:
    """One submission row with every field the data decided."""

    label: str
    variant: str
    partner: str | None
    finding_type: str
    score: float
    epcr: float
    notes: str
    hypothesis: str | None = None

    def to_spec(self) -> dict[str, Any]:
        """The row as :mod:`tools.design_submission` reads it."""
        out: dict[str, Any] = {
            "variant": self.variant,
            "epcr": self.epcr,
            "finding_type": self.finding_type,
            "label": self.label,
            "notes": self.notes,
        }
        if self.partner:
            out["partner"] = self.partner
        return out

    def to_json(self) -> dict[str, Any]:
        return {**self.to_spec(), "score": round(self.score, 4), "hypothesis": self.hypothesis}


@dataclass(frozen=True)
class Derivation:
    """Rows, priors, facts and the arithmetic that joined them."""

    rows: tuple[DerivedRow, ...]
    hypotheses: tuple[dict[str, Any], ...]
    facts: dict[str, AlleleFacts]
    anchor: dict[str, Any]
    lines: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        """Coordinate-free by construction: no field here ever held a position."""
        return {
            "anchor": self.anchor,
            "parameters": {"epcr_digits": EPCR_DIGITS, "secondary_share": SECONDARY_SHARE},
            "alleles": {name: f.to_json() for name, f in self.facts.items()},
            "rows": [row.to_json() for row in self.rows],
            "hypotheses": list(self.hypotheses),
            "arithmetic": list(self.lines),
        }


def derive(
    spec: dict[str, Any], facts: dict[str, AlleleFacts], anchor_confidence: float
) -> Derivation:
    """Fill ``rows`` and ``hypotheses`` from facts, the anchor, and nothing else.

    ``spec`` is the committed selector file. Its rows name alleles, a ``finding_type``, an
    optional ``label``, an optional digit-free ``rationale``, and (on exactly one primary
    row) the ``hypothesis`` the anchor confidence belongs to. Any ``epcr``, ``notes`` or
    in-callset ``prior`` in the file is refused: those are outputs here.
    """
    anchor = spec.get("derivation", {}).get("anchor", {})
    _refuse_hand_values(spec)
    if not 0 < anchor_confidence <= 1:
        raise DerivationError(f"anchor confidence must lie in (0, 1], got {anchor_confidence}")

    lines = [
        (
            f"anchor: row {anchor.get('row')!r} tests {anchor.get('hypothesis')} — "
            f"register suggested confidence {anchor_confidence:.4f}"
        )
    ]
    scored = [_score_row(item, facts) for item in spec["rows"]]
    primaries = [r for r in scored if r["finding_type"] == "primary"]
    secondaries = [r for r in scored if r["finding_type"] != "primary"]
    top = _anchor_row(primaries, anchor, lines)

    others = [r for r in primaries if r is not top]
    total = sum(r["score"] for r in others)
    residual = 1.0 - anchor_confidence
    epcr: dict[str, float] = {top["label"]: _sig(anchor_confidence)}
    for row in others:
        value = _sig(residual * row["score"] / total) if total else 0.0
        epcr[row["label"]] = value
        lines.append(
            f"{row['label']}: ({1:.0f} - {anchor_confidence:.4f}) x {row['score']:.4f} / "
            f"{total:.4f} = {value}"
        )
    lowest = min(epcr.values())
    floor = lowest * SECONDARY_SHARE
    top_secondary = max((r["score"] for r in secondaries), default=1.0) or 1.0
    for row in secondaries:
        value = _sig(floor * row["score"] / top_secondary)
        epcr[row["label"]] = value
        lines.append(
            f"{row['label']}: lowest primary {lowest:.4g} x {SECONDARY_SHARE} x "
            f"{row['score']:.4f} / {top_secondary:.4f} = {value}"
        )
    _require_distinct(epcr)

    rows = tuple(
        sorted(
            (
                DerivedRow(
                    label=r["label"],
                    variant=r["variant"],
                    partner=r["partner"],
                    finding_type=r["finding_type"],
                    score=r["score"],
                    epcr=epcr[r["label"]],
                    notes=_note(r, facts, anchor_confidence if r is top else None),
                    hypothesis=r.get("hypothesis"),
                )
                for r in scored
            ),
            key=lambda row: row.epcr,
            reverse=True,
        )
    )
    hypotheses = _priors(spec.get("hypotheses", []), rows, lines)
    return Derivation(
        rows=rows,
        hypotheses=tuple(hypotheses),
        facts=facts,
        anchor={**anchor, "confidence": _sig(anchor_confidence)},
        lines=tuple(lines),
    )


def _refuse_hand_values(spec: dict[str, Any]) -> None:
    for i, row in enumerate(spec["rows"], 1):
        for key in ("epcr", "notes"):
            if key in row:
                raise DerivationError(f"row {i}: {key!r} is derived, remove it from the selectors")
        rationale = row.get("rationale", "")
        if DIGIT.search(rationale):
            raise DerivationError(
                f"row {i}: rationale contains a number; numbers reach a note only from a table"
            )
    for hypothesis in spec.get("hypotheses", []):
        names = hypothesis.get("alleles", [])
        seen = not any(str(n).startswith(UNKNOWN_PREFIX) for n in names)
        if seen and "prior" in hypothesis:
            raise DerivationError(
                f"hypothesis {hypothesis.get('label')!r}: prior is derived from its row; "
                "only a hypothesis naming an _unknown allele declares one"
            )
        if not seen and "prior" not in hypothesis:
            raise DerivationError(
                f"hypothesis {hypothesis.get('label')!r} names an unseen allele and must "
                "declare a prior — the data cannot measure it"
            )


def _score_row(item: dict[str, Any], facts: dict[str, AlleleFacts]) -> dict[str, Any]:
    variant, partner = item["variant"], item.get("partner")
    for name in (variant, partner):
        if name and name not in facts:
            raise DerivationError(f"row names allele {name!r} with no facts")
    score = facts[variant].score + (facts[partner].score if partner else 0.0)
    label = item.get("label") or variant + (f"+{partner}" if partner else "")
    return {
        **item,
        "label": str(label),
        "variant": variant,
        "partner": partner,
        "finding_type": item.get("finding_type", "primary"),
        "score": score,
    }


def _anchor_row(
    primaries: list[dict[str, Any]], anchor: dict[str, Any], lines: list[str]
) -> dict[str, Any]:
    if not primaries:
        raise DerivationError("a submission needs at least one primary row")
    matches = [r for r in primaries if r["label"] == anchor.get("row")]
    if len(matches) != 1:
        raise DerivationError(
            f"derivation.anchor.row {anchor.get('row')!r} must name exactly one primary row"
        )
    top = matches[0]
    best = max(primaries, key=lambda r: r["score"])
    if best is not top and best["score"] > top["score"]:
        raise DerivationError(
            f"the ranking heuristic prefers {best['label']!r} ({best['score']:.3f}) over the "
            f"anchor {top['label']!r} ({top['score']:.3f}); the register and the ranker disagree"
        )
    lines.extend(f"{row['label']}: pair score {row['score']:.4f}" for row in primaries)
    return top


def _require_distinct(epcr: dict[str, float]) -> None:
    seen: dict[float, str] = {}
    for label, value in epcr.items():
        if value <= 0:
            raise DerivationError(f"{label}: epcr rounds to {value}; not in (0, 1]")
        if value in seen:
            raise DerivationError(
                f"{label} and {seen[value]} both derive epcr {value}; the rank would be "
                "decided by file order — split the tie in the data, not by hand"
            )
        seen[value] = label


def _note(row: dict[str, Any], facts: dict[str, AlleleFacts], anchor: float | None) -> str:
    parts = []
    if row.get("hypothesis"):
        parts.append(f"H:{row['hypothesis']}")
    parts.append(row["finding_type"])
    alleles = [facts[row["variant"]]]
    if row.get("partner"):
        alleles.append(facts[row["partner"]])
    parts.append(" + ".join(a.describe() for a in alleles))
    if row.get("rationale"):
        parts.append(str(row["rationale"]))
    parts.append(
        f"epcr = register weighing {anchor:.4f} (triage heuristic, not a calibrated posterior)"
        if anchor is not None
        else "epcr = share of residual mass by pair score"
        if row["finding_type"] == "primary"
        else "epcr below every primary row, ordered by allele score; not scored"
    )
    return " | ".join(parts)


def _priors(
    hypotheses: list[dict[str, Any]], rows: tuple[DerivedRow, ...], lines: list[str]
) -> list[dict[str, Any]]:
    declared = sum(float(h["prior"]) for h in hypotheses if "prior" in h)
    if declared >= 1:
        raise DerivationError(f"declared unseen priors sum to {declared}, leaving no mass")
    by_alleles = {
        frozenset(n for n in (r.variant, r.partner) if n): r
        for r in rows
        if r.finding_type == "primary"
    }
    mass = sum(r.epcr for r in by_alleles.values())
    out = []
    for hypothesis in hypotheses:
        if "prior" in hypothesis:
            out.append({**hypothesis, "prior_source": "declared"})
            continue
        row = by_alleles.get(frozenset(hypothesis["alleles"]))
        if row is None:
            raise DerivationError(
                f"hypothesis {hypothesis.get('label')!r} has no primary row holding its alleles"
            )
        prior = _sig((1 - declared) * row.epcr / mass)
        lines.append(
            f"prior {hypothesis['label']}: (1 - {declared:.2f}) x {row.epcr} / {mass:.4f} = {prior}"
        )
        out.append({**hypothesis, "prior": prior, "prior_source": f"row {row.label}"})
    return out


def _sig(value: float) -> float:
    """Round to :data:`EPCR_DIGITS` significant digits, so small shares stay distinct."""
    return float(f"{value:.{EPCR_DIGITS}g}")
