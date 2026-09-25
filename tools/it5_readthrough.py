#!/usr/bin/env python3
"""Route R1 of iteration 5: what the stop allele's sequence allows, and what it would take.

Four stages, each writing its own artefact:

``facts``
    Read the case's own allele record, pull the **public** transcript model (Ensembl REST) and
    the **public** protein-domain annotation (UniProt), and derive the stop codon's identity,
    its +4 base, its exon, its distance to the last exon-exon junction (the 50-55 nt rule that
    decides nonsense-mediated decay), and how much protein and which domains the truncation
    loses. Written to ``build/it5/r1/stop_facts.json`` — that file holds transcript offsets, so
    it stays under ``build/`` and never reaches a tracked table.
``control``
    Fit the context model on published, measured readthrough and score it with each PTC context
    held out in turn. This runs **before** any prediction for the case, and its verdict is
    carried into every downstream row.
``predict``
    Apply the model to the case's stop and write ``readthrough.tsv``.
``dosage``
    Evaluate the protein-dosage scenarios and write ``allele_dosage.tsv``; then write the
    pinned ``readthrough_candidates.tsv``.

Case-agnostic: the gene, the records file, the measurement table and the output directory are
all flags. The BubR1-specific numbers live in :mod:`mva.drugs.readthrough_case`, which cites
each one.

    uv run python tools/it5_readthrough.py all
    uv run python tools/it5_readthrough.py facts --gene BUB1B
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import duckdb

from mva.drugs import provenance
from mva.drugs import readthrough_case as default_case
from mva.drugs import readthrough_dossier as dossier
from mva.drugs import readthrough_manifests as manifests
from mva.drugs.cache import Fetcher
from mva.drugs.readthrough import ControlResult, Measurement, ReadthroughModel, held_out_control
from mva.drugs.readthrough_dataset import TOLEDANO_2024, load_wide, workbook_to_long
from mva.drugs.readthrough_dosage import evaluate, nearest_threshold
from mva.drugs.readthrough_external import COLUMNS, external_check
from mva.drugs.readthrough_facts import stop_facts, transcript_model
from mva.drugs.readthrough_tables import write_candidates, write_dosage, write_readthrough

ENTRY = (
    "docs/iteration5/step-1/methodology/"
    "158-the-stop-allele-can-be-read-through-and-it-is-not-the-lever.md"
)
BUILD = Path("build/it5/r1")
TABLES = Path("ressources/track2/it5")


def _card(args: argparse.Namespace) -> Any:
    """The case card module named by ``--card`` (the BUB1B one by default)."""
    return importlib.import_module(args.card) if args.card else default_case


def _dirs(args: argparse.Namespace) -> tuple[Path, Path]:
    """``(build, tables)`` for this run; a second case writes beside the first, never over it."""
    return Path(args.build), Path(args.tables)


WORKBOOK_URL = (
    "https://static-content.springer.com/esm/art%3A10.1038%2Fs41588-024-01878-5/"
    "MediaObjects/41588_2024_1878_MOESM4_ESM.xlsx"
)


# ── stage 1: the sequence facts ────────────────────────────────────────────────────────


def _record(records: Path, gene: str, consequence: str) -> dict[str, Any]:
    """The one allele record for ``gene`` with this consequence class, from the case's callset."""
    connection = duckdb.connect()
    rows = connection.execute(
        "select transcript, hgvs_c, hgvs_p, consequence, clin_sig, af_gnomad "
        "from read_parquet(?) where gene = ? and consequence = ?",
        [str(records), gene, consequence],
    ).fetchall()
    if len(rows) != 1:
        raise SystemExit(f"{gene}/{consequence}: expected one allele record, found {len(rows)}")
    keys = ("transcript", "hgvs_c", "hgvs_p", "consequence", "clin_sig", "af_gnomad")
    return dict(zip(keys, rows[0], strict=True))


