"""The two science endpoints: the register, its revisions, and the table that is not there.

Mocked below the API in the style of `test_viz_catalog.py`: `science.attached` is replaced
by a fake connection answering on a fragment of the SQL, so a failure here names the
contract — the `table_exists` flag, the column list, the revision ordering — and never the
network.

Every value is fabricated. **No genomic position appears in this file**, because a
hypothesis statement and an evidence claim are forbidden from carrying one, and a fixture
that broke that rule would be teaching the wrong shape.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from mva.viz import readstore, science
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
        self.seen.append((sql, params))
        for fragment, columns, rows in self.answers:
            if fragment in sql:
                return FakeCursor(columns, rows)
        raise AssertionError(f"unexpected SQL: {sql}")


#: Two claims, two revisions each — one that firmed up, one that was refuted. Nulls are
#: exercised where the register really carries them: an opening revision has no confidence,
#: no reasoning and no path yet.
HYPOTHESIS_ROWS = [
    (
        "H001",
        1,
        "2026-09-01T10:00:00",
        "step-2",
        "A recessive loss-of-function pair in BUB1B explains the phenotype.",
        "Two rare protein-altering alleles in BUB1B, both under 0.1% in gnomAD.",
        "Neither allele is rare, or only one is present in the callset.",
        None,
        "BUB1B",
        "proposed",
        None,
        None,
        "team",
        "iteration1",
    ),
    (
        "H001",
        2,
        "2026-09-02T11:30:00",
        "step-2",
        "A recessive loss-of-function pair in BUB1B explains the phenotype.",
        "Two rare protein-altering alleles in BUB1B, both under 0.1% in gnomAD.",
        "Neither allele is rare, or only one is present in the callset.",
        "panel-first",
        "BUB1B",
        "supported",
        0.69,
        "One supporting constraint row, one refuting absence.",
        "team",
        "iteration1",
    ),
    (
        "H002",
        1,
        "2026-09-01T10:05:00",
        "step-4",
        "The second allele is hiding in a filtered call.",
        "A non-PASS call in the same gene with balanced read support.",
        "No filtered call in the gene has balanced support.",
        None,
        None,
        "proposed",
        None,
        None,
        "team",
        "iteration1",
    ),
    (
        "H002",
        2,
        "2026-09-03T09:00:00",
        "step-4",
        "The second allele is hiding in a filtered call.",
        "A non-PASS call in the same gene with balanced read support.",
        "No filtered call in the gene has balanced support.",
        "rescue",
        None,
        "refuted",
        0.12,
        "Every filtered call in the gene is strand-skewed.",
        "team",
        "iteration1",
    ),
]

#: Four observations, both directions plus a neutral, and one with no lineage edge.
EVIDENCE_ROWS = [
    (
        1,
        "2026-09-01T12:00:00",
        "H001",
        "constraint",
        "supports",
        0.7,
        "BUB1B is depleted of loss-of-function variants in gnomAD.",
        "methodology/029",
        "lineage:panel_gene_constraint",
        "team",
    ),
    (
        2,
        "2026-09-01T12:10:00",
        "H001",
        "callset",
        "refutes",
        0.3,
        "Only one protein-altering allele in the gene passes the filters.",
        "methodology/030",
        None,
        "team",
    ),
    (
        3,
        "2026-09-02T08:00:00",
        "H002",
        "callset",
        "neutral",
        0.1,
        "Three filtered calls exist in the gene.",
        "methodology/031",
        None,
        "team",
    ),
    (
        4,
        "2026-09-03T08:30:00",
        "H002",
        "reads",
        "refutes",
        0.6,
        "All three filtered calls are strand-skewed in the raw reads.",
        "methodology/033",
        "lineage:read_probe",
        "team",
    ),
]

EXISTS = ("information_schema.tables", ("table_name",), [("hypotheses",)])
ABSENT = ("information_schema.tables", ("table_name",), [])


def connect(*answers):
    """A `science.attached` replacement that yields one fake connection."""
    fake = FakePostgres(list(answers))

    @contextmanager
    def attached(settings, read_only=False):
        yield fake

    return attached, fake


@pytest.fixture()
def populated(monkeypatch, tmp_path):
    attached, fake = connect(
        EXISTS,
        ("FROM pg.warehouse.hypotheses", science.HYPOTHESIS_COLUMNS, HYPOTHESIS_ROWS),
        ("FROM pg.warehouse.evidence", science.EVIDENCE_COLUMNS, EVIDENCE_ROWS),
    )
    monkeypatch.setattr(science, "attached", attached)
    return client_for(monkeypatch, tmp_path), fake


@pytest.fixture()
def missing(monkeypatch, tmp_path):
    attached, fake = connect(ABSENT)
    monkeypatch.setattr(science, "attached", attached)
    return client_for(monkeypatch, tmp_path), fake


def client_for(monkeypatch, tmp_path):
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    app = create_app(settings=SETTINGS, cache=Cache(tmp_path), origins=["http://x"])
    return TestClient(app)


# ── the shape every endpoint shares ──────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/api/science/hypotheses", "/api/science/evidence"])
def test_both_endpoints_answer_in_the_standard_envelope(populated, path):
    client, _ = populated
    body = client.get(path).json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["cached_at"] is None  # live, never cached
    assert body["source"].startswith("pg.warehouse.")


@pytest.mark.parametrize("path", ["/api/science/hypotheses", "/api/science/evidence"])
def test_the_payload_is_an_object_carrying_the_existence_flag(populated, path):
    client, _ = populated
    data = client.get(path).json()["data"]
    assert data["table_exists"] is True
    assert isinstance(data["rows"], list)


# ── the missing table ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/api/science/hypotheses", "/api/science/evidence"])
def test_a_register_that_was_never_written_is_a_flag_not_an_error(missing, path):
    client, _ = missing
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["data"] == {"table_exists": False, "rows": []}


@pytest.mark.parametrize("path", ["/api/science/hypotheses", "/api/science/evidence"])
def test_a_missing_register_is_never_created_by_a_read(missing, path):
    """A GET that materialised the table would turn 'no claim' into 'an empty register'."""
    client, fake = missing
    client.get(path)
    assert not any("CREATE" in sql.upper() for sql, _ in fake.seen)


@pytest.mark.parametrize(
    "path,table", [("/api/science/hypotheses", "hypotheses"), ("/api/science/evidence", "evidence")]
)
def test_the_existence_check_runs_before_the_read(missing, path, table):
    client, fake = missing
    client.get(path)
    assert len(fake.seen) == 1  # nothing was read after the miss
    sql, params = fake.seen[0]
    assert "information_schema.tables" in sql
    assert params == [SETTINGS.schema, table]


# ── the rows ─────────────────────────────────────────────────────────────────────────


def test_every_revision_is_served_not_only_the_latest(populated):
    client, _ = populated
    rows = client.get("/api/science/hypotheses").json()["data"]["rows"]
    assert len(rows) == 4
    assert [(r["hypothesis_id"], r["revision"]) for r in rows] == [
        ("H001", 1),
        ("H001", 2),
        ("H002", 1),
        ("H002", 2),
    ]


def test_revisions_are_ordered_by_claim_then_revision(populated):
    """Latest-revision-per-claim is the client's job, and it needs a stable order."""
    client, fake = populated
    client.get("/api/science/hypotheses")
    read = next(sql for sql, _ in fake.seen if "FROM pg.warehouse.hypotheses" in sql)
    assert "ORDER BY hypothesis_id, revision" in read


