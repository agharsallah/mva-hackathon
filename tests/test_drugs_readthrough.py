"""The context model, its backoff, and the held-out control that has to be able to fail.

Synthetic measurements only: the point of these tests is the arithmetic and the control's
verdict, not any published value.
"""

from __future__ import annotations

import pytest

from mva.drugs.readthrough import (
    ControlResult,
    Measurement,
    ReadthroughModel,
    leave_one_context_out,
    read_measurements,
)
from mva.drugs.readthrough_dosage import (
    Allele,
    DrugEffect,
    Scenario,
    Threshold,
    evaluate,
    nearest_threshold,
)


def _m(context: str, stop: str, plus4: str, value: float, drug: str = "D") -> Measurement:
    return Measurement(context, stop, plus4, drug, value, "percent", "assay", "PMID:0")


def test_prediction_uses_the_most_specific_cell_and_says_so() -> None:
    model = ReadthroughModel([_m("a", "UGA", "C", 2.0), _m("b", "UGA", "C", 4.0)])
    guess = model.predict("D", "UGA", "C")
    assert guess.value == pytest.approx(3.0)
    assert guess.level == "stop+4"
    assert guess.rows == 2
    assert guess.contexts == ("a", "b")


def test_backoff_to_stop_then_drug_then_nothing() -> None:
    rows = [_m("a", "UGA", "C", 2.0), _m("b", "UGA", "A", 4.0), _m("c", "UAG", "G", 1.0)]
    model = ReadthroughModel(rows)
    assert model.predict("D", "UGA", "G").level == "stop"  # two UGA rows, no UGA G cell
    assert model.predict("D", "UAA", "G").level == "drug"  # no UAA row at all
    assert model.predict("other", "UGA", "C").usable is False


def test_dna_spelling_is_normalised_to_rna() -> None:
    model = ReadthroughModel([_m("a", "TGA", "T", 2.0), _m("b", "UGA", "U", 4.0)])
    assert model.predict("D", "TGA", "T").rows == 2


def test_one_model_one_unit() -> None:
    mixed = [_m("a", "UGA", "C", 2.0), Measurement("b", "UGA", "C", "D", 3.0, "fold", "x", "y")]
    with pytest.raises(ValueError, match="one unit"):
        ReadthroughModel(mixed)


def _series(values: dict[str, tuple[str, str, float]]) -> list[Measurement]:
    return [
        _m(f"{name}{i}", stop, plus4, value + i * 0.01)
        for name, (stop, plus4, value) in values.items()
        for i in (0, 1, 2)
    ]


def test_control_passes_when_context_really_drives_the_value() -> None:
    """Two contexts per (stop, +4) cell, so holding one out still leaves the cell populated."""
    rows = _series(
        {
            "ugac": ("UGA", "C", 8.0),
            "ugaa": ("UGA", "A", 4.0),
            "uagg": ("UAG", "G", 2.0),
            "uaag": ("UAA", "G", 1.0),
        }
    )
    result = leave_one_context_out(rows, "D", min_contexts=4)
    assert isinstance(result, ControlResult)
    assert result.contexts == 12
    assert result.passed
    assert result.spearman is not None and result.spearman > 0.8
    assert result.pair_accuracy is not None and result.pair_accuracy > 0.8


def test_control_fails_when_the_value_is_unrelated_to_context() -> None:
    """Same four cells, but the values inside a cell are as far apart as across cells."""
    rows = [
        _m("a", "UGA", "C", 1.0),
        _m("b", "UGA", "C", 8.0),
        _m("c", "UGA", "A", 2.0),
        _m("d", "UGA", "A", 7.0),
        _m("e", "UAG", "G", 3.0),
        _m("f", "UAG", "G", 6.0),
    ]
    result = leave_one_context_out(rows, "D", min_contexts=4)
    assert result.passed is False
    assert result.spearman is not None and result.spearman < 0.5


def test_control_refuses_a_drug_with_too_few_contexts() -> None:
    result = leave_one_context_out([_m("a", "UGA", "C", 1.0)], "D")
    assert result.passed is False
    assert "contexts measured" in result.reason


def test_measurements_round_trip_through_a_tsv(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "m.tsv"
    path.write_text(
        "context\tstop\tplus4\tdrug\tvalue\tunit\tassay\tsource\n"
        "a\tUGA\tC\tD\t2.5\tpercent\tdual-luciferase\tPMID:1\n",
        encoding="utf-8",
    )
    rows = read_measurements(path)
    assert rows == [Measurement("a", "UGA", "C", "D", 2.5, "percent", "dual-luciferase", "PMID:1")]


def test_dosage_arithmetic_and_drug_effect() -> None:
    stop = Allele("stop", mrna=0.2, protein_per_mrna=1.0, full_length=0.0, specific_activity=1.0)
    missense = Allele(
        "missense", mrna=1.0, protein_per_mrna=0.3, full_length=1.0, specific_activity=1.0
    )
    untreated = evaluate(Scenario("now", (stop, missense)))
    assert untreated.total == pytest.approx(0.15)
    assert untreated.drug == "none"
    assert untreated.gain == 0.0

    drug = DrugEffect(
        "readthrough", applies_to="stop", nmd_escape_to=0.5, readthrough=0.02, product_activity=0.5
    )
    treated = evaluate(Scenario("treated", (stop, missense), drug=drug))
    assert treated.total == pytest.approx(0.15 + 0.5 * 0.5 * 0.02 * 0.5)
    assert treated.gain > 0


def test_allele_fractions_must_be_fractions() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        Allele("bad", mrna=1.4, protein_per_mrna=1.0, full_length=1.0, specific_activity=1.0)


def test_nearest_threshold_picks_the_closest_published_genotype() -> None:
    result = evaluate(
        Scenario(
            "now",
            (
                Allele("a", 1.0, 0.2, 1.0, 1.0),
                Allele("b", 0.1, 1.0, 0.0, 1.0),
            ),
        )
    )
    thresholds = (
        Threshold("wild type", 100.0, "healthy", "s"),
        Threshold("hypomorph", 11.0, "aneuploidy", "s"),
        Threshold("null", 0.0, "lethal", "s"),
    )
    assert result.percent == pytest.approx(10.0)
    assert nearest_threshold(result, thresholds) is not None
    picked = nearest_threshold(result, thresholds)
    assert picked is not None and picked.label == "hypomorph"
    assert nearest_threshold(result, ()) is None
