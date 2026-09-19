"""The matrix-archive reshaper, on three invented members.

No download and no patient data: the members are written by the test, with made-up
accessions, made-up residues and made-up scores.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from mva.zoo import tables


def member(directory: Path, accession: str, body: str) -> Path:
    path = directory / f"{accession}_LLR.csv"
    path.write_text(body)
    return path


@pytest.fixture
def members(tmp_path: Path) -> list[Path]:
    return [
        # two positions, two substitutions — the shape the publisher ships
        member(tmp_path, "U1", ",A 1,R 2\nK,-1.5,-2.5\nQ,-0.5,\n"),
        # a different protein length, so the two members share no schema at all
        member(tmp_path, "U2-3", ",W 7\nC,-9.0\n"),
        member(tmp_path, "U3", ",M 1\n"),  # header only: no rows, no crash
    ]


def test_accession_comes_from_the_file_name(tmp_path: Path) -> None:
    assert tables.accession_of(tmp_path / "P04637-2_LLR.csv") == "P04637-2"


def test_every_cell_becomes_one_row_keyed_by_all_three_parts(
    members: list[Path], tmp_path: Path
) -> None:
    target = tmp_path / "out.parquet"
    written = tables.unpivot_matrix_members(members, target, score_sign=-1)
    rows = {
        (row["uniprot"], row["hgvs_p"]): row["score"] for row in pq.read_table(target).to_pylist()
    }
    assert written == len(rows) == 4
    # score_sign = -1 flips the published log-likelihood ratio so higher = more damaging
    assert rows[("U1", "A1K")] == 1.5
    assert rows[("U1", "R2K")] == 2.5
    assert rows[("U1", "A1Q")] == 0.5
    assert rows[("U2-3", "W7C")] == 9.0


def test_a_blank_cell_is_absent_rather_than_null(members: list[Path], tmp_path: Path) -> None:
    target = tmp_path / "out.parquet"
    tables.unpivot_matrix_members(members, target)
    keys = {(row["uniprot"], row["hgvs_p"]) for row in pq.read_table(target).to_pylist()}
    assert ("U1", "R2Q") not in keys  # the one empty cell of the fixture


def test_the_sign_defaults_to_leaving_the_number_alone(members: list[Path], tmp_path: Path) -> None:
    target = tmp_path / "out.parquet"
    tables.unpivot_matrix_members(members, target)
    rows = {
        (row["uniprot"], row["hgvs_p"]): row["score"] for row in pq.read_table(target).to_pylist()
    }
    assert rows[("U1", "A1K")] == -1.5
