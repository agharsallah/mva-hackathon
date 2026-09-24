"""Pure-logic tests for the two-source candidate-safety assembly (entry 152).

No network, no OnSIDES, no PharmCAT: synthetic gene calls and a synthetic label table, so
the rules that decide a flag are testable on their own. What matters here is not that the
numbers are right for this patient, but that the *wording* and the *flag logic* cannot
drift: "no call" must never become "normal", and "nothing flagged" must never become "safe".
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mva.drugs.patient_safety import (
    UNFLAGGED_WORDING,
    GeneCall,
    LabelMatch,
    active_terms,
    build_rows,
    combined_flag,
    describe_genome,
    read_mapping,
    wilson_interval,
    write_table,
)

DRUGS = [("drugA", "D4"), ("drugB", "D2"), ("drugC", "D3")]
GENES = {"druga": ["GENE1"], "drugb": ["GENE2"]}


def calls() -> dict[str, GeneCall]:
    return {
        "GENE1": GeneCall(
            "GENE1",
            "no call",
            True,
            40,
            0,
            "region has almost no calls",
            assumed_phenotype="Normal Function",
        ),
        "GENE2": GeneCall("GENE2", "Poor Metabolizer", True, 10, 6, "fully observed"),
        "GENE3": GeneCall("GENE3", "Normal Metabolizer", True, 10, 10, "fully observed"),
    }


def matches() -> dict[str, LabelMatch]:
    return {
        "druga": LabelMatch("drugA", labels_total=100, labels_matched=90, effects=("Myopathy",)),
        "drugb": LabelMatch(
            "drugB", labels_total=100, labels_matched=5, effects=("Nephrocalcinosis",)
        ),
        "drugc": LabelMatch("drugC", labels_total=50, labels_matched=0),
    }


def test_no_call_is_not_normal_and_raises_the_flag() -> None:
    phrase, flag, caveat = describe_genome(["GENE1"], calls())
    assert flag is True
    assert "no call" in phrase
    assert "Normal Function" in phrase, "the assumed phenotype is shown, as an assumption"
    assert "almost no calls" in caveat


def test_an_actionable_phenotype_raises_the_flag_and_a_normal_one_does_not() -> None:
    assert describe_genome(["GENE2"], calls())[1] is True
    assert describe_genome(["GENE3"], calls())[1] is False


def test_a_gene_the_caller_does_not_cover_is_a_flag_not_a_silence() -> None:
    phrase, flag, caveat = describe_genome(["NOT_IN_PANEL"], calls())
    assert flag is True
    assert "not covered" in phrase
    assert "direct genotyping" in caveat


def test_unflagged_is_never_worded_as_safe() -> None:
    assert combined_flag(False, False) == UNFLAGGED_WORDING
    assert "not evidence of safety" in UNFLAGGED_WORDING
    assert "safe" not in UNFLAGGED_WORDING.replace("not evidence of safety", "")


def test_combined_flag_names_the_sources() -> None:
    assert combined_flag(True, True) == "both sources flag a question"
    assert combined_flag(True, False) == "genome flags a question"
    assert combined_flag(False, True) == "phenotype flags a question"


@pytest.mark.parametrize(
    ("hits", "trials", "expected"),
    [(0, 0, (0.0, 0.0)), (0, 10, (0.0, 0.28)), (10, 10, (0.72, 1.0))],
)
def test_wilson_interval_stays_inside_zero_and_one(
    hits: int, trials: int, expected: tuple[float, float]
) -> None:
    low, high = wilson_interval(hits, trials)
    assert 0.0 <= low <= high <= 1.0
    assert low == pytest.approx(expected[0], abs=0.02)
    assert high == pytest.approx(expected[1], abs=0.02)


def test_rate_trigger_fires_only_above_the_comparison_rate() -> None:
    rows = {r.drug: r for r in build_rows(DRUGS, GENES, calls(), matches(), {}, 0.40)}
    assert rows["drugA"].phenotype_flag is True  # 0.90 > 0.40
    assert rows["drugB"].phenotype_flag is False  # 0.05 < 0.40, no exact term declared
    assert rows["drugC"].phenotype_flag is False  # nothing matched at all


def test_exact_term_trigger_fires_below_the_comparison_rate() -> None:
    rows = {
        r.drug: r
        for r in build_rows(
            DRUGS, GENES, calls(), matches(), {}, 0.40, exact_effects=["Nephrocalcinosis"]
        )
    }
    assert rows["drugB"].phenotype_flag is True
    assert "exact phenotype term" in rows["drugB"].phenotype_flag_reason
    assert "label rate" in rows["drugA"].phenotype_flag_reason


def test_a_drug_with_no_label_and_no_gene_is_unflagged_not_safe() -> None:
    (row,) = build_rows([("drugC", "D3")], GENES, calls(), matches(), {}, 0.40)
    assert row.combined_flag == UNFLAGGED_WORDING
    assert row.genome_call == "no pharmacogene tied to this drug"


def test_written_table_carries_no_genotype_and_every_column(tmp_path: Path) -> None:
    out = tmp_path / "candidate_safety.tsv"
    written = write_table(build_rows(DRUGS, GENES, calls(), matches(), {}, 0.40), out)
    assert written == 3
    with out.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [r["drug"] for r in rows] == ["drugA", "drugB", "drugC"]
    text = out.read_text()
    for forbidden in ("*1/*", "/*", "chr", "0/1", "1/1"):
        assert forbidden not in text, f"a genotype-shaped string leaked: {forbidden}"


def test_the_shipped_mapping_excludes_the_parental_term_and_keeps_its_reason() -> None:
    mapping = read_mapping(Path("ressources/track2/hpo_to_adverse_terms.tsv"))
    parental = [r for r in mapping if r["hpo_id"] == "HP:0200067"]
    assert parental, "the parental-history term must be recorded, not silently dropped"
    assert parental[0]["used_for_flag"] == "no"
    assert "parents" in parental[0]["rationale"]
    assert all(row["rationale"] for row in mapping), "every mapping row states its reason"
    assert "10029146" in active_terms(mapping), "nephrocalcinosis must be an active term"
