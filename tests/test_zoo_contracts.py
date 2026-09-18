"""Wave-0 contracts of iteration 4: the steps exist, a claim can name its iteration, the
key is stable and coordinate-free, and the synthetic fixtures have the pinned shape."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mva.science import steps
from mva.science.cli import parser as science_parser
from mva.science.hypothesis import Hypothesis
from mva.zoo.types import (
    ALLELE_SCORES_COLUMNS,
    RECORD_COLUMNS,
    AlleleRecord,
    allele_id,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "it4"


def test_iteration4_declares_seven_research_steps():
    research = [s for s in steps.steps_for("iteration4") if s.takes_hypotheses]
    assert [s.slug for s in research] == [f"step-{n}" for n in range(1, 8)]
    assert all(s.iteration == "iteration4" for s in research)
    assert all(s.status == "planned" for s in research)
    assert steps.ITERATION == "iteration2", "iteration 4 runs beside iteration 2 (plan §5c O8)"


def test_hypothesis_add_takes_an_iteration():
    argv = [
        "hypothesis-add",
        "--iteration",
        "iteration4",
        "--step",
        "step-1",
        "--statement",
        "s",
        "--prediction",
        "p",
        "--refuted-by",
        "r",
    ]
    args = science_parser.build().parse_args(argv)
    assert args.iteration == "iteration4"
    claim = Hypothesis(
        step=args.step,
        statement=args.statement,
        prediction=args.prediction,
        refuted_by=args.refuted_by,
        iteration=args.iteration,
    )
    assert claim.filed_under == "iteration4"
    assert claim.step_record.title == "The allele record"
    assert claim.step_record is not steps.by_slug("step-1")


def test_hypothesis_add_rejects_an_unknown_iteration():
    argv = ["hypothesis-add", "--iteration", "iteration9", "--step", "step-1"]
    with pytest.raises(SystemExit):
        science_parser.build().parse_args(argv)


def test_allele_id_is_stable_and_contig_normalised():
    assert allele_id("chr1", 100000, "c", "g") == allele_id("1", 100000, "C", "G")
    assert len(allele_id("1", 100000, "C", "G")) == 16
    assert allele_id("1", 100000, "C", "G") != allele_id("1", 100000, "C", "T")


def test_masked_record_drops_every_catalogue_field():
    record = AlleleRecord(allele_id="x", gene="G", clin_sig="pathogenic", af_gnomad=0.1)
    masked = record.masked()
    assert masked.clin_sig is None
    assert masked.af_gnomad == 0.1
    assert masked.gene == "G"


def _tsv(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_fixture_records_carry_the_pinned_columns():
    rows = _tsv(FIXTURES / "records.tsv")
    assert len(rows) == 200
    pinned = {name for name, _ in RECORD_COLUMNS} - {"built_at", "source"}
    assert pinned <= set(rows[0])
    assert all(int(r["pos"]) < 1_000_000 and r["chrom"] == "1" for r in rows)
    ids = {r["allele_id"] for r in rows}
    assert len(ids) == 200
    assert all(
        allele_id(r["chrom"], int(r["pos"]), r["ref"], r["alt"]) == r["allele_id"] for r in rows
    )


@pytest.mark.parametrize("lane", ["alphamissense", "esm1b", "spliceai", "revel"])
def test_fixture_scores_join_the_records(lane):
    ids = {r["allele_id"] for r in _tsv(FIXTURES / "records.tsv")}
    rows = _tsv(FIXTURES / "scores" / f"{lane}.tsv")
    assert 0 < len(rows) <= 50
    assert {r["allele_id"] for r in rows} <= ids
    assert {"allele_id", "model", "version", "score"} <= set(rows[0])
    assert {name for name, _ in ALLELE_SCORES_COLUMNS} >= {"allele_id", "model", "version", "score"}


def test_fixture_pairs_have_exactly_one_confirmed_pair():
    rows = _tsv(FIXTURES / "pairs.tsv")
    assert len(rows) == 20
    assert sum(r["is_confirmed"] == "true" for r in rows) == 1
    assert all(r["allele_id_left"] != r["allele_id_right"] for r in rows)
