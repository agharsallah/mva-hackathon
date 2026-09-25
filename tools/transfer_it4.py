#!/usr/bin/env python3
"""Step 11, T1 — iteration 4's Track 2 chain on a second case, from one case file (entry 156).

**This file is the code change entry 156 records.** H096 (P4-31) predicted the chain would
run on Bloom syndrome by configuration alone. Four stages cannot be told about a new case
through flags or data files (entry 156, "Static survey", gaps 1, 5, 6, 8), so this file does
what those flags would do, and nothing else. No existing line of the chain is edited; every
plan below is built from the committed dataclasses and the committed tools' own constants.

    uv run python tools/transfer_it4.py twin      # gap 1: the twin, written to the case dir
    uv run python tools/transfer_it4.py sweep     # gap 5: SweepPlan from the case file
    uv run python tools/transfer_it4.py lincs fetch|run   # gap 6: ReversalPlan from the case
    uv run python tools/transfer_it4.py converge  # gap 8: RunPlan with the case's K1 rule
    uv run python tools/transfer_it4.py scan      # list MVA-case words in the case outputs
    uv run python tools/transfer_it4.py relabel   # apply relabel.json, re-hash the manifests

The walk (G1) and the twin generator (G2) need no code and run from ``tools/converge.py``.

``relabel`` exists because several stages write text that names the MVA case (BUB1B, the
child) into their manifests or rows whatever case they run on (gaps 2-4, 7, 9-11). The
substitutions are data (``relabel.json`` beside the case file); each one applied is recorded
with its count in ``transfer.provenance.json`` and every manifest that digests a changed file
is re-hashed, so no output silently disagrees with its manifest.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

# The path shim above must run before these imports.
from mva.drugs import provenance  # noqa: E402 - needs the sys.path line
from mva.drugs.checks import K1Rule, K3Rule  # noqa: E402 - needs the sys.path line
from mva.drugs.checks_sources import SweepColumns  # noqa: E402 - needs the sys.path line
from mva.drugs.convergence_run import (  # noqa: E402 - needs the sys.path line
    RunPlan,
    SafetyInputs,
)
from mva.drugs.convergence_run import execute as converge  # noqa: E402 - needs sys.path
from mva.drugs.screen_sweep_plan import SweepPlan  # noqa: E402 - needs the sys.path line
from mva.drugs.screen_sweep_run import execute as sweep  # noqa: E402 - needs the sys.path line
from mva.drugs.signature_reversal_plan import (  # noqa: E402 - needs the sys.path line
    ReversalPlan,
    fetch_inputs,
)
from mva.drugs.signature_reversal_run import execute as reverse  # noqa: E402 - needs sys.path

ENTRY = "docs/iteration4/step-11/methodology/156-the-chain-on-bloom-syndrome.md"
CASE = Path("ressources/track2/transfer-it4/BLM/case.json")
BUILD = Path("build/it4/track2-t1")
#: Words that name the MVA case; ``scan`` lists every hit in the case's outputs.
MVA_WORDS = (
    "BUB1B",
    "Bub1b",
    "BubR1",
    "child",
    "proband",
    "rhabdomyosarcoma",
    "aneuploid",
    "checkpoint-kinase",
    "spindle poison",
    "furosemide",
    "Challenge_Clinical_Phenotype_1",
    "rapalogs",
    "Track 1 pair",
)


def _tool(name: str) -> ModuleType:
    """Import ``tools/<name>.py`` as a module, so its constants are reused, not copied."""
    spec = importlib.util.spec_from_file_location(f"tool_{name}", REPO / "tools" / f"{name}.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import tools/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(path: Path) -> tuple[dict[str, Any], Path]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload, path.parent


def do_twin(case: dict[str, Any], home: Path) -> int:
    """Gap 1: ``tools/phenotype_twin.py`` with its committed directory pointed at the case."""
    twin = _tool("phenotype_twin")
    twin.__dict__["COMMITTED"] = home / "phenotype"  # the tool's module constant
    cfg = case["chain"]["twin"]
    args = argparse.Namespace(
        raw=twin.RAW,
        out=BUILD / "twin",
        hpo=list(case["case"]["hpo_terms"]),
        gene=cfg["gene"],
        null=cfg["null"],
        seed=cfg["seed"],
        pathway=list(cfg["pathway"]),
        controls=list(cfg["controls"]),
    )
    result = twin.run_all(args)
    twin.write(result, args)
    for name, study in result["studies"].items():
        for metric, hit in study["best"].items():
            p = study["null"]["empirical_p"][metric]
            print(
                f"{name} {metric:9} best {hit['genotype_id']} rank {hit['rank']:,}"
                f"/{study['n_genotypes']:,} ({hit['percentile']:.2f} %)  p={p:.4f}"
            )
    for c in result["controls"]:
        print(f"control {c['disease']} -> {c['gene']}: median pct {c['median_percentile']}")
    print(f"runtime {result['runtime_s']} s")
    return 0


def do_sweep(case: dict[str, Any], home: Path, workers: int | None) -> int:
    """Gap 5: entry 154's sweep, the lineage and annotation read from the case file."""
    tool = _tool("screen_sweep")
    cfg = case["chain"]["sweep"]
    plan = SweepPlan(
        reused=tool.REUSED,
        reused_dir=tool.E4_RAW,
        reused_manifest=tool.E4_MANIFEST,
        own=tool.OWN,
        own_dir=Path("build/it4/track2-s1/raw"),
        build_dir=BUILD / "sweep",
        out=home / "prism_sweep.tsv",
        generator_dir=home / "generators",
        generator="prism",
        entry=ENTRY,
        in_group_codes=tuple(cfg["in_group_codes"]),
        annotation_column=cfg["annotation_column"],
        min_in_group=int(cfg["min_in_group"]),
        min_arm=int(cfg["min_arm"]),
        alpha=float(cfg["alpha"]),
        top_fraction=float(cfg["top_fraction"]),
        hints=dict(cfg["hints"]),
        control_exclude=(*tool.CONTROL_EXCLUDE, *cfg["control_exclude_extra"]),
        positive_control_drugs=tuple(cfg["positive_control_drugs"]),
        positive_control_lineage=cfg["positive_control_lineage"],
        report_drugs=tuple(cfg["report_drugs"]),
        seed=int(cfg["seed"]),
        resamples=int(cfg["resamples"]),
        workers=workers,
        patient_data=(
            "none. Public cell-line screens and public line annotations only. The clinical "
            "input enters at one remove: Bloom syndrome's registry cancers (leukemia, "
            "lymphoma; PMID 35420546) chose the lineage contrast, its LOH mechanism (PMID "
            f"11101838) the annotation. The lineage contrast is tagged 'rms' by the code; "
            f"here it holds {len(cfg['in_group_codes'])} haematological OncotreeCodes."
        ),
    )
    return sweep(plan)


