#!/usr/bin/env python3
"""Build a Track-1 submission from a spec, rehearse it, and read it as a measurement.

Case-agnostic. Everything case-specific — which alleles, which rows, which answer keys are
still plausible — lives in a JSON **spec** the caller writes, and because a spec names real
patient coordinates it lives under gitignored ``build/``. This tool:

1. builds the rows with :mod:`mva.pipeline.submission` and writes the CSV (LF, template
   header, ``PROBAND01``);
2. re-reads the bytes exactly as the scorer would and grades them against every answer key
   in the spec's hypothesis space with :mod:`mva.pipeline.scorer` — the rehearsal — and,
   when the organisers' ``evaluation.py`` is present, grades the same file with *their* code
   too and refuses to finish if the two disagree on any exposed field
   (:mod:`mva.pipeline.scorer_reference`);
3. groups the keys by the reply they would produce with :mod:`mva.pipeline.probe_design`
   and prints the **decode table** with the expected information gain;
4. optionally writes a coordinate-free Markdown rendering of that table (labels only) for
   the report.

Spec shape (``build/submission/spec.json``)::

    {
      "alleles": {"stop": {"chrom": "15", "pos": 1, "ref": "T", "alt": "G"}, ...},
      "rows": [
        {"variant": "stop", "partner": "missense", "epcr": 0.95,
         "finding_type": "primary", "notes": "H:H009 | BUB1B | ..."},
        {"variant": "stop", "epcr": 0.60, "notes": "..."}
      ],
      "hypotheses": [
        {"label": "stop+missense", "alleles": ["stop", "missense"], "prior": 0.80},
        {"label": "stop+unknown",  "alleles": ["stop", "_unknown_1"], "prior": 0.05}
      ]
    }

An allele name starting with ``_unknown`` stands for an allele *not in the callset*; it is
minted as a synthetic variant that matches nothing, so "the partner is something we cannot
see" is a member of the hypothesis space like any other.
"""

from __future__ import annotations

import argparse
import json
import sys
from io import StringIO
from pathlib import Path

from mva.pipeline.probe_design import Design, Hypothesis, design
from mva.pipeline.scorer import score
from mva.pipeline.scorer_reference import (
    DEFAULT_REFERENCE,
    compare,
    grade_with_reference,
    load_reference,
)
from mva.pipeline.submission import Row, read_submission, write_submission
from mva.pipeline.variant import Variant

UNKNOWN_PREFIX = "_unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", type=Path, required=True, help="the JSON spec (gitignored)")
    parser.add_argument("--out", type=Path, required=True, help="where to write the CSV")
    parser.add_argument(
        "--decode-md",
        type=Path,
        help="write the decode table as Markdown with labels only, no coordinates",
    )
    parser.add_argument(
        "--reference-scorer",
        type=Path,
        default=DEFAULT_REFERENCE,
        help="the organisers' evaluation.py; the rehearsal is cross-checked against it",
    )
    parser.add_argument(
        "--skip-reference",
        action="store_true",
        help="do not cross-check against the organisers' scorer even if the file is present",
    )
    return parser.parse_args()


def load_alleles(spec: dict) -> dict[str, Variant]:
    found: dict[str, Variant] = {}
    for name, fields in spec["alleles"].items():
        found[name] = Variant.from_vcf(fields["chrom"], fields["pos"], fields["ref"], fields["alt"])
    return found


def unknown(name: str) -> Variant:
    """A placeholder allele that can match nothing in any submission."""
    index = int(name.rsplit("_", 1)[-1]) if name.rsplit("_", 1)[-1].isdigit() else 0
    return Variant("chrUnknown", 1 + index, "N", "N")


def build_rows(spec: dict, alleles: dict[str, Variant]) -> list[Row]:
    return [
        Row(
            variant=alleles[item["variant"]],
            partner=alleles[item["partner"]] if item.get("partner") else None,
            epcr=float(item["epcr"]),
            finding_type=item.get("finding_type", "primary"),
            notes=item.get("notes", ""),
        )
        for item in spec["rows"]
    ]


def build_space(spec: dict, alleles: dict[str, Variant]) -> list[Hypothesis]:
    space = []
    for item in spec["hypotheses"]:
        members = frozenset(
            unknown(name) if name.startswith(UNKNOWN_PREFIX) else alleles[name]
            for name in item["alleles"]
        )
        space.append(Hypothesis(members, item["label"], float(item.get("prior", 1.0))))
    return space


