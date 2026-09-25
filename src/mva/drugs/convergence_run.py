"""Run step 10's S2 end to end: join the generators, test convergence, run K1-K3, write tables.

The pure pieces are :mod:`mva.drugs.convergence` (join, null), :mod:`mva.drugs.checks` (K1,
K3), :mod:`mva.drugs.checks_safety` (K2 command lines and reader) and
:mod:`mva.drugs.convergence_candidates` (the table). This module wires them to files, runs
``tools/patient_safety.py`` for K2 as a subprocess (so the safety method is entry 152's own
code, not a copy), and writes one provenance manifest per table.

Everything case-specific is in :class:`RunPlan`: the generator ids and directory, the drug
excluded for the retrospective check, the annotation files, the screen table, the safety
inputs. Nothing below names a drug, a gene or a generator.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from . import convergence, provenance
from .checks import Check, K1Rule, K3Rule, k1, k3
from .checks_safety import SafetyPlan, faers_pairs, k2_from_table, mapped_terms
from .checks_sources import SweepColumns, annotation_for, load_moa_index, load_sweep
from .convergence_candidates import CandidateChecks, candidate_rows, query_names, write_candidates
from .convergence_tables import GeneratorList, read_generator, read_universe

__all__ = ["RunPlan", "SafetyInputs", "Scenario", "execute"]


@dataclass(frozen=True)
class SafetyInputs:
    """What K2 needs. ``pgx_from`` holds entry 152's ``pgx_summary.json`` (reused as is)."""

    tool: Path
    pgx_from: Path
    onsides: Path
    mapping: Path
    aliases: tuple[str, ...] = ()
    extra_genes: tuple[str, ...] = ()
    faers_scope: str = "converging"  # converging | all | none
    sources: str = ""


@dataclass(frozen=True)
class Scenario:
    """One sensitivity test: a generator subset, drugs excluded, universes swapped.

    ``universes`` maps a generator id to a universe file that replaces its own for this
    scenario only (e.g. a universe rule re-applied to the smaller generator set).
    ``role`` is written beside the result so a sensitivity is never read as the verdict.
    """

    label: str
    role: str
    generators: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    universes: tuple[tuple[str, Path], ...] = ()


@dataclass(frozen=True)
class RunPlan:
    generators_dir: Path
    generators: tuple[str, ...]
    out: Path
    safety_out: Path
    work: Path
    entry: str
    k: int = 2
    draws: int = 10_000
    seed: int = 20260925
    exclude: tuple[str, ...] = ()
    moa_annotations: tuple[Path, ...] = ()
    k1_rule: K1Rule = field(default_factory=K1Rule)
    sweep: Path | None = None
    sweep_columns: SweepColumns = field(default_factory=SweepColumns)
    k3_rule: K3Rule = field(default_factory=K3Rule)
    safety: SafetyInputs | None = None
    scenarios: tuple[Scenario, ...] = ()


def _scenario_lists(
    plan: RunPlan, lists: Sequence[GeneratorList], scenario: Scenario
) -> list[GeneratorList]:
    by_id = {item.generator: item for item in lists}
    swap = dict(scenario.universes)
    out: list[GeneratorList] = []
    for gen in scenario.generators:
        item = by_id[gen]
        if gen in swap:
            item = replace(item, universe=frozenset(read_universe(swap[gen]) | item.drugs))
        out.append(item)
    return out


def _tests(plan: RunPlan, lists: Sequence[GeneratorList]) -> list[dict[str, Any]]:
    """The primary test, the registered exclusion, then every declared scenario."""
    scenarios = [
        Scenario("primary: all generators", "primary (verdict input)", plan.generators),
        Scenario(
            "without " + ", ".join(plan.exclude),
            "registered sensitivity (H094 retrospective note)",
            plan.generators,
            plan.exclude,
        ),
        *plan.scenarios,
    ]
    out: list[dict[str, Any]] = []
    for scenario in scenarios:
        chosen = _scenario_lists(plan, lists, scenario)
        result, _ = convergence.run(
            chosen,
            label=scenario.label,
            k=plan.k,
            draws=plan.draws,
            seed=plan.seed,
            exclude=scenario.exclude,
        )
        out.append(
            {
                **result.as_dict(),
                "role": scenario.role,
                "generators": list(scenario.generators),
                "universe_swaps": {g: provenance.repo_relative(p) for g, p in scenario.universes},
            }
        )
    return out


