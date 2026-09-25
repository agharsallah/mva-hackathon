#!/usr/bin/env python3
"""Step 10, S2: do iteration 4's independent drug generators converge, and what survives?

    uv run python tools/converge.py walk      # G1: the PrimeKG walk, every reached drug labelled
    uv run python tools/converge.py twin      # G2: the phenotype twin's approved analogues
    uv run python tools/converge.py run       # join, permutation null, K1-K3, candidate table

``walk`` and ``twin`` write the table contract of ``docs/iteration4/step-10/README.md``
(``<id>.tsv``, ``<id>.universe.tsv``, ``<id>.provenance.json``) into ``--out-dir``. ``twin``
takes the other generators' universes (``--other-universe``, repeatable) because its own
universe is, by the step's rule, the widest available.

``run`` reads any set of generators by id (``--generator``, repeatable; the order is the
priority for the safety query name), counts the drugs named by at least ``--k`` of them,
draws the null, and runs the checks: K1 from the Repurposing Hub MOA annotation files, K2 by
re-running ``tools/patient_safety.py`` with the PharmCAT result of ``--pgx-from`` reused, K3
from ``--sweep`` when that file exists. ``--dry-run-dir`` redirects every output into one
build directory, for proving the pipeline before the real inputs exist.

Everything written is coordinate-free: drug names, gene symbols, counts, p values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# The path shim above must run before these imports.
from mva.drugs import primekg
from mva.drugs.cache import Fetcher
from mva.drugs.checks import K3Rule
from mva.drugs.checks_sources import SweepColumns
from mva.drugs.convergence_build import build_twin, build_walk
from mva.drugs.convergence_run import RunPlan, SafetyInputs, Scenario, execute
from mva.drugs.mechanism import DEFAULT_CARD, load
from mva.drugs.sources import openfda

IT4 = Path("ressources/track2/it4")
GENERATORS = IT4 / "generators"
ENTRY = "docs/iteration4/step-10/methodology/155-convergence-and-checks.md"
E4_RAW = Path("build/it4/track2-e4/raw")
HUB = (
    E4_RAW / "PRISM_24Q2_Extended_Primary_Compound_List.csv",
    E4_RAW / "PRISM_20Q2_secondary_treatment_info.csv",
)
E56 = Path("build/it4/track2-e56")
#: Entry 152's declared name aliases and literature gene pairs, re-used unchanged.
ALIASES = (
    "valproic acid=valproate",
    "nicotinamide=niacinamide",
    "cabozantinib s-malate=cabozantinib",
    "mecasermin rinfabate=mecasermin",
)
EXTRA_GENES = ("vincristine=CYP3A5,CEP72", "valproic acid=POLG")
SAFETY_SOURCES = (
    "PharmCAT 3.4.0 (CPIC/DPWG/FDA data 2026-07-13, reused from entry 152); OnSIDES v3.1.1 "
    "(CC BY 4.0); openFDA FAERS; ressources/track2/hpo_to_adverse_terms.tsv"
)


def do_walk(args: argparse.Namespace) -> int:
    card = load(args.card)
    mondo = str(card.raw.get("case", {}).get("mondo", ""))
    fetcher = Fetcher(source="openfda")
    manifest = build_walk(
        graph_path=args.graph,
        mondo=mondo,
        label=lambda name: openfda.label(fetcher, name),
        fetcher=fetcher,
        top=args.top,
        out_dir=args.out_dir,
        reference=args.reference,
        entry=args.entry,
    )
    fetcher.close()
    print(
        json.dumps(
            {"counts": manifest["counts"], "reproduces": manifest["reproduces_entry_142"]}, indent=2
        )
    )
    return 0


def do_twin(args: argparse.Namespace) -> int:
    manifest = build_twin(
        interventions=args.interventions,
        others=args.other_universe,
        out_dir=args.out_dir,
        entry=args.entry,
    )
    print(
        json.dumps(
            {"counts": manifest["counts"], "skipped": len(manifest["rows_not_voting"])}, indent=2
        )
    )
    return 0


def _contrasts(pairs: list[str]) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for pair in pairs:
        direction, _, contrast = pair.partition("=")
        out.setdefault(direction.strip(), []).append(contrast.strip())
    return {k: tuple(v) for k, v in out.items()}


def _scenario(text: str) -> Scenario:
    """``label;gens=a,b;exclude=X,Y;swap=gen:path,gen:path`` -> a sensitivity :class:`Scenario`."""
    label, *parts = text.split(";")
    fields = dict(p.split("=", 1) for p in parts)
    swaps = [s.split(":", 1) for s in fields.get("swap", "").split(",") if s]
    return Scenario(
        label=label.strip(),
        role=fields.get("role", "sensitivity (not a verdict input)"),
        generators=tuple(g for g in fields["gens"].split(",") if g),
        exclude=tuple(x for x in fields.get("exclude", "").split(",") if x),
        universes=tuple((g, Path(path)) for g, path in swaps),
    )


def do_run(args: argparse.Namespace) -> int:
    dry = args.dry_run_dir
    out = dry / "candidates.tsv" if dry else args.out
    safety_out = dry / "candidate_safety.tsv" if dry else args.safety_out
    work = dry or args.work
    safety = None
    if not args.skip_safety:
        safety = SafetyInputs(
            tool=Path("tools/patient_safety.py"),
            pgx_from=args.pgx_from,
            onsides=args.onsides,
            mapping=args.mapping,
            aliases=ALIASES,
            extra_genes=EXTRA_GENES,
            faers_scope=args.faers_scope,
            sources=SAFETY_SOURCES,
        )
    plan = RunPlan(
        generators_dir=args.generators_dir,
        generators=tuple(args.generator),
        out=out,
        safety_out=safety_out,
        work=work,
        entry=args.entry,
        k=args.k,
        draws=args.draws,
        seed=args.seed,
        exclude=tuple(args.exclude),
        moa_annotations=tuple(p for p in (args.moa_annotation or HUB) if p.is_file()),
        sweep=args.sweep,
        sweep_columns=SweepColumns(
            drug=args.sweep_drug,
            contrast=args.sweep_contrast,
            delta=args.sweep_delta,
            p=args.sweep_p,
            p_opposite=args.sweep_p_opposite,
            only_column=args.sweep_only,
        ),
        k3_rule=K3Rule(direction_contrasts=_contrasts(args.contrast), alpha=0.05),
        safety=safety,
        scenarios=tuple(_scenario(text) for text in args.scenario),
    )
    summary = execute(plan)
    for test in summary["tests"]:
        print(
            f"  {test['label'][:34]:<34} observed {test['observed']}"
            f"  null p95 {test['null_p95']:.1f}"
            f"  mean {test['null_mean']:.2f}  p {test['p_value']:.4g}  drugs {test['drugs']}"
        )
    print(f"  survivors: {summary['survivors']}  checks run: {summary['checks_run']}")
    print(f"  -> {out}, {work / 'convergence.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    walk = sub.add_parser("walk", help="G1: the PrimeKG walk as a generator table")
    walk.add_argument("--card", type=Path, default=DEFAULT_CARD)
    walk.add_argument("--graph", type=Path, default=primekg.DEFAULT_PARQUET)
    walk.add_argument("--top", type=int, default=50)
    walk.add_argument("--out-dir", type=Path, default=GENERATORS)
    walk.add_argument("--reference", type=Path, default=Path("ressources/track2/ranking-walk.tsv"))
    walk.add_argument("--entry", default=ENTRY)
    twin = sub.add_parser("twin", help="G2: the phenotype twin's approved analogues")
    twin.add_argument(
        "--interventions", type=Path, default=Path("ressources/track2/model_interventions.tsv")
    )
    twin.add_argument("--other-universe", type=Path, action="append", default=[])
    twin.add_argument("--out-dir", type=Path, default=GENERATORS)
    twin.add_argument("--entry", default=ENTRY)
    run = sub.add_parser("run", help="join, null, checks, candidate table")
    run.add_argument("--generators-dir", type=Path, default=GENERATORS)
    run.add_argument(
        "--generator", action="append", required=True, help="generator id, in priority order"
    )
    run.add_argument("--out", type=Path, default=IT4 / "candidates.tsv")
    run.add_argument("--safety-out", type=Path, default=IT4 / "candidate_safety.tsv")
    run.add_argument("--work", type=Path, default=Path("build/it4/track2-s2"))
    run.add_argument("--dry-run-dir", type=Path, help="write every output here instead")
    run.add_argument("--entry", default=ENTRY)
    run.add_argument("--k", type=int, default=2)
    run.add_argument("--draws", type=int, default=10_000)
    run.add_argument("--seed", type=int, default=20260925)
    run.add_argument(
        "--exclude", action="append", default=[], help="join key removed in the second test"
    )
    run.add_argument(
        "--moa-annotation", type=Path, action="append", default=[], help="default: HUB"
    )
    run.add_argument("--sweep", type=Path, default=IT4 / "prism_sweep.tsv")
    run.add_argument("--sweep-drug", default="drug")
    run.add_argument("--sweep-contrast", default="contrast")
    run.add_argument("--sweep-delta", default="cliffs_delta")
    run.add_argument("--sweep-p", default="p_raw")
    run.add_argument("--sweep-p-opposite", default=None)
    run.add_argument("--sweep-only", default=None, help="keep sweep rows where this column is true")
    run.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="sensitivity: 'label;gens=a,b;exclude=X;swap=gen:universe.tsv'",
    )
    run.add_argument("--contrast", action="append", default=[], help="DIRECTION=contrast (K3)")
    run.add_argument("--skip-safety", action="store_true")
    run.add_argument("--pgx-from", type=Path, default=E56)
    run.add_argument("--onsides", type=Path, default=E56 / "onsides/csv")
    run.add_argument(
        "--mapping", type=Path, default=Path("ressources/track2/hpo_to_adverse_terms.tsv")
    )
    run.add_argument("--faers-scope", choices=["converging", "all", "none"], default="converging")
    args = parser.parse_args(argv)
    verbs = {"walk": do_walk, "twin": do_twin, "run": do_run}
    return verbs[args.verb](args)


if __name__ == "__main__":
    raise SystemExit(main())
