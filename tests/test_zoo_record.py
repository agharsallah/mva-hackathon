"""Step 1's allele record, built against a miniature warehouse — no patient data, no network.

Both schemas live in one in-memory DuckDB attached as ``pg``, so every statement
:mod:`mva.zoo.record` issues runs exactly as it would against the hosted PostgreSQL. The
rows come from ``fixtures/it4/records.tsv`` (200 synthetic alleles, chromosome 1 below
1,000,000, invented genes ``GENEA``–``GENEJ``); the four join tables are invented from it,
each with a deliberately different ``chrom`` spelling so the contig normalisation is
exercised rather than assumed.

What each group pins:

* the ``allele_id`` DuckDB computes and the one :func:`mva.zoo.types.allele_id` computes
  agree on every contig spelling — the whole coordinate-free design rests on that;
* an allele listed twice (two overlapping genes, two spellings) is **one** record;
* the read-only alleles arrive through the union and are flagged;
* ``--mask-catalogue`` nulls ``clin_sig`` and nothing else;
* the HGVS pass resumes from its checkpoint instead of re-asking;
* the write leaves a table, a parquet, a provenance manifest and a lineage edge that
  agree with each other.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb
import pytest

from mva.pipeline.variant import Variant
from mva.pipeline.vep_response import VepRecord
from mva.warehouse.settings import Postgres
from mva.zoo import record as rec
from mva.zoo.record_hgvs import Coordinate, hgvs_pass
from mva.zoo.types import allele_id

FIXTURE = Path("fixtures/it4/records.tsv")

CODING_ALLELES_COLUMNS = (
    "gene VARCHAR, gene_id VARCHAR, chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, "
    "allele_ix INTEGER, gt VARCHAR, zygosity VARCHAR, filter VARCHAR, qual DOUBLE, "
    "dp INTEGER, vaf DOUBLE, pgt VARCHAR, pid VARCHAR"
)
ANNOTATION_COLUMNS = (
    "chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, rsid VARCHAR, gene VARCHAR, "
    "consequence VARCHAR, impact VARCHAR, gnomad_af DOUBLE, gnomad_af_grpmax DOUBLE, "
    "clin_sig VARCHAR, annotated_at TIMESTAMP, source VARCHAR"
)
INSILICO_COLUMNS = ANNOTATION_COLUMNS.replace(
    "annotated_at TIMESTAMP",
    "am_pathogenicity DOUBLE, am_class VARCHAR, spliceai_ds_max DOUBLE, spliceai VARCHAR, "
    "exon_index INTEGER, exon_total INTEGER, annotated_at TIMESTAMP",
)

#: The confirmed pair's shape, transplanted onto two invented chromosome-1 alleles: one
#: truncating and one missense allele of one gene. Risk R9 / open question O7 of the plan
#: asks whether both land in a consequence class an MVP lane covers, and
#: ``consequence_classes`` is what answers it on day 1.
PAIR = [
    ("BUB1B", "1", 800_001, "C", "T", "stop_gained"),
    ("BUB1B", "1", 800_101, "G", "A", "missense_variant"),
]


def fixture_rows() -> list[dict[str, str]]:
    with FIXTURE.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def _number(text: str) -> float | None:
    return float(text) if text else None


@pytest.fixture
def rows() -> list[dict[str, str]]:
    return fixture_rows()


@pytest.fixture
def warehouse(rows):
    """The miniature warehouse, torn down after each test."""
    connection = make_warehouse(rows)
    yield connection
    connection.close()


def _call(gene: str, chrom: str, pos, ref: str, alt: str) -> tuple:
    """One ``coding_alleles`` row: what varies, then a constant PASS het call."""
    return (gene, f"ENSG_{gene}", chrom, int(pos), ref, alt, 1, "0/1", "het", "PASS",
            900.0, 40, 0.5, None, None)  # fmt: skip


def _ann(chrom, pos, ref, alt, gene, consequence, af=None, clin=None, wide=False) -> tuple:
    """One annotation row. ``wide`` adds iteration 2's six in-silico columns."""
    head = (chrom, int(pos), ref, alt, None, gene, consequence, "MODERATE", af, None, clin)
    return head + (None,) * (6 if wide else 0) + (None, "vep")


