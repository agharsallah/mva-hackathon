"""The protein-structure endpoint: model resolution, the assembled payload, and the 502.

The mmCIF reader itself is tested in ``tests/test_viz_mmcif.py``; this module owns the
endpoint around it.

No test here reaches the network. The transport is an ``httpx.MockTransport`` in the style
of ``tests/test_viz_genestructure.py``, and the coordinate file is
``tests/fixtures/mini_alphafold.cif`` — six residues trimmed out of the real AlphaFold
model for BUB1B.

Every value below is **public reference data**: Ensembl's own gene record, UniProt's
accession, and an AlphaFold model that is identical for every human. Nothing here is
patient-derived, and this endpoint reads no warehouse table at all — which is why, unlike
the gene-structure tests, there is no mocked ``queries.fetch``.

The reply fixtures are trimmed copies of live replies recorded in
``docs/step-0/methodology/056-protein-structure-endpoint.md``.
"""

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mva.viz import proteinstructure, readstore
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.viz.proteinstructure import ProteinModelError

MINI_CIF = (Path(__file__).parent / "fixtures" / "mini_alphafold.cif").read_text(encoding="utf-8")

# ── trimmed live replies ─────────────────────────────────────────────────────────────

#: ``GET /lookup/id/ENSG00000156970?expand=1``, cut to the canonical transcript.
BUB1B_LOOKUP = {
    "id": "ENSG00000156970",
    "display_name": "BUB1B",
    "canonical_transcript": "ENST00000287598.11",
    "Transcript": [
        {
            "id": "ENST00000287598",
            "is_canonical": 1,
            "Translation": {"id": "ENSP00000287598", "length": 1050},
        },
    ],
}

#: ``GET /xrefs/id/ENSP00000287598?external_db=Uniprot/SWISSPROT`` — one row, verbatim
#: except for the trimmed description. ``primary_id`` is the accession AlphaFold is keyed
#: by; ``display_id`` carries a version suffix and is deliberately *not* used.
SWISSPROT_XREFS = [
    {
        "dbname": "Uniprot/SWISSPROT",
        "primary_id": "O60566",
        "display_id": "O60566.231",
        "db_display_name": "UniProtKB/Swiss-Prot",
        "ensembl_identity": 100,
        "xref_identity": 100,
        "ensembl_start": 1,
        "ensembl_end": 1050,
        "info_type": "DIRECT",
    }
]

#: ``GET /api/prediction/O60566`` — the live reply is a **list of three isoform models**,
#: trimmed here to the fields this module reads. 1050 is the canonical translation length,
#: so the first entry is the one that must win; the other two are the decoys.
ALPHAFOLD_PREDICTION = [
    {
        "entryId": "AF-O60566-F1",
        "uniprotAccession": "O60566",
        "uniprotStart": 1,
        "uniprotEnd": 1050,
        "latestVersion": 6,
        "allVersions": [1, 2, 3, 4, 5, 6],
        "cifUrl": "https://alphafold.test/files/AF-O60566-F1-model_v6.cif",
        "pdbUrl": "https://alphafold.test/files/AF-O60566-F1-model_v6.pdb",
        "globalMetricValue": 63.59,
    },
    {
        "entryId": "AF-O60566-3-F1",
        "uniprotEnd": 1064,
        "latestVersion": 6,
        "cifUrl": "https://alphafold.test/files/AF-O60566-3-F1-model_v6.cif",
    },
    {
        "entryId": "AF-O60566-2-F1",
        "uniprotEnd": 933,
        "latestVersion": 6,
        "cifUrl": "https://alphafold.test/files/AF-O60566-2-F1-model_v6.cif",
    },
]

MODEL_URL = ALPHAFOLD_PREDICTION[0]["cifUrl"]


# ── a mock Ensembl + AlphaFold ───────────────────────────────────────────────────────


def upstream(
    lookup=BUB1B_LOOKUP,
    xrefs=SWISSPROT_XREFS,
    prediction=ALPHAFOLD_PREDICTION,
    cif=MINI_CIF,
    status: dict[str, int] | None = None,
    calls: list | None = None,
):
    """An ``httpx.Client`` answering the four URLs this module fetches."""
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
        if path.startswith("/xrefs/id"):
            return httpx.Response(200, json=xrefs)
        if path.startswith("/api/prediction"):
            return httpx.Response(200, json=prediction)
        if path.endswith(".cif"):
            return httpx.Response(200, text=cif)
        raise AssertionError(f"unexpected path {path}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def built(**kwargs) -> dict:
    with upstream(**kwargs) as client:
        return proteinstructure.structure(
            "BUB1B",
            client=client,
            base_url="https://ensembl.test",
            alphafold_url="https://alphafold.test",
        )


# ── model resolution ─────────────────────────────────────────────────────────────────


def test_the_swissprot_xref_supplies_the_accession():
    with upstream() as client:
        found = proteinstructure.uniprot_accession(
            client, "https://ensembl.test", "ENSP00000287598"
        )
    assert found == "O60566"


def test_trembl_is_tried_when_swissprot_has_nothing():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url.query))
        reviewed = "SWISSPROT" in str(request.url)
        return httpx.Response(200, json=[] if reviewed else [{"primary_id": "A0A123"}])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = proteinstructure.uniprot_accession(client, "https://ensembl.test", "ENSP0")
    assert found == "A0A123"
    assert len(seen) == 2