def do_lincs(case: dict[str, Any], home: Path, command: str) -> int:
    """Gap 6: entry 153's reversal, the perturbed gene and control genes from the case."""
    tool = _tool("signature_reversal")
    cfg = case["chain"]["lincs"]
    gene = cfg["perturbation"]
    plan = ReversalPlan(
        perturbation=gene,
        consensus=tool.CONSENSUS,
        gene_info=tool.GENE_INFO,
        per_signature_database="l1000_xpr",
        gene_space="landmark",
        size=100,
        decoys=int(cfg["decoys"]),
        seed=int(cfg["seed"]),
        top_n=int(cfg["top_n"]),
        decoy_max_hits=1,
        sigcom_limit=10_000,
        drug_database="l1000_cp",
        control_databases=("l1000_xpr", "l1000_shRNA"),
        control_genes=tuple(cfg["control_genes"]),
        control_cut=0.05,
        raw_dir=BUILD / "lincs" / "raw",
        build_dir=BUILD / "lincs",
        out=home / "lincs_reversal.tsv",
        generator_dir=home / "generators",
        entry=ENTRY,
        claim=(
            "H096 (P4-31) clause (a), stage G4: a BLM loss-of-function signature queried for "
            "reversers by entry 153's method, unchanged"
        ),
        mechanism_note=(
            f"loss-of-function query: {case['case']['disease']} is biallelic {gene} loss of "
            "function (PMID 28232778)"
        ),
        patient_data=(
            "none. Public LINCS signatures, gene symbols and drug names only; the gene comes "
            "from the case file, no clinical term is read."
        ),
    )
    return fetch_inputs(plan) if command == "fetch" else reverse(plan)