def _insert(connection, table: str, width: int, rows) -> None:
    connection.executemany(f"INSERT INTO {table} VALUES ({', '.join(['?'] * width)})", rows)


def make_warehouse(rows):
    """A two-schema DuckDB standing in for the hosted database.

    ``coding_alleles`` and ``it2_insilico_annotations`` spell the contig bare (``1``); the
    two annotation tables spell it ``chr1``. That mismatch is real — the repository holds
    both conventions — and every join below has to survive it. Three deliberate awkward
    rows: one allele listed under two overlapping genes, the same allele listed again under
    the other contig spelling, and a read-only allele the VCF also saw.
    """
    connection = duckdb.connect()
    connection.execute("ATTACH ':memory:' AS pg")
    for schema in ("results", "warehouse"):
        connection.execute(f"CREATE SCHEMA pg.{schema}")
    connection.execute(f"CREATE TABLE pg.results.coding_alleles ({CODING_ALLELES_COLUMNS})")
    connection.execute(f"CREATE TABLE pg.warehouse.coding_annotations ({ANNOTATION_COLUMNS})")
    connection.execute(f"CREATE TABLE pg.warehouse.it2_insilico_annotations ({INSILICO_COLUMNS})")
    connection.execute(f"CREATE TABLE pg.warehouse.it2_read_annotations ({ANNOTATION_COLUMNS})")

    coding = [row for row in rows if row["is_read_only"] == "false"]
    read_only = [row for row in rows if row["is_read_only"] == "true"]

    calls = [_call(row["gene"], "1", row["pos"], row["ref"], row["alt"]) for row in coding]
    calls.append(_call("GENEZ", "1", coding[0]["pos"], coding[0]["ref"], coding[0]["alt"]))
    calls.append(_call("GENEA", "chr1", coding[1]["pos"], coding[1]["ref"], coding[1]["alt"]))
    calls += [_call(gene, chrom, pos, ref, alt) for gene, chrom, pos, ref, alt, _c in PAIR]
    _insert(connection, "pg.results.coding_alleles", 15, calls)

    # Layer 2's VEP annotations cover every coding allele. The gene symbol is suffixed so a
    # test can prove the in-silico table wins the coalesce where both tables have a row.
    _insert(
        connection,
        "pg.warehouse.coding_annotations",
        13,
        [
            _ann(
                "chr1",
                row["pos"],
                row["ref"],
                row["alt"],
                f"{row['gene']}_ANN",
                row["consequence"],
                _number(row["af_gnomad"]),
                row["clin_sig"] or None,
            )
            for row in coding
        ]
        + [
            _ann("chr1", pos, ref, alt, f"{gene}_ANN", consequence, 0.0)
            for gene, _chrom, pos, ref, alt, consequence in PAIR
        ],
    )
    # Iteration 2's in-silico pass covered the first 100 alleles only.
    _insert(
        connection,
        "pg.warehouse.it2_insilico_annotations",
        19,
        [
            _ann(
                "1",
                row["pos"],
                row["ref"],
                row["alt"],
                row["gene"],
                row["consequence"],
                _number(row["af_gnomad"]),
                row["clin_sig"] or None,
                wide=True,
            )
            for row in coding[:100]
        ]
        + [
            _ann("1", pos, ref, alt, gene, consequence, 0.0, wide=True)
            for gene, _chrom, pos, ref, alt, consequence in PAIR
        ],
    )
    # The read-only alleles, plus one the VCF also saw: the union must not duplicate it.
    _insert(
        connection,
        "pg.warehouse.it2_read_annotations",
        13,
        [
            _ann(
                "chr1",
                row["pos"],
                row["ref"],
                row["alt"],
                row["gene"],
                row["consequence"],
                _number(row["af_gnomad"]),
                row["clin_sig"] or None,
            )
            for row in read_only + coding[:1]
        ],
    )
    return connection


