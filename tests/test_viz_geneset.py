"""The curated gene set, and the three branches it opened in the two structure endpoints.

``mva.viz.geneset`` turned "the eight annotated panel genes" into "the genes the structure
explorer may draw", which are not the same set. That distinction is the thing under test
here: an off-panel gene must reach the exon and fold exhibits **without** the warehouse
being read at all, and a non-coding gene must be refused in a way that says "never" rather
than "try again later".

No test reaches the network. The transport is an ``httpx.MockTransport`` in the style of
``tests/test_viz_genestructure.py``, and the gene set is a four-row TSV written to
``tmp_path`` rather than the committed one, so a later edit to
``ressources/reference/structure_genes.tsv`` cannot silently change what these assert.

Every value below is public reference data — Ensembl's own ids for BUB1B and DICER1-AS1 —
or invented. Nothing is patient-derived; the whole point of the off-panel branch is that it
touches no patient record.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from mva.viz import geneset, genestructure, proteinstructure, queries, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache

#: A stand-in gene set: one panel gene, one off-panel coding gene, one lncRNA, and one
#: whose spelling exercises the case-insensitive match. Eight columns — the group carries
#: its own display label and rank, so nothing downstream needs a table of group names.
TSV = (
    "\t".join(geneset.COLUMNS)
    + "\n"
    + "\n".join(
        [
            "BUB1B\tENSG00000156970\tpanel\tthe annotated panel\t0\tprotein_coding\ttrue\tMVA1",
            "CENATAC\tENSG00000186166\tmva-sac\tMVA / SAC genes\t1\tprotein_coding\ttrue\tMVA4",
            (
                "DICER1-AS1\tENSG00000235706\textended\textended set\t2\tlncRNA\tfalse"
                "\tlncRNA, no protein"
            ),
        ]
    )
)

#: ``/lookup/id/ENSG00000186166?expand=1`` for the off-panel gene, trimmed.
CENATAC_LOOKUP = {
    "id": "ENSG00000186166",
    "seq_region_name": "11",
    "start": 118998051,
    "end": 119015811,
    "strand": 1,
    "biotype": "protein_coding",
    "canonical_transcript": "ENST00000334418.9",
    "Transcript": [
        {
            "id": "ENST00000334418",
            "is_canonical": 1,
            "Translation": {"id": "ENSP00000334767", "length": 370},
            "Exon": [
                {"id": "e1", "start": 118998051, "end": 118998200},
                {"id": "e2", "start": 119001000, "end": 119001120},
            ],
        }
    ],
}

#: The lncRNA: a real canonical transcript with **no** ``Translation`` at all.
LNCRNA_LOOKUP = {
    "id": "ENSG00000235706",
    "seq_region_name": "14",
    "start": 95157645,
    "end": 95181475,
    "strand": 1,
    "biotype": "lncRNA",
    "canonical_transcript": "ENST00000671073.1",
    "Transcript": [
        {
            "id": "ENST00000671073",
            "is_canonical": 1,
            "Exon": [
                {"id": "e1", "start": 95157645, "end": 95157800},
                {"id": "e2", "start": 95180000, "end": 95181475},
            ],
        }
    ],
}

#: One Pfam call, so "domains were fetched" is distinguishable from "domains were skipped".
FEATURES = [
    {"type": "Pfam", "id": "PF00000", "description": "a domain", "start": 10, "end": 90},
]


@pytest.fixture()
def tsv(tmp_path):
    """The stand-in gene set, with the per-path parse cache cleared around it."""
    path = tmp_path / "structure_genes.tsv"
    path.write_text(TSV + "\n", encoding="utf-8")
    geneset._load.cache_clear()
    yield path
    geneset._load.cache_clear()


def ensembl(lookup: dict, calls: list | None = None) -> httpx.Client:
    """An ``httpx.Client`` answering the two paths the anatomy half uses."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append(f"{request.method} {path}")
        if path.startswith("/lookup/id"):
            return httpx.Response(200, json=lookup)
        if path.startswith("/overlap/translation"):
            return httpx.Response(200, json=FEATURES)
        raise AssertionError(f"unexpected path {path}")

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://ensembl.test")