def test_no_uniprot_xref_at_all_is_none_not_a_guess():
    def handler(_request):
        return httpx.Response(200, json=[])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert proteinstructure.uniprot_accession(client, "https://ensembl.test", "ENSP0") is None


def test_the_isoform_matching_the_translation_length_is_the_one_modelled():
    with upstream() as client:
        model = proteinstructure.alphafold_model(client, "https://alphafold.test", "O60566", 1050)
    # `created` and `entry_id` were added for the fixture manifest
    # (`app/src/fixtures/data/protein/_provenance.json`, methodology 061). Neither reaches
    # the payload — `trace` does not read them and the frozen client contract has no field
    # for them — so this assertion widened rather than the payload changing. The trimmed
    # reply fixture above carries no `modelCreatedDate`, hence `None`.
    assert model == {
        "model_url": MODEL_URL,
        "version": "6",
        "provenance": "alphafold",
        "created": None,
        "entry_id": "AF-O60566-F1",
    }


def test_the_version_comes_from_the_reply_and_is_never_composed():
    prediction = [dict(ALPHAFOLD_PREDICTION[0], latestVersion=9)]
    with upstream(prediction=prediction) as client:
        model = proteinstructure.alphafold_model(client, "https://alphafold.test", "O60566", 1050)
    assert model["version"] == "9"


def test_the_canonical_entry_wins_when_no_length_is_known():
    with upstream() as client:
        model = proteinstructure.alphafold_model(client, "https://alphafold.test", "O60566", None)
    assert model["model_url"] == MODEL_URL


def test_a_fragment_model_is_matched_by_its_span_not_by_where_it_ends():
    """``uniprotEnd == length`` only holds when ``uniprotStart == 1``; F2 starts at 200."""
    prediction = [
        dict(ALPHAFOLD_PREDICTION[0], uniprotStart=1, uniprotEnd=900),
        {
            "entryId": "AF-O60566-F2",
            "uniprotStart": 200,
            "uniprotEnd": 1249,
            "latestVersion": 6,
            "cifUrl": "https://alphafold.test/files/AF-O60566-F2-model_v6.cif",
        },
    ]
    with upstream(prediction=prediction) as client:
        model = proteinstructure.alphafold_model(client, "https://alphafold.test", "O60566", 1050)
    assert model["model_url"].endswith("AF-O60566-F2-model_v6.cif")


def test_alphafold_holding_no_model_is_an_error_not_an_empty_trace():
    with upstream(prediction=[]) as client, pytest.raises(ProteinModelError):
        proteinstructure.alphafold_model(client, "https://alphafold.test", "O60566", 1050)


# ── assembly ─────────────────────────────────────────────────────────────────────────


def test_the_payload_carries_exactly_the_contract_s_fields():
    payload = built()
    assert set(payload) == {
        "gene",
        "protein",
        "uniprot",
        "provenance",
        "model_url",
        "version",
        "protein_length",
        "residues",
        "covered",
        "secondary",
        "partners",
    }
    assert set(payload["residues"][0]) == {"n", "aa", "ca", "plddt"}
    assert set(payload["secondary"][0]) == {"kind", "start", "end"}


def test_the_payload_reports_the_translation_the_lollipop_uses():
    payload = built()
    assert payload["protein"] == "ENSP00000287598"
    assert payload["protein_length"] == 1050  # Ensembl's length, not the model's 5 residues
    assert payload["uniprot"] == "O60566"
    assert payload["provenance"] == "alphafold"
    assert payload["model_url"] == MODEL_URL
    assert payload["version"] == "6"
    assert payload["partners"] == []


def test_a_model_shorter_than_the_translation_reports_the_gap_it_leaves():
    payload = built()
    assert payload["covered"] == [[1, 3], [5, 6]]
    assert [r["n"] for r in payload["residues"]] == [1, 2, 3, 5, 6]


def test_the_four_upstream_calls_are_made_in_order_and_only_once():
    calls: list[str] = []
    built(calls=calls)
    assert calls == [
        "GET /lookup/id/ENSG00000156970",
        "GET /xrefs/id/ENSP00000287598",
        "GET /api/prediction/O60566",
        "GET /files/AF-O60566-F1-model_v6.cif",
    ]


def test_an_off_panel_gene_never_reaches_an_upstream():
    calls: list[str] = []
    with upstream(calls=calls) as client, pytest.raises(LookupError):
        proteinstructure.structure(
            "SONIC", client=client, base_url="https://ensembl.test", alphafold_url="https://af.test"
        )
    assert calls == []


