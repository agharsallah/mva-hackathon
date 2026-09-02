"""The compound-het pair matrix: the phase classifier, and the endpoint that serves it.

Two halves, both hermetic.

* **The classifier** (:mod:`mva.viz.phase`) is pure — dicts in, verdicts out — so every
  one of the four states is asserted directly against the semantics documented in
  ``ideation/data-findings.md`` §2.4 and ``methodology/006``.
* **The endpoint** is mocked below the database exactly as ``test_viz_api.py`` mocks it:
  ``queries.fetch`` is replaced, so a failure here means the route, the envelope or the
  matrix assembly is wrong, never that PostgreSQL was unreachable.

Positions in this file are three-digit counters. They are not coordinates.
"""

import pytest
from fastapi.testclient import TestClient

from mva.viz import phase, queries
from mva.viz.app import create_app
from mva.viz.cache import Cache


def variant(
    pos: int,
    alt: str = "A",
    *,
    gt: str = "0/1",
    pgt: str | None = None,
    pid: str | None = None,
    allele_ix: int = 1,
    af: float | None = None,
    impact: str | None = "MODERATE",
    annotated: bool = True,
) -> dict:
    """One ``panel_het_pairs`` row, with only the fields a test cares about set."""
    return {
        "gene": "BUB1B",
        "chrom": "15",
        "pos": pos,
        "ref": "G",
        "alt": alt,
        "allele_ix": allele_ix,
        "gt": gt,
        "qual": 800.0,
        "dp": 40,
        "vaf": 0.5,
        "pgt": pgt,
        "pid": pid,
        "rsid": None,
        "consequence": "missense_variant",
        "impact": impact,
        "gnomad_af": af,
        "gnomad_af_grpmax": af,
        "clin_sig": None,
        "annotated": annotated,
        "is_rare_recessive": None if not annotated else (af is None or af < 0.01),
        "is_protein_altering": None if not annotated else impact in ("HIGH", "MODERATE"),
    }


# ── the classifier: the four states ──────────────────────────────────────────────────


class TestClassify:
    def test_one_phase_set_two_different_haplotypes_is_trans(self):
        left = variant(500, pgt="0|1", pid="500_G_A")
        right = variant(520, pgt="1|0", pid="500_G_A")
        assert phase.classify(left, right) == "trans"

    def test_one_phase_set_the_same_haplotype_is_cis(self):
        left = variant(500, pgt="0|1", pid="500_G_A")
        right = variant(520, pgt="0|1", pid="500_G_A")
        assert phase.classify(left, right) == "cis"

    def test_different_phase_sets_resolve_nothing(self):
        """Two phase sets are two independent read-backed islands. Their relative order
        is not measured, and guessing it would invent the answer the case turns on."""
        left = variant(500, pgt="0|1", pid="500_G_A")
        right = variant(900, pgt="1|0", pid="900_C_T")
        assert phase.classify(left, right) == "unknown"

    def test_an_absent_phase_set_resolves_nothing(self):
        assert phase.classify(variant(500), variant(520)) == "unknown"

    def test_a_phase_set_with_no_pgt_resolves_nothing(self):
        left = variant(500, pgt=None, pid="500_G_A")
        right = variant(520, pgt="1|0", pid="500_G_A")
        assert phase.classify(left, right) == "unknown"

    def test_an_empty_string_counts_as_absent_not_as_a_shared_phase_set(self):
        """A warehouse read can hand back ``''`` where the VCF had no field. Two of those
        must not look like two variants in one phase set."""
        left = variant(500, pgt="", pid="")
        right = variant(520, pgt="", pid="")
        assert phase.classify(left, right) == "unknown"

    def test_the_two_alts_of_a_one_two_site_are_trans_by_genotype(self):
        left = variant(700, "A", gt="1/2", allele_ix=1)
        right = variant(700, "C", gt="1/2", allele_ix=2)
        assert phase.classify(left, right) == "trans"
        assert phase.is_auto_trans(left, right) is True

    def test_a_pgt_resolved_trans_pair_is_not_labelled_auto(self):
        left = variant(500, pgt="0|1", pid="500_G_A")
        right = variant(520, pgt="1|0", pid="500_G_A")
        assert phase.is_auto_trans(left, right) is False


# ── the matrix ───────────────────────────────────────────────────────────────────────

FOUR = [
    variant(500, "T", pgt="0|1", pid="500_G_A"),  # 0 ─┐ trans with 1
    variant(520, "C", pgt="1|0", pid="500_G_A"),  # 1 ─┘
    variant(700, "A", gt="1/2", allele_ix=1),  # 2 ─┐ auto-trans with 3
    variant(700, "C", gt="1/2", allele_ix=2),  # 3 ─┘
]


