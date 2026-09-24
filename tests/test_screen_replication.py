"""The rank-contrast engine on synthetic matrices — no network, no downloads, no screen.

Each test fixes one property the E4 result rests on: the sign convention (positive Cliff's
delta always means "the in-group is more sensitive", whichever end of the metric that is),
the refusal to test a group too small to carry a rank test, the Benjamini-Hochberg step-up,
and the group builders' handling of ties. A regression in any of these would silently flip
or inflate a published number.
"""

from __future__ import annotations

import numpy as np
import pytest

from mva.drugs.screen_replication import (
    Group,
    benjamini_hochberg,
    cliffs_delta,
    contrast_item,
    median_split,
    negative_control_sample,
    with_adjusted,
)
from mva.drugs.screen_replication_prism import core_broad_id, normalise_name


def group(inside: list[str], outside: list[str]) -> Group:
    return Group(
        name="synthetic",
        inside=frozenset(inside),
        outside=frozenset(outside),
        in_label="in",
        out_label="out",
        definition="synthetic fixture",
    )


class TestCliffsDelta:
    def test_perfect_separation_is_one(self) -> None:
        assert cliffs_delta(np.array([4.0, 5.0, 6.0]), np.array([1.0, 2.0, 3.0])) == 1.0

    def test_reversed_separation_is_minus_one(self) -> None:
        assert cliffs_delta(np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0])) == -1.0

    def test_identical_groups_are_zero(self) -> None:
        same = np.array([1.0, 2.0, 3.0])
        assert cliffs_delta(same, same) == 0.0


class TestTestItem:
    def test_lower_is_sensitive_flips_the_sign(self) -> None:
        """With a kill metric where lower means deader, a lower in-group is *more* sensitive."""
        values = {"a": -3.0, "b": -3.1, "c": -3.2, "x": 0.0, "y": 0.1, "z": 0.2}
        result = contrast_item(
            "drug", "DRUG", values, group(["a", "b", "c"], ["x", "y", "z"]), resamples=200
        )
        assert result.delta == 1.0
        assert result.p_raw is not None and result.p_raw < 0.06
        # Medians come back on the caller's own scale, not the internally flipped one.
        assert result.median_in == pytest.approx(-3.1)
        assert result.median_out == pytest.approx(0.1)

    def test_higher_is_sensitive_flips_back(self) -> None:
        values = {"a": 9.0, "b": 8.0, "c": 7.0, "x": 1.0, "y": 2.0, "z": 3.0}
        result = contrast_item(
            "drug",
            "DRUG",
            values,
            group(["a", "b", "c"], ["x", "y", "z"]),
            lower_is_sensitive=False,
            resamples=200,
        )
        assert result.delta == 1.0
        assert result.median_in == pytest.approx(8.0)

    def test_wrong_direction_gives_a_large_p_and_a_negative_delta(self) -> None:
        """A refuted prediction must be reportable, not silently two-sided."""
        values = {"a": 3.0, "b": 3.1, "c": 3.2, "x": 0.0, "y": 0.1, "z": 0.2}
        result = contrast_item(
            "drug", "DRUG", values, group(["a", "b", "c"], ["x", "y", "z"]), resamples=200
        )
        assert result.delta == -1.0
        assert result.p_raw is not None and result.p_raw > 0.9

    def test_too_few_lines_is_reported_not_tested(self) -> None:
        values = {"a": 1.0, "b": 2.0, "x": 3.0, "y": 4.0, "z": 5.0}
        result = contrast_item("drug", "DRUG", values, group(["a", "b"], ["x", "y", "z"]))
        assert result.status == "too-few-lines"
        assert result.p_raw is None
        assert result.delta is None
        assert result.n_in == 2

    def test_missing_values_are_dropped_before_counting(self) -> None:
        values = {"a": 1.0, "b": float("nan"), "c": 2.0, "x": 5.0, "y": 6.0, "z": 7.0}
        result = contrast_item("drug", "DRUG", values, group(["a", "b", "c"], ["x", "y", "z"]))
        assert result.n_in == 2
        assert result.status == "too-few-lines"

    def test_the_bootstrap_interval_is_deterministic_and_brackets_the_estimate(self) -> None:
        values = {f"i{k}": -float(k) for k in range(8)} | {f"o{k}": float(k) for k in range(8)}
        g = group([f"i{k}" for k in range(8)], [f"o{k}" for k in range(8)])
        first = contrast_item("d", "D", values, g, resamples=400, seed=7)
        second = contrast_item("d", "D", values, g, resamples=400, seed=7)
        assert first == second
        assert first.ci_low is not None and first.ci_high is not None
        assert first.ci_low <= first.delta <= first.ci_high  # type: ignore[operator]


