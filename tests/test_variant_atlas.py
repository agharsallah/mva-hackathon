"""The variant atlas's pure logic: table building, statistics, parsing. No network, no weights."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from mva.drugs.variant_atlas import (
    Change,
    build_atlas,
    evaluate,
    labelled_rows,
    parse_change,
    place,
    read_ddg_tsv,
)
from mva.drugs.variant_atlas_model import (
    auroc,
    bootstrap_auroc,
    fit_logistic,
    loo_probabilities,
    percentile_rank,
    roc_points,
)
from mva.drugs.variant_atlas_sources import (
    Feature,
    Residue,
    features_from,
    ken_boxes,
    read_esm1b_matrix,
    shrake_rupley,
)

# A synthetic four-residue protein; nothing here is patient data.
RESIDUES = [
    Residue(1, "M", 90.0, 0.1),
    Residue(2, "K", 80.0, 0.9),
    Residue(3, "E", 40.0, 0.5),
    Residue(4, "N", 95.0, 0.0),
]
FEATURES = [
    Feature("kinase", 3, 4, "UniProt Domain"),
    Feature("pfam kinase", 1, 4, "InterPro pfam"),
]


def _ddg() -> list[tuple[int, str, str, float]]:
    rows = []
    for residue in RESIDUES:
        for k, alt in enumerate("ACDEFGHIKLMNPQRSTVWY"):
            if alt != residue.aa:
                rows.append((residue.position, residue.aa, alt, residue.position + k / 100))
    return rows


def test_auroc_counts_ties_as_half_and_needs_both_classes() -> None:
    assert auroc([3, 2, 1], [1, 1, 0]) == 1.0
    assert auroc([1, 2], [1, 0]) == 0.0
    assert auroc([1, 1], [1, 0]) == 0.5
    with pytest.raises(ValueError):
        auroc([1, 2], [1, 1])


def test_bootstrap_interval_brackets_a_perfect_separation() -> None:
    low, high = bootstrap_auroc([5, 4, 3, 1, 0], [1, 1, 1, 0, 0], n=200, seed=1)
    assert low == high == 1.0


def test_roc_runs_from_origin_to_one_one() -> None:
    points = roc_points([0.9, 0.2, 0.5], [1, 0, 1])
    assert points[0] == (0.0, 0.0) and points[-1] == (1.0, 1.0)
    assert (0.0, 1.0) in points  # both positives above the negative


def test_ridge_logistic_is_monotone_in_a_positive_feature() -> None:
    fit = fit_logistic([[0.0], [1.0], [2.0], [3.0]], [0, 0, 1, 1], ("x",))
    assert fit.coef[1] > 0
    assert fit.probability([3.0]) > 0.5 > fit.probability([0.0])
    assert len(loo_probabilities([[0.0], [1.0], [2.0], [3.0]], [0, 0, 1, 1], ("x",))) == 4


def test_percentile_rank_is_mid_rank() -> None:
    assert percentile_rank([1, 2, 3, 4], 4) == 87.5
    assert percentile_rank([1, 1], 1) == 50.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("R727C", Change("R", 727, "C")),
        ("p.Arg727Cys", Change("R", 727, "C")),
        ("ENSP00000000001.1:p.Leu10Pro", Change("L", 10, "P")),
        ("p.Leu10Ter", None),
        ("c.123A>G", None),
    ],
)
def test_parse_change(text: str, expected: Change | None) -> None:
    assert parse_change(text) == expected


def test_build_atlas_has_19_rows_per_residue_and_names_the_domain() -> None:
    atlas = build_atlas("P00000", _ddg(), RESIDUES, FEATURES)
    assert atlas.height == 19 * len(RESIDUES)
    pct = atlas["ddg_percentile"].to_numpy()
    assert pct.min() > 0 and pct.max() < 100
    row = atlas.filter(pl.col("change") == "N4K").row(0, named=True)
    assert row["region"] == "kinase" and row["features"] == "kinase; pfam kinase"
    assert atlas.filter(pl.col("position") == 1)["region"][0] == "pfam kinase"


def test_build_atlas_refuses_a_numbering_mismatch() -> None:
    with pytest.raises(ValueError, match="structure has"):
        build_atlas("P00000", [(1, "A", "C", 0.1)], RESIDUES, FEATURES)


def test_read_ddg_tsv_drops_self_swaps(tmp_path: Path) -> None:
    path = tmp_path / "x.tsv"
    path.write_text("position\twt\talt\tddg\n1\tM\tM\t0.0\n1\tM\tA\t0.5\n")
    assert read_ddg_tsv(path) == [(1, "M", "A", 0.5)]


def test_labels_join_evaluate_and_place(tmp_path: Path) -> None:
    atlas = build_atlas("P00000", _ddg(), RESIDUES, FEATURES)
    labels = tmp_path / "labels.tsv"
    lines = ["protein_change\tclass\tpmid\tprimary"]
    lines += [f"{c}\tabundance-lowering\t1\tyes" for c in ("N4A", "N4W", "E3W")]
    lines += [f"{c}\tstable\t1\tyes" for c in ("M1A", "K2A", "M1W")]
    lines += ["K2W\tambiguous\t1\tno"]
    labels.write_text("\n".join(lines) + "\n")
    labelled = labelled_rows(atlas, labels, "abundance-lowering", "stable", primary_only=True)
    assert labelled.height == 6
    result = evaluate(labelled, bootstrap=100)
    assert result["raw"]["ddg"]["auroc"] == 1.0
    assert set(result["models"]) == {"ddg", "ddg+rsa+plddt"}
    placed = place(atlas, labelled, Change("N", 4, "Y"))
    assert placed["calls"]["ddg"]["call"] == "abundance-lowering"
    assert placed["in_labelled_set"] is False


def test_labels_absent_from_the_atlas_raise(tmp_path: Path) -> None:
    atlas = build_atlas("P00000", _ddg(), RESIDUES, FEATURES)
    labels = tmp_path / "labels.tsv"
    labels.write_text("protein_change\tclass\tpmid\tprimary\nA9C\tstable\t1\tyes\n")
    with pytest.raises(ValueError, match="absent"):
        labelled_rows(atlas, labels, "abundance-lowering", "stable", primary_only=True)


def test_shrake_rupley_single_atom_is_its_whole_sphere() -> None:
    area = shrake_rupley(np.zeros((1, 3)), np.array([1.7]))
    assert area[0] == pytest.approx(4 * math.pi * 3.1**2)
    pair = shrake_rupley(np.array([[0.0, 0, 0], [1.0, 0, 0]]), np.array([1.7, 1.7]))
    assert (pair < area[0]).all()


def test_ken_boxes_and_features() -> None:
    assert [(f.start, f.end) for f in ken_boxes("AKENKENX")] == [(2, 4), (5, 7)]
    uniprot = {"features": [
        {"type": "Domain", "description": "Protein kinase",
         "location": {"start": {"value": 3}, "end": {"value": 9}}},
        {"type": "Helix", "location": {"start": {"value": 1}, "end": {"value": 2}}},
    ]}  # fmt: skip
    interpro = {"results": [{
        "metadata": {"accession": "PF1", "name": "dom", "source_database": "pfam"},
        "proteins": [{"entry_protein_locations": [{"fragments": [{"start": 1, "end": 5}]}]}],
    }]}  # fmt: skip
    got = features_from(uniprot, interpro)
    assert [(f.name, f.source) for f in got] == [
        ("Protein kinase", "UniProt Domain"),
        ("dom", "InterPro pfam PF1"),
    ]


def test_read_esm1b_matrix(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    path.write_text(",M 1,K 2\nA,-1.5,-2.0\nK,-3.0,0.0\n")
    assert read_esm1b_matrix(path) == {(1, "A"): -1.5, (2, "A"): -2.0, (1, "K"): -3.0,
                                       (2, "K"): 0.0}  # fmt: skip
