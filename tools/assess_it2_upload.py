#!/usr/bin/env python3
"""Is a second oracle upload worth a slot? Measured, not asserted.

The budget is six uploads and one is spent. The rule this project holds itself to is that a
slot is spent only when a **pre-registered decode table** shows expected information gain
above zero bits on a live hypothesis. This stage computes that number for the three things a
second Track 1 upload could still be aimed at, and writes the answer beside the fusion.

It is deliberately **case-agnostic and coordinate-free**. The questions it asks are about the
*instrument*, not about this child: how much uncertainty is left in the hypothesis space, and
whether the scorer's reply can distinguish the candidates in it. The variants below are
synthetic placeholders built at runtime — the real alleles never enter this file and never
need to, because none of the three answers depends on which positions they sit at.

The three questions, and why they are the only ones left:

1. **The causal pair.** The first reply was a full match at rank 1 with F-max 1.000, so the
   space collapsed to a single point. A distribution with one member has zero entropy, and an
   upload cannot remove uncertainty that is not there.
2. **A second causal pair (a dual diagnosis).** The scorer's answer key holds **one or two**
   alleles. Three is not a reply this oracle can give, so "there is also a second causal pair"
   is not a hypothesis this instrument can test at all — a stronger statement than "it would
   teach us little".
3. **Secondary findings.** Rows below the causal pair change no number in the reply: the
   ranks and F-max are computed against the answer key, which rank 1 already matches exactly.
   Simulated here rather than argued.

Usage::

    uv run python tools/assess_it2_upload.py
    uv run python tools/assess_it2_upload.py --out build/it2/step-6
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mva.io.writers import write_json
from mva.pipeline.probe_design import Hypothesis, design, entropy
from mva.pipeline.submission import Row
from mva.pipeline.variant import Variant


#: Synthetic alleles. The arithmetic below is about the shape of the hypothesis space and the
#: scorer's reply, neither of which depends on a position, so nothing real is needed — and a
#: tool that needed a real one would be a tool that could leak one.
def bits(value: float) -> float:
    """Round a bit count to zero when it is zero.

    ``prior - expected`` over an identical pair of entropies produces ``-0.0`` in IEEE
    arithmetic, and a decision table that printed "-0.000 bits" would invite a reader to
    wonder what a negative information gain means. It means nothing; it is a sign bit.
    """
    return 0.0 if abs(value) < 1e-12 else value


def placeholder(index: int) -> Variant:
    """A distinct synthetic allele. Never a patient position; see the module docstring."""
    return Variant("chr1", 1_000 + index, "A", "T")


def single_point_space() -> dict[str, Any]:
    """Question 1 — how much is left to learn about the causal pair itself?"""
    left, right = placeholder(1), placeholder(2)
    confirmed = Hypothesis(truth=frozenset({left, right}), label="the confirmed pair", prior=1.0)
    rows = [Row(variant=left, partner=right, epcr=0.99, finding_type="primary")]
    found = design(rows, [confirmed])
    return {
        "question": "the causal pair",
        "hypotheses": 1,
        "prior_entropy_bits": bits(found.prior_entropy),
        "expected_information_gain_bits": bits(found.expected_information_gain),
        "distinguishable_replies": len(found.outcomes),
        "why": (
            "the first reply was a full match at rank 1 with F-max 1.000, which eliminated "
            "every other answer key in the pre-registered space; a distribution with one "
            "member has zero entropy and an upload cannot remove uncertainty that is absent"
        ),
    }


def dual_diagnosis_space() -> dict[str, Any]:
    """Question 2 — can this oracle even be asked whether a *second* pair is also causal?"""
    three = frozenset({placeholder(1), placeholder(2), placeholder(3)})
    try:
        Hypothesis(truth=three, label="two causal pairs")
    except ValueError as refusal:
        return {
            "question": "a second causal pair (dual diagnosis)",
            "expressible": False,
            "expected_information_gain_bits": 0.0,
            "why": (
                "the scorer's answer key holds one or two alleles, so a truth naming three "
                f"is not a reply this instrument can produce: {refusal}"
            ),
        }
    raise AssertionError(
        "the answer key accepted three alleles — the scorer contract this tool reasons "
        "about has changed, and the dual-diagnosis conclusion must be re-derived"
    )


def secondary_findings_space() -> dict[str, Any]:
    """Question 3 — do rows below the causal pair change any number in the reply?"""
    left, right = placeholder(1), placeholder(2)
    confirmed = Hypothesis(truth=frozenset({left, right}), label="the confirmed pair", prior=1.0)
    bare = [Row(variant=left, partner=right, epcr=0.99, finding_type="primary")]
    with_secondaries = bare + [
        Row(variant=placeholder(index), epcr=0.5 - index / 100, finding_type="secondary")
        for index in (3, 4, 5)
    ]
    first, second = design(bare, [confirmed]), design(with_secondaries, [confirmed])
    identical = [outcome.key for outcome in first.outcomes] == [
        outcome.key for outcome in second.outcomes
    ]
    return {
        "question": "secondary findings below the causal pair",
        "reply_unchanged": identical,
        "expected_information_gain_bits": bits(second.expected_information_gain),
        "why": (
            "ranks and F-max are computed against the answer key, which rank 1 already "
            "matches exactly; simulating the same truth with and without three secondary "
            "rows produces the identical reply, so the extra rows carry qualitative review "
            "value and measure nothing"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/it2/step-6"))
    args = parser.parse_args(argv)

    questions = [single_point_space(), dual_diagnosis_space(), secondary_findings_space()]
    best = bits(max(float(q["expected_information_gain_bits"]) for q in questions))
    summary = {
        "assessed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "questions": questions,
        "expected_information_gain_bits": best,
        "upload": (
            "no second upload: no live hypothesis gains a bit"
            if best <= 0
            else "a live hypothesis gains information; design a decode table before spending a slot"
        ),
        "budget": "6 uploads, 1 spent (entry 083); the remaining 5 stay in reserve",
        "check": f"entropy([1.0]) == {entropy([1.0])!r}",
    }
    write_json(args.out / "upload-assessment.json", summary)

    for question in questions:
        print(
            f"  {question['question']:<42} "
            f"EIG {float(question['expected_information_gain_bits']):.3f} bits"
        )
    print(f"\n{summary['upload']}")
    print(f"wrote {args.out / 'upload-assessment.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