class FakeVep:
    """An annotator with no network behind it: it answers from the query itself.

    ``skip`` drops every n-th allele so the run has a realistic gap, which is what makes
    ``p4_1a_fraction`` a number worth testing rather than always 1.0.
    """

    def __init__(self, skip: int = 0) -> None:
        self.calls = 0
        self.asked: list[Variant] = []
        self.skip = skip

    def annotate_many(self, variants):
        self.calls += 1
        self.asked.extend(variants)
        answered = []
        for index, variant in enumerate(variants):
            if self.skip and index % self.skip == 0:
                continue
            answered.append(
                VepRecord(
                    variant=variant,
                    transcript="ENST00000000001",
                    hgvsc="ENST00000000001.1:c.11C>T",
                    hgvsp="ENSP00000000001.1:p.Pro4Leu" if variant.alt == "G" else None,
                    uniprot="Q00000",
                    consequence="missense_variant",
                )
            )
        return answered

    def version(self) -> dict[str, str]:
        return {"release": "116", "assembly": "GRCh38"}

    def close(self) -> None:  # pragma: no cover - parity with the real client
        pass


SCHEMAS = rec.Schemas(warehouse="warehouse", results="results")


class TestAlleleIdInSql:
    """The one equality the coordinate-free design rests on."""

    @pytest.mark.parametrize("chrom", ["1", "chr1", "CHR1", "Chr1", "X", "chrX", "MT"])
    def test_sql_agrees_with_python_on_every_spelling(self, chrom):
        connection = duckdb.connect()
        connection.execute("CREATE TABLE t (chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR)")
        connection.execute("INSERT INTO t VALUES (?, ?, ?, ?)", [chrom, 123_456, "a", "g"])

        found = connection.execute(f"SELECT {rec.allele_id_sql()} FROM t").fetchone()

        assert found is not None
        assert found[0] == allele_id(chrom, 123_456, "a", "g")

    def test_every_fixture_row_agrees(self, warehouse, rows):
        built = rec.read_alleles(warehouse, SCHEMAS)
        expected = {
            allele_id(place.chrom, place.pos, place.ref, place.alt)
            for place in built.coordinates.values()
        }

        assert expected == set(built.coordinates)
        assert {row["allele_id"] for row in rows} <= set(built.coordinates)


class TestBuildRecords:
    def test_an_allele_listed_twice_is_one_record(self, warehouse, rows):
        built = rec.read_alleles(warehouse, SCHEMAS)
        keys = [record.allele_id for record in built.records]

        assert len(keys) == len(set(keys))
        # 200 fixture alleles + the two synthetic BUB1B ones; the two duplicate call rows
        # and the read-only allele that the VCF also saw add nothing.
        assert len(keys) == len(rows) + len(PAIR)

    def test_read_only_alleles_arrive_through_the_union_and_are_flagged(self, warehouse, rows):
        built = rec.read_alleles(warehouse, SCHEMAS)
        read_only = [record for record in built.records if record.is_read_only]
        expected = {row["allele_id"] for row in rows if row["is_read_only"] == "true"}

        assert {record.allele_id for record in read_only} == expected
        assert all(record.gene for record in read_only)

    def test_the_in_silico_table_wins_the_coalesce(self, warehouse, rows):
        built = {
            record.allele_id: record for record in rec.read_alleles(warehouse, SCHEMAS).records
        }
        coding = [row for row in rows if row["is_read_only"] == "false"]

        assert built[coding[0]["allele_id"]].gene == coding[0]["gene"]  # in-silico covered
        assert built[coding[150]["allele_id"]].gene == f"{coding[150]['gene']}_ANN"  # fallback

    def test_frequency_and_clinvar_class_come_across(self, warehouse, rows):
        built = {record.allele_id: record for record in rec.build_records(warehouse, SCHEMAS)}
        with_class = next(row for row in rows if row["clin_sig"])

        assert built[with_class["allele_id"]].clin_sig == with_class["clin_sig"]
        assert built[with_class["allele_id"]].af_gnomad == pytest.approx(
            float(with_class["af_gnomad"])
        )

    def test_mask_catalogue_nulls_clin_sig_and_nothing_else(self, warehouse):
        plain = rec.build_records(warehouse, SCHEMAS)
        masked = rec.build_records(warehouse, SCHEMAS, mask_catalogue=True)

        assert any(record.clin_sig for record in plain)
        assert all(record.clin_sig is None for record in masked)
        assert [record.af_gnomad for record in masked] == [record.af_gnomad for record in plain]
        assert [record.gene for record in masked] == [record.gene for record in plain]

    def test_settings_object_is_accepted_in_place_of_schema_names(self, warehouse):
        settings = Postgres(schema="warehouse", result_schema="results")

        assert rec.build_records(warehouse, settings) == rec.build_records(warehouse, SCHEMAS)

    def test_limit_trims_the_read(self, warehouse):
        assert len(rec.read_alleles(warehouse, SCHEMAS, limit=7).records) == 7

    def test_inputs_count_every_source_table(self, warehouse):
        inputs = rec.read_alleles(warehouse, SCHEMAS).inputs

        assert set(inputs) == {
            "results.coding_alleles",
            "warehouse.coding_annotations",
            "warehouse.it2_insilico_annotations",
            "warehouse.it2_read_annotations",
        }
        assert all(count > 0 for count in inputs.values())


