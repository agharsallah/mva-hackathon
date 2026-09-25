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
import json
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import duckdb

from mva.drugs import provenance
from mva.drugs import readthrough_case as case
from mva.drugs import readthrough_dossier as dossier
from mva.drugs import readthrough_manifests as manifests
from mva.drugs.cache import Fetcher
from mva.drugs.readthrough import ControlResult, Measurement, ReadthroughModel, held_out_control
from mva.drugs.readthrough_context import (
    Domain,
    TranscriptModel,
    nmd_call,
    parse_hgvs_c,
    stop_context,
    transcript_from_ensembl,
    truncation,
)
from mva.drugs.readthrough_dataset import TOLEDANO_2024, load_wide
from mva.drugs.readthrough_dosage import evaluate, nearest_threshold
from mva.drugs.readthrough_tables import write_candidates, write_dosage, write_readthrough

ENTRY = "docs/iteration5/step-1/methodology/<numbered by the coordinator>-r1.md"
BUILD = Path("build/it5/r1")
TABLES = Path("ressources/track2/it5")
ENSEMBL = "https://rest.ensembl.org"
WORKBOOK_URL = (
    "https://static-content.springer.com/esm/art%3A10.1038%2Fs41588-024-01878-5/"
    "MediaObjects/41588_2024_1878_MOESM4_ESM.xlsx"
)
UNIPROT = "https://rest.uniprot.org/uniprotkb"


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


def _transcript(fetcher: Fetcher, transcript: str, accession: str) -> TranscriptModel:
    lookup = fetcher.get_json(
        f"{ENSEMBL}/lookup/id/{transcript}", {"expand": 1, "content-type": "application/json"}
    )
    cds = fetcher.get_json(
        f"{ENSEMBL}/sequence/id/{transcript}", {"type": "cds", "content-type": "application/json"}
    )["seq"]
    features = fetcher.get_json(
        f"{UNIPROT}/{accession}.json", {"fields": "ft_domain,ft_region,ft_motif,ft_mod_res"}
    )
    domains = tuple(
        Domain(
            feature.get("description") or feature["type"],
            int(feature["location"]["start"]["value"]),
            int(feature["location"]["end"]["value"]),
        )
        for feature in features.get("features", [])
        if feature["type"] == "Domain"
    )
    return transcript_from_ensembl(lookup, cds, domains=domains)


def facts(args: argparse.Namespace) -> dict[str, Any]:
    """Derive every sequence fact the route needs, and cache them under ``build/``."""
    record = _record(Path(args.records), args.gene, "stop_gained")
    spelling = parse_hgvs_c(str(record["hgvs_c"]).split(":", 1)[-1])
    fetcher = Fetcher(source="ensembl-uniprot", cache_dir=BUILD / "cache")
    model = _transcript(fetcher, str(record["transcript"]), args.accession)
    context = stop_context(model, spelling.offset, spelling.alt, flank=args.flank)
    decay = nmd_call(model, context.codon_index, rule_nt=args.nmd_rule_nt)
    lost = truncation(model, context.codon_index)
    out = {
        "gene": args.gene,
        "transcript": model.transcript_id,
        "uniprot": args.accession,
        "coding_length_nt": len(model.cds),
        "protein_length_aa": model.protein_length,
        "exons_total": model.exons_total,
        "coding_exons": model.coding_exons,
        "stop": {
            "rna_stop": context.rna_stop,
            "tetranucleotide": context.tetranucleotide,
            "plus4": context.plus4,
            "minus1": context.minus1,
            "reference_codon": context.reference_codon,
            "upstream": context.upstream,
            "downstream": context.downstream,
            "codon_index": context.codon_index,
        },
        "nmd": {
            "exon_index": decay.exon_index,
            "nt_to_last_junction": decay.nt_to_last_junction,
            "junctions_downstream": decay.junctions_downstream,
            "rule_nt": decay.rule_nt,
            "competent": decay.competent,
            "reason": decay.reason,
        },
        "truncation": {
            "residues_kept": lost.residues_kept,
            "protein_length": lost.protein_length,
            "fraction_lost": lost.fraction_lost,
            "domains_lost": list(lost.domains_lost),
            "domains_truncated": list(lost.domains_truncated),
            "domains_kept": list(lost.domains_kept),
        },
        "clin_sig": record["clin_sig"],
        "af_gnomad": record["af_gnomad"],
        "source": "Ensembl REST (gene model, CDS) + UniProt (domains); allele from the callset",
        "patient_data": (
            "transcript offsets only, no genomic position; this file stays under build/"
        ),
    }
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "stop_facts.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "stop"}, indent=2))
    return out


