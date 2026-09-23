#!/usr/bin/env python3
"""Step 7's graph walk over PrimeKG: a card in, an approved-drug ranking out.

    uv run python tools/track2_walk.py walk                              # the real card
    uv run python tools/track2_walk.py walk --card ressources/track2/decoys/XDH/mechanism.json \\
        --mondo MONDO:0010209 --mondo-reason "..." --out-dir ressources/track2/decoys/XDH
    uv run python tools/track2_walk.py compare --decoy ressources/track2/decoys/XDH
    uv run python tools/track2_walk.py explain --drug "Dasatinib"      # every path, printed

``walk`` reads the card's MONDO id (``case.mondo``; ``--mondo`` overrides it, and the override
and its reason go into the manifest), resolves it to a PrimeKG disease node, walks
:data:`mva.drugs.graph_walk.DEFAULT_METAPATHS`, keeps the first ``--keep`` drugs holding a US
label (openFDA, through the cached ``mva.drugs`` client) and writes ``ranking-walk.tsv``,
``ranking-walk.paths.tsv`` (every path behind the top ``--paths-top``) and a provenance
manifest. It also checks the card's clinical HPO terms against the disease node.

``compare`` computes the two step-7 numbers from written tables only: the top-k overlap with a
decoy's ranking (P4-11) and the top-k matches against ``drug_candidates.tsv`` (P4-12).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# The path shim above must run before these imports.
from mva.drugs import graph_walk, primekg, provenance, walk_table
from mva.drugs.cache import Fetcher
from mva.drugs.mechanism import DEFAULT_CARD, MechanismCard, load
from mva.drugs.names import base_name
from mva.drugs.sources import openfda

TRACK2 = Path("ressources/track2")
CANDIDATES = TRACK2 / "drug_candidates.tsv"
KG_MANIFEST = Path("build/primekg/primekg.provenance.json")
NAME = "ranking-walk"
HPO = re.compile(r"HP:\d{7}")


def clinical_terms(card: MechanismCard) -> dict[str, Any]:
    """The card's HPO terms, plus any HPO id in the clinical file the card names."""
    case = card.raw.get("case", {})
    on_card = [str(t) for t in case.get("hpo_terms", [])]
    source = case.get("clinical_terms_source")
    in_file: list[str] = []
    if source and Path(source).is_file():
        in_file = sorted(set(HPO.findall(Path(source).read_text(encoding="utf-8"))))
    terms = sorted(set(on_card) | set(in_file))
    return {
        "source": source,
        "on_card": on_card,
        "in_source_file": in_file,
        "only_in_source_file": sorted(set(in_file) - set(on_card)),
        "terms": terms,
    }


def _kg_input(parquet: Path) -> dict[str, Any]:
    recorded = json.loads(KG_MANIFEST.read_text()) if KG_MANIFEST.is_file() else {}
    entry = dict((recorded.get("inputs") or [{}])[0])
    sha, size = provenance.digest(parquet)
    entry.update(
        {
            "converted_path": provenance.repo_relative(parquet),
            "converted_sha256": sha,
            "converted_bytes": size,
            "manifest": "ressources/track2/primekg.provenance.json",
        }
    )
    return entry