class TestConfirmedPair:
    """Risk R9 / open question O7: is the pair inside an MVP lane's consequence class?"""

    def test_names_the_pair_by_gene_and_reports_both_classes(self, warehouse):
        records = rec.build_records(warehouse, SCHEMAS)

        classes = rec.consequence_classes(records, gene="BUB1B")

        assert len(classes) == 2
        assert sorted(classes.values()) == ["missense_variant", "stop_gained"]

    def test_an_absent_gene_yields_nothing_rather_than_guessing(self, warehouse):
        records = rec.build_records(warehouse, SCHEMAS)

        assert rec.consequence_classes(records, gene="NOTAGENE") == {}


class TestHgvsPass:
    def test_fills_every_spelling_the_annotator_knows(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)
        fake = FakeVep()

        passed = hgvs_pass(built.records, built.coordinates, fake, checkpoint_dir=tmp_path)

        assert all(record.hgvs_c for record in passed.records)
        assert all(record.transcript == "ENST00000000001" for record in passed.records)
        assert all(record.uniprot == "Q00000" for record in passed.records)
        assert passed.source == "ensembl-vep-rest release=116 assembly=GRCh38"

    def test_a_rerun_resumes_from_the_checkpoint_instead_of_re_asking(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)
        first, second = FakeVep(), FakeVep()

        one = hgvs_pass(built.records, built.coordinates, first, checkpoint_dir=tmp_path)
        two = hgvs_pass(built.records, built.coordinates, second, checkpoint_dir=tmp_path)

        assert first.calls > 0 and one.asked == len(built.records)
        assert second.calls == 0 and two.asked == 0
        assert two.resumed == len(built.records)
        assert [r.hgvs_c for r in two.records] == [r.hgvs_c for r in one.records]

    def test_the_checkpoint_is_jsonl_one_file_per_batch(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        hgvs_pass(
            built.records, built.coordinates, FakeVep(), checkpoint_dir=tmp_path, batch_size=50
        )

        files = sorted(tmp_path.glob("batch-*.jsonl"))
        assert len(files) == 5  # 202 alleles in batches of 50
        assert json.loads(files[0].read_text().splitlines()[0])["hgvsc"]

    def test_an_unanswered_allele_keeps_its_row(self, warehouse, tmp_path):
        built = rec.read_alleles(warehouse, SCHEMAS)

        passed = hgvs_pass(
            built.records, built.coordinates, FakeVep(skip=4), checkpoint_dir=tmp_path
        )

        assert len(passed.records) == len(built.records)
        assert any(record.hgvs_c is None for record in passed.records)

    def test_an_annotator_that_cannot_say_its_version_yields_no_label(self, warehouse, tmp_path):
        class Silent(FakeVep):
            version = None  # not callable

        built = rec.read_alleles(warehouse, SCHEMAS, limit=4)
        passed = hgvs_pass(built.records, built.coordinates, Silent(), checkpoint_dir=tmp_path)

        assert passed.source == ""


class TestCoordinateStaysBehind:
    def test_no_record_field_can_hold_a_position(self, warehouse):
        built = rec.read_alleles(warehouse, SCHEMAS)

        assert not hasattr(built.records[0], "pos")
        assert isinstance(next(iter(built.coordinates.values())), Coordinate)
