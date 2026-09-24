#!/usr/bin/env python3
"""Which mouse genotype is this patient's phenotypic twin? (entry 150, experiment E2)

Two subcommands, both gene- and disease-agnostic:

``fetch``  download the eight public files into ``--raw`` (skips files already present) and
           write ``manifest.json`` there: URL, retrieval time, bytes, sha256, licence, the
           server's Last-Modified and the ontology ``data-version``.
``run``    score an HPO query (default: the case's two term sets from
           ``mva.phenotype.terms``) against every MGI genotype, locate ``--gene``'s best
           genotype, and run the controls: IC-matched null, leave-one-term-out, the
           within-pathway genes, and disease -> gene positive controls.

Usage::

    uv run python tools/phenotype_twin.py fetch
    uv run python tools/phenotype_twin.py run --gene Bub1b
    uv run python tools/phenotype_twin.py run --hpo HP:0002859 HP:0000121 --gene Bub1b --null 200

Outputs: ``build/it4/track2-e2/twin.json`` (everything, incl. null percentiles) and the
committed, coordinate-free ``ressources/phenotype/phenotype_twin.json`` (the same minus the
top-25 lists), ``phenotype_twin_genotypes.tsv`` (every genotype of the gene) and a
``.provenance.json`` beside them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from mva.phenotype import cross_species_run as run  # noqa: E402  - needs the sys.path line
from mva.phenotype.terms import PROBAND_ONLY, WITH_PARENTAL  # noqa: E402

RAW = REPO / "build" / "it4" / "track2-e2" / "raw"
OUT = REPO / "build" / "it4" / "track2-e2"
COMMITTED = REPO / "ressources" / "phenotype"
ENTRY = "docs/iteration4/step-9/methodology/150-the-childs-phenotype-twin-among-mgi-mice.md"

MGI = "https://www.informatics.jax.org/downloads/reports/"
MGI_LICENCE = "MGI: free use; cite Mouse Genome Informatics (www.informatics.jax.org)"
SOURCES: dict[str, tuple[str, str]] = {
    "MGI_PhenoGenoMP.rpt": (MGI + "MGI_PhenoGenoMP.rpt", MGI_LICENCE),
    "MGI_PhenotypicAllele.rpt": (MGI + "MGI_PhenotypicAllele.rpt", MGI_LICENCE),
    "mp.obo": ("https://purl.obolibrary.org/obo/mp.obo", "CC BY 4.0"),
    "hp.obo": ("https://purl.obolibrary.org/obo/hp.obo", "HPO licence (free with attribution)"),
    "phenotype.hpoa": (
        "https://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa",
        "HPO licence (free with attribution)",
    ),
    "mp_hp_mgi_all.sssom.tsv": (
        (
            "https://raw.githubusercontent.com/mapping-commons/mh_mapping_initiative/master/"
            "mappings/mp_hp_mgi_all.sssom.tsv"
        ),
        "CC BY 4.0 (declared in the file header)",
    ),
    "upheno-species-independent.sssom.tsv": (
        (
            "https://raw.githubusercontent.com/obophenotype/upheno/master/mappings/"
            "upheno-species-independent.sssom.tsv"
        ),
        "CC BY 4.0 (uPheno)",
    ),
    "hp-to-mp-bestmatches.tsv": (
        (
            "https://raw.githubusercontent.com/obophenotype/upheno/master/mappings/"
            "hp-to-mp-bestmatches.tsv"
        ),
        "CC BY 4.0 (uPheno)",
    ),
}

#: Case defaults for the controls; any gene or disease can be passed instead.
PATHWAY = ("Trip13", "Cep57", "Bub1", "Bub3", "Mad2l1", "Ttk", "Cdc20")
CONTROLS = (
    "OMIM:210900=Blm",
    "OMIM:257300=Bub1b",
    "OMIM:310200=Dmd",
    "OMIM:154700=Fbn1",
    "OMIM:100800=Fgfr3",
    "OMIM:312750=Mecp2",
    "OMIM:209900=Bbs1",
    "OMIM:251260=Nbn",
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _data_version(path: Path) -> str | None:
    if path.suffix != ".obo":
        return None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("data-version:"):
                return line.split(":", 1)[1].strip()
            if line.startswith("[Term]"):
                break
    return None


def fetch(raw: Path) -> dict[str, Any]:
    """Download missing files; (re)write the manifest over every file present."""
    raw.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, (url, licence) in SOURCES.items():
        dest = raw / name
        last_modified = None
        if not dest.exists() or dest.stat().st_size == 0:
            with urllib.request.urlopen(url) as reply:
                last_modified = reply.headers.get("Last-Modified")
                dest.write_bytes(reply.read())
        else:
            headers = raw / f"{name}.headers"
            if headers.exists():
                for line in headers.read_text().splitlines():
                    if line.lower().startswith("last-modified:"):
                        last_modified = line.split(":", 1)[1].strip()
        entries.append(
            {
                "name": name,
                "url": url,
                "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, UTC).isoformat(
                    timespec="seconds"
                ),
                "last_modified": last_modified,
                "data_version": _data_version(dest),
                "bytes": dest.stat().st_size,
                "sha256": _sha(dest),
                "licence": licence,
            }
        )
    manifest = {"built_by": "tools/phenotype_twin.py fetch", "entry": ENTRY, "files": entries}
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def _write_tsv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = [k for k in rows[0] if k != "per_term"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {k: ";".join(map(str, v)) if isinstance(v, list) else v for k, v in row.items()}
            )


def run_all(args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    inputs = run.load(args.raw)
    queries = (
        {"custom": tuple(args.hpo)}
        if args.hpo
        else {WITH_PARENTAL.name: WITH_PARENTAL.ids, PROBAND_ONLY.name: PROBAND_ONLY.ids}
    )
    result: dict[str, Any] = {
        "gene": args.gene,
        "n_genotypes": len(inputs.corpus),
        "n_mp_terms": len(inputs.corpus.terms),
        "unresolved_annotations": inputs.corpus.unresolved,
        "bridge_hp_terms": len(inputs.bridge.mappable()),
        "studies": {},
        "pathway": {},
        "controls": [],
    }
    for name, query in queries.items():
        result["studies"][name] = run.twin_study(inputs, query, args.gene, args.null, args.seed)
        result["pathway"][name] = run.pathway(inputs, query, args.pathway)
    for pair in args.controls:
        disease, gene = pair.split("=", 1)
        result["controls"].append(run.disease_control(inputs, disease, gene, seed=args.seed))
    result["runtime_s"] = round(time.time() - started, 1)
    return result


def write(result: dict[str, Any], args: argparse.Namespace) -> None:
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "twin.json").write_text(json.dumps(result, indent=1) + "\n")
    COMMITTED.mkdir(parents=True, exist_ok=True)
    slim = json.loads(json.dumps(result))
    for study in slim["studies"].values():
        study.pop("top_genotypes", None)
    (COMMITTED / "phenotype_twin.json").write_text(json.dumps(slim, indent=1) + "\n")
    first = next(iter(result["studies"].values()))
    _write_tsv(COMMITTED / "phenotype_twin_genotypes.tsv", first["genotypes"])
    manifest = json.loads((args.raw / "manifest.json").read_text())
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    provenance = {
        "name": "phenotype_twin",
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/phenotype_twin.py run " + " ".join(sys.argv[2:]),
        "code_version": commit,
        "code_version_note": "the commit at build time, which precedes the commit landing this",
        "modules": [
            "src/mva/phenotype/cross_species.py",
            "src/mva/phenotype/cross_species_io.py",
            "src/mva/phenotype/cross_species_controls.py",
            "src/mva/phenotype/cross_species_run.py",
        ],
        "sources": {
            "clinical": "the case's HPO terms (mva.phenotype.terms; "
            "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md)",
            "genomic": "the gene only (BUB1B, the Track 1 pair); no variant or position read",
        },
        "parameters": {
            "null": args.null,
            "seed": args.seed,
            "gene": args.gene,
            "pathway": list(args.pathway),
            "controls": list(args.controls),
        },
        "inputs": manifest["files"],
        "outputs": {
            "phenotype_twin.json": "every study, null percentiles, controls, pathway",
            "phenotype_twin_genotypes.tsv": "every genotype of the gene, first query only",
        },
        "entry": ENTRY,
    }
    (COMMITTED / "phenotype_twin.provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--raw", type=Path, default=RAW)
    r = sub.add_parser("run")
    r.add_argument("--raw", type=Path, default=RAW)
    r.add_argument("--out", type=Path, default=OUT)
    r.add_argument("--hpo", nargs="*", default=None, help="HP ids; default: the case's term sets")
    r.add_argument("--gene", default="Bub1b", help="MGI gene symbol (mouse casing)")
    r.add_argument("--null", type=int, default=1000)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--pathway", nargs="*", default=list(PATHWAY))
    r.add_argument("--controls", nargs="*", default=list(CONTROLS), help="DISEASE=Gene")
    args = parser.parse_args()
    if args.cmd == "fetch":
        manifest = fetch(args.raw)
        for item in manifest["files"]:
            print(f"{item['bytes']:>12,}  {item['sha256'][:12]}  {item['name']}")
        return 0
    result = run_all(args)
    write(result, args)
    for name, study in result["studies"].items():
        for metric, hit in study["best"].items():
            p = study["null"]["empirical_p"][metric]
            print(
                f"{name:14} {metric:9} best {hit['genotype_id']} rank {hit['rank']:,}"
                f"/{study['n_genotypes']:,} ({hit['percentile']:.2f} %)  p={p:.4f}"
            )
    for c in result["controls"]:
        print(f"control {c['disease']} -> {c['gene']}: median pct {c['median_percentile']}")
    print(f"runtime {result['runtime_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