def _facts() -> dict[str, Any]:
    path = BUILD / "stop_facts.json"
    if not path.is_file():
        raise SystemExit(f"{path} missing: run `it5_readthrough.py facts` first")
    return json.loads(path.read_text(encoding="utf-8"))


# ── stage 2 + 3: the control, then the prediction ──────────────────────────────────────


def dataset(args: argparse.Namespace) -> None:
    """Reshape the published workbook's PTC sheet into the long TSV every later stage reads."""
    import openpyxl

    source = Path(args.workbook)
    if not source.is_file():
        raise SystemExit(
            f"{source} missing. Download it first:\n  curl -L -o {source} '{WORKBOOK_URL}'"
        )
    sheet = openpyxl.load_workbook(source, read_only=True, data_only=True)[args.sheet]
    rows = [row[2:] for row in sheet.iter_rows(values_only=True)]
    header = [str(cell) for cell in rows[0]]
    out = Path(args.measurements)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(
            ["" if cell is None else str(cell) for cell in row] for row in rows[1:] if row[0]
        )
    print(f"wrote {out}: {len(rows) - 1} PTC rows, sha256 {provenance.digest(source)[0][:12]}…")


def _measurements(args: argparse.Namespace) -> list[Measurement]:
    path = Path(args.measurements)
    if not path.is_file():
        raise SystemExit(f"{path} missing: run `it5_readthrough.py dataset` first")
    return load_wide(path, TOLEDANO_2024)


def _panels(measurements: list[Measurement], seed: int) -> dict[str, frozenset[str]]:
    """Both held-out sets, fixed before any prediction: the named panel and a random 20 %."""
    contexts = sorted({m.context for m in measurements})
    rng = random.Random(seed)
    return {
        "panel": case.BENCHMARK_PANEL,
        "random20": frozenset(rng.sample(contexts, k=int(0.2 * len(contexts)))),
    }


def control(args: argparse.Namespace) -> dict[str, ControlResult]:
    """Both declared held-out controls, per drug. The named panel is the one rows carry."""
    measurements = _measurements(args)
    drugs = sorted({m.drug for m in measurements})
    results: dict[str, ControlResult] = {}
    recorded: dict[str, dict[str, Any]] = {}
    for name, held in _panels(measurements, args.seed).items():
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
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "controls.json").write_text(
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
    known = _facts()
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
    path = TABLES / "readthrough.tsv"
    written = write_readthrough(path, rows)
    provenance.write(
        manifests.readthrough_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            workbook=Path(args.workbook),
            workbook_url=WORKBOOK_URL,
            stop_facts=BUILD / "stop_facts.json",
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


# ── stage 4: dosage, then the candidate table ──────────────────────────────────────────


def dosage(args: argparse.Namespace) -> None:
    """Evaluate every scenario and write the dosage and candidate tables."""
    known = _facts()
    predicted = case.best_readthrough(TABLES / "readthrough.tsv")
    scenarios = case.scenarios(known, predicted)
    results = [(evaluate(s), None) for s in scenarios]
    scored = [(r, nearest_threshold(r, case.THRESHOLDS)) for r, _ in results]
    path = TABLES / "allele_dosage.tsv"
    written = write_dosage(path, scored)
    provenance.write(
        manifests.dosage_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            stop_facts=BUILD / "stop_facts.json",
            readthrough_table=TABLES / "readthrough.tsv",
            published_alleles=Path("ressources/track2/bub1b_published_alleles.tsv"),
            parameters=case.DOSAGE_PARAMETERS,
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({written} rows)")

    candidates = dossier.candidates(TABLES / "readthrough.tsv")
    path = TABLES / "readthrough_candidates.tsv"
    written = write_candidates(path, candidates)
    provenance.write(
        manifests.candidates_manifest(
            entry=ENTRY,
            output_path=path,
            rows=written,
            readthrough_table=TABLES / "readthrough.tsv",
            hpo_map=Path("ressources/track2/hpo_to_adverse_terms.tsv"),
        ),
        path.with_suffix(".provenance.json"),
    )
    print(f"wrote {path} ({written} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage",
        choices=("dataset", "facts", "control", "predict", "dosage", "all"),
        help="which stage to run",
    )
    parser.add_argument("--gene", default="BUB1B")
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
            "dosage": dosage,
        }[stage](args)


if __name__ == "__main__":
    main()
