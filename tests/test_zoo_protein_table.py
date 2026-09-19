"""The per-protein lane: ``gene`` + ``hgvs_p`` → a table keyed by accession and ``R550Q``.

Everything here is synthetic — invented accessions, invented genes, invented scores. The
load-bearing assertions are that the wild-type residue is part of the key (so a
wrong-isoform match is unrepresentable) and that anything which is not a plain substitution
is silently unscored rather than mis-keyed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo.adapters import protein_table
from mva.zoo.types import AlleleRecord


class TestShortChange:
    @pytest.mark.parametrize(
        ("hgvs_p", "expected"),
        [
            ("ENSP00000000001.1:p.Arg550Gln", "R550Q"),
            ("ENSP00000000001:p.Met1Val", "M1V"),
            ("p.Trp26Cys", "W26C"),
        ],
    )
    def test_reads_a_substitution(self, hgvs_p: str, expected: str) -> None:
        assert protein_table.short_change(hgvs_p) == expected

    @pytest.mark.parametrize(
        "hgvs_p",
        [
            None,
            "",
            "ENSP00000000001.1:p.Arg550Ter",  # a stop: no row in a substitution table
            "ENSP00000000001.1:p.Arg550fs",  # a frameshift
            "ENSP00000000001.1:p.Arg550=",  # synonymous
            "ENSP00000000001.1:p.Arg550_Gln551del",  # a deletion
            "ENST00000000001.1:c.1649G>A",  # the cDNA spelling, not the protein one
        ],
    )
    def test_declines_anything_that_is_not_a_substitution(self, hgvs_p: str | None) -> None:
        assert protein_table.short_change(hgvs_p) is None


@pytest.fixture
def lane(tmp_path: Path) -> Any:
    """A two-gene table: GENEA has two isoforms, GENEB one, and a third gene is absent."""
    con = duckdb.connect()
    scores = tmp_path / "scores.parquet"
    genes = tmp_path / "genes.csv"
    con.execute(
        "COPY (SELECT * FROM (VALUES "
        "('U1', 'R10Q', -4.0), ('U1', 'K11E', -1.0), "  # isoform 1 of GENEA
        "('U1-2', 'R10Q', -6.0), "  # isoform 2, worse at the same residue
        "('U2', 'W5C', -2.5)"  # GENEB
        ") AS t(uniprot, hgvs_p, score)) TO ? (FORMAT parquet)",
        [str(scores)],
    )
    genes.write_text("id,gene\nU1,GENEA\nU1-2,GENEA\nU2,GENEB\n")
    return protein_table.ProteinTableAdapter(
        name="fake",
        version="fixture-1",
        parquet=scores,
        gene_map=genes,
        score_sign=-1,
        connection=con,
    )


def record(allele: str, gene: str | None, hgvs_p: str | None) -> AlleleRecord:
    return AlleleRecord(allele_id=allele, gene=gene, hgvs_p=hgvs_p, consequence="missense_variant")


class TestJoin:
    def test_scores_through_the_gene_map(self, lane: Any) -> None:
        rows = list(lane.score([record("a1", "GENEB", "ENSP1:p.Trp5Cys")]))
        assert [(item.allele_id, item.score) for item in rows] == [("a1", 2.5)]

    def test_takes_the_worst_isoform(self, lane: Any) -> None:
        rows = list(lane.score([record("a1", "GENEA", "ENSP1:p.Arg10Gln")]))
        # score_sign = -1 flips the published log-likelihood ratio, so the *largest*
        # oriented number is the most damaging: isoform U1-2's -6.0 becomes 6.0.
        assert rows[0].score == 6.0

    def test_a_wrong_residue_cannot_match(self, lane: Any) -> None:
        # The table's row at residue 10 of GENEA is an arginine. An allele that claims a
        # lysine there is a different protein, and the key simply does not exist.
        assert list(lane.score([record("a1", "GENEA", "ENSP1:p.Lys10Gln")])) == []

    def test_a_gene_the_map_does_not_carry_scores_nothing(self, lane: Any) -> None:
        assert list(lane.score([record("a1", "GENEZ", "ENSP1:p.Arg10Gln")])) == []

    def test_a_non_substitution_scores_nothing(self, lane: Any) -> None:
        assert list(lane.score([record("a1", "GENEA", "ENSP1:p.Arg10Ter")])) == []

    def test_coverage_counts_only_what_joined(self, lane: Any) -> None:
        records = [
            record("a1", "GENEA", "ENSP1:p.Arg10Gln"),
            record("a2", "GENEZ", "ENSP1:p.Arg10Gln"),
            record("a3", "GENEA", "ENSP1:p.Arg10Ter"),
        ]
        coverage = lane.coverage(records)
        assert (coverage.scored, coverage.total) == (1, 3)

    def test_a_missing_table_says_what_to_run(self, tmp_path: Path) -> None:
        lane = protein_table.ProteinTableAdapter(
            name="fake",
            version="v",
            parquet=tmp_path / "absent.parquet",
            gene_map=tmp_path / "absent.csv",
        )
        with pytest.raises(FileNotFoundError, match="fetch script"):
            list(lane.score([record("a1", "GENEA", "ENSP1:p.Arg10Gln")]))
