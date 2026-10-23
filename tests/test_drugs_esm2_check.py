"""The ESM-2 check's pure half: windows, the score table and the exact permutation tail."""

from __future__ import annotations

import math

import polars as pl
import pytest

from mva.drugs.esm2_check import (
    AMINO,
    evaluate,
    exact_tail,
    jobs,
    paired_difference,
    primary_start,
    score_table,
)


def test_primary_window_is_centred_and_clamped() -> None:
    assert primary_start(1, 1050) == 0
    assert primary_start(512, 1050) == 0
    assert primary_start(520, 1050) == 8
    assert primary_start(1050, 1050) == 28
    for site in range(1, 1051):
        start = primary_start(site, 1050)
        assert start < site <= start + 1022
    assert primary_start(5, 100) == 0  # shorter than the context: one window


def test_jobs_cover_primary_n_and_c_without_duplicates() -> None:
    planned = jobs(1050)
    assert len(planned) == len(set(planned))
    assert sum(1 for s, _ in planned if s == 0) == 1022
    assert sum(1 for s, _ in planned if s == 28) == 1022
    assert len(planned) == 1022 + 1022 + 27  # sites 513..539 have their own centred window
    with pytest.raises(ValueError):
        primary_start(0, 1050)


def _fake_log_probs(sequence: str, context: int) -> dict[tuple[int, int], list[float]]:
    out = {}
    for start, site in jobs(len(sequence), context):
        vec = [-3.0] * 20
        vec[AMINO.index(sequence[site - 1])] = -0.1  # the reference is likeliest
        vec[AMINO.index("P")] = -6.0 - 0.01 * start  # proline is worst, a bit window-dependent
        out[(start, site)] = vec
    return out


def test_score_table_signs_counts_and_windows() -> None:
    seq = "MKTAYIAKQRQISFVKSHFSRQ"
    table = score_table(seq, _fake_log_probs(seq, 16), context=16)
    assert table.height == 19 * len(seq)
    assert (table["wt"] != table["alt"]).all()
    row = table.filter(pl.col("change") == "K2A").row(0, named=True)
    assert row["damage"] == pytest.approx(2.9)
    assert row["llr"] == pytest.approx(-2.9)
    assert table.filter(pl.col("position") == 1)["damage_c"].null_count() == 19  # C omits site 1
    pro = table.filter(pl.col("alt") == "P")
    assert (pro["damage"] > table.filter(pl.col("alt") == "A")["damage"].max()).all()


def test_score_table_rejects_missing_or_nonfinite() -> None:
    seq = "MKTAYIAKQR"
    probs = _fake_log_probs(seq, 8)
    bad = dict(probs)
    bad[next(iter(bad))] = [math.nan] * 20
    with pytest.raises(ValueError):
        score_table(seq, bad, context=8)
    probs.pop((primary_start(5, len(seq), 8), 5))
    with pytest.raises(ValueError):
        score_table(seq, probs, context=8)


def test_exact_tail_matches_the_protocol_table() -> None:
    labels = [1, 1, 1, 1, 1, 0, 0, 0]
    assert exact_tail([8, 7, 6, 5, 4, 3, 2, 1], labels) == (1 / 56, 1, 56)
    assert exact_tail([8, 7, 6, 5, 3, 4, 2, 1], labels)[1] == 2  # 14/15
    assert exact_tail([8, 7, 6, 4, 3, 5, 2, 1], labels)[1] == 4  # 13/15
    tail, _, _ = exact_tail([1.0] * 8, labels)
    assert tail == 1.0  # all ties: every assignment reaches 0.5


def test_paired_difference_is_zero_for_identical_predictors() -> None:
    scores, labels = [5, 4, 3, 2, 1, 0.5, 6, 0], [1, 1, 1, 1, 1, 0, 0, 0]
    out = paired_difference(scores, scores, labels, n=50)
    assert out["difference"] == 0.0
    assert out["ci95"] == (0.0, 0.0)


def test_evaluate_joins_and_reports_three_predictors() -> None:
    seq = "MKTAYIAKQRQISFVKSHFSRQ"
    table = score_table(seq, _fake_log_probs(seq, 16), context=16)
    changes = ["K2P", "T3P", "A4P", "Y5P", "I6P", "A7G", "K8R", "Q9E"]
    labelled = pl.DataFrame({
        "change": changes, "label": ["x"] * 8, "y": [1] * 5 + [0] * 3,
        "ddg": [1.0, 2, 3, 4, 5, 0, 0.5, 6], "esm1b_llr": [-1.0] * 8,
    })  # fmt: skip
    out = evaluate(labelled, table, bootstrap=50)
    assert out["predictors"]["esm2_damage"]["auroc"] == 1.0
    assert out["predictors"]["esm2_damage"]["exact_hits"] == 1
    assert out["predictors"]["esm1b_llr_negated"]["auroc"] == 0.5
    assert set(out["paired"]) == {"esm2_minus_thermompnn_ddg", "esm2_minus_esm1b_llr_negated"}
    with pytest.raises(ValueError):
        evaluate(labelled.with_columns(change=pl.lit("K2Z")), table)
