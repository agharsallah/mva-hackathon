#!/usr/bin/env python3
"""Iteration 5, route R4: which candidate for which allele state, and what a test is worth.

Reads any number of route candidate tables (the pinned iteration-5 schema), a per-child
safety table and the decision config; writes ``decision_*.tsv`` + one provenance manifest
each and ``decision_summary.json`` (read by ``tools/render_it5_r4.py``). The engine lives in
``src/mva/drugs/decision_*.py``; this script only wires files to it.

    # the final run, once R1-R3 have written their tables
    uv run python tools/it5_decision.py run \\
        --candidates ressources/track2/it5/*_candidates.tsv \\
        --safety ressources/track2/it4/candidate_safety.tsv \\
        --out ressources/track2/it5

    # the dry run: iteration-4 candidates re-scored under a stated dry-run rubric, plus a
    # synthetic fixture exercising every branch; outputs stay under build/
    uv run python tools/it5_decision.py dryrun

``--set PARAM=VALUE`` overrides one config parameter for a what-if (addresses in
``mva.drugs.decision_config``); an overridden run says so in its manifests.
Every output is a triage heuristic, not a calibrated posterior (see the manifests' wording).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mva.drugs import decision_config, provenance
from mva.drugs.decision_io import COLUMNS, read_candidates, read_safety, read_tsv
from mva.drugs.decision_run import analyse, write
from mva.drugs.tables import write_tsv

CONFIG = Path("ressources/track2/it5/decision_config.json")
SAFETY = Path("ressources/track2/it4/candidate_safety.tsv")
IT4_CANDIDATES = Path("ressources/track2/it4/candidates.tsv")
DRYRUN = Path("build/it5/r4/dryrun")
ENTRY = "docs/iteration5/step-1/work/r4-entry.md (draft; number assigned at merge)"

#: Dry-run only: how an iteration-4 generator's listing becomes an evidence row. These are
#: R4's stated weights for exercising the pipeline, not a finding about any drug.
IT4_RUBRIC = {
    "twin": (0.4, "passed", "published rescue in the phenotype twin, approved analogue (e150)"),
    "prism": (0.2, "passed", "PRISM top 0.5 %, no drug past correction (e154); control passed"),
    "lincs": (0.2, "failed", "LINCS reversal; registered positive control failed (e153)"),
    "walk": (0.1, "unknown", "PrimeKG walk proximity, no mechanism argument (e142)"),
}

#: Synthetic rows (SYNTH- names) so every branch and control state is exercised.
FIXTURE = [
    ("SYNTH-READTHROUGH-1", "fixture-r1", "stop_allele", 0.6, "true"),
    ("SYNTH-STABILISER-1", "fixture-r2", "missense_unstable", 0.7, "true"),
    ("SYNTH-STABILISER-1 hydrochloride", "fixture-r3", "missense_unstable", 0.4, "true"),
    ("SYNTH-BYPASS-1", "fixture-r3", "missense_inactive", 0.5, "unknown"),
    ("SYNTH-FAILED-1", "fixture-r2", "any", 0.9, "false"),
    ("SYNTH-GENERAL-1", "fixture-r3", "any", 0.25, "true"),
]


def _meta(args: argparse.Namespace, raw: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    files = [*args.candidates, args.config] + ([args.safety] if args.safety else [])
    return {
        "entry": ENTRY,
        "tool": "tools/it5_decision.py " + args.command,
        "inputs": [
            {"file": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]} for p in files
        ],
        "parameters": {"config": raw, "overrides": overrides, "steps": args.steps},
        "assumptions": (
            "state variables are independent; a row's mechanism branch acts only in the states "
            "its applicability rule names; utilities are products of stated weights; a drug "
            "absent from the safety table is 'unassessed', never 'safe'"
        ),
        "limitations": (
            "every weight is a choice or a placeholder (the config's todo markers list which); "
            "no harm term beyond the safety factor; EVSI assumes the test's sensitivity and "
            "specificity are known; utility units are not money, QALYs or probabilities"
        ),
        "validation": (
            "positive control: the hand-worked four-drug case in "
            "tests/test_drugs_decision.py is reproduced exactly (EU, EVPI 0.18, EVSI 0.096, "
            "flip at P(unstable) = 0.36)"
        ),
        "sources": {
            "clinical": (
                "the proband's 7 own HPO terms enter only through the per-child safety table "
                "(iteration 4, entries 152/155: OnSIDES label effects matched to the terms)"
            ),
            "genomic": (
                "the two BUB1B alleles enter as state variables (stop_gained -> "
                "readthrough_feasible; missense -> missense_class) and, through the safety "
                "table, as PharmCAT actionability words; no position is read or written"
            ),
        },
        "todos": decision_config.todos(raw),
        "dry_run": args.command == "dryrun",
    }


def _lineage(path: Path, meta: dict[str, Any], tables: list[Path]) -> None:
    """One edge per (output table, input file), in ``warehouse.data_lineage``'s columns."""
    edges = [
        {
            "target_schema": provenance.repo_relative(table.parent),
            "target_table": table.stem,
            "target_rows": sum(1 for _ in table.open(encoding="utf-8")) - 1,
            "source_kind": "file",
            "source_ref": source["file"],
            "source_version": "",
            "source_sha256": source["sha256"],
            "transform": (
                "validate pinned schema -> dedup (names.base_name) -> utility table -> "
                "EU / EVPI / EVPPI / EVSI -> exact flip points, sweep, tornado"
            ),
            "tool": meta["tool"],
            "notes": "dry run" if meta["dry_run"] else meta["entry"],
        }
        for table in tables
        for source in meta["inputs"]
    ]
    doc = {
        "name": "it5-r4-lineage",
        "format": "one edge per object, warehouse.data_lineage columns; not loaded by R4",
        "sources": meta["sources"],
        "validation": meta["validation"],
        "todos": meta["todos"],
        "edges": edges,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _run(args: argparse.Namespace) -> int:
    config, raw = decision_config.load(args.config)
    overrides = list(args.set or [])
    for item in overrides:
        param, _, value = item.rpartition("=")
        config = decision_config.with_param(config, param, float(value))
    rows = read_candidates(args.candidates)
    safety = read_safety(args.safety)
    report = analyse(
        config, rows, safety, tornado_metric=raw.get("tornado_metric"), steps=args.steps
    )
    meta = _meta(args, raw, overrides)
    written = write(report, args.out, meta)
    for path in written:
        print(f"wrote {provenance.repo_relative(path)}")
    if args.lineage:
        _lineage(args.lineage, meta, [p for p in written if p.suffix == ".tsv"])
        print(f"wrote {provenance.repo_relative(args.lineage)}")
    best = report["best"]
    print(
        f"\nrows {report['n_rows']}, drugs {report['n_drugs']}, excluded {len(report['excluded'])}"
    )
    print(f"best overall: {best['action']} (EU {best['expected_utility']:.4f}; heuristic)")
    for state in report["states"]:
        print(f"  {state['state']:<55} p={state['prior']:.3f}  best {state['best']}")
    for voi in report["voi"]:
        print(f"  {voi['kind']:<6} {voi['target']:<28} {voi['value']:.4f}")
    for todo in decision_config.todos(raw):
        print(f"  TODO {todo[:110]}")
    return 0


def _adapt_it4(source: Path, out: Path) -> Path:
    rows = []
    for rec in read_tsv(source):
        branch = "missense_unstable" if "D3" in rec["direction_hints"].split("|") else "any"
        for gen in rec["generators"].split("|"):
            strength, control, why = IT4_RUBRIC[gen]
            rows.append(
                {
                    "drug_name": rec["query_name"] or rec["drug"],
                    "route": f"it4-{gen}",
                    "branch": branch,
                    "evidence_kind": f"it4 generator {gen}",
                    "evidence_strength": strength,
                    "positive_control_passed": control,
                    "source": f"{provenance.repo_relative(source)} (entry 155)",
                    "notes": f"dry-run rubric: {why}",
                }
            )
    write_tsv(out, COLUMNS, rows)
    return out


def _dryrun(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    fixture = args.out / "fixture_candidates.tsv"
    write_tsv(
        fixture,
        COLUMNS,
        (
            {
                "drug_name": n,
                "route": r,
                "branch": b,
                "evidence_kind": "synthetic",
                "evidence_strength": s,
                "positive_control_passed": c,
                "source": "synthetic",
                "notes": "synthetic fixture row; never a finding",
            }
            for n, r, b, s, c in FIXTURE
        ),
    )
    adapted = _adapt_it4(IT4_CANDIDATES, args.out / "it4_adapted_candidates.tsv")
    args.candidates = [adapted, fixture]
    return _run(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "dryrun"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", type=Path, default=CONFIG)
        cmd.add_argument("--safety", type=Path, default=SAFETY)
        cmd.add_argument("--out", type=Path, default=DRYRUN if name == "dryrun" else None)
        cmd.add_argument("--set", action="append", metavar="PARAM=VALUE")
        cmd.add_argument("--steps", type=int, default=101, help="grid points per prior sweep")
        cmd.add_argument("--lineage", type=Path, help="also write the lineage edges here")
        if name == "run":
            cmd.add_argument("--candidates", type=Path, nargs="+", required=True)
    args = parser.parse_args(argv)
    if args.out is None:
        parser.error("--out is required for run")
    return _dryrun(args) if args.command == "dryrun" else _run(args)


if __name__ == "__main__":
    sys.exit(main())
