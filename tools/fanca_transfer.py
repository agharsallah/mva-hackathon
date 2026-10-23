"""Bounded FANCA transfer: real cached-public MGI scoring and unlabelled graph walks.

Run from the repository root with ``uv run python tools/fanca_transfer.py``.
No network requests, patient data, fixtures, or approval/efficacy claims are made.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mva.drugs import graph_walk, primekg  # noqa: E402 - repository path shim
from mva.phenotype import cross_species_io  # noqa: E402
from mva.phenotype.ontology import parse_obo  # noqa: E402

HOME = Path("ressources/track2/transfer-it4/FANCA")
RAW = Path("build/it4/track2-e2/raw")
GRAPH = Path("build/primekg/kg.parquet")


def dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


def digest(path: Path) -> dict[str, object]:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def main() -> None:  # noqa: PLR0915 - one bounded experiment, no production pipeline changes
    started = time.monotonic()
    HOME.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location(
        "transfer_it4_fanca", ROOT / "tools/transfer_it4.py"
    )
    assert spec and spec.loader
    transfer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transfer)
    transfer.__dict__["BUILD"] = HOME / "work"
    terms = cross_species_io.parse_disease_terms(RAW / "phenotype.hpoa", "OMIM:227650")
    ontology = parse_obo(RAW / "hp.obo")
    with (RAW / "phenotype.hpoa").open() as handle:
        annotations = [
            r
            for r in csv.DictReader((s for s in handle if not s.startswith("#")), delimiter="\t")
            if r["database_id"] == "OMIM:227650" and r["aspect"] == "P" and r["qualifier"] != "NOT"
        ]
    with (HOME / "hpo_case.tsv").open("w") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["hpo_id", "name", "reference", "evidence"], delimiter="\t"
        )
        writer.writeheader()
        for r in annotations:
            writer.writerow(
                {k: r[k] for k in ("hpo_id", "reference", "evidence")}
                | {
                    "name": ontology.concepts[r["hpo_id"]].name,
                }
            )
    case = {
        "version": 1,
        "case": {
            "disease": "Fanconi anemia (FANCA hypothesis; disease-level phenotype)",
            "omim_phenotype": "227650",
            "mondo": "MONDO:0019391",
            "hpo_terms": list(terms),
            "hpo_source": digest(RAW / "phenotype.hpoa")
            | {
                "release": "2026-09-02",
                "rule": "aspect P, qualifier != NOT, deduplicate in file order",
                "scope": "disease-level annotation, not a FANCA-specific patient or subtype",
            },
        },
        "gene": {"symbol": "FANCA", "mouse_symbol": "Fanca"},
        "mechanism": {
            "class": "biallelic loss-of-function hypothesis; no individual variants asserted",
            "pathway": "FA core complex / DNA interstrand cross-link repair",
            "source": "https://medlineplus.gov/genetics/condition/fanconi-anemia/",
            "distinction": "MVA: BUB1B spindle checkpoint; Bloom: BLM homologous recombination",
        },
        "chain": {
            "twin": {
                "gene": "Fanca",
                "null": 100,
                "seed": 0,
                "pathway": ["Fancc", "Fancd2", "Fancg"],
                "controls": [],
            }
        },
        "limitations": [
            "Bounded null: 100 draws vs 1000 historically; no calibration panel rerun.",
            "No patient genome or pharmacogenomics; no clinical interpretation.",
            "Not run: PRISM, LINCS, approval labels, intervention curation, convergence, K1/K2/K3.",
        ],
    }
    dump(HOME / "case.json", case)
    print(f"HPO: {len(terms)} terms; executing existing transfer_it4.do_twin", flush=True)
    mark = time.monotonic()
    transfer.do_twin(case, HOME)
    twin_seconds = time.monotonic() - mark
    # Correct the existing writer's fixed MVA labels explicitly, without changing its code.
    manifest_path = HOME / "phenotype/phenotype_twin.provenance.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"] = {
        "clinical": "OMIM:227650 non-NOT aspect-P terms; see ../hpo_case.tsv and ../case.json",
        "genomic": "Fanca gene only; no variants or patient data",
    }
    manifest["entry"] = str(HOME / "README.md")
    manifest["built_by"] = "uv run python tools/fanca_transfer.py"
    manifest["transfer_note"] = "Corrected legacy MVA labels; numerical outputs unchanged."
    dump(manifest_path, manifest)
    print("Loading real PrimeKG graph once; scoring all three diseases identically", flush=True)
    mark = time.monotonic()
    graph = primekg.load_graph(GRAPH)
    graph_results = {}
    top_sets = {}
    for label, mondo in [
        ("FANCA", "MONDO:0019391"),
        ("MVA", "MONDO:0009759"),
        ("Bloom", "MONDO:0008876"),
    ]:
        nodes = primekg.disease_nodes(GRAPH, mondo)
        if not nodes:
            raise RuntimeError(f"No graph node for {label} {mondo}")
        walk = graph_walk.walk(graph, [n.key for n in nodes], damping=1.0)
        ranking = walk.ranking()
        rows = [
            {
                "rank": i,
                "drug": r.drug.name,
                "source_id": r.drug.source_id,
                "score": r.score,
                "paths": r.paths,
                "best_path": r.best.render(graph),
            }
            for i, r in enumerate(ranking, 1)
        ]
        with (HOME / f"{label.lower()}_graph_ranking.tsv").open("w") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["rank", "drug", "source_id", "score", "paths", "best_path"],
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(rows)
        graph_results[label] = {
            "nodes": [n.as_dict() for n in nodes],
            "paths": len(walk.paths),
            "drugs_reached": len(rows),
            "top10": rows[:10],
        }
        top_sets[label] = {r["drug"] for r in rows[:50]}
    graph_seconds = time.monotonic() - mark
    phenotype = json.loads((HOME / "phenotype/phenotype_twin.json").read_text())
    baseline = {}
    for label, path in [
        ("MVA", Path("ressources/phenotype/phenotype_twin.json")),
        ("Bloom", Path("ressources/track2/transfer-it4/BLM/phenotype/phenotype_twin.json")),
        ("FANCA", HOME / "phenotype/phenotype_twin.json"),
    ]:
        d = json.loads(path.read_text())
        baseline[label] = {
            "source": str(path),
            "gene": d["gene"],
            "studies": {
                k: {"best": v["best"], "n_genotypes": v["n_genotypes"]}
                for k, v in d["studies"].items()
            },
        }
    outputs = [
        digest(p) for p in sorted(HOME.rglob("*")) if p.is_file() and p.name != "summary.json"
    ]
    summary = {
        "status": "partial_cached_public_computation_NOT_end_to_end",
        "built_at": datetime.now(UTC).isoformat(),
        "command": "uv run python tools/fanca_transfer.py",
        "live_requests": 0,
        "fixture_inputs": 0,
        "patient_data": "none",
        "hpo_terms": len(terms),
        "twin_seconds": twin_seconds,
        "graph_seconds": graph_seconds,
        "wall_seconds": time.monotonic() - started,
        "phenotype_comparison": baseline,
        "fanca_empirical_p": phenotype["studies"]["custom"]["null"]["empirical_p"],
        "graph_comparison": graph_results,
        "top50_unlabelled_graph_jaccard": {
            label: len(top_sets["FANCA"] & top_sets[label])
            / len(top_sets["FANCA"] | top_sets[label])
            for label in ("MVA", "Bloom")
        },
        "comparison_limitations": [
            "Graph scores are identically rerun unlabelled rankings, not approved-drug generators.",
            "Fanconi graph node is disease-wide, not FANCA-specific.",
            "Historical phenotype queries/null sizes differ; not a controlled accuracy benchmark.",
            "No FANCA-specific therapeutic rescue evidence established by these computations.",
        ],
        "inputs": [digest(GRAPH), digest(RAW / "manifest.json"), digest(Path(__file__))],
        "outputs": outputs,
    }
    dump(HOME / "summary.json", summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "status",
                    "hpo_terms",
                    "twin_seconds",
                    "graph_seconds",
                    "wall_seconds",
                    "fanca_empirical_p",
                    "top50_unlabelled_graph_jaccard",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
