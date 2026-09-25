"""The wide-table loader, the pinned candidate columns, and the table writers.

Synthetic rows only. The loader's two real hazards are covered: a censored value (``>3.2``)
and a context identifier the source table reuses for two different stop codons.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mva.drugs.readthrough import ControlResult, Prediction
from mva.drugs.readthrough_dataset import WideSpec, load_wide
from mva.drugs.readthrough_dosage import Allele, Scenario, Threshold, evaluate
from mva.drugs.readthrough_tables import (
    CANDIDATE_COLUMNS,
    Candidate,
    write_candidates,
    write_dosage,
    write_readthrough,
)

SPEC = WideSpec(
    context_column="id",
    stop_column="stop",
    downstream_column="down",
    upstream_column="up",
    drug_columns=("DrugA", "DrugB"),
    unit="percent",
    assay="reporter",
    source="PMID:1",
)

WIDE = (
    "id\tstop\tdown\tup\tDrugA\tDrugB\n"
    "GENE_R1X\ttga\tgaa\tctt\t1.5\t>3.2\n"
    "GENE_R2X\ttag\tacc\tgtg\t0.4\t\n"
    "GENE_R3X\ttga\tcaa\tttt\t2.0\t1.0\n"
    "GENE_R3X\ttaa\tcaa\tttt\t0.9\t1.1\n"
)


def _tsv(tmp_path: Path) -> Path:
    path = tmp_path / "wide.tsv"
    path.write_text(WIDE, encoding="utf-8")
    return path


def test_loader_reads_context_orientation_and_skips_empty_cells(tmp_path: Path) -> None:
    rows = load_wide(_tsv(tmp_path), SPEC)
    first = next(r for r in rows if r.context == "GENE_R1X" and r.drug == "DrugA")
    assert first.stop == "tga"
    assert first.plus4 == "g"  # +4 is the FIRST base of the downstream field
    assert first.minus1 == "t"  # -1 is the LAST base of the 5'->3' upstream field
    assert first.key == ("UGA", "G")
    assert first.fine_key == ("UGA", "G", "U")
    assert not any(r.context == "GENE_R2X" and r.drug == "DrugB" for r in rows)


def test_loader_keeps_a_censored_value_as_its_lower_bound_and_flags_it(tmp_path: Path) -> None:
    rows = load_wide(_tsv(tmp_path), SPEC)
    censored = next(r for r in rows if r.context == "GENE_R1X" and r.drug == "DrugB")
    assert censored.value == pytest.approx(3.2)
    assert censored.censored is True
    assert sum(r.censored for r in rows) == 1


def test_a_reused_identifier_is_split_by_stop_codon(tmp_path: Path) -> None:
    contexts = {r.context for r in load_wide(_tsv(tmp_path), SPEC)}
    assert "GENE_R3X(tga)" in contexts
    assert "GENE_R3X(taa)" in contexts
    assert "GENE_R3X" not in contexts
    assert "GENE_R1X" in contexts  # used once, so it keeps its plain name


def test_readthrough_table_header_and_a_refused_prediction(tmp_path: Path) -> None:
    path = tmp_path / "rt.tsv"
    guess = Prediction("D", "UGA", "A", None, "none", 0, (), "percent", "G")
    control = ControlResult("D", 14, 0.83, 0.0003, 100, 82, True, "ok")
    assert write_readthrough(path, [(guess, control, "PMID:1")]) == 1
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t")[:5] == [
        "drug_name",
        "stop_codon",
        "plus4",
        "minus1",
        "predicted_readthrough",
    ]
    assert lines[1].split("\t")[4] == ""  # no value, not a zero
    assert "true" in lines[1]


def test_dosage_table_names_the_nearest_published_genotype(tmp_path: Path) -> None:
    path = tmp_path / "dosage.tsv"
    result = evaluate(
        Scenario(
            "now", (Allele("stop", 0.1, 1.0, 0.0, 1.0), Allele("missense", 1.0, 0.25, 1.0, 1.0))
        )
    )
    threshold = Threshold("H/H", 10.0, "progeroid", "PMID:1")
    assert write_dosage(path, [(result, threshold)]) == 1
    row = path.read_text(encoding="utf-8").splitlines()[1].split("\t")
    assert row[2] == "0.000"  # the stop allele contributes nothing
    assert row[4] == "12.50"
    assert "H/H" in row


def test_candidate_columns_are_pinned_and_validated(tmp_path: Path) -> None:
    path = tmp_path / "cand.tsv"
    rows = [
        Candidate("weak", "R1", "any", "kind", 0.2, "n/a", "s", "n"),
        Candidate("strong", "R1", "stop_allele", "kind", 0.8, "true", "s", "n"),
    ]
    assert write_candidates(path, rows) == 2
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == list(CANDIDATE_COLUMNS)
    assert lines[1].startswith("strong")  # strongest evidence first
    with pytest.raises(ValueError, match="branch"):
        Candidate("bad", "R1", "elsewhere", "kind", 0.5, "n/a", "s", "n")
    with pytest.raises(ValueError, match="evidence_strength"):
        Candidate("bad", "R1", "any", "kind", 1.5, "n/a", "s", "n")


def test_a_manifest_names_every_input_with_a_digest(tmp_path: Path) -> None:
    from mva.drugs.readthrough_manifests import readthrough_manifest

    table = tmp_path / "rt.tsv"
    table.write_text("drug_name\n", encoding="utf-8")
    facts = tmp_path / "stop_facts.json"
    facts.write_text("{}", encoding="utf-8")
    book = tmp_path / "book.xlsx"
    book.write_bytes(b"xlsx")
    made = readthrough_manifest(
        entry="docs/…/r1.md",
        output_path=table,
        rows=9,
        workbook=book,
        workbook_url="https://example.invalid/book.xlsx",
        stop_facts=facts,
        parameters={"min_rows_per_cell": 2},
    )
    assert {row["file"] for row in made["inputs"]} == {book.as_posix(), facts.as_posix()}
    assert all(len(row["sha256"]) == 64 for row in made["inputs"])
    assert made["output"]["rows"] == 9
    assert made["parameters"]["min_rows_per_cell"] == 2
    for field in ("assumptions", "limitations", "validation", "sources", "columns", "entry"):
        assert made[field]
    assert "no genomic position" in made["patient_data"]


def test_a_missing_input_is_named_without_a_digest(tmp_path: Path) -> None:
    from mva.drugs.readthrough_manifests import candidates_manifest

    table = tmp_path / "c.tsv"
    table.write_text("drug_name\n", encoding="utf-8")
    made = candidates_manifest(
        entry="e",
        output_path=table,
        rows=1,
        readthrough_table=table,
        hpo_map=tmp_path / "absent.tsv",
    )
    absent = next(r for r in made["inputs"] if r["file"].endswith("absent.tsv"))
    assert "sha256" not in absent  # a manifest never invents a digest for a file it did not read
