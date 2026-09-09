#!/usr/bin/env python3
"""Turn a committed, coordinate-free selector spec into the gitignored submission spec.

    uv run python tools/resolve_submission_spec.py \\
        --selectors submissions/track1/iteration-1/spec.selectors.json \\
        --out build/submission/spec.json

Reads ``alleles`` as selectors (see :mod:`mva.warehouse.submission_spec`), resolves each to
one ``(chrom, pos, ref, alt)`` in the warehouse, and writes the spec
:mod:`tools.design_submission` consumes. When the selector file carries a ``derivation``
block, every non-coordinate field is **derived** rather than copied
(:mod:`mva.warehouse.submission_rows`): the facts a note quotes come from the selector's
own table, the epcr ladder is anchored on the register's suggested confidence for the
hypothesis the rank-1 row tests, and the in-callset priors follow the rows. The derivation
is written coordinate-free next to the selectors (``derivation.json`` + ``derivation.md``)
so a judge reads *why each number is what it is* without a database. A selector file
without that block is copied through as before.

Prints one line per allele **without** the position — the file is
the only place a coordinate lands. With ``--check`` it compares against an existing spec
and reports whether every allele resolved to the same coordinates (again without printing
them), so a rebuilt spec can be proven identical to the one a submission was built from.

With ``--record-lineage`` it also appends this iteration's edges to
``warehouse.data_lineage`` (:mod:`mva.warehouse.submission_lineage`): one per selector
table, one for the committed selector file by digest, one for the delivered phenotype
document by digest. That is the last hop of the provenance chain — the result tables to the
rows an organiser scores — and it is the hop a judge most wants to check. Appending is
idempotent, so resolving twice does not double the edges.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mva.science.record import from_register
from mva.warehouse.postgres import attached
from mva.warehouse.settings import Postgres
from mva.warehouse.submission_facts import AlleleFacts, fetch_facts
from mva.warehouse.submission_lineage import record_iteration
from mva.warehouse.submission_rows import Derivation, DerivationError, derive
from mva.warehouse.submission_spec import Selector, SelectorError, resolve_all

DEFAULT_REGISTER = Path("docs/science-register.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--selectors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="the spec to write (gitignored)")
    parser.add_argument(
        "--check",
        type=Path,
        help="an existing spec; report whether every allele resolves to the same coordinates",
    )
    parser.add_argument(
        "--record-lineage",
        action="store_true",
        help="append this iteration's edges to warehouse.data_lineage (idempotent)",
    )
    parser.add_argument(
        "--register",
        type=Path,
        default=DEFAULT_REGISTER,
        help="the committed research register the epcr anchor is read from",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root, so the recorded paths are repository-relative",
    )
    return parser.parse_args()


def anchor_confidence(register_path: Path, hypothesis_id: str) -> float:
    """The register's suggested confidence for one claim — a triage heuristic, quoted as such."""
    record = from_register(json.loads(register_path.read_text(encoding="utf-8")))
    for dossier in record.dossiers:
        if dossier.hypothesis.hypothesis_id == hypothesis_id:
            return float(dossier.weighing.confidence)
    raise DerivationError(f"{hypothesis_id} is not in {register_path}")


def derived(raw: dict, register_path: Path) -> Derivation:
    """Facts from the warehouse, the anchor from the register, everything else arithmetic."""
    anchor = raw["derivation"].get("anchor", {})
    confidence = anchor_confidence(register_path, str(anchor.get("hypothesis", "")))
    selectors = {name: Selector.from_json(name, item) for name, item in raw["alleles"].items()}
    facts: dict[str, AlleleFacts] = {}
    with attached(Postgres.from_env(), read_only=True) as connection:
        for name, selector in selectors.items():
            facts[name] = fetch_facts(connection, name, selector)
    found = derive(raw, facts, confidence)
    print("\nderivation:")
    for line in found.lines:
        print(f"  {line}")
    return found


