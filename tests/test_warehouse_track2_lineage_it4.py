"""Iteration 4's Track 2 lineage: four manifest shapes in, one edge per input out.

Every manifest here is fabricated in a temporary checkout: made-up hosts, digests and drug
tables. No genomic position appears — a manifest names URLs, digests, paths and counts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mva.warehouse import track2_lineage
from mva.warehouse.submission_lineage import CLINICAL_FILE
from mva.warehouse.track2_lineage_it4 import (
    PATIENT_NOTE,
    it4_edges,
    manifest_edges,
    target_name,
)

T2 = "ressources/track2"


def _write(root: Path, relative: str, payload: object) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def _by(edges: list[dict[str, object]], target: str) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for edge in edges:
        if edge["target_table"] == target:
            grouped.setdefault(str(edge["source_kind"]), []).append(edge)
    return grouped


RUN = {
    "name": "walk",
    "built_by": "tools/fake.py walk",
    "entry": "docs/x/methodology/999-fake.md",
    "generator_rule": "top 2 by score",
    "inputs": [
        {"name": "graph", "path": "build/graph.parquet", "sha256": "a" * 64, "release": "G 1"},
        {
            "name": "labels",
            "url": "https://labels.example/api/label.json",
            "retrieved_from": "2099-01-01T00:00:00+00:00",
            "retrieved_at": "2099-01-02T00:00:00+00:00",
            "sha256": "b" * 64,
        },
        {
            "name": "labels again",
            "url": "https://labels.example/api/other.json",
            "retrieved_at": "2099-01-03T00:00:00+00:00",
            "sha256": "c" * 64,
        },
        {"name": "dump", "url": "https://files.example/d.csv", "sha256": "d" * 64, "bytes": 9},
        {"path": f"{T2}/it4/generators/other.provenance.json", "sha256": "e" * 64},
        {"name": f"{T2}/it4/prism_sweep.tsv", "sha256": "f" * 64},
        {"name": "a guideline (PMID 1)", "role": "fixes a mapping choice"},
    ],
    "outputs": [
        {"path": f"{T2}/it4/generators/walk.tsv", "rows": 2},
        {"path": f"{T2}/it4/generators/walk.universe.tsv", "rows": 7},
        {"path": "build/scratch.json", "rows": 1},
    ],
    "other_universes": [{"path": f"{T2}/it4/generators/prism.universe.tsv", "sha256": "1" * 64}],
}


def test_targets_are_named_from_their_path_under_track2() -> None:
    assert target_name(f"{T2}/it4/generators/walk.universe.tsv") == "it4.generators.walk.universe"
    assert target_name(f"{T2}/bub1b_atlas.parquet") == "bub1b_atlas"
    assert target_name(f"{T2}/transfer-it4/BLM/candidates.tsv") == "transfer.BLM.candidates"


def test_a_run_manifest_gives_every_table_output_one_edge_per_input(tmp_path: Path) -> None:
    manifest = _write(tmp_path, f"{T2}/it4/generators/walk.provenance.json", RUN)
    edges = manifest_edges(manifest, tmp_path)
    assert {e["target_table"] for e in edges} == {
        "it4.generators.walk",
        "it4.generators.walk.universe",
    }
    listed = _by(edges, "it4.generators.walk")
    assert [e["source_ref"] for e in listed["file"]] == [
        "build/graph.parquet",
        "https://files.example/d.csv",
    ]
    assert listed["file"][0]["source_version"] == "G 1"
    (api,) = listed["api"]  # two replies, one host
    assert api["source_ref"] == "labels.example"
    rolled = hashlib.sha256(("b" * 64 + "c" * 64).encode()).hexdigest()
    assert api["source_sha256"] == rolled
    assert [e["source_ref"] for e in listed["table"]] == ["track2.it4.prism_sweep"]
    assert all(e["transform"] == "top 2 by score" for e in edges)
    assert all("entry docs/x/methodology/999-fake.md" in str(e["notes"]) for e in edges)
    assert {e["target_rows"] for e in listed["file"]} == {2}


def test_only_the_universe_output_rests_on_the_other_universes(tmp_path: Path) -> None:
    manifest = _write(tmp_path, f"{T2}/it4/generators/walk.provenance.json", RUN)
    edges = manifest_edges(manifest, tmp_path)
    universe = [e["source_ref"] for e in _by(edges, "it4.generators.walk.universe")["table"]]
    listed = [e["source_ref"] for e in _by(edges, "it4.generators.walk")["table"]]
    assert "track2.it4.generators.prism.universe" in universe
    assert "track2.it4.generators.prism.universe" not in listed


def test_a_curated_table_counts_its_rows_only_when_the_digest_still_matches(
    tmp_path: Path,
) -> None:
    body = "drug\tterm\nA\tx\nB\ty\n"
    _write(tmp_path, f"{T2}/curated.tsv", body)
    _write(tmp_path, CLINICAL_FILE, "HP:0000001")
    curated = {
        "built_by": "hand-curated",
        "sha256": hashlib.sha256(body.encode()).hexdigest(),
        "sources": {"clinical": f"{CLINICAL_FILE} - the terms"},
        "inputs": [{"name": "PubMed", "url": "https://pubmed.example", "retrieved_at": "2099"}],
    }
    manifest = _write(tmp_path, f"{T2}/curated.provenance.json", curated)
    edges = manifest_edges(manifest, tmp_path)
    grouped = _by(edges, "curated")
    assert grouped["api"][0]["target_rows"] == 2
    assert grouped["api"][0]["source_sha256"] == ""  # no digest recorded, none invented
    assert grouped["clinical"][0]["source_ref"] == CLINICAL_FILE
    _write(tmp_path, f"{T2}/curated.provenance.json", {**curated, "sha256": "0" * 64})
    assert {e["target_rows"] for e in manifest_edges(manifest, tmp_path)} == {0}


def test_the_childs_pharmcat_summary_is_a_derived_edge(tmp_path: Path) -> None:
    safety = {
        "tool": "tools/fake_safety.py table",
        "rows": 5,
        "inputs": [
            {"file": "build/work/pgx_summary.json", "sha256": "2" * 64},
            {"file": "build/work/label_summary.json", "sha256": "3" * 64},
            {"file": f"{T2}/hpo_to_adverse_terms.tsv", "sha256": "4" * 64},
        ],
    }
    _write(tmp_path, f"{T2}/it4/candidate_safety.tsv", "drug\nA\n")
    manifest = _write(tmp_path, f"{T2}/it4/candidate_safety.provenance.json", safety)
    grouped = _by(manifest_edges(manifest, tmp_path), "it4.candidate_safety")
    (derived,) = grouped["derived"]
    assert derived["source_ref"] == "build/work/pgx_summary.json"
    assert derived["source_sha256"] == "2" * 64
    assert PATIENT_NOTE in str(derived["notes"])
    assert grouped["table"][0]["source_ref"] == "track2.hpo_to_adverse_terms"
    assert grouped["file"][0]["target_rows"] == 5
    assert grouped["file"][0]["tool"] == "tools/fake_safety.py table"


def test_a_transfer_case_is_found_by_glob_and_never_points_at_the_child(tmp_path: Path) -> None:
    home = f"{T2}/transfer-it4/CASEX"
    _write(tmp_path, f"{home}/case.json", {"version": 3})
    _write(tmp_path, f"{home}/transfer.provenance.json", {"outputs": [{"path": f"{home}/a.tsv"}]})
    _write(tmp_path, f"{home}/phenotype/twin_genotypes.tsv", "g\n1\n2\n3\n")
    _write(
        tmp_path,
        f"{home}/phenotype/twin.provenance.json",
        {"outputs": {"twin.json": "a study", "twin_genotypes.tsv": "genotypes"}},
    )
    _write(
        tmp_path,
        f"{home}/candidates.provenance.json",
        {
            "sources": {"clinical": f"copied prose naming {CLINICAL_FILE}"},
            "inputs": [
                {"path": f"{home}/no-genome/pgx_summary.json", "sha256": "5" * 64},
                {"path": f"{home}/generators/walk.tsv", "sha256": "6" * 64},
            ],
            "outputs": [{"path": f"{home}/candidates.tsv", "rows": 4}],
        },
    )
    edges = it4_edges(tmp_path)
    assert {e["target_table"] for e in edges} == {
        "transfer.CASEX.candidates",
        "transfer.CASEX.phenotype.twin_genotypes",
    }
    kinds = {str(e["source_kind"]) for e in edges}
    assert kinds.isdisjoint({"clinical", "derived", "submission"})
    grouped = _by(edges, "transfer.CASEX.candidates")
    assert grouped["card"][0]["source_ref"] == f"{home}/case.json"
    assert grouped["card"][0]["source_version"] == "v3"
    assert grouped["table"][0]["source_ref"] == "track2.transfer.CASEX.generators.walk"
    assert _by(edges, "transfer.CASEX.phenotype.twin_genotypes")["card"][0]["target_rows"] == 3


def test_planned_edges_carry_iteration_4_and_an_empty_checkout_carries_none(
    tmp_path: Path,
) -> None:
    assert it4_edges(tmp_path) == []
    _write(tmp_path, f"{T2}/it4/generators/walk.provenance.json", RUN)
    targets = {e["target_table"] for e in track2_lineage.planned_edges(tmp_path)}
    assert "it4.generators.walk" in targets
    assert all(
        e["target_schema"] == track2_lineage.TRACK2_SCHEMA
        for e in track2_lineage.planned_edges(tmp_path)
    )