class TestBenjaminiHochberg:
    def test_matches_the_worked_step_up(self) -> None:
        # m = 4; q_(i) = min over j >= i of m * p_(j) / j, clipped at 1.
        assert benjamini_hochberg([0.01, 0.02, 0.03, 0.04]) == pytest.approx(
            [0.04, 0.04, 0.04, 0.04]
        )

    def test_is_monotone_in_the_original_order(self) -> None:
        p = [0.9, 0.001, 0.5, 0.02]
        q = benjamini_hochberg(p)
        by_p = [q[i] for i in sorted(range(4), key=lambda i: p[i])]
        assert by_p == sorted(by_p)
        assert all(a <= b for a, b in zip(p, q, strict=True))

    def test_empty_family(self) -> None:
        assert benjamini_hochberg([]) == []

    def test_with_adjusted_skips_untested_rows(self) -> None:
        values = {"a": -1.0, "b": -2.0, "c": -3.0, "x": 0.0, "y": 1.0, "z": 2.0}
        g = group(["a", "b", "c"], ["x", "y", "z"])
        tested = contrast_item("t", "T", values, g, resamples=100)
        skipped = contrast_item("s", "S", {"a": 1.0, "x": 0.0, "y": 1.0, "z": 2.0}, g)
        out = {r.item_id: r for r in with_adjusted([tested, skipped])}
        assert out["s"].p_adjusted is None
        assert out["t"].p_adjusted == pytest.approx(out["t"].p_raw)  # family of one


class TestGroupBuilders:
    def test_median_split_drops_ties_at_the_median(self) -> None:
        g = median_split({f"l{i}": float(v) for i, v in enumerate([1, 2, 2, 2, 3])}, name="a")
        assert g.inside == frozenset({"l4"})
        assert g.outside == frozenset({"l0"})
        assert "ties at the median dropped" in g.definition

    def test_median_split_can_keep_ties_on_the_low_side(self) -> None:
        scores = {f"l{i}": float(v) for i, v in enumerate([1, 2, 2, 2, 3])}
        g = median_split(scores, name="a", exclude_ties=False)
        assert g.outside == frozenset({"l0", "l1", "l2", "l3"})

    def test_quantile_split_drops_the_middle_band(self) -> None:
        g = median_split({f"l{i}": float(i) for i in range(9)}, name="a", quantiles=(1 / 3, 2 / 3))
        assert g.inside and g.outside
        assert not (g.inside & g.outside)
        assert len(g.inside) + len(g.outside) < 9

    def test_non_finite_scores_are_ignored(self) -> None:
        g = median_split({"a": 1.0, "b": 3.0, "c": float("nan")}, name="a")
        assert "c" not in g.inside | g.outside


class TestControlSample:
    def test_is_seeded_and_excludes_the_candidates(self) -> None:
        universe = [f"d{i}" for i in range(50)]
        first = negative_control_sample(universe, exclude=["d0", "d1"], size=10, seed=3)
        second = negative_control_sample(universe, exclude=["d0", "d1"], size=10, seed=3)
        assert first == second
        assert len(first) == 10
        assert not {"d0", "d1"} & set(first)

    def test_never_asks_for_more_than_the_pool_holds(self) -> None:
        assert len(negative_control_sample(["a", "b"], exclude=[], size=10, seed=1)) == 2


class TestIdentifierKeys:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("VALPROIC ACID", "VALPROICACID"),
            ("Valproic-acid", "VALPROICACID"),
            (" hydroxychloroquine ", "HYDROXYCHLOROQUINE"),
            ("PLX-4720", "PLX4720"),
        ],
    )
    def test_name_normalisation(self, raw: str, expected: str) -> None:
        assert normalise_name(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("BRD:BRD-K09416995-001-39-9", "BRD-K09416995"),
            ("BRD-K09416995-001-11-1", "BRD-K09416995"),
            ("not-an-id", "NOT-AN-ID"),
        ],
    )
    def test_broad_id_core_is_release_independent(self, raw: str, expected: str) -> None:
        assert core_broad_id(raw) == expected