def do_converge(case: dict[str, Any], home: Path) -> int:
    """Gap 8: entry 155's run with the case's K1 rule, K3 map and label-only K2."""
    tool = _tool("converge")
    cfg = case["chain"]["converge"]
    k1 = cfg["k1"]
    safety = SafetyInputs(
        tool=Path("tools/patient_safety.py"),
        pgx_from=Path(cfg["k2"]["pgx_from"]),
        onsides=Path("build/it4/track2-e56/onsides/csv"),
        mapping=Path(cfg["k2"]["mapping"]),
        aliases=tool.ALIASES,
        extra_genes=(),
        faers_scope="converging",
        sources=(
            "OnSIDES v3.1.1 (CC BY 4.0); openFDA FAERS; "
            f"{cfg['k2']['mapping']}; genome half not run (no patient genome)"
        ),
    )
    plan = RunPlan(
        generators_dir=home / "generators",
        generators=tuple(cfg["generators"]),
        out=home / "candidates.tsv",
        safety_out=home / "candidate_safety.tsv",
        work=BUILD / "converge",
        entry=ENTRY,
        k=int(cfg["k"]),
        draws=int(cfg["draws"]),
        seed=int(cfg["seed"]),
        moa_annotations=tuple(p for p in tool.HUB if p.is_file()),
        k1_rule=K1Rule(
            do_not_moa=tuple(k1["do_not_moa"]),
            caution_moa=tuple(k1["caution_moa"]),
            checkpoint_targets=tuple(k1["targets"]),
            source_entry=k1["source"],
        ),
        sweep=home / "prism_sweep.tsv",
        sweep_columns=SweepColumns(p_opposite="p_opposite", only_column="representative"),
        k3_rule=K3Rule(
            direction_contrasts={d: tuple(c) for d, c in cfg["k3_contrasts"].items()},
            alpha=0.05,
        ),
        safety=safety,
        # converge.py's own scenario parser, reused rather than copied.
        scenarios=tuple(tool._scenario(t) for t in cfg.get("scenarios", [])),  # noqa: SLF001 - reuse, not copy
    )
    summary = converge(plan)
    for test in summary["tests"]:
        print(
            f"  {test['label'][:34]:<34} observed {test['observed']}  null p95 "
            f"{test['null_p95']:.1f}  mean {test['null_mean']:.2f}  p {test['p_value']:.4g}"
            f"  drugs {test['drugs']}"
        )
    print(f"  survivors: {summary['survivors']}  checks run: {summary['checks_run']}")
    return 0


def _outputs(home: Path) -> list[Path]:
    """Every committed text output of the case (the case file and relabel.json excluded)."""
    skip = {"case.json", "relabel.json", "transfer.provenance.json"}
    return sorted(
        p
        for p in home.rglob("*")
        if p.is_file() and p.suffix in {".tsv", ".json"} and p.name not in skip
    )


def do_scan(home: Path) -> int:
    """List every MVA-case word in the case's outputs (the input to relabel.json)."""
    hits = 0
    for path in _outputs(home):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = [w for w in MVA_WORDS if w.lower() in line.lower()]
            if found:
                hits += 1
                print(f"{provenance.repo_relative(path)}:{number}: {found}  {line.strip()[:160]}")
    print(f"{hits} lines")
    return 0


