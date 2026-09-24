#!/usr/bin/env python3
"""Variant atlas CLI: build the per-substitution table, test it on labelled alleles, place one.

Gene-agnostic: a UniProt accession, the ThermoMPNN lane's ΔΔG table
(``src/mva/zoo/modal_apps/thermompnn.py``) and, optionally, an ESM1b LLR matrix are the
inputs. Nothing patient-derived is read except by ``place``, which writes under ``build/``.

    ESM1B=build/it4/tables/esm1b/esm1b-extracted/content/ALL_hum_isoforms_ESM1b_LLR
    uv run python tools/variant_atlas.py build --uniprot O60566 \\
        --ddg build/it4/track2-e1/thermompnn/O60566.tsv \\
        --esm1b "$ESM1B/O60566_LLR.csv" \\
        --region "BUB3-binding (GLEBS) bound:387-483:literature PMID 20516114" \\
        --out ressources/track2/bub1b_atlas.parquet
    A=ressources/track2/bub1b_atlas.parquet L=ressources/track2/bub1b_published_alleles.tsv
    uv run python tools/variant_atlas.py evaluate --atlas $A --labels $L \\
        --out build/it4/track2-e1/evaluate.json
    uv run python tools/variant_atlas.py place --atlas $A --labels $L \\
        --case src/mva/zoo/zoo.example.toml \\
        --records build/it4/records.parquet --out build/it4/track2-e1/child.json

``build`` writes ``<out>`` plus ``<out stem>.provenance.json``. ``place`` refuses to write
outside ``build/``: its output names the patient's substitution.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
from typing import Any

import polars as pl

from mva.drugs import provenance
from mva.drugs.variant_atlas import (
    MODELS,
    build_atlas,
    evaluate,
    labelled_rows,
    parse_change,
    place,
    read_ddg_tsv,
)
from mva.drugs.variant_atlas_sources import (
    AF_API,
    INTERPRO,
    UNIPROT,
    alphafold_pdb,
    features_from,
    interpro_entries,
    ken_boxes,
    parse_region,
    read_esm1b_matrix,
    residues_from_pdb,
    uniprot_entry,
)

POSITIVE, NEGATIVE = "abundance-lowering", "stable"
ENTRY = "docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md"


def _file_input(name: str, path: Path, role: str, url: str | None = None) -> dict[str, Any]:
    sha, size = provenance.digest(path)
    row = {"name": name, "path": provenance.repo_relative(path), "sha256": sha, "bytes": size}
    return row | ({"url": url} if url else {}) | {"role": role}


def cmd_build(args: argparse.Namespace) -> int:
    cache = Path("build/variant_atlas") / args.uniprot
    pdb = alphafold_pdb(args.uniprot, cache)
    entry = uniprot_entry(args.uniprot, cache)
    interpro = interpro_entries(args.uniprot, cache)
    residues = residues_from_pdb(pdb.read_text())
    sequence = entry["sequence"]["value"]
    if "".join(r.aa for r in residues) != sequence:
        raise SystemExit("AlphaFold model and UniProt canonical sequence differ")
    features = features_from(entry, interpro) + ken_boxes(sequence)
    features += [parse_region(spec) for spec in args.region]
    esm = read_esm1b_matrix(args.esm1b) if args.esm1b else None
    atlas = build_atlas(args.uniprot, read_ddg_tsv(args.ddg), residues, features, esm)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    atlas.write_parquet(args.out)
    reply = json.loads(args.ddg.with_suffix(".reply.json").read_text())
    inputs = [
        _file_input("AlphaFold DB model", pdb, "structure: pLDDT, RSA, ThermoMPNN input",
                    AF_API.format(acc=args.uniprot)),
        _file_input("UniProtKB entry", cache / "uniprot.json", "sequence + curated features",
                    UNIPROT.format(acc=args.uniprot)),
        _file_input("InterPro entries", cache / "interpro.json", "member-database domains",
                    INTERPRO.format(acc=args.uniprot)),
        _file_input("ThermoMPNN site-saturation scan", args.ddg,
                    "ddg (kcal/mol, + = destabilising)")
        | {"model": reply["version"], "weights_digest": reply["digest"], "gpu": reply["gpu"]},
    ]  # fmt: skip
    if args.esm1b:
        inputs.append(
            _file_input("ESM1b LLR matrix (Brandes et al. 2023, PMID 37563329)", args.esm1b,
                        "esm1b_llr (<= 0, more negative = less plausible)",
                        "https://huggingface.co/spaces/ntranoslab/esm_variants")
        )  # fmt: skip
    manifest = provenance.envelope(args.out.stem, "tools/variant_atlas.py build") | {
        "entry": ENTRY,
        "method": (
            "one row per single-residue substitution (19 x length, self-swaps dropped). "
            "ddg = ThermoMPNN on the AlphaFold model; ddg_percentile = mid-rank percentile "
            "of ddg over all rows (100 = most destabilising); plddt = CA B-factor of the "
            "AlphaFold model; rsa = Shrake-Rupley SASA (probe 1.4 A, 100 dots, Bondi radii) "
            "/ Tien 2013 max ASA, capped at 1; region = first covering feature in the order "
            "UniProt Domain > Region > Motif > literature > InterPro; features = all covering."
        ),
        "regions_from_literature": args.region,
        "inputs": inputs,
        "outputs": [provenance.output(args.out, atlas.height)],
        "patient_data": (
            "none. Protein-generic: every row is a possible substitution of the public "
            "reference protein; no patient allele is marked or implied."
        ),
    }
    provenance.write(manifest, args.out.with_name(f"{args.out.stem}.provenance.json"))
    print(json.dumps({"rows": atlas.height, "positions": atlas["position"].n_unique(),
                      "out": str(args.out)}))  # fmt: skip
    return 0


def _labelled(args: argparse.Namespace, primary_only: bool) -> tuple[pl.DataFrame, pl.DataFrame]:
    atlas = pl.read_parquet(args.atlas)
    return atlas, labelled_rows(atlas, args.labels, POSITIVE, NEGATIVE, primary_only)


def cmd_evaluate(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {"positive": POSITIVE, "negative": NEGATIVE, "sets": {}}
    for name, primary in (("primary", True), ("extended", False)):
        _, labelled = _labelled(args, primary)
        result = evaluate(labelled)
        result["alleles"] = labelled.select(
            ["change", "label", "pmid", "ddg", "ddg_percentile", "esm1b_llr", "plddt", "rsa",
             "region"]
        ).to_dicts()  # fmt: skip
        report["sets"][name] = result
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    for name, result in report["sets"].items():
        line = {"set": name, "n": [result["n_positive"], result["n_negative"]]}
        line |= {k: round(v["auroc"], 3) for k, v in result["raw"].items()}
        line |= {f"{k} (LOO)": round(v["auroc_loo"], 3) for k, v in result["models"].items()}
        print(json.dumps(line))
    return 0


def cmd_place(args: argparse.Namespace) -> int:
    if not args.out.resolve().is_relative_to(Path("build").resolve()):
        raise SystemExit("place names the patient's substitution: its output stays in build/")
    case = tomllib.loads(args.case.read_text())["case"]
    records = pl.read_parquet(args.records, columns=["gene", "consequence", "hgvs_p"])
    hits = records.filter(
        (pl.col("gene") == case["confirmed_gene"])
        & pl.col("consequence").str.contains("missense_variant")
    )
    if hits.height != 1:
        raise SystemExit(f"expected one missense record, found {hits.height}")
    change = parse_change(str(hits["hgvs_p"][0]))
    if change is None:
        raise SystemExit("unparseable hgvs_p")
    atlas, primary = _labelled(args, True)
    _, extended = _labelled(args, False)
    out = {
        "gene": case["confirmed_gene"],
        "primary": place(atlas, primary, change),
        "extended": place(atlas, extended, change),
        "models": {k: list(v) for k, v in MODELS.items()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {args.out} (build/ only: names the substitution)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--uniprot", required=True)
    build.add_argument("--ddg", type=Path, required=True)
    build.add_argument("--esm1b", type=Path)
    build.add_argument("--region", action="append", default=[],
                       help="name:start-end:source (a literature-derived span)")  # fmt: skip
    build.add_argument("--out", type=Path, required=True)
    for name in ("evaluate", "place"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--atlas", type=Path, required=True)
        cmd.add_argument("--labels", type=Path, required=True)
        cmd.add_argument("--out", type=Path, required=True)
        if name == "place":
            cmd.add_argument("--case", type=Path, required=True)
            cmd.add_argument("--records", type=Path, required=True)
    args = parser.parse_args(argv)
    handler = {"build": cmd_build, "evaluate": cmd_evaluate, "place": cmd_place}
    return handler[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
