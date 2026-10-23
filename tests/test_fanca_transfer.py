"""Read-only regression checks for the public FANCA transfer and its safety boundary."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from mva.phenotype.cross_species_io import parse_disease_terms

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "ressources/track2/transfer-it4/FANCA"


def test_fanca_public_case_and_partial_scope() -> None:
    case = json.loads((HOME / "case.json").read_text())
    summary = json.loads((HOME / "summary.json").read_text())
    assert case["gene"] == {"symbol": "FANCA", "mouse_symbol": "Fanca"}
    assert case["case"]["omim_phenotype"] == "227650"
    assert summary["command"] == "uv run python tools/fanca_transfer.py"
    assert summary["status"] == "partial_cached_public_computation_NOT_end_to_end"
    assert summary["live_requests"] == summary["fixture_inputs"] == 0
    assert summary["patient_data"] == "none"
    assert case["chain"]["twin"]["null"] == 100
    assert not (HOME / "candidates.tsv").exists()
    manifest = json.loads((HOME / "phenotype/phenotype_twin.provenance.json").read_text())
    assert "Fanca" in manifest["sources"]["genomic"]
    assert "BUB1B" not in manifest["sources"]["genomic"]
    assert manifest["built_by"] == summary["command"]


def test_fanca_case_terms_match_public_source() -> None:
    case = json.loads((HOME / "case.json").read_text())
    source = ROOT / case["case"]["hpo_source"]["path"]
    if not source.exists():
        pytest.skip("Original public HPO cache absent; no fixture substitution")
    assert list(parse_disease_terms(source, "OMIM:227650")) == case["case"]["hpo_terms"]
    assert len(case["case"]["hpo_terms"]) == 34
    with source.open() as handle:
        rows = [
            r
            for r in csv.DictReader((s for s in handle if not s.startswith("#")), delimiter="\t")
            if r["database_id"] == "OMIM:227650" and r["aspect"] == "P" and r["qualifier"] != "NOT"
        ]
    with (HOME / "hpo_case.tsv").open() as handle:
        actual = list(csv.DictReader(handle, delimiter="\t"))
    keys = ("hpo_id", "reference", "evidence")
    assert [tuple(r[k] for k in keys) for r in actual] == [tuple(r[k] for k in keys) for r in rows]


def test_fanca_artifact_hashes() -> None:
    summary = json.loads((HOME / "summary.json").read_text())
    for record in summary["inputs"] + summary["outputs"]:
        path = ROOT / record["path"]
        if not path.exists():
            pytest.skip(f"Original reproducibility input absent: {record['path']}")
        assert path.stat().st_size == record["bytes"], path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], path
    source = json.loads((HOME / "case.json").read_text())["case"]["hpo_source"]
    path = ROOT / source["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