def _rehash(node: Any, digests: dict[str, tuple[str, int]]) -> int:
    """Correct every ``{path, sha256[, bytes]}`` dict whose file's digest has changed."""
    changed = 0
    if isinstance(node, dict):
        path = node.get("path") or node.get("file")
        if isinstance(path, str) and path in digests and "sha256" in node:
            sha, size = digests[path]
            if node["sha256"] != sha or node.get("bytes", size) != size:
                node["sha256"] = sha
                if "bytes" in node:
                    node["bytes"] = size
                changed += 1
        for value in node.values():
            changed += _rehash(value, digests)
    elif isinstance(node, list):
        for value in node:
            changed += _rehash(value, digests)
    return changed


def do_relabel(home: Path) -> int:
    """Apply ``relabel.json``; record each substitution; re-hash manifests of changed files."""
    rules = json.loads((home / "relabel.json").read_text(encoding="utf-8"))["substitutions"]
    record: list[dict[str, Any]] = []
    digests: dict[str, tuple[str, int]] = {}
    ledger = home / "transfer.provenance.json"
    before = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
    earlier = {(r["file"], r["from"]): r["replaced"] for r in before.get("substitutions", [])}
    for rule in rules:
        path = Path(rule["file"])
        text = path.read_text(encoding="utf-8")
        count = text.count(rule["from"])
        if count:
            path.write_text(text.replace(rule["from"], rule["to"]), encoding="utf-8")
            digests[provenance.repo_relative(path)] = provenance.digest(path)
        record.append({**rule, "replaced": count + earlier.get((rule["file"], rule["from"]), 0)})
        print(f"{count:>4}  gap {rule['gap']}  {rule['file']}")
    rehashed = 0
    while True:  # to a fixed point: a re-hashed manifest may itself be digested by another
        files = [p for p in home.rglob("*") if p.is_file() and p.name != "transfer.provenance.json"]
        current = {provenance.repo_relative(p): provenance.digest(p) for p in files}
        passed = 0
        for manifest in (p for p in files if p.name.endswith(".provenance.json")):
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            n = _rehash(payload, current)
            if n:
                manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                digests[provenance.repo_relative(manifest)] = provenance.digest(manifest)
                passed += n
        rehashed += passed
        if not passed:
            break
    out = provenance.envelope("transfer", built_by="tools/transfer_it4.py relabel")
    out.update(
        {
            "entry": ENTRY,
            "why": (
                "stages write MVA-case text into their outputs whatever case they run on "
                "(entry 156, gaps 2-4, 7, 9-11); each substitution below restores the truth "
                "for this case, and every manifest digesting a changed file was re-hashed"
            ),
            "substitutions": record,
            "manifest_digests_updated": rehashed + int(before.get("manifest_digests_updated", 0)),
            "outputs": [
                provenance.output(Path(p), 0)
                for p in sorted(
                    {
                        *digests,
                        *(
                            o["path"] if isinstance(o, dict) else o
                            for o in before.get("outputs", [])
                        ),
                    }
                )
            ],
        }
    )
    provenance.write(out, ledger)
    print(f"re-hashed {rehashed} manifest digests; wrote {home / 'transfer.provenance.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("verb", choices=["twin", "sweep", "lincs", "converge", "scan", "relabel"])
    parser.add_argument("command", nargs="?", choices=["fetch", "run"], default="run")
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)
    case, home = _case(args.case)
    if args.verb == "twin":
        return do_twin(case, home)
    if args.verb == "sweep":
        return do_sweep(case, home, args.workers)
    if args.verb == "lincs":
        return do_lincs(case, home, args.command)
    if args.verb == "converge":
        return do_converge(case, home)
    if args.verb == "scan":
        return do_scan(home)
    return do_relabel(home)


if __name__ == "__main__":
    raise SystemExit(main())