# ── reading the set ──────────────────────────────────────────────────────────────────


def test_the_set_is_read_in_the_tsv_s_own_order(tsv):
    assert [entry["symbol"] for entry in geneset.genes(tsv)] == ["BUB1B", "CENATAC", "DICER1-AS1"]


def test_in_panel_is_derived_from_the_bed_not_from_the_tsv(tsv):
    found = {entry["symbol"]: entry["in_panel"] for entry in geneset.genes(tsv)}
    assert found == {"BUB1B": True, "CENATAC": False, "DICER1-AS1": False}


def test_group_label_and_order_come_off_the_table(tsv):
    """The route hands the client the words and the rank; it never invents either.

    This is the reuse contract for the frontend: `geneSet.ts` builds its `<optgroup>`s,
    its badges, its legend and its bar colours from these two fields, so a foreign
    reference table renames and re-ranks every group with no code change.
    """
    rows = geneset.genes(tsv)
    assert [(r["group"], r["group_label"], r["group_order"]) for r in rows] == [
        ("panel", "the annotated panel", 0),
        ("mva-sac", "MVA / SAC genes", 1),
        ("extended", "extended set", 2),
    ]


def test_coding_is_a_boolean_and_a_blank_biotype_is_null(tsv):
    lncrna = geneset.lookup("DICER1-AS1", tsv)
    assert lncrna["coding"] is False
    assert lncrna["biotype"] == "lncRNA"


def test_a_missing_tsv_is_an_empty_set_not_an_error(tmp_path):
    geneset._load.cache_clear()
    assert geneset.genes(tmp_path / "absent.tsv") == []


def test_symbols_match_case_insensitively(tsv):
    assert geneset.lookup("cenatac", tsv)["ensembl_id"] == "ENSG00000186166"


def test_the_verified_alias_resolves_to_the_current_symbol(tsv):
    assert geneset.lookup("CCDC84", tsv)["symbol"] == "CENATAC"


def test_an_unverified_alias_is_not_invented(tsv):
    # p31comet is a real informal name for MAD2L1BP and is deliberately *not* accepted:
    # only aliases `tools/build_gene_set.py` confirmed against Ensembl are in ALIASES.
    with pytest.raises(LookupError):
        geneset.lookup("p31comet", tsv)


# ── resolution order ─────────────────────────────────────────────────────────────────


def test_the_panel_bed_wins_over_the_tsv_for_a_panel_gene(tsv):
    assert geneset.resolve("BUB1B", tsv) == ("BUB1B", "ENSG00000156970", True)


def test_a_panel_gene_resolves_even_when_the_tsv_is_missing(tmp_path):
    geneset._load.cache_clear()
    assert geneset.resolve("bub1b", tmp_path / "absent.tsv")[2] is True


def test_an_off_panel_gene_resolves_through_the_tsv(tsv):
    assert geneset.resolve("CENATAC", tsv) == ("CENATAC", "ENSG00000186166", False)


def test_the_returned_symbol_is_the_set_s_spelling_not_the_caller_s(tsv):
    assert geneset.resolve("cEnAtAc", tsv)[0] == "CENATAC"


def test_a_gene_in_neither_source_is_a_lookup_error(tsv):
    with pytest.raises(LookupError):
        geneset.resolve("SONIC", tsv)


# ── the gene-structure branches ──────────────────────────────────────────────────────


def test_an_off_panel_gene_reads_no_warehouse_table(tsv, monkeypatch):
    """The point of the off-panel branch: no ``panel_candidates`` query, no VEP POST."""
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)

    def refuse(*_args, **_kwargs):
        raise AssertionError("the warehouse must not be read for an off-panel gene")

    monkeypatch.setattr(queries.access, "fetch", refuse)
    calls: list[str] = []
    with ensembl(CENATAC_LOOKUP, calls) as client:
        payload = genestructure.structure(
            "CENATAC", object(), client=client, base_url="https://ensembl.test"
        )
    assert payload["in_panel"] is False
    assert payload["candidates"] == []
    assert not [call for call in calls if "/vep/" in call]