def test_a_transcript_without_a_translation_is_a_stated_failure():
    """And it is a *different* class from an upstream failure.

    ``NoProteinError``, not ``ProteinModelError``: a canonical transcript that does not
    translate will never start translating, so the route answers 422 ("this cannot be
    answered for this gene") rather than 502 ("come back later"). Entry 060 records why the
    two are separate classes, and ``tests/test_viz_geneset.py`` asserts the 422 end to end.
    """
    lookup = {"id": "ENSG00000156970", "Transcript": [{"id": "ENST0", "is_canonical": 1}]}
    with pytest.raises(proteinstructure.NoProteinError, match="no protein-coding"):
        built(lookup=lookup)


def test_a_translation_with_no_uniprot_xref_is_a_stated_failure():
    with pytest.raises(ProteinModelError, match="no UniProt accession"):
        built(xrefs=[])


@pytest.mark.parametrize(
    "fragment", ["/lookup/", "/xrefs/", "/api/prediction", "AF-O60566-F1-model_v6.cif"]
)
def test_any_upstream_refusal_is_a_protein_model_error(fragment):
    with pytest.raises(ProteinModelError, match="503"):
        built(status={fragment: 503})


def test_an_unparseable_coordinate_file_is_a_protein_model_error():
    with pytest.raises(ProteinModelError, match="not a coordinate file"):
        built(cif="<html>maintenance</html>")


def test_a_reply_that_is_not_json_is_a_protein_model_error():
    def handler(_request):
        return httpx.Response(200, text="<html>maintenance</html>")

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProteinModelError, match="not JSON"),
    ):
        proteinstructure.structure(
            "BUB1B",
            client=client,
            base_url="https://ensembl.test",
            alphafold_url="https://af.test",
        )


def test_a_transport_failure_is_a_protein_model_error():
    def handler(request):
        raise httpx.ConnectError("no route to host", request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ProteinModelError, match="ConnectError"),
    ):
        proteinstructure.structure(
            "BUB1B",
            client=client,
            base_url="https://ensembl.test",
            alphafold_url="https://af.test",
        )


def test_nothing_patient_derived_can_be_in_the_payload():
    """A structural guarantee, not a spot check: no callset field exists in the shape."""
    payload = built()
    assert not {"chrom", "pos", "ref", "alt", "gt", "candidates"} & set(payload)
    assert all(not {"pos", "chrom"} & set(residue) for residue in payload["residues"])


# ── the HTTP surface ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """The whole app, with both upstreams and the read store replaced."""
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    build = proteinstructure.structure
    fake = upstream()
    monkeypatch.setattr(
        proteinstructure,
        "structure",
        lambda gene, config=None, **kw: build(
            gene,
            client=fake,
            base_url="https://ensembl.test",
            alphafold_url="https://alphafold.test",
        ),
    )
    app = create_app(settings=object(), cache=Cache(tmp_path), origins=["http://localhost:5173"])
    with TestClient(app) as running:
        yield running
    fake.close()


def test_the_endpoint_answers_in_the_shared_envelope(client):
    body = client.get("/api/panel/protein-structure?gene=BUB1B").json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["data"]["gene"] == "BUB1B"
    assert body["data"]["protein"] == "ENSP00000287598"
    assert "alphafold db" in body["source"]


def test_the_answer_is_cached_and_refresh_rebuilds_it(client, monkeypatch):
    assert client.get("/api/panel/protein-structure?gene=BUB1B").json()["cached_at"]

    seen: list[str] = []
    monkeypatch.setattr(
        proteinstructure,
        "structure",
        lambda gene, config=None, **kw: seen.append(gene) or {"gene": gene},
    )
    assert client.get("/api/panel/protein-structure?gene=BUB1B").status_code == 200
    assert seen == []  # served from disk
    client.get("/api/panel/protein-structure?gene=BUB1B&refresh=true")
    assert seen == ["BUB1B"]


def test_an_off_panel_gene_is_a_404(client):
    reply = client.get("/api/panel/protein-structure?gene=SONIC")
    assert reply.status_code == 404
    assert "SONIC" in reply.json()["detail"]


def test_a_key_that_would_escape_the_cache_directory_is_a_422(client):
    assert client.get("/api/panel/protein-structure?gene=../etc").status_code == 422


def test_an_upstream_outage_is_a_502_with_the_upstream_detail(client, monkeypatch):
    def down(gene, _settings=None, **kw):
        raise ProteinModelError("GET https://alphafold.ebi.ac.uk/api/prediction/X -> 503")

    monkeypatch.setattr(proteinstructure, "structure", down)
    reply = client.get("/api/panel/protein-structure?gene=TRIP13")
    assert reply.status_code == 502
    assert "503" in reply.json()["detail"]


def test_an_ensembl_failure_inside_the_reused_helper_is_also_a_502(client, monkeypatch):
    """``pick_transcript`` is reused from ``genestructure``, so it raises *its* error type."""
    from mva.viz.genestructure import EnsemblError

    def down(gene, _settings=None, **kw):
        raise EnsemblError("no transcripts for 'ENSG00000156970'")

    monkeypatch.setattr(proteinstructure, "structure", down)
    assert client.get("/api/panel/protein-structure?gene=CEP57").status_code == 502


def test_the_route_is_declared_on_the_panel_tag(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/panel/protein-structure"]["get"]["tags"] == ["panel"]