def do_walk(args: argparse.Namespace) -> int:
    card = load(args.card)
    mondo = args.mondo or str(card.raw.get("case", {}).get("mondo", ""))
    if args.mondo and not args.mondo_reason:
        raise SystemExit("--mondo overrides the card; --mondo-reason must say why")
    nodes = primekg.disease_nodes(args.graph, mondo)
    if not nodes:
        raise SystemExit(f"{mondo} resolves to no PrimeKG disease node")
    keys = [n.key for n in nodes]
    genes = primekg.disease_genes(args.graph, keys)
    print(f"  {mondo} -> {[n.name for n in nodes]}  genes {genes}")
    clinical = clinical_terms(card)
    checks = primekg.phenotype_check(args.graph, keys, clinical["terms"])
    for c in checks:
        print(f"    {c.hpo}  node={c.node_name!r}  linked={c.linked}")

    started = time.monotonic()
    graph = primekg.load_graph(args.graph)
    result = graph_walk.walk(graph, keys, damping=args.damping)
    ranking = result.ranking()
    took = time.monotonic() - started
    print(f"  {len(result.paths):,} paths to {len(ranking):,} drugs in {took:.0f}s")

    fetcher = Fetcher(source="openfda")
    kept, checked = walk_table.keep_approved(
        ranking, lambda name: openfda.label(fetcher, name), args.keep
    )
    print(f"  {len(kept)} approved kept after {checked} label checks")
    candidates = walk_table.candidate_names(args.candidates)
    soc = card.raw.get("case", {}).get("context_standard_of_care", {}).get("drugs", [])
    records = walk_table.rows(result, kept, candidates=candidates, standard_of_care=soc)
    out = args.out_dir / f"{NAME}.tsv"
    paths_out = args.out_dir / f"{NAME}.paths.tsv"
    walk_table.write_tsv(records, walk_table.COLUMNS, out)
    path_records = walk_table.path_rows(result, kept, args.paths_top)
    walk_table.write_tsv(path_records, walk_table.PATH_COLUMNS, paths_out)
    for r in records[:20]:
        print(f"    {r['rank']:>3} {r['drug_name']:<28} {r['score']:>10} paths={r['paths']}")

    manifest = provenance.envelope(NAME, built_by=f"{Path(__file__).name} walk")
    manifest["method"] = (
        "The card's MONDO id is matched against every member of PrimeKG's (grouped) disease "
        "node ids; from those nodes every simple path along the metapaths is enumerated over "
        "the subgraph of their relations; a path weighs the product of degree^-damping over "
        "its intermediate nodes (degree over the walked relations); a drug's score is the "
        "sum of its path weights (degree-weighted path count). Drugs are taken in score "
        "order (ties by name) and kept when openFDA holds a label for their base name, "
        "until `keep` are kept."
    )
    manifest["card"] = {
        "path": provenance.repo_relative(args.card),
        "version": card.version,
        "gene": card.gene_symbol,
        "disease": card.disease_name,
        "decoy": card.raw.get("decoy"),
    }
    manifest["source"] = {
        "mondo": mondo,
        "from": "--mondo override" if args.mondo else "card case.mondo",
        "override_reason": args.mondo_reason,
        "resolved_nodes": [n.as_dict() for n in nodes],
        "resolution": "MONDO number matched against the '_'-joined member list of x_id",
        "disease_genes": genes,
    }
    manifest["parameters"] = {
        "metapaths": {m.name: [list(h) for h in m.hops] for m in graph_walk.DEFAULT_METAPATHS},
        "damping": args.damping,
        "keep": args.keep,
        "paths_top": args.paths_top,
        "tie_break": "score descending, then drug name, then PrimeKG node key",
        "approval_gate": "openFDA label present for mva.drugs.names.base_name(drug_name)",
    }
    manifest["clinical"] = {**clinical, "check": [c.as_dict() for c in checks]}
    manifest["counts"] = {
        "graph_nodes": len(graph.nodes),
        "paths": len(result.paths),
        "drugs_reached": len(ranking),
        "label_checks": checked,
        "kept": len(kept),
    }
    manifest["inputs"] = [
        _kg_input(args.graph),
        provenance.api_input(
            "openfda", openfda.ENDPOINT, role="US label present = approved", fetcher=fetcher
        ),
        {"name": "drug_candidates", **provenance.output(args.candidates, len(candidates))},
    ]
    manifest["outputs"] = [
        provenance.output(out, len(records)),
        provenance.output(paths_out, len(path_records)),
    ]
    manifest["patient_data"] = (
        "none. A public knowledge graph and public drug labels, walked from a disease "
        "identifier. The clinical HPO terms are read only to check their presence in the "
        "graph; no genomic position appears anywhere."
    )
    written = provenance.write(manifest, args.out_dir / f"{NAME}.provenance.json")
    print(f"  -> {out}, {paths_out}, {written}")
    fetcher.close()
    return 0


def _top(path: Path, k: int) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    return [base_name(line.split("\t")[1]) for line in lines[:k]]


def do_compare(args: argparse.Namespace) -> int:
    real = _top(args.real / f"{NAME}.tsv", args.top)
    decoy = _top(args.decoy / f"{NAME}.tsv", args.top)
    candidates = walk_table.candidate_names(args.candidates)
    shared = graph_walk.overlap(real, decoy)
    matches = sorted(set(real) & candidates)
    record = {
        "top": args.top,
        "real": provenance.repo_relative(args.real / f"{NAME}.tsv"),
        "decoy": provenance.repo_relative(args.decoy / f"{NAME}.tsv"),
        "decoy_overlap": len(shared),
        "decoy_shared": shared,
        "candidate_matches": len(matches),
        "candidate_matched": matches,
        "candidates": provenance.repo_relative(args.candidates),
        "matching": "mva.drugs.names.base_name on both sides",
        "computed_at": provenance.now(),
        "code_version": provenance.code_version(),
    }
    print(json.dumps(record, indent=2))
    if args.write:
        provenance.write(record, args.real / "ranking-walk.comparison.json")
    return 0


def do_explain(args: argparse.Namespace) -> int:
    lines = (args.dir / f"{NAME}.paths.tsv").read_text(encoding="utf-8").splitlines()[1:]
    for line in lines:
        rank, drug, metapath, weight, path = line.split("\t")
        if base_name(drug) == base_name(args.drug):
            print(f"{rank:>3} [{metapath}] w={weight}  {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    walk = sub.add_parser("walk", help="walk the graph from the card's disease node")
    walk.add_argument("--card", type=Path, default=DEFAULT_CARD)
    walk.add_argument("--mondo", help="override the card's case.mondo (recorded)")
    walk.add_argument("--mondo-reason", help="why the override (required with --mondo)")
    walk.add_argument("--graph", type=Path, default=primekg.DEFAULT_PARQUET)
    walk.add_argument("--out-dir", type=Path, default=TRACK2)
    walk.add_argument("--candidates", type=Path, default=CANDIDATES)
    walk.add_argument("--keep", type=int, default=100, help="approved drugs to keep")
    walk.add_argument("--paths-top", type=int, default=20, help="drugs whose paths are written")
    walk.add_argument("--damping", type=float, default=1.0, help="degree exponent")
    compare = sub.add_parser("compare", help="decoy overlap and candidate matches")
    compare.add_argument("--real", type=Path, default=TRACK2)
    compare.add_argument("--decoy", type=Path, required=True)
    compare.add_argument("--candidates", type=Path, default=CANDIDATES)
    compare.add_argument("--top", type=int, default=20)
    compare.add_argument("--write", action="store_true", help="write the comparison json")
    explain = sub.add_parser("explain", help="print every written path for one drug")
    explain.add_argument("--drug", required=True)
    explain.add_argument("--dir", type=Path, default=TRACK2)
    args = parser.parse_args(argv)
    verbs = {"walk": do_walk, "compare": do_compare, "explain": do_explain}
    return verbs[args.verb](args)


if __name__ == "__main__":
    raise SystemExit(main())