def rehearse(csv_text: str, space: list[Hypothesis]) -> list[tuple[str, dict]]:
    """Grade the written bytes against every answer key, as the scorer would read them."""
    parsed = read_submission(StringIO(csv_text))
    out = []
    for hypothesis in space:
        result = score(parsed, hypothesis.truth)
        out.append(
            (
                hypothesis.label,
                {
                    "rank_points": result.rank_points,
                    "f_max": round(result.f_max, 4),
                    "f_max_threshold": result.f_max_threshold,
                    "full_match_rank": result.full_match_rank,
                    "partial_match_rank": result.partial_match_rank,
                },
            )
        )
    return out


def cross_check(csv_path: Path, space: list[Hypothesis], reference_path: Path) -> bool:
    """Grade the written file with the organisers' code and compare field by field.

    Returns ``True`` when both scorers agree on every key (or the reference is absent, which
    is reported), ``False`` on the first disagreement — the tool then exits non-zero, because
    a rehearsal the real scorer would grade differently is worse than no rehearsal.
    """
    reference = load_reference(reference_path)
    if reference is None:
        print(f"\ncross-check: organisers' scorer not found at {reference_path}; skipped")
        return True
    print(f"\ncross-check against the organisers' scorer ({reference_path}):")
    parsed = read_submission(StringIO(csv_path.read_text(encoding="utf-8")))
    agree = True
    for hypothesis in space:
        ours = score(parsed, hypothesis.truth)
        theirs = grade_with_reference(reference, csv_path, hypothesis.truth)
        differences = compare(ours, theirs)
        status = "agree" if not differences else "DISAGREE " + "; ".join(map(str, differences))
        print(f"  {hypothesis.label:<28} {status}")
        agree = agree and not differences
    return agree


def row_label(item: dict) -> str:
    """A coordinate-free name for a row: its own label, else the allele names it joins."""
    if item.get("label"):
        return str(item["label"])
    return item["variant"] + (f"+{item['partner']}" if item.get("partner") else "")


def decode_markdown(found: Design, labels_by_row: list[str]) -> str:
    header = (
        "| Reply: full match rank | partial match rank | F-max | at epcr | prior mass | survivors |"
    )
    lines = [header, "|---|---|---|---|---|---|"]
    for outcome in found.outcomes:
        full, partial, f_max, threshold = outcome.key
        survivors = ", ".join(h.label for h in outcome.hypotheses)
        lines.append(
            f"| {full if full is not None else '—'} | {partial if partial is not None else '—'} "
            f"| {f_max:.3f} | {threshold if threshold is not None else '—'} "
            f"| {outcome.mass:.2f} | {survivors} |"
        )
    summary = (
        f"Prior entropy {found.prior_entropy:.3f} bits · expected posterior "
        f"{found.expected_posterior_entropy:.3f} bits · **expected information gain "
        f"{found.expected_information_gain:.3f} bits** · largest ambiguity "
        f"{found.max_ambiguity} hypotheses in one reply."
    )
    lines += [
        "",
        summary,
        "",
        "Rows, in rank order: "
        + "; ".join(f"{i + 1}. {label}" for i, label in enumerate(labels_by_row)),
    ]
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    alleles = load_alleles(spec)
    rows = build_rows(spec, alleles)
    space = build_space(spec, alleles)

    buffer = StringIO()
    write_submission(rows, buffer)
    csv_text = buffer.getvalue()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(csv_text, encoding="utf-8")
    print(f"wrote {args.out}  ({len(rows)} rows, {len(csv_text)} bytes, LF)")

    print("\nrehearsal — the written bytes graded against every answer key in the space:")
    for label, result in rehearse(csv_text, space):
        print(f"  {label:<28} {result}")

    if not args.skip_reference and not cross_check(args.out, space, args.reference_scorer):
        sys.exit("cross-check failed: the replica and the organisers' scorer disagree")

    found = design(rows, space)
    labels_by_row = [row_label(item) for item in spec["rows"]]
    table = decode_markdown(found, labels_by_row)
    print("\ndecode table:\n" + table)
    if args.decode_md:
        args.decode_md.parent.mkdir(parents=True, exist_ok=True)
        args.decode_md.write_text(table + "\n", encoding="utf-8")
        print(f"\nwrote {args.decode_md} (labels only, no coordinates)")
    if any(UNKNOWN_PREFIX in h.label for h in space) and found.max_ambiguity > 1:
        print(
            "\nnote: some replies leave more than one hypothesis standing — "
            "the follow-up probe is decided by which reply arrives.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
