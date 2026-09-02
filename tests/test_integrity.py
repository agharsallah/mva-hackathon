"""Tests for the conservation checks and the VCF raw layer.

The point of these is adversarial: a fingerprint that cannot *fail* is worthless, so most
of what follows deliberately corrupts data and asserts the check notices. The corruptions
are the real ones — a dropped row, a NULL where an empty string was, a sentinel silently
retyped — not invented ones.
"""

import gzip
from pathlib import Path

import duckdb
import pytest

from mva.warehouse.integrity import compare, fingerprint, render, retyped
from mva.warehouse.vcfstage import (
    FILE_COLUMNS,
    RAW_COLUMNS,
    iter_raw,
    read_shape,
    source_digest,
    stage_raw,
    verify_roundtrip,
)

HEADER = "\n".join(
    [
        "##fileformat=VCFv4.2",
        "##contig=<ID=1,length=248956422>",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
    ]
)
RECORDS = [
    "1\t13273\t.\tG\tC\t385.77\tMQ40\tAC=2;AF=1\tGT:AD:DP\t1/1:0,13:13",
    "1\t14907\trs6\tA\tG\t.\tPASS\tAC=1;AF=0.5\tGT:AD:DP\t0/1:7,8:15",
    "2\t99\t.\tT\tA,G\t50\tLowQual\tAC=1,1\tGT:AD:DP\t1/2:0,5,6:11",
]