def test_an_opening_revision_keeps_its_nulls(populated):
    """A claim with no verdict yet has no confidence — rendered as a gap, never as zero."""
    client, _ = populated
    rows = client.get("/api/science/hypotheses").json()["data"]["rows"]
    opening = next(r for r in rows if r["hypothesis_id"] == "H001" and r["revision"] == 1)
    assert opening["confidence"] is None
    assert opening["reasoning"] is None
    assert opening["path"] is None
    assert opening["status"] == "proposed"


def test_a_refuted_claim_is_served_as_a_revision_not_a_deletion(populated):
    client, _ = populated
    rows = client.get("/api/science/hypotheses").json()["data"]["rows"]
    latest = next(r for r in rows if r["hypothesis_id"] == "H002" and r["revision"] == 2)
    assert latest["status"] == "refuted"
    assert any(r["hypothesis_id"] == "H002" and r["status"] == "proposed" for r in rows)


def test_evidence_carries_both_directions_and_a_null_lineage(populated):
    client, _ = populated
    rows = client.get("/api/science/evidence").json()["data"]["rows"]
    assert {r["direction"] for r in rows} == {"supports", "refutes", "neutral"}
    assert any(r["lineage_ref"] is None for r in rows)
    assert all(r["source_ref"] for r in rows)  # an unsourced row cannot exist


def test_the_columns_are_named_rather_than_star_selected(populated):
    """`SELECT *` would let a column added upstream change the browser's shape silently."""
    client, fake = populated
    client.get("/api/science/evidence")
    read = next(sql for sql, _ in fake.seen if "FROM pg.warehouse.evidence" in sql)
    assert "SELECT *" not in read
    for column in science.EVIDENCE_COLUMNS:
        assert column in read


def test_the_column_lists_match_the_register_ddl():
    """The API's shape is the register's shape, checked against the code that creates it."""
    from mva.science import evidence as evidence_module
    from mva.science import hypothesis as hypothesis_module

    for module, columns in (
        (hypothesis_module, science.HYPOTHESIS_COLUMNS),
        (evidence_module, science.EVIDENCE_COLUMNS),
    ):
        recorded = []

        class Recorder:
            def execute(self, sql, params=None, _recorded=recorded):
                _recorded.append(sql)

        module.ensure_table(Recorder(), "warehouse")
        ddl = recorded[0]
        body = ddl.split("(", 1)[1]
        declared = tuple(
            line.split()[0]
            for line in (raw.strip() for raw in body.splitlines())
            if line and line.split()[0].isidentifier()
        )
        assert declared == columns


def test_no_genomic_position_reaches_the_register_payload(populated):
    """Statements and claims name a gene and a consequence, never a coordinate."""
    client, _ = populated
    text = client.get("/api/science/hypotheses").text + client.get("/api/science/evidence").text
    import re

    assert not re.search(r"\bchr[0-9XYM]", text)
