"""The data catalogue: the two endpoints that describe the data rather than read it.

Mocked below the API in the style of `test_viz_units.py`: `catalog.attached` is replaced
by a fake connection that answers on a fragment of the SQL, so a failure names the
assembly — the location string, the description mapping, the upload match, the null
lineage — and never the network.

Every value here is fabricated. No genomic position appears in this file, because the
catalogue never carries one.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from mva.viz import catalog, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.warehouse.settings import Postgres

#: Default schema names, so the module never reads the developer's `.env`.
SETTINGS = Postgres()


class FakeCursor:
    def __init__(self, columns, rows):
        self.description = [(name,) for name in columns]
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakePostgres:
    """Answers a query by matching a fragment of its SQL. Unmatched SQL is a failure."""

    def __init__(self, answers):
        self.answers = answers
        self.seen = []

    def execute(self, sql, params=None):
        self.seen.append(sql)
        for fragment, columns, rows in self.answers:
            if fragment in sql:
                return FakeCursor(columns, rows)
        raise AssertionError(f"unexpected SQL: {sql}")


OBJECT_COLUMNS = ("bucket", "object_key", "file_name", "kind", "role", "size_bytes",
                  "content_type", "sha256", "sha256_source", "hash_verified",
                  "version_id", "last_modified", "sample", "flowcell", "lane",
                  "read_num", "first_uploaded_at")

#: Four objects: the callset, its index, one FASTQ mate, and a document whose upload the
#: ledger never saw. The last one is the null case the contract has to carry.
OBJECT_ROWS = [
    ("mva", "source/SAMPLE_FLOW.vcf.gz", "SAMPLE_FLOW.vcf.gz", "vcf", "variants",
     315153971, "binary/octet-stream", "a" * 64, "publisher", True, "v-vcf",
     "2026-08-29T13:46:24", "SAMPLE", "FLOW", None, None, "2026-08-29T15:14:05"),
    ("mva", "source/SAMPLE_FLOW.vcf.gz.tbi", "SAMPLE_FLOW.vcf.gz.tbi", "index",
     "variant_index", 2343376, "binary/octet-stream", "b" * 64, "publisher", True,
     "v-tbi", "2026-08-29T13:46:26", "SAMPLE", "FLOW", None, None, "2026-08-29T15:11:44"),
    ("mva", "source/SAMPLE_FLOW_S16_L003_R2_001.fastq.gz",
     "SAMPLE_FLOW_S16_L003_R2_001.fastq.gz", "fastq", "reads", 10621354344,
     "binary/octet-stream", "c" * 64, "publisher", True, "v-fq",
     "2026-08-29T14:08:15", "SAMPLE", "FLOW", 3, 2, "2026-08-29T16:08:15"),
    ("mva", "source/Phenotype.docx", "Phenotype.docx", "document", "document", 16865,
     "binary/octet-stream", "d" * 64, "upload", True, "v-doc",
     "2026-08-29T13:11:40", None, None, None, None, None),
]

#: Six tables, including a name that exists in **both** schemas: the staged catalogue is
#: keyed by bare table name, so a description must not leak across the schema boundary.
TABLE_ANSWERS = [
    ("information_schema.tables", ("schema", "table"),
     [("results", "contig_counts"), ("results", "derivation_runs"),
      ("results", "stats_tstv"), ("warehouse", "contig_counts"),
      ("warehouse", "nobody_owns_this"), ("warehouse", "variants_raw")]),
    ("postgres_query", ("s", "t", "n"),
     [("results", "contig_counts", 25), ("results", "derivation_runs", 14),
      ("results", "stats_tstv", 1), ("warehouse", "contig_counts", 1690),
      ("warehouse", "nobody_owns_this", 3), ("warehouse", "variants_raw", 5012204)]),
    ("warehouse_catalog", ("table_name", "description"),
     [("contig_counts", "Variant records per contig."),
      ("hf_lfs_sha256", "A catalogue row for a table that was never ingested.")]),
    ("derivation_runs GROUP BY", ("derivation", "question"),
     [("stats_tstv", "What is the transition/transversion ratio?")]),
    ("data_lineage", ("target_schema", "target_table", "produced_at", "source_kind",
                      "source_ref", "tool"),
     [("results", "stats_tstv", "2026-08-31T17:57:32", "table",
       "warehouse.stats_summary", "mva-warehouse pg-derive"),
      ("warehouse", "variants_raw", "2026-08-29T21:02:49", "object",
       "s3://mva/source/SAMPLE_FLOW.vcf.gz", "mva-warehouse")]),
]


#: Only the objects query selects this column, so the fragment cannot match another.
OBJECTS_FRAGMENT = "first_uploaded_at"


@pytest.fixture()
def fake(monkeypatch):
    """The whole catalogue, answered from memory."""
    connection = FakePostgres([(OBJECTS_FRAGMENT, OBJECT_COLUMNS, OBJECT_ROWS),
                               *TABLE_ANSWERS])

    @contextmanager
    def attached(settings, read_only=False):
        yield connection

    monkeypatch.setattr(catalog, "attached", attached)
    return connection


def by_name(found: list[dict]) -> dict:
    return {row["file_name"]: row for row in found}


# ── the object inventory ─────────────────────────────────────────────────────────────

def test_the_location_is_built_from_the_bucket_and_the_key(fake):
    row = by_name(catalog.objects(settings=SETTINGS))["SAMPLE_FLOW.vcf.gz"]
    assert row["location"] == "s3://mva/source/SAMPLE_FLOW.vcf.gz"
    # both halves stay available, so a reader is not forced to parse the URL back apart
    assert row["object_key"] == "source/SAMPLE_FLOW.vcf.gz"


def test_every_contract_field_is_present_and_in_order(fake):
    row = catalog.objects(settings=SETTINGS)[0]
    assert list(row) == ["file_name", "object_key", "location", "kind", "role",
                         "description", "size_bytes", "content_type", "sha256",
                         "sha256_source", "hash_verified", "version_id", "last_modified",
                         "first_uploaded_at", "sample", "flowcell", "lane", "read_num"]


def test_an_object_with_a_ledger_row_carries_its_first_upload(fake):
    found = by_name(catalog.objects(settings=SETTINGS))
    assert found["SAMPLE_FLOW.vcf.gz"]["first_uploaded_at"] == "2026-08-29T15:14:05"


def test_an_object_the_ledger_never_saw_is_null_not_a_guess(fake):
    """A file fetched straight from the publisher never passed through the ledger."""
    found = by_name(catalog.objects(settings=SETTINGS))
    assert found["Phenotype.docx"]["first_uploaded_at"] is None
    assert found["Phenotype.docx"]["last_modified"] == "2026-08-29T13:11:40"


def test_the_objects_query_left_joins_rather_than_dropping_the_unmatched(fake):
    catalog.objects(settings=SETTINGS)
    assert "LEFT JOIN" in fake.seen[0]


# ── the description mapping ──────────────────────────────────────────────────────────

def test_each_role_gets_its_own_sentence(fake):
    found = by_name(catalog.objects(settings=SETTINGS))
    assert found["SAMPLE_FLOW.vcf.gz"]["description"].startswith("The callset:")
    assert "Tabix index" in found["SAMPLE_FLOW.vcf.gz.tbi"]["description"]
    assert "gzipped FASTQ" in found["SAMPLE_FLOW_S16_L003_R2_001.fastq.gz"]["description"]
    assert "Word document" in found["Phenotype.docx"]["description"]


def test_a_read_names_its_lane_and_its_mate(fake):
    found = by_name(catalog.objects(settings=SETTINGS))
    described = found["SAMPLE_FLOW_S16_L003_R2_001.fastq.gz"]["description"]
    assert described.endswith("Lane 3, mate R2, sample SAMPLE, flowcell FLOW.")


def test_an_object_with_no_parsed_metadata_gets_no_trailing_clause(fake):
    assert catalog.describe({"role": "document", "file_name": "notes.txt"}) == \
        catalog.DOCUMENTS[".txt"]


def test_an_unrecognised_role_claims_nothing_rather_than_guessing():
    described = catalog.describe({"role": "", "file_name": "mystery.bin"})
    assert described == catalog.ROLES[""]
    assert "nothing is claimed" in described


def test_an_unknown_document_extension_still_gets_the_generic_sentence():
    assert catalog.describe({"role": "document",
                             "file_name": "notes.rtf"}) == catalog.DOCUMENTS[""]


# ── the table catalogue ──────────────────────────────────────────────────────────────

def by_table(found: list[dict]) -> dict:
    return {f"{row['schema']}.{row['table']}": row for row in found}


def test_every_table_in_both_schemas_is_listed_with_an_exact_count(fake):
    found = by_table(catalog.tables(settings=SETTINGS))
    assert len(found) == 6
    assert found["warehouse.variants_raw"]["rows"] == 5012204
    assert found["warehouse.contig_counts"]["rows"] == 1690


def test_the_counts_are_one_pushed_down_statement_not_one_per_table(fake):
    catalog.tables(settings=SETTINGS)
    pushed = [sql for sql in fake.seen if "postgres_query" in sql]
    assert len(pushed) == 1
    assert pushed[0].count("UNION ALL") == 5  # six tables, five joins


def test_a_staged_table_is_described_by_the_warehouse_catalogue(fake):
    found = by_table(catalog.tables(settings=SETTINGS))
    assert found["warehouse.contig_counts"]["description"] == \
        "Variant records per contig."


def test_a_derived_table_is_described_by_its_derivations_question(fake):
    found = by_table(catalog.tables(settings=SETTINGS))
    assert found["results.stats_tstv"]["description"] == \
        "What is the transition/transversion ratio?"


def test_a_table_neither_source_owns_falls_back_to_the_in_code_one_liner(fake):
    found = by_table(catalog.tables(settings=SETTINGS))
    assert found["warehouse.variants_raw"]["description"] == \
        catalog.UNCATALOGUED["variants_raw"]
    assert found["results.derivation_runs"]["description"] == \
        catalog.UNCATALOGUED["derivation_runs"]


def test_a_table_nothing_describes_is_null_rather_than_invented(fake):
    found = by_table(catalog.tables(settings=SETTINGS))
    assert found["warehouse.nobody_owns_this"]["description"] is None


def test_a_catalogue_row_for_a_table_that_no_longer_exists_is_not_listed(fake):
    """`warehouse_catalog` still names `hf_lfs_sha256`; the database does not have it."""
    assert "warehouse.hf_lfs_sha256" not in by_table(catalog.tables(settings=SETTINGS))


def test_the_latest_lineage_edge_is_attached_to_its_table(fake):
    row = by_table(catalog.tables(settings=SETTINGS))["warehouse.variants_raw"]
    assert row["produced_at"] == "2026-08-29T21:02:49"
    assert row["source_kind"] == "object"
    assert row["source_ref"] == "s3://mva/source/SAMPLE_FLOW.vcf.gz"
    assert row["tool"] == "mva-warehouse"


def test_a_table_with_no_lineage_edge_carries_four_nulls(fake):
    """The ledgers were never derived from anything, and saying so is the honest answer."""
    row = by_table(catalog.tables(settings=SETTINGS))["warehouse.contig_counts"]
    assert (row["produced_at"], row["source_kind"], row["source_ref"], row["tool"]) == \
        (None, None, None, None)


def test_a_description_never_crosses_between_schemas(fake):
    """The staged catalogue describes `warehouse.contig_counts`. A results table that
    happens to share the name is a different table and must not borrow the sentence."""
    found = by_table(catalog.tables(settings=SETTINGS))
    assert found["warehouse.contig_counts"]["description"]
    assert found["results.contig_counts"]["description"] is None


def test_one_attach_serves_the_whole_table_catalogue(fake):
    catalog.tables(settings=SETTINGS)
    assert len(fake.seen) == 5  # list, counts, catalogue, questions, lineage


# ── the HTTP surface ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    with TestClient(create_app(settings=SETTINGS, cache=Cache(tmp_path), origins=[])) as run:
        yield run


def envelope(response) -> dict:
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["source"]
    return body


def test_the_object_catalogue_is_live_and_names_its_two_tables(client):
    body = envelope(client.get("/api/catalog/objects"))
    assert body["cached_at"] is None
    assert "source_objects" in body["source"] and "source_files" in body["source"]
    assert len(body["data"]) == 4


def test_the_table_catalogue_is_cached_and_a_refresh_rebuilds_it(client, fake):
    first = envelope(client.get("/api/catalog/tables"))
    assert first["cached_at"] is not None
    seen = len(fake.seen)
    client.get("/api/catalog/tables")
    assert len(fake.seen) == seen  # the second request never reached the database
    client.get("/api/catalog/tables", params={"refresh": "true"})
    assert len(fake.seen) > seen
