"""Route R2 (a): the proteome logic on synthetic matrices. No network, no real drug or value.

Every gene, drug and number here is invented, so a passing test cannot rest on this case's
data. What is checked is the property each function promises: the proliferation correction
removes exactly the declared covariate, a hit needs a real rise (not only a small fall), a
control that names a missing inducer fails, and the rubric caps a failed-control row.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from mva.drugs.proteome import (
    ProteomeMatrix,
    Response,
    breadth,
    control_outcome,
    fit_corrected,
    rank_responses,
    robust_z,
    score_correlations,
    set_score,
    z_matrix,
)
from mva.drugs.proteome_run import ControlSpec, ProteomePlan, run_dataset
from mva.drugs.proteome_sets import ALIASES, SAC_MODULE, TIROSH_G2M, TIROSH_S, members
from mva.drugs.proteome_sources import collapse, compound_of, drug_means, read_wide_log2fc
from mva.drugs.proteome_tables import control_rows, hit_rows, protein_strength, write_tsv

SET = tuple(f"CYC{i}" for i in range(12))


def matrix(rows: dict[str, list[float]], perturbations: list[str]) -> ProteomeMatrix:
    genes = tuple(rows)
    return ProteomeMatrix(genes, tuple(perturbations), np.array([rows[g] for g in genes]), "test")


def synthetic(
    n: int = 40, *, spike: float = 2.0, seed: int = 7
) -> tuple[ProteomeMatrix, np.ndarray]:
    """A cell-cycle axis, a target that follows it, and one drug that raises the target."""
    rng = np.random.default_rng(seed)
    axis = rng.normal(0, 1, n)
    rows = {g: list(axis + rng.normal(0, 0.05, n)) for g in SET}
    target = axis * 1.3 + rng.normal(0, 0.05, n)
    target[0] += spike
    rows["TARGET"] = list(target)
    rows["NOISE"] = list(rng.normal(0, 1, n))
    return matrix(rows, [f"D{i}" for i in range(n)]), axis


class TestScoreAndFit:
    def test_score_is_the_median_of_set_members(self) -> None:
        m = matrix({"A": [1.0, 3.0], "B": [3.0, 5.0], "C": [5.0, 7.0]}, ["d1", "d2"])
        score, used = set_score(m, ["A", "B", "C"], min_members=3)
        assert used == ("A", "B", "C")
        assert list(score) == [3.0, 5.0]

    def test_score_refuses_a_set_that_is_barely_present(self) -> None:
        m = matrix({"A": [1.0]}, ["d1"])
        with pytest.raises(ValueError, match="set members"):
            set_score(m, ["A", "ABSENT"], min_members=3)

    def test_a_perturbation_missing_most_members_scores_nan(self) -> None:
        m = matrix(
            {"A": [1.0, math.nan], "B": [2.0, math.nan], "C": [3.0, 4.0]}, ["full", "sparse"]
        )
        score, _ = set_score(m, ["A", "B", "C"], min_members=3)
        assert score[0] == 2.0
        assert math.isnan(score[1])

    def test_regression_removes_the_covariate_and_keeps_the_spike(self) -> None:
        m, axis = synthetic()
        fit = fit_corrected("TARGET", m.row("TARGET"), axis)
        assert fit.slope == pytest.approx(1.3, abs=0.05)
        assert fit.r2 > 0.9  # one spiked drug of 40 costs a little fit
        assert fit_corrected("TARGET", synthetic(spike=0.0)[0].row("TARGET"), axis).r2 > 0.99
        assert fit.z[0] > 10  # the spiked drug
        assert max(abs(z) for z in fit.z[1:]) < 5

    def test_a_target_that_only_follows_the_axis_has_no_outlier(self) -> None:
        m, axis = synthetic(spike=0.0)
        fit = fit_corrected("TARGET", m.row("TARGET"), axis)
        assert max(abs(z) for z in fit.z) < 5

    def test_fit_refuses_too_few_usable_perturbations(self) -> None:
        with pytest.raises(ValueError, match="fewer than 3"):
            fit_corrected("T", np.array([1.0, 2.0]), np.array([1.0, 2.0]))

    def test_robust_z_of_a_flat_residual_is_nan_not_infinity(self) -> None:
        assert np.isnan(robust_z(np.zeros(5))).all()


class TestRankingAndHits:
    def test_a_fall_smaller_than_expected_is_not_a_hit(self) -> None:
        # The target drops, but far less than the cell cycle: a big z, a negative raw value.
        m, axis = synthetic(spike=0.0)
        values = m.values.copy()
        values[m.index()["TARGET"], 0] = -0.2
        axis = axis.copy()
        axis[0] = -3.0
        shifted = ProteomeMatrix(m.genes, m.perturbations, values, "test")
        fit = fit_corrected("TARGET", shifted.row("TARGET"), axis)
        ranked = rank_responses(shifted, fit, axis, z_min=3.0)
        top = ranked[0]
        assert top.perturbation == "D0"
        assert top.z > 3 and top.raw < 0 and not top.hit

    def test_perturbations_without_a_residual_rank_last(self) -> None:
        m, axis = synthetic()
        axis = axis.copy()
        axis[5] = math.nan
        fit = fit_corrected("TARGET", m.row("TARGET"), axis)
        ranked = rank_responses(m, fit, axis, z_min=3.0)
        assert ranked[-1].perturbation == "D5"
        assert ranked[-1].rank == 0 and not ranked[-1].hit

    def test_breadth_counts_the_share_of_proteins_a_drug_raises(self) -> None:
        m, axis = synthetic()
        values = m.values.copy()
        values[:, 1] += 6.0  # a drug that lifts everything
        wide = ProteomeMatrix(m.genes, m.perturbations, values, "test")
        share = breadth(z_matrix(wide, axis, min_n=10), wide.values, z_min=3.0)
        assert share[1] > 0.5
        assert share[2] < 0.2

    def test_score_correlations_place_the_target_high(self) -> None:
        m, axis = synthetic()
        r = score_correlations(m, axis)
        assert r[m.index()["TARGET"]] > 0.9
        assert abs(r[m.index()["NOISE"]]) < 0.5


class TestControls:
    def _responses(self, ranks: dict[str, tuple[int, float, bool]]) -> list[Response]:
        return [
            Response(name, raw=1.0 if hit else -1.0, score=0.0, residual=z, z=z, rank=rank, hit=hit)
            for name, (rank, z, hit) in ranks.items()
        ]

    def test_control_passes_only_when_every_inducer_is_a_top_hit(self) -> None:
        responses = self._responses(
            {
                "A": (1, 9.0, True),
                "B": (2, 8.0, True),
                **{f"X{i}": (i + 3, 0.0, False) for i in range(97)},
            }
        )
        tight = control_outcome("HSP", ["A", "B"], responses, top_fraction=0.02, z_min=3.0)
        assert tight.cut_rank == 1 and not tight.passed  # B sits at rank 2, outside the cut
        loose = control_outcome("HSP", ["A", "B"], responses, top_fraction=0.05, z_min=3.0)
        assert loose.passed and loose.ranks == {"A": 1, "B": 2}

    def test_an_inducer_the_dataset_lacks_fails_the_control(self) -> None:
        responses = self._responses({"A": (1, 9.0, True)})
        out = control_outcome("HSP", ["A", "MISSING"], responses, top_fraction=1.0, z_min=3.0)
        assert not out.passed and out.ranks["MISSING"] is None

    def test_an_inducer_outside_the_cut_fails(self) -> None:
        responses = self._responses(
            {"A": (50, 4.0, True), **{f"X{i}": (i + 1, 0.0, False) for i in range(99)}}
        )
        assert not control_outcome("HSP", ["A"], responses, top_fraction=0.02, z_min=3.0).passed


class TestRunDataset:
    def _plan(self) -> ProteomePlan:
        return ProteomePlan("TARGET", SET, z_min=3.0, top_fraction=0.1, broad_share=0.5)

    def test_a_failed_gating_control_marks_the_dataset_uninterpretable(self) -> None:
        m, _ = synthetic()
        gates = (ControlSpec("NOISE", ("D3",), True, "invented"),)
        out = run_dataset("d", "ctx", m, self._plan(), gates, with_breadth=False)
        assert not out.interpretable
        assert out.responses[0].perturbation == "D0"  # the target is still ranked

    def test_a_passing_control_leaves_the_dataset_interpretable(self) -> None:
        m, _ = synthetic()
        gates = (ControlSpec("TARGET", ("D0",), True, "the spiked drug"),)
        out = run_dataset("d", "ctx", m, self._plan(), gates, with_breadth=False)
        assert out.interpretable and out.fit["fit_n"] == 40

    def test_no_gating_control_is_never_interpretable(self) -> None:
        m, _ = synthetic()
        out = run_dataset("d", "ctx", m, self._plan(), (), with_breadth=False)
        assert not out.interpretable


class TestSetsAndSources:
    def test_members_follow_dataset_spelling_through_aliases(self) -> None:
        assert members(["CENPU"], {"MLF1IP"}) == ("MLF1IP",)
        assert members(["CENPU"], {"CENPU", "MLF1IP"}) == ("CENPU",)
        assert ALIASES["JPT1"] == ("HN1",)

    def test_excluded_genes_never_enter_the_score(self) -> None:
        assert "BUB1" in TIROSH_G2M and "BUB1" in SAC_MODULE
        got = members(TIROSH_G2M, set(TIROSH_G2M), SAC_MODULE)
        assert not set(got) & SAC_MODULE and len(got) < len(TIROSH_G2M)
        assert not set(TIROSH_S) & set(TIROSH_G2M)

    def test_collapse_keeps_the_best_covered_row_per_gene(self) -> None:
        genes, values = collapse([("A", [1.0, math.nan]), ("A", [2.0, 3.0]), ("B", [4.0, 5.0])])
        assert genes == ["A", "B"]
        assert list(values[0]) == [2.0, 3.0]

    def test_compound_of_splits_mitchell_labels(self) -> None:
        assert compound_of("Sildenafil_PDE5A") == "Sildenafil"
        assert compound_of("NVP-BEP800_HSP90AA1;HSP90B1") == "NVP-BEP800"
        assert compound_of("PlainName") == "PlainName"

    def test_drug_means_average_replicates(self) -> None:
        m = matrix({"A": [1.0, 3.0, 10.0]}, ["X_1", "X_2", "Y_1"])
        out = drug_means(m)
        assert out.perturbations == ("X", "Y")
        assert list(out.values[0]) == [2.0, 10.0]

    def test_read_wide_log2fc_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "m.csv"
        path.write_text("Gene Name,UniprotID,DrugA_T1,DrugB_T2\nG1,P1,0.5,NA\nG1,P2,0.1,0.2\n")
        m = read_wide_log2fc(path)
        assert m.perturbations == ("DrugA_T1", "DrugB_T2")
        assert list(m.values[0]) == [0.1, 0.2]  # the better-covered G1 row wins


class TestTables:
    def _row(self, **over: object) -> dict[str, object]:
        row = {
            "hit": True,
            "sensitivity_z": 4.0,
            "broad": False,
            "raw_log2fc": 0.5,
            "dataset_interpretable": True,
            "canonical_name": "X",
            "dataset": "d",
            "context": "c",
            "rank": 1,
            "robust_z": 4.0,
            "chembl_id": "",
            "breadth": 0.01,
        }
        row.update(over)
        return row

    def test_the_rubric_adds_up_and_caps_a_failed_control(self) -> None:
        full, why = protein_strength(self._row(), replicated=True, z_min=3.0)
        assert full == 1.0 and "replicated" in why
        capped, why2 = protein_strength(
            self._row(dataset_interpretable=False), replicated=True, z_min=3.0
        )
        assert capped == 0.10 and "control failed: capped" in why2

    def test_a_weak_hit_scores_below_a_strong_one(self) -> None:
        weak, _ = protein_strength(
            self._row(sensitivity_z=0.5, broad=True, raw_log2fc=0.05), replicated=False, z_min=3.0
        )
        strong, _ = protein_strength(self._row(), replicated=False, z_min=3.0)
        assert weak == 0.40 and strong > weak

    def test_write_tsv_writes_header_and_requested_columns(self, tmp_path: Path) -> None:
        path = tmp_path / "t.tsv"
        n = write_tsv(path, [{"a": 1, "b": 2}], ["b", "missing"])
        lines = path.read_text().splitlines()
        assert n == 1 and lines[0] == "b\tmissing" and lines[1] == "2\t"

    def test_hit_and_control_rows_carry_the_dataset_verdict(self) -> None:
        m, _ = synthetic()
        plan = ProteomePlan("TARGET", SET, z_min=3.0, top_fraction=0.1, broad_share=0.5)
        res = run_dataset(
            "d",
            "ctx",
            m,
            plan,
            (ControlSpec("TARGET", ("D0",), True, "spiked"),),
            with_breadth=False,
        )
        rows = hit_rows(res, lambda label: label, lambda name: (name, True, "id"), broad_share=0.5)
        assert rows[0]["dataset_interpretable"] is True and rows[0]["compound"] == "D0"
        assert control_rows(res)[0]["control_passed"] is True
