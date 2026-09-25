"""Build the walk (G1) and twin (G2) generator tables, with their provenance manifests.

The I/O side of :mod:`mva.drugs.convergence_generators`: run the entry-142 walk unchanged,
look up a US label for **every** drug it reaches (the entry-142 table stopped at the first
100 labelled drugs, so it cannot define a universe), and write the table contract. The walk
itself - metapaths, damping, tie-break - is :func:`mva.drugs.graph_walk.walk` with the
defaults entry 142 used; the build checks it reproduces entry 142's top 100 before writing.

openFDA answers ``400`` to a few systematic chemical names it cannot parse; such a drug is
recorded as *query refused* and enters the universe as not approved (it cannot be proven
labelled). The count is written into the manifest.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import graph_walk, primekg, provenance
from .cache import SourceError
from .convergence_generators import (
    WalkCandidate,
    twin_rows,
    twin_universe,
    walk_rows,
    walk_universe,
)
from .convergence_tables import write_generator
from .names import base_name

__all__ = ["build_twin", "build_walk", "label_all", "reproduces"]

ENTRY_150 = "docs/iteration4/step-9/methodology/150-the-childs-phenotype-twin-among-mgi-mice.md"

Label = Callable[[str], dict[str, Any]]


def label_all(
    ranking: Sequence[graph_walk.Ranked], label: Label
) -> tuple[list[WalkCandidate], int]:
    """A :class:`WalkCandidate` per reached drug; returns them and the refused-query count."""
    out: list[WalkCandidate] = []
    refused = 0
    cache: dict[str, dict[str, Any] | None] = {}
    for position, row in enumerate(ranking, start=1):
        key = base_name(row.drug.name)
        if key not in cache:
            try:
                cache[key] = label(key)
            except SourceError as error:
                if "HTTP 400" not in error.detail:
                    raise
                cache[key] = None
                refused += 1
        found = cache[key]
        out.append(
            WalkCandidate(
                drug_name=row.drug.name,
                drugbank_id=row.drug.source_id,
                score=row.score,
                rank_all=position,
                labelled=None if found is None else bool(found.get("has_label")),
                application="|".join((found or {}).get("application_numbers", ())[:3]),
                targets=row.targets,
                best_path="",
            )
        )
    return out, refused


def reproduces(
    candidates: Sequence[WalkCandidate], reference: Path, n: int = 100
) -> dict[str, Any]:
    """Does the first ``n`` labelled drugs match the entry-142 table, name and score?"""
    with reference.open(encoding="utf-8", newline="") as handle:
        ref = [(r["drug_name"], r["score"]) for r in csv.DictReader(handle, delimiter="\t")][:n]
    ours = [(c.drug_name, f"{c.score:.6g}") for c in candidates if c.labelled][: len(ref)]
    mismatches = [i + 1 for i, (a, b) in enumerate(zip(ref, ours, strict=False)) if a != b]
    return {
        "reference": provenance.repo_relative(reference),
        "compared": len(ref),
        "identical": not mismatches and len(ours) == len(ref),
        "mismatched_ranks": mismatches[:20],
    }


def build_walk(
    *,
    graph_path: Path,
    mondo: str,
    label: Label,
    fetcher: Any,
    top: int,
    out_dir: Path,
    reference: Path,
    entry: str,
    generator: str = "walk",
) -> dict[str, Any]:
    """Walk, label everything reached, write ``<generator>.*``; returns the manifest."""
    nodes = primekg.disease_nodes(graph_path, mondo)
    if not nodes:
        raise SystemExit(f"{mondo} resolves to no PrimeKG disease node")
    graph = primekg.load_graph(graph_path)
    result = graph_walk.walk(graph, [n.key for n in nodes], damping=1.0)
    ranking = result.ranking()
    candidates, refused = label_all(ranking, label)
    best = {r.drug.key: r.best.render(result.graph) for r in ranking}
    candidates = [
        replace(c, best_path=best[r.drug.key]) for c, r in zip(candidates, ranking, strict=True)
    ]
    rows = walk_rows(candidates, top, generator)
    universe = walk_universe(candidates)
    listing, universe_path = write_generator(out_dir, generator, rows, universe)
    check = reproduces(candidates, reference)
    manifest = provenance.envelope(generator, built_by="tools/converge.py walk")
    manifest.update(
        {
            "entry": entry,
            "generator_rule": (
                f"top {top} openFDA-labelled drugs (distinct by mva.drugs.names.base_name) in "
                "PrimeKG-walk score order; universe = every drug the walk reached, approved "
                "when openFDA holds a label for its base name"
            ),
            "method": (
                "mva.drugs.graph_walk.walk from the card's MONDO disease node over "
                "DEFAULT_METAPATHS, damping 1.0 (entry 142, unchanged); every reached drug's "
                "base name looked up with mva.drugs.sources.openfda.label through the shared "
                "cache; the table contract of docs/iteration4/step-10/README.md"
            ),
            "parameters": {"mondo": mondo, "top": top, "damping": 1.0},
            "reproduces_entry_142": check,
            "counts": {
                "paths": len(result.paths),
                "drugs_reached": len(ranking),
                "universe_drugs": len(universe),
                "universe_approved": sum(universe.values()),
                "label_queries_refused": refused,
                "listed": len(rows),
            },
            "inputs": [
                {
                    "name": "PrimeKG kg.parquet",
                    "path": provenance.repo_relative(graph_path),
                    "sha256": provenance.digest(graph_path)[0],
                    "bytes": provenance.digest(graph_path)[1],
                    "release": "PrimeKG 2.1 (doi:10.7910/DVN/IXA7BM)",
                    "licence": "CC0-1.0",
                    "manifest": "ressources/track2/primekg.provenance.json",
                },
                provenance.api_input(
                    "openfda",
                    "https://api.fda.gov/drug/label.json",
                    role="US label present = approved",
                    fetcher=fetcher,
                ),
            ],
            "outputs": [
                provenance.output(listing, len(rows)),
                provenance.output(universe_path, len(universe)),
            ],
            "sources": {
                "genomic": (
                    "the gene set of the disease node (BUB1B and its PrimeKG disease "
                    "genes); no patient data"
                ),
                "clinical": "none: the walk starts from the disease identifier, not the HPO terms",
            },
            "limitations": (
                "openFDA label presence is the approval proxy (a US label, any indication); a drug "
                "whose name openFDA refuses to search is counted not approved"
            ),
        }
    )
    provenance.write(manifest, out_dir / f"{generator}.provenance.json")
    return manifest


def _universe_file(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            r["drug"] for r in csv.DictReader(handle, delimiter="\t") if r["approved"] == "true"
        ]


def build_twin(
    *,
    interventions: Path,
    others: Sequence[Path],
    out_dir: Path,
    entry: str,
    generator: str = "twin",
) -> dict[str, Any]:
    """Apply the G2 rule to the twin's intervention table; write ``<generator>.*``."""
    with interventions.open(encoding="utf-8", newline="") as handle:
        table = list(csv.DictReader(handle, delimiter="\t"))
    rows, skipped = twin_rows(table, generator)
    other_sets = [_universe_file(p) for p in others]
    universe = twin_universe(table, other_sets)
    listing, universe_path = write_generator(out_dir, generator, rows, universe)
    manifest = provenance.envelope(generator, built_by="tools/converge.py twin")
    manifest.update(
        {
            "entry": entry,
            "generator_rule": (
                "every approved analogue in model_interventions.tsv on a row whose "
                "supports_direction begins with 'supports'; 'approved' read from the row's "
                "own analogue_status (mva.drugs.convergence_generators.approved_analogues). "
                "Universe = approved analogues named by any row, plus every approved drug in "
                "the other generators' universes (the widest space, so the null is harder)"
            ),
            "rows_not_voting": skipped,
            "other_universes": [
                {**provenance.output(p, len(s)), "approved": len(s)}
                for p, s in zip(others, other_sets, strict=True)
            ],
            "counts": {
                "table_rows": len(table),
                "listed": len(rows),
                "universe_drugs": len(universe),
            },
            "inputs": [
                {
                    "name": "model_interventions.tsv",
                    "path": provenance.repo_relative(interventions),
                    "sha256": provenance.digest(interventions)[0],
                    "bytes": provenance.digest(interventions)[1],
                    "manifest": "ressources/track2/model_interventions.provenance.json",
                    "entry": ENTRY_150,
                }
            ],
            "outputs": [
                provenance.output(listing, len(rows)),
                provenance.output(universe_path, len(universe)),
            ],
            "sources": {
                "clinical": (
                    "the child's 8 HPO terms chose the twin mice (entry 150); rows link "
                    "rescued phenotypes to them"
                ),
                "genomic": (
                    "the gene BUB1B (Track 1 pair) chose the mouse models; no patient sequence"
                ),
            },
            "limitations": (
                "abstract-level literature table, hand-curated in entry 150; 'supports' is that "
                "table's own word. 'hypothesis only' rows (the rapalogs) do not vote by this rule"
            ),
        }
    )
    provenance.write(manifest, out_dir / f"{generator}.provenance.json")
    return manifest