def derivation_markdown(found: Derivation) -> str:
    """The derivation as a report-ready table: labels, facts, scores, epcr — no coordinate."""
    lines = [
        "# How every non-coordinate field of the submission was derived",
        "",
        (
            f"**Anchor:** row `{found.anchor.get('row')}` tests {found.anchor.get('hypothesis')}; "
            f"the register's suggested confidence is {found.anchor.get('confidence')} "
            "(a transparent triage heuristic, not a calibrated posterior). Written by "
            "`tools/resolve_submission_spec.py`; source `derivation.json` beside this file."
        ),
        "",
        "## Alleles — what the result table says",
        "",
        "| allele | table | gene | consequence | call | gnomAD | ClinVar | score |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, f in found.facts.items():
        call = " ".join(p for p in (f.zygosity, f.filter) if p)
        call += f" DP {f.dp}" if f.dp is not None else ""
        lines.append(
            f"| {name} | `{f.table}` | {f.gene or '—'} | {f.most_severe or '—'} | {call or '—'} "
            f"| {'absent' if f.gnomad_af is None else f'{f.gnomad_af:.3g}'} "
            f"| {f.clin_sig or 'not listed'} | {f.score:.3f} |"
        )
    lines += [
        "",
        "## Rows — the epcr ladder",
        "",
        "| rank | row | type | pair score | epcr | hypothesis |",
        "|---|---|---|---|---|---|",
    ]
    for rank, row in enumerate(found.rows, 1):
        lines.append(
            f"| {rank} | {row.label} | {row.finding_type} | {row.score:.3f} | {row.epcr} "
            f"| {row.hypothesis or '—'} |"
        )
    lines += ["", "## Hypothesis priors", "", "| hypothesis | prior | source |", "|---|---|---|"]
    lines += [
        f"| {h['label']} | {h['prior']} | {h.get('prior_source', 'declared')} |"
        for h in found.hypotheses
    ]
    lines += ["", "## Arithmetic", "", "```", *found.lines, "```", ""]
    return "\n".join(lines)


def write_derivation(found: Derivation, folder: Path) -> None:
    (folder / "derivation.json").write_text(
        json.dumps(found.to_json(), indent=2) + "\n", encoding="utf-8"
    )
    (folder / "derivation.md").write_text(derivation_markdown(found), encoding="utf-8")
    print(f"wrote {folder / 'derivation.json'} and derivation.md (labels only, no coordinates)")


def main() -> int:
    args = parse_args()
    raw = json.loads(args.selectors.read_text(encoding="utf-8"))
    try:
        alleles = resolve_all(Postgres.from_env(), raw["alleles"])
    except SelectorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for name, allele in alleles.items():
        print(f"  {name:<14} chr{allele.chrom}  {allele.ref}>{allele.alt}  (position withheld)")

    spec = {
        "_source": str(args.selectors),
        "alleles": {name: allele.to_json() for name, allele in alleles.items()},
        "rows": raw["rows"],
        "hypotheses": raw["hypotheses"],
    }
    if "derivation" in raw:
        try:
            found = derived(raw, args.register)
        except (DerivationError, SelectorError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        spec["rows"] = [row.to_spec() for row in found.rows]
        spec["hypotheses"] = [
            {k: v for k, v in h.items() if k != "prior_source"} for h in found.hypotheses
        ]
        spec["_derivation"] = str(args.selectors.parent / "derivation.json")
        write_derivation(found, args.selectors.parent)
    if args.check and args.check.is_file():
        existing = json.loads(args.check.read_text(encoding="utf-8"))["alleles"]
        same = {name: existing.get(name) == allele.to_json() for name, allele in alleles.items()}
        missing = sorted(set(existing) - set(alleles))
        verdict = "identical" if all(same.values()) and not missing else "DIFFERENT"
        print(f"check against {args.check}: {verdict}")
        for name, ok in same.items():
            if not ok:
                print(f"  {name}: differs from the existing spec")
        for name in missing:
            print(f"  {name}: in the existing spec, not among the selectors")
        if verdict != "identical":
            return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}  ({len(alleles)} alleles, {len(raw['rows'])} rows)")
    if args.record_lineage:
        recorded = record_iteration(
            Postgres.from_env(), args.selectors.parent.resolve(), args.root.resolve()
        )
        print(recorded.describe())
    return 0


if __name__ == "__main__":
    sys.exit(main())