def facts(args: argparse.Namespace) -> dict[str, Any]:
    """Derive every sequence fact the route needs, and cache them under ``build/``.

    The allele comes from the case's own callset, unless the card carries a published one
    (``ALLELE``) — a transfer case is read from the literature, never from a patient.
    """
    card, (build, _) = _card(args), _dirs(args)
    record = getattr(card, "ALLELE", None) or _record(Path(args.records), args.gene, "stop_gained")
    fetcher = Fetcher(source="ensembl-uniprot", cache_dir=build / "cache")
    model = transcript_model(fetcher, str(record["transcript"]), args.accession)
    out = stop_facts(
        record,
        model,
        gene=args.gene,
        accession=args.accession,
        flank=args.flank,
        nmd_rule_nt=args.nmd_rule_nt,
    )
    build.mkdir(parents=True, exist_ok=True)
    (build / "stop_facts.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "stop"}, indent=2))
    return out


def _facts(build: Path) -> dict[str, Any]:
    path = build / "stop_facts.json"
    if not path.is_file():
        raise SystemExit(f"{path} missing: run `it5_readthrough.py facts` first")
    return json.loads(path.read_text(encoding="utf-8"))


# ── stage 2 + 3: the control, then the prediction ──────────────────────────────────────


def dataset(args: argparse.Namespace) -> None:
    """Reshape the published workbook's PTC sheet into the long TSV every later stage reads."""
    source = Path(args.workbook)
    if not source.is_file():
        raise SystemExit(
            f"{source} missing. Download it first:\n  curl -L -o {source} '{WORKBOOK_URL}'"
        )
    out = Path(args.measurements)
    written = workbook_to_long(source, args.sheet, out)
    print(f"wrote {out}: {written} PTC rows, sha256 {provenance.digest(source)[0][:12]}…")


def _measurements(args: argparse.Namespace) -> list[Measurement]:
    path = Path(args.measurements)
    if not path.is_file():
        raise SystemExit(f"{path} missing: run `it5_readthrough.py dataset` first")
    return load_wide(path, TOLEDANO_2024)


def _panels(
    measurements: list[Measurement], seed: int, panel: frozenset[str]
) -> dict[str, frozenset[str]]:
    """Both held-out sets, fixed before any prediction: the named panel and a random 20 %."""
    contexts = sorted({m.context for m in measurements})
    rng = random.Random(seed)
    return {
        "panel": panel,
        "random20": frozenset(rng.sample(contexts, k=int(0.2 * len(contexts)))),
    }


def control(args: argparse.Namespace) -> dict[str, ControlResult]:
    """Both declared held-out controls, per drug. The named panel is the one rows carry."""
    card, (build, _) = _card(args), _dirs(args)
    measurements = _measurements(args)
    drugs = sorted({m.drug for m in measurements})
    results: dict[str, ControlResult] = {}
    recorded: dict[str, dict[str, Any]] = {}
    for name, held in _panels(measurements, args.seed, card.BENCHMARK_PANEL).items():
        recorded[name] = {"held_out_contexts": len(held), "drugs": {}}
        print(f"-- control {name}: {len(held)} contexts held out of the fit")
        for drug in drugs:
            result = held_out_control(
                measurements,
                drug,
                held,
                min_contexts=args.min_contexts,
                min_spearman=args.min_spearman,
            )
            accuracy = result.pair_accuracy
            print(
                f"   {drug:12s} n={result.contexts:5d} "
                f"rho={'n/a' if result.spearman is None else f'{result.spearman:5.2f}'} "
                f"pair_acc={'n/a' if accuracy is None else f'{accuracy:.3f}'} "
                f"passed={str(result.passed and (accuracy or 0) >= args.min_pair_accuracy).lower()}"
            )
            strict = result.passed and (accuracy or 0.0) >= args.min_pair_accuracy
            recorded[name]["drugs"][drug] = {
                "contexts": result.contexts,
                "spearman": result.spearman,
                "p_value": result.p_value,
                "pair_accuracy": accuracy,
                "passed": strict,
            }
            if name == "panel":
                results[drug] = replace(result, passed=strict)
            elif not strict and drug in results:
                results[drug] = replace(
                    results[drug],
                    passed=False,
                    reason=results[drug].reason + "; but the random 20 % held-out set failed",
                )
    build.mkdir(parents=True, exist_ok=True)
    (build / "controls.json").write_text(
        json.dumps(
            {
                "bar": {
                    "min_spearman": args.min_spearman,
                    "min_pair_accuracy": args.min_pair_accuracy,
                },
                "seed": args.seed,
                "controls": recorded,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return results


def predict(args: argparse.Namespace) -> None:
    """Apply the model to the case's stop and write the readthrough table."""
    build, tables = _dirs(args)
    known = _facts(build)
    measurements = _measurements(args)
    model = ReadthroughModel(measurements)
    controls = control(args)
    stop = known["stop"]["rna_stop"]
    plus4, minus1 = known["stop"]["plus4"], known["stop"]["minus1"]
    rows = []
    for drug in model.drugs:
        guess = model.predict(drug, stop, plus4, minus1)
        sources = sorted({m.source for m in measurements if m.drug == drug})
        rows.append((guess, controls.get(drug), ";".join(sources)))
    path = tables / "readthrough.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    written = write_readthrough(path, rows)
    provenance.write(
        manifests.readthrough_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            workbook=Path(args.workbook),
            workbook_url=WORKBOOK_URL,
            stop_facts=build / "stop_facts.json",
            case_notes=getattr(_card(args), "NOTES", None),
            parameters={
                "min_rows_per_cell": model.min_rows,
                "backoff": "(drug, stop, +4, -1) -> (drug, stop, +4) -> (drug, stop) -> (drug)",
                "controls": {
                    "panel": "the named benchmark panel, held out of the fit before any run",
                    "random20": f"a random 20 % of contexts, seed {args.seed}",
                },
                "min_contexts": args.min_contexts,
                "min_spearman": args.min_spearman,
                "min_pair_accuracy": args.min_pair_accuracy,
            },
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({written} rows)")


# ── external check: predict a context the fit has never seen, against its measurement ──


def holdout(args: argparse.Namespace) -> None:
    """Refit without one *measured* PTC context, predict it, and compare with the measurement.

    This is the check a case only gets when the published dataset happens to contain its own
    gene: the context is removed from the fit entirely, so the comparison is external.
    """
    _, tables = _dirs(args)
    card = _card(args)
    contexts = tuple(args.holdout_context) or tuple(getattr(card, "HOLDOUT_CONTEXTS", ()))
    if not contexts:
        raise SystemExit("no --holdout-context given and the card names none")
    try:
        rows, summary = external_check(_measurements(args), contexts)
    except KeyError as missing:
        raise SystemExit(f"{missing.args[0]} (measurements: {args.measurements})") from missing
    path = tables / "readthrough_external_check.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(COLUMNS), delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    provenance.write(
        manifests.external_check_manifest(
            entry=ENTRY,
            output_path=path,
            rows=len(rows),
            measurements=Path(args.measurements),
            parameters={"held_out_contexts": list(contexts), "summary": summary},
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({len(rows)} rows)")
    print(json.dumps(summary, indent=1))


# ── stage 4: dosage, then the candidate table ──────────────────────────────────────────


def dosage(args: argparse.Namespace) -> None:
    """Evaluate every scenario and write the dosage and candidate tables."""
    card, (build, tables) = _card(args), _dirs(args)
    known = _facts(build)
    predicted = card.best_readthrough(tables / "readthrough.tsv")
    scenarios = card.scenarios(known, predicted)
    results = [(evaluate(s), None) for s in scenarios]
    scored = [(r, nearest_threshold(r, card.THRESHOLDS)) for r, _ in results]
    path = tables / "allele_dosage.tsv"
    written = write_dosage(path, scored)
    provenance.write(
        manifests.dosage_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            stop_facts=build / "stop_facts.json",
            readthrough_table=tables / "readthrough.tsv",
            published_alleles=Path(card.PUBLISHED_ALLELES),
            parameters=card.DOSAGE_PARAMETERS,
            case_notes=getattr(card, "NOTES", None),
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({written} rows)")

    if not getattr(card, "DOSSIER", True):
        return
    candidates = dossier.candidates(tables / "readthrough.tsv")
    path = tables / "readthrough_candidates.tsv"
    written = write_candidates(path, candidates)
    provenance.write(
        manifests.candidates_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            readthrough_table=tables / "readthrough.tsv",
            hpo_map=Path("ressources/track2/hpo_to_adverse_terms.tsv"),
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({written} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=("dataset", "facts", "control", "predict", "holdout", "dosage", "all"),
        help="which stage to run",
    )
    parser.add_argument("--gene", default="BUB1B")
    parser.add_argument(
        "--card", default="", help="case-card module (default: mva.drugs.readthrough_case)"
    )
    parser.add_argument("--build", default=str(BUILD), help="working directory for this case")
    parser.add_argument("--tables", default=str(TABLES), help="where the case's tables are written")
    parser.add_argument(
        "--holdout-context",
        action="append",
        default=[],
        help="a measured PTC context to remove from the fit and predict (repeatable)",
    )
    parser.add_argument("--accession", default="O60566", help="UniProt accession for the protein")
    parser.add_argument("--records", default="build/it4/records.parquet")
    parser.add_argument("--measurements", default=str(BUILD / "toledano_ptc.tsv"))
    parser.add_argument("--workbook", default=str(BUILD / "toledano_MOESM4.xlsx"))
    parser.add_argument("--sheet", default="Supp_Table 3")
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--min-pair-accuracy", type=float, default=0.7)
    parser.add_argument("--flank", type=int, default=6, help="nt of context either side")
    parser.add_argument("--nmd-rule-nt", type=int, default=55)
    parser.add_argument("--min-contexts", type=int, default=4)
    parser.add_argument("--min-spearman", type=float, default=0.5)
    args = parser.parse_args()
    stages = (
        ("dataset", "facts", "control", "predict", "dosage")
        if args.stage == "all"
        else (args.stage,)
    )
    for stage in stages:
        print(f"\n=== {stage} ===")
        {
            "dataset": dataset,
            "facts": facts,
            "control": control,
            "predict": predict,
            "holdout": holdout,
            "dosage": dosage,
        }[stage](args)


if __name__ == "__main__":
    main()