class TestMatrix:
    def test_only_the_resolved_cells_travel(self):
        pairs = phase.resolved(FOUR)
        assert [(p["i"], p["j"], p["phase"], p["auto"]) for p in pairs] == [
            (0, 1, "trans", False),
            (2, 3, "trans", True),
        ]

    def test_a_cis_pair_is_reported_so_the_grid_can_exclude_it(self):
        rows = [variant(500, "T", pgt="0|1", pid="P"), variant(520, "C", pgt="0|1", pid="P")]
        assert phase.resolved(rows) == [{"i": 0, "j": 1, "phase": "cis", "auto": False}]

    def test_indices_address_the_variant_list_not_a_coordinate(self):
        """The cell key is a position in the axis order, so no coordinate is repeated."""
        for pair in phase.resolved(FOUR):
            assert set(pair) == {"i", "j", "phase", "auto"}

    def test_the_summary_counts_the_whole_grid_including_what_is_unknown(self):
        found = phase.summarise(len(FOUR), phase.resolved(FOUR))
        assert found == {
            "n_het": 4,
            "n_pairs": 6,
            "n_trans": 2,
            "n_auto_trans": 1,
            "n_cis": 0,
            "n_unknown": 4,
            "pct_unknown": 66.67,
        }

    def test_a_gene_with_one_het_allele_has_no_pairs_and_no_percentage(self):
        """Zero pairs is not "0% unknown" — there is nothing to be unknown about."""
        found = phase.summarise(1, [])
        assert (found["n_pairs"], found["pct_unknown"]) == (0, None)

    def test_the_payload_carries_the_axis_the_cells_and_the_counts(self):
        found = phase.matrix("BUB1B", FOUR)
        assert set(found) == {"gene", "variants", "pairs", "summary"}
        assert found["gene"] == "BUB1B" and found["variants"] is FOUR

    def test_an_empty_gene_is_an_answer_not_a_crash(self):
        found = phase.matrix("TRIP13", [])
        assert found["pairs"] == [] and found["summary"]["n_pairs"] == 0


# ── the endpoint ─────────────────────────────────────────────────────────────────────

ROWS = [dict(row) for row in FOUR]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    def fetch(settings, sql, params=None):
        if "panel_het_pairs" in sql:
            gene = (params or [None])[0]
            return [dict(row) for row in ROWS] if gene == "BUB1B" else []
        if "mva_panel_grch38" in sql:
            gene = (params or [None])[0]
            # TRIP13 is in the panel and simply has no het PASS allele; ZZZ is not.
            return [{"chrom": "chr5", "start": 100, "end": 900}] if gene == "TRIP13" else []
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(queries.access, "fetch", fetch)
    with TestClient(
        create_app(settings=None, cache=Cache(tmp_path), origins=["http://localhost:5173"])
    ) as running:
        yield running


def test_the_matrix_answers_in_the_standard_envelope(client):
    body = client.get("/api/panel/het-pairs?gene=BUB1B").json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["cached_at"] is None, "cheap enough to be live"
    assert body["source"] == "pg.results.panel_het_pairs"


def test_the_payload_is_the_axis_the_resolved_cells_and_the_counts(client):
    data = client.get("/api/panel/het-pairs?gene=BUB1B").json()["data"]
    assert len(data["variants"]) == 4
    assert [(p["i"], p["j"], p["phase"]) for p in data["pairs"]] == [
        (0, 1, "trans"),
        (2, 3, "trans"),
    ]
    assert data["summary"]["n_unknown"] == 4


def test_the_raw_phase_fields_reach_the_client(client):
    """The classification is served, but so is the evidence for it — a client must be
    able to check the verdict rather than take it."""
    first = client.get("/api/panel/het-pairs?gene=BUB1B").json()["data"]["variants"][0]
    assert first["pgt"] == "0|1" and first["pid"] == "500_G_A"


def test_a_panel_gene_with_no_het_allele_is_an_empty_matrix_not_a_404(client):
    data = client.get("/api/panel/het-pairs?gene=TRIP13").json()["data"]
    assert data == {
        "gene": "TRIP13",
        "variants": [],
        "pairs": [],
        "summary": {
            "n_het": 0,
            "n_pairs": 0,
            "n_trans": 0,
            "n_auto_trans": 0,
            "n_cis": 0,
            "n_unknown": 0,
            "pct_unknown": None,
        },
    }


def test_an_unknown_gene_is_a_404_like_the_locus_route(client):
    response = client.get("/api/panel/het-pairs?gene=ZZZ")
    assert response.status_code == 404
    assert "ZZZ" in response.json()["detail"]


def test_the_gene_is_required(client):
    assert client.get("/api/panel/het-pairs").status_code == 422
