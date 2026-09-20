"""Protein windows: read the change out of ``hgvs_p``, cut the sequence, refuse the rest.

No network: every test injects either a ``{accession: sequence}`` dict or a fake fetcher.
No patient data: the sequences here are invented letters, and the records come from
``fixtures/it4/``.

The assertion that matters most is :meth:`TestWindowPair.test_a_disagreeing_residue_is_
refused`. A window built on the wrong isoform looks exactly like a good one, gets scored
with full confidence, and is wrong — so the reference residue ``hgvs_p`` names must match
the sequence at that position or nothing is emitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from mva.zoo import record_window
from mva.zoo.record_window import ProteinChange, SequenceCache
from mva.zoo.types import AlleleRecord

PROTEIN = "MKVLAAGIVGLNQYLERSTDWACHPQFMKVLAAGIVGLNQYLERSTDWACHPQFM" * 4


def record(allele: str, hgvs_p: str | None, consequence: str = "missense_variant") -> AlleleRecord:
    return AlleleRecord(allele_id=allele, hgvs_p=hgvs_p, consequence=consequence)


class TestParseProteinChange:
    def test_a_plain_substitution_gives_accession_position_and_both_residues(self) -> None:
        change = record_window.parse_protein_change("ENSP00000287598.7:p.Asn1002Lys")
        assert change == ProteinChange("ENSP00000287598", 1002, "N", "K")

    def test_the_version_suffix_is_dropped(self) -> None:
        bare = record_window.parse_protein_change("ENSP00000287598:p.Asn1002Lys")
        versioned = record_window.parse_protein_change("ENSP00000287598.14:p.Asn1002Lys")
        assert bare == versioned

    @pytest.mark.parametrize(
        "spelling",
        [
            "ENSP00000287598.7:p.Leu737Ter",  # a stop: no mutant protein to window
            "ENSP00000287598.7:p.Arg12fs",  # a frameshift
            "ENSP00000287598.7:p.Leu5=",  # synonymous
            "ENSP00000287598.7:p.Ala5_Gly7del",  # in-frame deletion
            "ENSP00000287598.7:p.Asn1002Asn",  # no change at all
            "ENST00000287598.7:c.2211C>G",  # a cDNA spelling, not a protein one
            "",
            None,
        ],
    )
    def test_anything_that_is_not_a_one_residue_substitution_is_refused(
        self, spelling: str | None
    ) -> None:
        assert record_window.parse_protein_change(spelling) is None

    def test_an_unknown_three_letter_code_is_refused_rather_than_guessed(self) -> None:
        assert record_window.parse_protein_change("ENSP1:p.Zzz10Ala") is None

    def test_selenocysteine_is_known(self) -> None:
        change = record_window.parse_protein_change("ENSP1:p.Sec10Ala")
        assert change is not None and change.ref_aa == "U"


class TestWindowPair:
    def test_the_two_windows_differ_at_exactly_one_letter(self) -> None:
        change = ProteinChange("P", 30, PROTEIN[29], "W")
        pair = record_window.window_pair(PROTEIN, change, radius=10)
        assert pair is not None
        reference, mutant = pair
        assert len(reference) == len(mutant) == 21
        assert sum(a != b for a, b in zip(reference, mutant, strict=True)) == 1

    def test_the_changed_residue_sits_in_the_middle(self) -> None:
        change = ProteinChange("P", 30, PROTEIN[29], "W")
        pair = record_window.window_pair(PROTEIN, change, radius=10)
        assert pair is not None and pair[1][10] == "W"

    def test_a_disagreeing_residue_is_refused(self) -> None:
        wrong = "W" if PROTEIN[29] != "W" else "A"
        assert record_window.window_pair(PROTEIN, ProteinChange("P", 30, wrong, "G"), 10) is None

    def test_a_position_past_the_end_is_refused(self) -> None:
        change = ProteinChange("P", len(PROTEIN) + 5, "A", "G")
        assert record_window.window_pair(PROTEIN, change, 10) is None

    def test_a_window_at_the_terminus_is_clamped_not_padded(self) -> None:
        change = ProteinChange("P", 2, PROTEIN[1], "W")
        pair = record_window.window_pair(PROTEIN, change, radius=10)
        assert pair is not None and len(pair[0]) == 12
        assert pair[0].startswith(PROTEIN[:2])

    def test_the_whole_protein_comes_back_when_the_radius_exceeds_it(self) -> None:
        short = "MKVL"
        pair = record_window.window_pair(short, ProteinChange("P", 2, "K", "R"), radius=64)
        assert pair == ("MKVL", "MRVL")


class TestSequenceCache:
    def test_a_written_sequence_reads_back(self, tmp_path: Path) -> None:
        cache = SequenceCache(tmp_path)
        cache.write("ENSP1", PROTEIN)
        assert cache.read("ENSP1") == PROTEIN
        assert cache.load(["ENSP1", "ENSP2"]) == {"ENSP1": PROTEIN}

    def test_an_unwritten_accession_is_none_not_an_error(self, tmp_path: Path) -> None:
        assert SequenceCache(tmp_path / "nothing-here").read("ENSP1") is None

    def test_a_corrupt_cache_file_is_treated_as_missing(self, tmp_path: Path) -> None:
        cache = SequenceCache(tmp_path)
        cache.directory.mkdir(parents=True, exist_ok=True)
        cache.path("ENSP1").write_text("{ not json")
        assert cache.read("ENSP1") is None

    def test_only_the_uncached_accessions_are_asked_for(self, tmp_path: Path) -> None:
        cache = SequenceCache(tmp_path)
        cache.write("ENSP1", "MKV")
        asked: list[list[str]] = []

        def fetcher(ids: Any) -> dict[str, str]:
            asked.append(list(ids))
            return dict.fromkeys(ids, "MKVL")

        got = record_window.fetch_sequences(["ENSP1", "ENSP2"], cache=cache, fetcher=fetcher)
        assert asked == [["ENSP2"]]
        assert got == {"ENSP1": "MKV", "ENSP2": "MKVL"}

    def test_a_fetched_sequence_is_cached_for_the_next_run(self, tmp_path: Path) -> None:
        cache = SequenceCache(tmp_path)
        record_window.fetch_sequences(
            ["ENSP9"], cache=cache, fetcher=lambda ids: {"ENSP9": PROTEIN}
        )
        assert SequenceCache(tmp_path).read("ENSP9") == PROTEIN

    def test_accessions_are_asked_for_in_batches(self, tmp_path: Path) -> None:
        sizes: list[int] = []
        record_window.fetch_sequences(
            [f"ENSP{i}" for i in range(7)],
            cache=SequenceCache(tmp_path),
            fetcher=lambda ids: (sizes.append(len(ids)), dict.fromkeys(ids, "MKV"))[1],
            batch=3,
        )
        assert sizes == [3, 3, 1]


class TestProteinWindows:
    def test_every_missense_record_with_a_sequence_gets_a_pair(self) -> None:
        records = [
            record("a", f"ENSP1:p.{_three(PROTEIN[29])}30Trp"),
            record("b", f"ENSP1:p.{_three(PROTEIN[9])}10Trp"),
        ]
        windows, report = record_window.protein_windows(
            records, sequences={"ENSP1": PROTEIN}, radius=5
        )
        assert set(windows) == {"a", "b"}
        assert report.complete == 2 and report.parsed == 2
        assert report.as_dict()["fraction_complete"] == 1.0

    def test_a_missing_sequence_is_counted_not_hidden(self) -> None:
        records = [record("a", "ENSP404:p.Ala10Gly")]
        windows, report = record_window.protein_windows(records, sequences={})
        assert windows == {}
        assert report.sequence_missing == 1 and report.complete == 0

    def test_a_residue_mismatch_is_its_own_number(self) -> None:
        wrong = "W" if PROTEIN[29] != "W" else "A"
        records = [record("a", f"ENSP1:p.{_three(wrong)}30Gly")]
        _, report = record_window.protein_windows(records, sequences={"ENSP1": PROTEIN})
        assert report.residue_mismatch == 1 and report.sequence_missing == 0

    def test_a_nonsense_allele_is_never_windowed(self) -> None:
        records = [record("a", "ENSP1:p.Leu737Ter", consequence="stop_gained")]
        windows, report = record_window.protein_windows(records, sequences={"ENSP1": PROTEIN})
        assert windows == {} and report.parsed == 0 and report.considered == 1

    def test_a_clamped_window_is_complete_but_counted_as_truncated(self) -> None:
        records = [record("a", f"ENSP1:p.{_three(PROTEIN[1])}2Trp")]
        _, report = record_window.protein_windows(records, sequences={"ENSP1": PROTEIN}, radius=64)
        assert report.complete == 1 and report.truncated_at_terminus == 1

    def test_the_network_is_only_touched_when_no_sequences_are_supplied(self) -> None:
        calls: list[Any] = []
        record_window.protein_windows(
            [record("a", "ENSP1:p.Ala10Gly")],
            cache=SequenceCache(Path("/nonexistent-cache")),
            fetcher=lambda ids: (calls.append(ids), {})[1],
        )
        assert calls == [["ENSP1"]]


class TestWriteWindows:
    @pytest.fixture
    def records_parquet(self, tmp_path: Path) -> Path:
        target = tmp_path / "records.parquet"
        con = duckdb.connect()
        con.execute(
            "CREATE TEMP TABLE r (allele_id VARCHAR, gene VARCHAR, "
            "protein_window_ref VARCHAR, protein_window_alt VARCHAR)"
        )
        con.executemany("INSERT INTO r VALUES (?, ?, NULL, NULL)", [["a", "GENEA"], ["b", "GENEB"]])
        con.execute("COPY (SELECT * FROM r) TO ? (FORMAT parquet)", [str(target)])
        con.close()
        return target

    def test_the_windows_land_in_the_parquet_and_nothing_else_changes(
        self, records_parquet: Path
    ) -> None:
        filled = record_window.write_windows(records_parquet, {"a": ("MKV", "MRV")})
        assert filled == 1
        con = duckdb.connect()
        rows = con.execute(
            "SELECT allele_id, gene, protein_window_ref, protein_window_alt "
            "FROM read_parquet(?) ORDER BY allele_id",
            [str(records_parquet)],
        ).fetchall()
        assert rows == [("a", "GENEA", "MKV", "MRV"), ("b", "GENEB", None, None)]

    def test_writing_no_windows_leaves_the_file_readable(self, records_parquet: Path) -> None:
        assert record_window.write_windows(records_parquet, {}) == 0
        con = duckdb.connect()
        count = con.execute("SELECT count(*) FROM read_parquet(?)", [str(records_parquet)])
        assert count.fetchall() == [(2,)]

    def test_no_staging_file_is_left_behind(self, records_parquet: Path) -> None:
        record_window.write_windows(records_parquet, {"a": ("MKV", "MRV")})
        assert not records_parquet.with_suffix(".windows.parquet").exists()

    def test_a_missing_record_set_names_the_command_that_makes_it(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="mva-zoo records"):
            record_window.write_windows(tmp_path / "nope.parquet", {})


def _three(one_letter: str) -> str:
    """The three-letter spelling of a one-letter residue — the tests' inverse map."""
    return next(key for key, value in record_window.AMINO_ACIDS.items() if value == one_letter)


class TestBisectingOnFailure:
    """Ensembl answers 500 for the whole POST when one id in it is unknown."""

    def test_one_bad_accession_does_not_cost_the_batch(self, tmp_path: Path) -> None:
        def fetcher(ids: Any) -> dict[str, str]:
            if "BAD" in ids:
                raise RuntimeError("500")
            return dict.fromkeys(ids, "MKV")

        got = record_window.fetch_sequences(
            ["A", "B", "BAD", "C"], cache=SequenceCache(tmp_path), fetcher=fetcher, batch=4
        )
        assert got == {"A": "MKV", "B": "MKV", "C": "MKV"}

    def test_the_bisection_stops_at_one_id(self, tmp_path: Path) -> None:
        asked: list[int] = []

        def fetcher(ids: Any) -> dict[str, str]:
            asked.append(len(ids))
            raise RuntimeError("500")

        assert (
            record_window.fetch_sequences(
                ["A", "B", "C", "D"], cache=SequenceCache(tmp_path), fetcher=fetcher, batch=4
            )
            == {}
        )
        assert sorted(asked) == [1, 1, 1, 1, 2, 2, 4]