@pytest.fixture
def vcf(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.vcf"
    path.write_text(HEADER + "\n" + "\n".join(RECORDS) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def vcf_gz(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.vcf.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(HEADER + "\n" + "\n".join(RECORDS) + "\n")
    return path


@pytest.fixture
def con():
    connection = duckdb.connect()
    yield connection
    connection.close()


class TestVcfShape:
    def test_counts_only_the_double_hash_lines(self, vcf: Path):
        assert read_shape(vcf).header_lines == 2

    def test_finds_the_sample_name(self, vcf: Path):
        assert read_shape(vcf).sample == "SAMPLE"

    def test_recognises_a_single_sample_callset(self, vcf: Path):
        assert read_shape(vcf).is_single_sample

    def test_reads_gzip_the_same_as_plain(self, vcf: Path, vcf_gz: Path):
        assert read_shape(vcf) == read_shape(vcf_gz)


class TestIterRaw:
    def test_yields_every_record_with_a_line_number(self, vcf: Path):
        rows = list(iter_raw(vcf))
        assert len(rows) == len(RECORDS)
        assert [r[0] for r in rows] == ["1", "2", "3"]

    def test_keeps_fields_uninterpreted(self, vcf: Path):
        rows = list(iter_raw(vcf))
        assert rows[1][1:] == RECORDS[1].split("\t"), "no field may be rewritten"
        assert rows[2][5] == "A,G", "a multi-allelic ALT stays one field here"
        assert rows[1][6] == ".", "the missing-value marker survives as text"

    def test_a_malformed_record_raises_rather_than_vanishing(self, tmp_path: Path):
        path = tmp_path / "bad.vcf"
        path.write_text(HEADER + "\n" + RECORDS[0] + "\n1\t2\t3\n", encoding="utf-8")
        with pytest.raises(ValueError, match="has 3 fields"):
            list(iter_raw(path))

    def test_limit_stops_early(self, vcf: Path):
        assert len(list(iter_raw(vcf, limit=2))) == 2


class TestRoundTrip:
    def test_source_digest_ignores_the_header(self, vcf: Path, tmp_path: Path):
        other = tmp_path / "other.vcf"
        other.write_text(
            "##different\n" + HEADER.split("\n", 1)[1] + "\n" + "\n".join(RECORDS) + "\n",
            encoding="utf-8",
        )
        assert source_digest(vcf)[0] == source_digest(other)[0]

    def test_digest_changes_when_a_record_changes(self, vcf: Path, tmp_path: Path):
        other = tmp_path / "other.vcf"
        other.write_text(
            HEADER + "\n" + "\n".join(RECORDS).replace("13273", "13274") + "\n", encoding="utf-8"
        )
        assert source_digest(vcf)[0] != source_digest(other)[0]

    def test_live_read_reproduces_the_source_bytes(self, vcf: Path):
        assert verify_roundtrip(vcf)["identical"]

    def test_gzip_reproduces_the_source_bytes(self, vcf_gz: Path):
        assert verify_roundtrip(vcf_gz)["identical"]

    def test_staged_parquet_reproduces_the_source_bytes(self, vcf: Path, tmp_path: Path):
        out, written = stage_raw(vcf, tmp_path / "raw.parquet")
        assert written == len(RECORDS)
        assert verify_roundtrip(vcf, parquet=out)["identical"]

    def test_every_field_from_the_file_stays_text(self, vcf: Path, tmp_path: Path):
        out, _ = stage_raw(vcf, tmp_path / "raw.parquet")
        types = {
            row[0]: row[1]
            for row in duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{out}')").fetchall()
        }
        assert [*types] == list(RAW_COLUMNS)
        assert {types[name] for name in FILE_COLUMNS} == {"VARCHAR"}, (
            "typing a VCF field here would risk silent loss"
        )
        assert types["line_no"] == "BIGINT", "our own bookkeeping, not file data"


class TestFingerprint:
    def _make(self, con, rows):
        con.execute(
            "CREATE OR REPLACE TABLE t AS SELECT * FROM (VALUES " + ", ".join(rows) + ") AS v(a, b)"
        )

    def test_identical_data_has_no_discrepancies(self, con):
        self._make(con, ["('x', 1)", "('y', 2)"])
        con.execute("CREATE OR REPLACE TABLE u AS SELECT * FROM t")
        assert compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u")) == []

    def test_a_dropped_row_is_caught(self, con):
        self._make(con, ["('x', 1)", "('y', 2)"])
        con.execute("CREATE OR REPLACE TABLE u AS SELECT * FROM t WHERE a <> 'y'")
        found = compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u"))
        assert any(d.scope == "row count" and "-1" in d.detail for d in found)

    def test_a_changed_value_is_caught_at_equal_row_count(self, con):
        self._make(con, ["('x', 1)", "('y', 2)"])
        con.execute("CREATE OR REPLACE TABLE u AS SELECT replace(a,'y','z') AS a, b FROM t")
        found = compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u"))
        assert any(d.scope == "a" for d in found), "same counts, different content"

    def test_empty_string_turning_into_null_is_caught(self, con):
        con.execute("CREATE OR REPLACE TABLE t AS SELECT '' AS a")
        con.execute("CREATE OR REPLACE TABLE u AS SELECT NULL::VARCHAR AS a")
        found = compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u"))
        assert found, "the one loss DuckDB's CSV reader really causes must be detectable"

    def test_null_is_not_confused_with_the_string_NULL(self, con):  # noqa: N802 - "NULL" names the literal string under test
        con.execute("CREATE OR REPLACE TABLE t AS SELECT NULL::VARCHAR AS a")
        con.execute("CREATE OR REPLACE TABLE u AS SELECT 'NULL' AS a")
        assert compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u"))

    def test_checksum_ignores_row_order(self, con):
        self._make(con, ["('x', 1)", "('y', 2)"])
        con.execute("CREATE OR REPLACE TABLE u AS SELECT * FROM t ORDER BY a DESC")
        assert compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u")) == []

    def test_duplicates_do_not_cancel(self, con):
        con.execute("CREATE OR REPLACE TABLE t AS SELECT 'x' AS a UNION ALL SELECT 'x'")
        con.execute("CREATE OR REPLACE TABLE u AS SELECT 'y' AS a UNION ALL SELECT 'y'")
        assert compare(fingerprint(con, "t", "t"), fingerprint(con, "u", "u")), (
            "an XOR checksum would wrongly call these equal"
        )

    def test_a_pure_retype_is_reported_separately_not_as_loss(self, con):
        con.execute("CREATE OR REPLACE TABLE t AS SELECT '1' AS a")
        con.execute("CREATE OR REPLACE TABLE u AS SELECT 1::BIGINT AS a")
        before, after = fingerprint(con, "t", "t"), fingerprint(con, "u", "u")
        assert compare(before, after) == [], "content is the same"
        assert retyped(before, after) == [("a", "VARCHAR", "BIGINT")]

    def test_render_states_the_verdict(self, con):
        self._make(con, ["('x', 1)"])
        before = after = fingerprint(con, "t", "t")
        assert "No discrepancies" in render(before, after, [])