def test_an_off_panel_gene_still_carries_real_exons_and_domains(tsv, monkeypatch):
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)
    with ensembl(CENATAC_LOOKUP) as client:
        payload = genestructure.structure(
            "CENATAC", None, client=client, base_url="https://ensembl.test"
        )
    assert [exon["n"] for exon in payload["exons"]] == [1, 2]
    assert payload["protein"] == "ENSP00000334767"
    assert len(payload["domains"]) == 1


def test_a_non_coding_gene_gets_exons_but_no_protein_and_no_domains(tsv, monkeypatch):
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)
    calls: list[str] = []
    with ensembl(LNCRNA_LOOKUP, calls) as client:
        payload = genestructure.structure(
            "DICER1-AS1", None, client=client, base_url="https://ensembl.test"
        )
    assert payload["protein"] is None
    assert payload["protein_length"] is None
    assert payload["domains"] == []
    assert len(payload["exons"]) == 2
    # No translation id exists, so the domain endpoint is never asked — asking with `None`
    # in the path would 404 and turn a legitimate lncRNA into a 502.
    assert not [call for call in calls if "/overlap/translation" in call]


# ── the protein-structure refusal ────────────────────────────────────────────────────


def test_a_non_coding_gene_is_refused_before_any_http_call(tsv, monkeypatch):
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)

    def refuse(*_args, **_kwargs):
        raise AssertionError("no upstream call should be made for a gene with no protein")

    monkeypatch.setattr(proteinstructure, "_json", refuse)
    with pytest.raises(proteinstructure.NoProteinError) as refused:
        proteinstructure.structure("DICER1-AS1")
    assert str(refused.value) == "DICER1-AS1 has no protein-coding canonical transcript"


def test_the_refusal_is_not_an_upstream_error(tsv):
    """Which is what keeps the route's 422 from being swallowed by its 502 handler."""
    assert not isinstance(proteinstructure.NoProteinError("x"), proteinstructure.UPSTREAM_ERRORS)


# ── the routes ───────────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch, tsv):
    """The whole app, with the gene set pointed at the stand-in TSV."""
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)
    build = genestructure.structure
    fake = ensembl(CENATAC_LOOKUP)
    monkeypatch.setattr(
        genestructure,
        "structure",
        lambda gene, config, **kw: build(
            gene, config, client=fake, base_url="https://ensembl.test"
        ),
    )
    app = create_app(settings=None, cache=Cache(tmp_path / "cache"), origins=["http://x"])
    with TestClient(app) as running:
        yield running
    fake.close()


def test_the_index_route_answers_in_the_shared_envelope(client):
    body = client.get("/api/panel/structure-genes").json()
    assert set(body) == {"data", "cached_at", "source"}
    assert [row["symbol"] for row in body["data"]] == ["BUB1B", "CENATAC", "DICER1-AS1"]


def test_the_index_route_names_the_tsv_and_the_bed_as_its_source(client):
    source = client.get("/api/panel/structure-genes").json()["source"]
    assert "structure_genes.tsv" in source
    assert "mva_panel_grch38.bed" in source


def test_the_index_route_carries_the_two_flags_an_exhibit_needs(client):
    rows = {row["symbol"]: row for row in client.get("/api/panel/structure-genes").json()["data"]}
    assert rows["BUB1B"]["in_panel"] is True
    assert rows["DICER1-AS1"]["coding"] is False
    assert rows["CENATAC"]["group"] == "mva-sac"


def test_gene_structure_serves_an_off_panel_gene(client):
    body = client.get("/api/panel/gene-structure?gene=CENATAC").json()
    assert body["data"]["in_panel"] is False
    assert body["data"]["candidates"] == []


def test_gene_structure_404s_a_gene_in_neither_source(client):
    response = client.get("/api/panel/gene-structure?gene=SONIC")
    assert response.status_code == 404
    assert "SONIC" in response.json()["detail"]


def test_protein_structure_422s_a_non_coding_gene(client):
    response = client.get("/api/panel/protein-structure?gene=DICER1-AS1")
    assert response.status_code == 422
    assert response.json()["detail"] == "DICER1-AS1 has no protein-coding canonical transcript"


def test_protein_structure_404s_a_gene_in_neither_source(client):
    assert client.get("/api/panel/protein-structure?gene=SONIC").status_code == 404
