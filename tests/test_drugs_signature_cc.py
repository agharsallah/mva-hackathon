"""Route R2 (b): the cell-cycle-corrected signature logic, on synthetic consensus matrices.

No network and no real gene, drug or coefficient: the matrices are built so the right answer
is known. What is checked: the regression removes the shared axis, a sibling that is similar
only through that axis stops being similar after correction, the control needs both its
clauses, and reversal ranks the opposite-pointing row first.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pytest

from mva.drugs.signature_cc import (
    Consensus,
    cc_residuals,
    pc_residuals,
    read_consensus,
    row_scores,
    sibling_control,
    similarity,
)
from mva.drugs.signature_cc_reversal import decoy_counts, rank_reversers, top_labels

GENES = tuple(f"G{i}" for i in range(20))


def consensus(rows: dict[str, np.ndarray]) -> Consensus:
    return Consensus(tuple(rows), GENES, np.vstack(list(rows.values())))


def world(seed: int = 3, n: int = 60) -> tuple[Consensus, np.ndarray]:
    """One shared axis; QUERY and SHARED differ only through it, TRUE also shares a private part."""
    rng = np.random.default_rng(seed)
    axis = rng.normal(0, 1, len(GENES))
    private = rng.normal(0, 1, len(GENES))
    rows = {f"K{i}": rng.normal(0, 0.4, len(GENES)) + rng.normal(0, 1) * axis for i in range(n)}
    rows["QUERY"] = axis * 2 + private + rng.normal(0, 0.1, len(GENES))
    rows["SHARED"] = axis * 2 + rng.normal(0, 0.1, len(GENES))
    rows["TRUE"] = axis * 2 + private + rng.normal(0, 0.1, len(GENES))
    return consensus(rows), axis


class TestCorrection:
    def test_regression_removes_the_shared_axis(self) -> None:
        cons, axis = world()
        scores = cons.values @ axis / (axis @ axis)
        residual, r2 = cc_residuals(cons.values, [scores])
        assert float(np.abs(residual @ axis).max()) < 1e-8
        assert r2.mean() > 0.2

    def test_correction_separates_a_shared_axis_sibling_from_a_true_one(self) -> None:
        cons, axis = world()
        at = cons.row_index()["QUERY"]
        before = similarity(cons.values, cons.values[at])
        scores = cons.values @ axis / (axis @ axis)
        after_matrix, _ = cc_residuals(cons.values, [scores])
        after = similarity(after_matrix, after_matrix[at])
        index = cons.row_index()
        assert before[index["SHARED"]] > 0.8 and before[index["TRUE"]] > 0.8
        assert after[index["TRUE"]] > 0.5
        assert after[index["SHARED"]] < after[index["TRUE"]] - 0.3

    def test_pc_removal_shrinks_the_dominant_axis(self) -> None:
        cons, _ = world()
        raw = pc_residuals(cons.values, 0)
        one = pc_residuals(cons.values, 1)
        assert float(np.linalg.norm(one)) < float(np.linalg.norm(raw))
        assert pc_residuals(cons.values, 0).shape == cons.values.shape

    def test_row_scores_average_the_members_present(self) -> None:
        cons = consensus({"A": np.arange(20.0), "B": np.ones(20)})
        assert row_scores(cons, ["G0", "G2", "ABSENT"]).tolist() == [1.0, 1.0]
        with pytest.raises(ValueError, match="no score member"):
            row_scores(cons, ["ABSENT"])

    def test_nan_cells_do_not_poison_a_column(self) -> None:
        values = np.array([[1.0, 2.0], [np.nan, 3.0], [3.0, 4.0]])
        residual, _ = cc_residuals(values, [np.array([0.0, 1.0, 2.0])])
        assert np.isfinite(residual).all()


class TestControl:
    def _sims(self, order: list[str], universe: int) -> tuple[list[str], np.ndarray]:
        labels = order + [f"F{i}" for i in range(universe - len(order))]
        return labels, np.linspace(1.0, -1.0, len(labels))

    def test_pass_needs_both_clauses(self) -> None:
        labels, sims = self._sims(["QUERY", "SIB1", "SIB2"], 1000)
        good = sibling_control(
            labels, sims, "QUERY", ["SIB1", "SIB2"], cut=0.05, draws=2000, seed=1
        )
        assert good.any_in_cut and good.permutation_p < 0.05 and good.passed

    def test_one_top_sibling_with_poor_others_fails_the_permutation(self) -> None:
        labels, sims = self._sims(["QUERY", "SIB1"], 1000)
        labels[900] = "SIB2"
        out = sibling_control(labels, sims, "QUERY", ["SIB1", "SIB2"], cut=0.05, draws=2000, seed=1)
        assert out.any_in_cut and not out.passed and out.permutation_p > 0.05

    def test_siblings_absent_from_the_library_fail_rather_than_pass(self) -> None:
        labels, sims = self._sims(["QUERY"], 100)
        out = sibling_control(labels, sims, "QUERY", ["NOWHERE"], cut=0.05, draws=100, seed=1)
        assert out.siblings_present == () and not out.passed

    def test_the_query_never_ranks_itself(self) -> None:
        labels, sims = self._sims(["QUERY", "SIB1"], 50)
        out = sibling_control(labels, sims, "QUERY", ["SIB1"], cut=0.5, draws=100, seed=1)
        assert out.universe == 49 and out.ranks["SIB1"] == 1


class TestReversal:
    def test_the_opposite_row_ranks_first(self) -> None:
        query = np.arange(20.0) - 10
        rows = np.vstack([-query, query, np.zeros(20)])
        ranked = rank_reversers(["mirror", "copy", "flat"], rows, query)
        assert ranked[0].label == "mirror" and ranked[0].rank == 1
        assert ranked[-1].label == "flat" and ranked[-1].rank == 0

    def test_top_labels_and_decoy_counts_track_shared_reversers(self) -> None:
        query = np.arange(20.0) - 10
        other = np.roll(query, 5)
        rows = np.vstack([-query, -other])
        labels = ["anti_query", "anti_other"]
        assert top_labels(rank_reversers(labels, rows, query), 1) == {"anti_query"}
        counts = decoy_counts(labels, rows, [other, other], 1)
        assert counts["anti_other"] == 2 and counts["anti_query"] == 0


class TestReader:
    def test_read_consensus_keeps_requested_columns_and_rows(self, tmp_path: Path) -> None:
        path = tmp_path / "c.tsv.gz"
        with gzip.open(path, "wt") as handle:
            handle.write("\tG1\tG2\tG3\n")
            handle.write("KO1\t1\t2\t3\n")
            handle.write("KO2\t4\t5\t6\n")
        cons = read_consensus(path, {"G1", "G3"}, keep_row=lambda label: label != "KO2")
        assert cons.rows == ("KO1",) and cons.columns == ("G1", "G3")
        assert cons.col(["G3"]).tolist() == [[3.0]]