def _vocabulary(plan: RunPlan) -> set[str]:
    """OnSIDES's RxNorm ingredient names, when the safety inputs point at an OnSIDES copy."""
    if plan.safety is None:
        return set()
    path = plan.safety.onsides / "vocab_rxnorm_ingredient.csv"
    if not path.is_file():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        return {r["rxnorm_name"].strip().lower() for r in csv.DictReader(handle)}


def _k1_checks(plan: RunPlan, drugs: dict[str, str]) -> dict[str, Check]:
    index = load_moa_index(list(plan.moa_annotations))
    out: dict[str, Check] = {}
    for drug, label in drugs.items():
        note = annotation_for(index, drug, label)
        out[drug] = k1(note.moa if note else None, note.targets if note else (), plan.k1_rule)
    return out


def _directions(lists: Sequence[GeneratorList]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for item in lists:
        for drug, row in item.best().items():
            out.setdefault(drug, set()).update(row.direction_hint.split("|"))
    return out


def _k3_checks(plan: RunPlan, lists: Sequence[GeneratorList]) -> dict[str, Check] | None:
    if plan.sweep is None or not plan.sweep.is_file():
        return None
    sweep = load_sweep(plan.sweep, plan.sweep_columns)
    return {d: k3(sorted(h), sweep.get(d, []), plan.k3_rule) for d, h in _directions(lists).items()}


def _run_tool(tool: Path, argv: list[str], log: list[dict[str, Any]]) -> None:
    command = [sys.executable, str(tool), *argv]
    done = subprocess.run(command, check=True, capture_output=True, text=True)
    log.append({"argv": [str(tool), *argv], "stdout_tail": done.stdout.strip().splitlines()[-3:]})


def _k2_checks(
    plan: RunPlan, names: dict[str, str], converging: set[str], log: list[dict[str, Any]]
) -> dict[str, Check] | None:
    safety = plan.safety
    if safety is None:
        return None
    work = plan.work / "safety"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(safety.pgx_from / "pgx_summary.json", work / "pgx_summary.json")
    table = work / "safety_drugs.tsv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["drug_name", "direction_id", "drug"])
        for drug in sorted(names):
            writer.writerow([names[drug], "converging" if drug in converging else "single", drug])
    with safety.mapping.open(encoding="utf-8", newline="") as handle:
        terms = mapped_terms(list(csv.DictReader(handle, delimiter="\t")))
    scope = {"converging": sorted(converging), "all": sorted(names), "none": []}[safety.faers_scope]
    steps = SafetyPlan(
        work=work,
        drug_table=f"{table}:drug_name:direction_id",
        onsides=safety.onsides,
        mapping=safety.mapping,
        out=plan.safety_out,
        entry=plan.entry,
        sources=safety.sources,
        faers=tuple(faers_pairs((names[d] for d in scope), terms)),
        aliases=safety.aliases,
        extra_genes=safety.extra_genes,
    )
    _run_tool(safety.tool, steps.labels(), log)
    if steps.faers:
        _run_tool(safety.tool, steps.faers_argv(), log)
    _run_tool(safety.tool, steps.table(), log)
    by_query = k2_from_table(plan.safety_out)
    return {d: by_query[q] for d, q in names.items() if q in by_query}


def execute(plan: RunPlan) -> dict[str, Any]:
    """Run S2; returns the convergence summary it also writes to ``work/convergence.json``."""
    plan.work.mkdir(parents=True, exist_ok=True)
    lists = [read_generator(plan.generators_dir, g) for g in plan.generators]
    tests = _tests(plan, lists)
    names = query_names(lists, _vocabulary(plan))
    converging = set(tests[0]["drugs"])
    log: list[dict[str, Any]] = []
    k1s = _k1_checks(plan, names)
    k3s = _k3_checks(plan, lists)
    k2s = _k2_checks(plan, names, converging, log)
    checks = {
        d: CandidateChecks(k1=k1s.get(d), k2=(k2s or {}).get(d), k3=(k3s or {}).get(d))
        for d in names
    }
    rows = candidate_rows(lists, checks, k=plan.k, names=names)
    written = write_candidates(rows, plan.generators, plan.out)
    summary = {
        "generators": {
            item.generator: {
                "listed_approved": len(item.drugs),
                "universe_approved": len(item.universe),
                "listed_outside_universe": list(item.outside_universe),
            }
            for item in lists
        },
        "tests": tests,
        "seed": plan.seed,
        "pairwise_shared": dict(convergence.pairwise(lists)),
        "survivors": [r["drug"] for r in rows if r["survivor"] == "true"],
        "checks_run": {"k1": True, "k2": k2s is not None, "k3": k3s is not None},
    }
    (plan.work / "convergence.json").write_text(json.dumps(summary, indent=2) + "\n")
    _manifest(plan, lists, summary, written, log)
    return summary


def _manifest(
    plan: RunPlan,
    lists: Sequence[GeneratorList],
    summary: dict[str, Any],
    written: int,
    log: list[dict[str, Any]],
) -> None:
    manifest = provenance.envelope(plan.out.stem, built_by="tools/converge.py run")
    manifest["entry"] = plan.entry
    manifest["method"] = (
        "Join every generator's approved list on mva.drugs.names.base_name; the statistic is "
        f"the number of drugs named by >= {plan.k} generators; the null replaces each list by "
        f"an equal-sized draw without replacement from its own approved universe, {plan.draws} "
        f"draws, numpy default_rng seed {plan.seed}; one-sided p = (1 + #null >= observed) / "
        f"(1 + draws); repeated with {list(plan.exclude)} removed from every list and universe. "
        "K1 from the Drug Repurposing Hub MOA, K2 by re-running entry 152's "
        "tools/patient_safety.py (labels, faers, table) with its PharmCAT result reused, K3 "
        "from the screen-wide sweep. A survivor converges and fails no check."
    )
    manifest["parameters"] = {
        "k": plan.k,
        "draws": plan.draws,
        "seed": plan.seed,
        "exclude": list(plan.exclude),
        "generators": list(plan.generators),
        "k1_rule": plan.k1_rule.as_manifest(),
        "k3_rule": plan.k3_rule.as_manifest(),
        "k3_sweep_columns": plan.sweep_columns.__dict__,
        "k2_faers_scope": plan.safety.faers_scope if plan.safety else None,
        "k2_faers_rule": "every drug in scope x every MedDRA PT with used_for_flag = yes",
    }
    inputs: list[dict[str, Any]] = []
    for item in lists:
        for suffix in (".tsv", ".universe.tsv", ".provenance.json"):
            path = plan.generators_dir / f"{item.generator}{suffix}"
            if path.is_file():
                sha, size = provenance.digest(path)
                inputs.append(
                    {"path": provenance.repo_relative(path), "sha256": sha, "bytes": size}
                )
    extra = [*plan.moa_annotations, *([plan.sweep] if plan.sweep and plan.sweep.is_file() else [])]
    if plan.safety:
        extra += [plan.safety.pgx_from / "pgx_summary.json", plan.safety.mapping]
    for path in extra:
        sha, size = provenance.digest(path)
        inputs.append({"path": provenance.repo_relative(path), "sha256": sha, "bytes": size})
    manifest["inputs"] = inputs
    manifest["safety_commands"] = log
    manifest["summary"] = summary
    manifest["outputs"] = [provenance.output(plan.out, written)]
    manifest["sources"] = {
        "genomic": "BUB1B mechanism (walk, screen, signatures) and, in K2, PharmCAT phenotypes "
        "of the child's callset (actionability words only, reused from entry 152)",
        "clinical": "the 8 HPO terms through the phenotype twin (G2) and K2's label matching",
    }
    manifest["limitations"] = (
        "each generator's approval proxy differs (openFDA label, PRISM Launched, ChEMBL phase "
        "4); a caution never removes a drug; an unflagged K2 row means two sources are silent"
    )
    provenance.write(manifest, plan.out.with_name(plan.out.stem + ".provenance.json"))
