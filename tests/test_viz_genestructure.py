"""The gene-structure endpoint: Ensembl parsing, the protein lollipop, and the 502.

No test here reaches the network. The transport is an ``httpx.MockTransport``, in the
style of ``tests/test_annotate_vep.py``, and the warehouse is mocked below
``queries.fetch`` in the style of ``tests/test_viz_api.py``.

The reply fixtures are trimmed copies of live replies from ``https://rest.ensembl.org``
recorded in ``docs/step-0/methodology/040``. Their coordinates are **public reference
data** — Ensembl's own exon bounds for BUB1B and TP53. The variant positions are
fabricated; the proband's live only in the cache under gitignored ``build/``.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from mva.viz import genestructure, queries, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.genestructure import EnsemblError

# ── trimmed live replies ─────────────────────────────────────────────────────────────

#: BUB1B, plus strand. Two transcripts, one canonical and versioned in the pointer.
BUB1B_LOOKUP = {
    "id": "ENSG00000156970",
    "display_name": "BUB1B",
    "seq_region_name": "15",
    "start": 40160984,
    "end": 40221123,
    "strand": 1,
    "biotype": "protein_coding",
    "canonical_transcript": "ENST00000287598.11",
    "Transcript": [
        {
            "id": "ENST00000560120",
            "is_canonical": 0,
            "biotype": "protein_coding_CDS_not_defined",
            "Exon": [{"id": "ENSE00002546677", "start": 40161023, "end": 40161255}],
        },
        {
            "id": "ENST00000287598",
            "is_canonical": 1,
            "biotype": "protein_coding",
            "Translation": {"id": "ENSP00000287598", "length": 1050},
            "Exon": [
                {"id": "ENSE00001929183", "start": 40161069, "end": 40161255},
                {"id": "ENSE00003642586", "start": 40165053, "end": 40165196},
                {"id": "ENSE00003506275", "start": 40170062, "end": 40170121},
            ],
        },
    ],
}

#: TP53, minus strand — exon 1 is the *rightmost* box on a coordinate axis.
TP53_LOOKUP = {
    "id": "ENSG00000141510",
    "seq_region_name": "17",
    "start": 7661779,
    "end": 7687546,
    "strand": -1,
    "canonical_transcript": "ENST00000269305.9",
    "Transcript": [
        {
            "id": "ENST00000269305",
            "is_canonical": 1,
            "Translation": {"id": "ENSP00000269305", "length": 393},
            "Exon": [
                {"id": "e1", "start": 7687377, "end": 7687490},
                {"id": "e2", "start": 7676521, "end": 7676622},
                {"id": "e3", "start": 7676382, "end": 7676403},
            ],
        },
    ],
}

#: The translation overlap reply mixes domains with predictions and cross-references.
BUB1B_FEATURES = [
    {
        "type": "Pfam",
        "id": "PF08311",
        "start": 57,
        "end": 179,
        "description": "Mad3/Bub1 homology region 1",
        "interpro": "IPR013212",
    },
    {
        "type": "Gene3D",
        "id": "1.10.510.10",
        "start": 782,
        "end": 1042,
        "description": "Transferase(Phosphotransferase) domain 1",
    },
    {"type": "Gene3D", "id": "1.25.40.430", "start": 46, "end": 203, "description": ""},
    {
        "type": "SuperFamily",
        "id": "SSF56112",
        "start": 791,
        "end": 984,
        "description": "Protein kinase-like domain superfamily",
        "interpro": "IPR011009",
    },
    # everything below is filtered out
    {
        "type": "PANTHER",
        "id": "PTHR14030",
        "start": 21,
        "end": 1036,
        "description": "Mitotic spindle checkpoint protein Bub1/Mad3",
    },
    {"type": "sifts", "id": "5khu.Q", "start": 1, "end": 1050, "description": "Via SIFTS"},
    {"type": "alphafold", "id": "AF-O60566-F1", "start": 1, "end": 1050},
    {"type": "Seg", "id": "seg", "start": 209, "end": 218},
    {"type": "MobiDBLite", "id": "mobidb-lite", "start": 368, "end": 393},
    {"type": "ncoils", "id": "Coil", "start": 432, "end": 462},
]

#: Two fabricated alleles: one lands in the coding sequence, one does not.
CANDIDATES = [
    {
        "chrom": "15",
        "pos": 1500,
        "ref": "G",
        "alt": "A",
        "rsid": "rs1801516",
        "gene": "BUB1B",
        "consequence": "missense_variant",
        "impact": "MODERATE",
        "gnomad_af": None,
        "clin_sig": None,
        "qual": 812.5,
        "filter": "PASS",
        "gt": "0/1",
        "dp": 38,
        "vaf": 0.47,
        "is_rare_recessive": True,
        "is_protein_altering": True,
    },
    {
        "chrom": "15",
        "pos": 1600,
        "ref": "C",
        "alt": "T",
        "rsid": None,
        "gene": "BUB1B",
        "consequence": "splice_region_variant",
        "impact": "HIGH",
        "gnomad_af": 0.02,
        "clin_sig": None,
        "qual": 700.0,
        "filter": "PASS",
        "gt": "0/1",
        "dp": 30,
        "vaf": 0.5,
        "is_rare_recessive": False,
        "is_protein_altering": True,
    },
    {
        "chrom": "15",
        "pos": 1700,
        "ref": "A",
        "alt": "G",
        "rsid": None,
        "gene": "BUB1B",
        "consequence": "intron_variant",
        "impact": "MODIFIER",
        "gnomad_af": None,
        "clin_sig": None,
        "qual": 500.0,
        "filter": "PASS",
        "gt": "0/1",
        "dp": 20,
        "vaf": 0.5,
        "is_rare_recessive": True,
        "is_protein_altering": False,
    },
]

VEP_REPLY = [
    {
        "input": "15 1500 . G A . . .",
        "most_severe_consequence": "missense_variant",
        "transcript_consequences": [
            {"transcript_id": "ENST00000560120", "gene_symbol": "BUB1B"},
            {
                "transcript_id": "ENST00000287598",
                "gene_symbol": "BUB1B",
                "canonical": 1,
                "protein_start": 349,
                "protein_end": 349,
                "amino_acids": "Q/R",
                "impact": "MODERATE",
                "consequence_terms": ["missense_variant"],
            },
        ],
    },
    {
        "input": "15 1600 . C T . . .",
        "most_severe_consequence": "splice_region_variant",
        "transcript_consequences": [
            {
                "transcript_id": "ENST00000287598",
                "gene_symbol": "BUB1B",
                "canonical": 1,
                "impact": "LOW",
                "consequence_terms": ["splice_region_variant"],
            },
        ],
    },
]


# ── a mock Ensembl ───────────────────────────────────────────────────────────────────


def ensembl(
    lookup=BUB1B_LOOKUP,
    features=BUB1B_FEATURES,
    vep=VEP_REPLY,
    status: dict[str, int] | None = None,
    calls: list | None = None,
):
    """An ``httpx.Client`` answering the three paths this module uses."""
    status = status or {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if calls is not None:
            calls.append(f"{request.method} {path}")
        for fragment, code in status.items():
            if fragment in path:
                return httpx.Response(code, text="upstream said no")
        if path.startswith("/lookup/id"):
            return httpx.Response(200, json=lookup)
        if path.startswith("/overlap/translation"):
            return httpx.Response(200, json=features)
        if path.startswith("/vep/"):
            return httpx.Response(200, json=vep)
        raise AssertionError(f"unexpected path {path}")

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://ensembl.test")


@pytest.fixture()
def settings(monkeypatch):
    """A warehouse that answers the one query this module makes."""

    def fetch(_settings, sql, params=None):
        assert "panel_candidates" in sql, sql
        return [dict(row) for row in CANDIDATES]

    monkeypatch.setattr(queries, "fetch", fetch)
    return object()


# ── the panel gate ───────────────────────────────────────────────────────────────────


def test_panel_gene_resolves_the_bed_s_stable_id():
    assert genestructure.panel_gene("BUB1B") == "ENSG00000156970"


def test_panel_gene_refuses_an_off_panel_symbol():
    with pytest.raises(LookupError):
        genestructure.panel_gene("SONIC")


# ── transcript choice and exon numbering ─────────────────────────────────────────────


def test_canonical_pointer_is_matched_without_its_version():
    picked = genestructure.pick_transcript(BUB1B_LOOKUP)
    assert picked["id"] == "ENST00000287598"


def test_canonical_flag_is_the_fallback_when_the_pointer_is_absent():
    lookup = dict(BUB1B_LOOKUP, canonical_transcript=None)
    assert genestructure.pick_transcript(lookup)["id"] == "ENST00000287598"


def test_a_translating_transcript_wins_when_nothing_is_marked_canonical():
    lookup = {
        "id": "X",
        "Transcript": [{"id": "a"}, {"id": "b", "Translation": {"id": "p", "length": 10}}],
    }
    assert genestructure.pick_transcript(lookup)["id"] == "b"


def test_no_transcripts_is_an_ensembl_error_not_an_empty_track():
    with pytest.raises(EnsemblError):
        genestructure.pick_transcript({"id": "ENSG0", "Transcript": []})


def test_plus_strand_exons_are_numbered_left_to_right():
    numbered = genestructure.exons(BUB1B_LOOKUP["Transcript"][1], 1)
    assert [(e["n"], e["start"]) for e in numbered] == [(1, 40161069), (2, 40165053), (3, 40170062)]


def test_minus_strand_exon_one_is_the_highest_coordinate():
    numbered = genestructure.exons(TP53_LOOKUP["Transcript"][0], -1)
    assert [e["n"] for e in numbered] == [1, 2, 3]
    assert numbered[0]["start"] == 7687377
    assert numbered[-1]["start"] == 7676382


def test_exon_numbering_survives_an_api_that_returns_them_out_of_order():
    shuffled = {"Exon": list(reversed(BUB1B_LOOKUP["Transcript"][1]["Exon"]))}
    assert [e["start"] for e in genestructure.exons(shuffled, 1)] == [40161069, 40165053, 40170062]


# ── domain filtering ─────────────────────────────────────────────────────────────────


def test_only_domain_sources_survive_the_overlap_reply():
    with ensembl() as client:
        found = genestructure.fetch_domains(client, "https://ensembl.test", "ENSP00000287598")
    assert {d["source"] for d in found} == {"Pfam", "Gene3D", "SuperFamily"}


def test_predictions_and_structures_are_dropped_by_name():
    with ensembl() as client:
        found = genestructure.fetch_domains(client, "https://ensembl.test", "ENSP0")
    dropped = {"PANTHER", "sifts", "alphafold", "Seg", "MobiDBLite", "ncoils"}
    assert dropped.isdisjoint({d["source"] for d in found})


def test_an_empty_description_falls_back_to_the_accession():
    with ensembl() as client:
        found = genestructure.fetch_domains(client, "https://ensembl.test", "ENSP0")
    gene3d = next(d for d in found if d["accession"] == "1.25.40.430")
    assert gene3d["name"] == "1.25.40.430"


def test_domains_come_back_sorted_by_start():
    with ensembl() as client:
        found = genestructure.fetch_domains(client, "https://ensembl.test", "ENSP0")
    assert [d["start_aa"] for d in found] == sorted(d["start_aa"] for d in found)


# ── protein positions ────────────────────────────────────────────────────────────────


def test_protein_start_is_read_off_the_matching_transcript():
    with ensembl() as client:
        placed, failure = genestructure.protein_positions(
            client, "https://ensembl.test", CANDIDATES[:2], "ENST00000287598"
        )
    assert failure is None
    assert placed == {"15 1500 . G A . . .": 349}


def test_a_position_on_another_transcript_is_not_borrowed():
    with ensembl() as client:
        placed, _ = genestructure.protein_positions(
            client, "https://ensembl.test", CANDIDATES[:1], "ENST99999999999"
        )
    assert placed == {}


def test_no_alleles_means_no_vep_call_at_all():
    calls: list[str] = []
    with ensembl(calls=calls) as client:
        placed, failure = genestructure.protein_positions(
            client, "https://ensembl.test", [], "ENST00000287598"
        )
    assert (placed, failure, calls) == ({}, None, [])


def test_a_vep_outage_is_reported_not_raised():
    with ensembl(status={"/vep/": 503}) as client:
        placed, failure = genestructure.protein_positions(
            client, "https://ensembl.test", CANDIDATES[:1], "ENST00000287598"
        )
    assert placed == {}
    assert "503" in failure


# ── assembly ─────────────────────────────────────────────────────────────────────────


def built(settings, **kwargs) -> dict:
    with ensembl(**kwargs) as client:
        return genestructure.structure(
            "BUB1B", settings, client=client, base_url="https://ensembl.test"
        )


def test_the_payload_carries_the_contract_s_fields(settings):
    payload = built(settings)
    assert set(payload) == {
        "gene",
        "ensembl_id",
        "chrom",
        "start",
        "end",
        "strand",
        "biotype",
        "transcript",
        "protein",
        "protein_length",
        "exons",
        "domains",
        "candidates",
    }
    assert payload["chrom"] == "15"  # bare, the way the callset spells it
    assert payload["protein_length"] == 1050
    assert payload["transcript"] == "ENST00000287598"


def test_only_protein_altering_alleles_become_candidates(settings):
    labels = [c["consequence"] for c in built(settings)["candidates"]]
    assert labels == ["missense_variant", "splice_region_variant"]
    assert "intron_variant" not in labels


def test_a_placed_candidate_carries_its_amino_acid_position(settings):
    placed = built(settings)["candidates"][0]
    assert placed["protein_pos"] == 349
    assert placed["reason"] is None
    assert placed["label"] == "missense · rs1801516"
    assert placed["rare"] is True


def test_an_unplaceable_candidate_states_why_instead_of_vanishing(settings):
    unplaced = built(settings)["candidates"][1]
    assert unplaced["protein_pos"] is None
    assert "splice_region_variant" in unplaced["reason"]
    assert "ENST00000287598" in unplaced["reason"]


def test_a_vep_outage_leaves_every_candidate_unplaced_with_the_reason(settings):
    candidates = built(settings, status={"/vep/": 500})["candidates"]
    assert [c["protein_pos"] for c in candidates] == [None, None]
    assert all("VEP call failed" in c["reason"] for c in candidates)


def test_no_patient_genomic_coordinate_reaches_the_payload(settings):
    payload = built(settings)
    text = repr(payload["candidates"])
    for row in CANDIDATES:
        assert str(row["pos"]) not in text
    assert not any(
        key in c for c in payload["candidates"] for key in ("pos", "chrom", "ref", "alt")
    )


def test_the_rare_flag_is_carried_rather_than_used_as_a_filter(settings):
    assert [c["rare"] for c in built(settings)["candidates"]] == [True, False]


def test_a_lookup_outage_raises_rather_than_inventing_a_gene(settings):
    with pytest.raises(EnsemblError):
        built(settings, status={"/lookup/": 502})


def test_an_unparseable_reply_is_an_ensembl_error(settings):
    def handler(_request):
        return httpx.Response(200, text="<html>maintenance</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EnsemblError):
        genestructure.structure("BUB1B", settings, client=client, base_url="https://ensembl.test")


def test_a_transport_failure_is_an_ensembl_error(settings):
    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(EnsemblError):
        genestructure.structure("BUB1B", settings, client=client, base_url="https://ensembl.test")


# ── the HTTP surface ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch, settings):
    """The whole app, with Ensembl and the read store replaced."""
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    build = genestructure.structure
    fake = ensembl()
    monkeypatch.setattr(
        genestructure,
        "structure",
        lambda gene, config, **kw: build(
            gene, config, client=fake, base_url="https://ensembl.test"
        ),
    )
    app = create_app(settings=settings, cache=Cache(tmp_path), origins=["http://localhost:5173"])
    with TestClient(app) as running:
        yield running
    fake.close()


def test_the_endpoint_answers_in_the_shared_envelope(client):
    body = client.get("/api/panel/gene-structure?gene=BUB1B").json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["data"]["gene"] == "BUB1B"
    assert "ensembl rest" in body["source"]


def test_the_answer_is_cached_and_refresh_rebuilds_it(client, monkeypatch):
    first = client.get("/api/panel/gene-structure?gene=BUB1B")
    assert first.json()["cached_at"]

    seen: list[str] = []
    monkeypatch.setattr(
        genestructure, "structure", lambda gene, config, **kw: seen.append(gene) or {"gene": gene}
    )
    assert client.get("/api/panel/gene-structure?gene=BUB1B").status_code == 200
    assert seen == []  # served from disk
    client.get("/api/panel/gene-structure?gene=BUB1B&refresh=true")
    assert seen == ["BUB1B"]


def test_an_off_panel_gene_is_a_404(client):
    reply = client.get("/api/panel/gene-structure?gene=SONIC")
    assert reply.status_code == 404
    assert "SONIC" in reply.json()["detail"]


def test_a_key_that_would_escape_the_cache_directory_is_a_422(client):
    assert client.get("/api/panel/gene-structure?gene=../etc").status_code == 422


def test_an_ensembl_outage_is_a_502_with_the_upstream_detail(client, monkeypatch):
    def down(gene, _settings, **kw):
        raise EnsemblError("GET https://rest.ensembl.org/lookup/id/X -> 503")

    monkeypatch.setattr(genestructure, "structure", down)
    reply = client.get("/api/panel/gene-structure?gene=TRIP13")
    assert reply.status_code == 502
    assert "503" in reply.json()["detail"]


def test_the_route_is_declared_on_the_panel_tag(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/panel/gene-structure"]["get"]["tags"] == ["panel"]
