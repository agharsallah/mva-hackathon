"""Reference-data provenance: the manifests, the endpoint that lists them, and the
per-reply ``source`` lines the three structure routes now carry.

Two things are under test, and they are the two halves of one rule — *every dataset names
its source and its lineage*:

* :mod:`mva.viz.refprovenance` reads a ``*provenance.json`` written beside a committed
  reference table or a fixture directory and normalises it onto the single row shape
  ``ReferenceProvenanceRow`` in ``app/src/api/types/provenance.ts``. Two manifest
  families exist with different shapes (``hpo_provenance.json`` maps output file → row
  count; this repository's newer tools write a list carrying the digest), and both must
  come out the same shape without either being rewritten to suit the other.
* the envelope's ``source`` must name *this reply's* upstreams — the AlphaFold model URL
  and version, the Ensembl release the gene set was resolved at, the disk-cache key — not
  only the module's generic list of endpoints it could have called.

No test reaches the network. Every manifest below is written into ``tmp_path``, and the
one Ensembl call that exists (``/info/data``, used by the build tools) is served by an
``httpx.MockTransport``. Nothing here is patient-derived: a manifest records public
reference upstreams, and the perimeter rule is that no genomic position is ever written
into one.
"""

import hashlib
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mva.viz import ensembl, geneset, genestructure, proteinstructure, readstore, refprovenance
from mva.viz.app import create_app
from mva.viz.cache import Built, Cache
from mva.viz.response import cached, describe

#: The keys ``ReferenceProvenanceRow`` declares. Asserted as a set so the Python row and
#: the TypeScript interface cannot drift apart silently in either direction.
ROW_KEYS = {
    "name",
    "kind",
    "path",
    "built_at",
    "built_by",
    "code_version",
    "inputs",
    "outputs",
    "note",
}

#: A manifest in ``hpo_provenance.json``'s shape: ``outputs`` is a *mapping* of file name
#: to row count and records no digest at all.
MAPPING_STYLE = {
    "release": "hp/releases/2026-06-23",
    "built_at": "2026-09-03T08:09:03+00:00",
    "built_by": "tools/build_phenotype_data.py",
    "code_version": "796b213",
    "method": "Resnik similarity over the most informative common ancestor.",
    "inputs": [
        {
            "name": "hp.obo",
            "url": "https://purl.obolibrary.org/obo/hp.obo",
            "sha256": "a" * 64,
            "bytes": 11222341,
            "release": "hp/releases/2026-06-23",
        }
    ],
    "outputs": {"table.tsv": 19836},
}

#: A manifest in the shape ``tools/build_gene_set.py`` writes: ``outputs`` is a list and
#: carries the digest measured at build time.
LIST_STYLE = {
    "name": "structure_genes",
    "built_at": "2026-09-03T12:05:55+00:00",
    "built_by": "tools/build_gene_set.py",
    "code_version": "cb066b8",
    "note": "23 curated genes resolved live against Ensembl REST release 116.",
    "inputs": [
        {"name": "Ensembl REST", "url": "https://rest.ensembl.org", "release": "116"},
        {"name": "panel.bed", "url": "file://panel.bed", "sha256": "b" * 64, "bytes": 786},
    ],
    "outputs": [{"path": "structure_genes.tsv", "sha256": "c" * 64, "bytes": 2569, "rows": 23}],
}


@pytest.fixture()
def reference(tmp_path) -> Path:
    """A reference directory holding one manifest of each family, plus one corrupt file."""
    directory = tmp_path / "reference"
    directory.mkdir()
    (directory / "table.tsv").write_text("a\tb\n1\t2\n", encoding="utf-8")
    (directory / "hpo_provenance.json").write_text(json.dumps(MAPPING_STYLE), encoding="utf-8")
    (directory / "structure_genes.provenance.json").write_text(
        json.dumps(LIST_STYLE), encoding="utf-8"
    )
    (directory / "broken.provenance.json").write_text("{ not json", encoding="utf-8")
    (directory / "notes.md").write_text("not a manifest", encoding="utf-8")
    return directory


# ── the primitives ───────────────────────────────────────────────────────────────────


def test_the_digest_is_the_sha256_and_the_byte_count(tmp_path):
    path = tmp_path / "f.txt"
    path.write_bytes(b"abc")
    sha, size = refprovenance.digest(path)
    assert size == 3
    assert sha == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_a_digest_of_a_file_larger_than_one_chunk_is_still_right(tmp_path, monkeypatch):
    """The chunked read must not change the answer — the whole point of one definition."""
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * 5000)
    whole = refprovenance.digest(path)
    monkeypatch.setattr(refprovenance, "CHUNK", 7)
    assert refprovenance.digest(path) == whole == (hashlib.sha256(b"x" * 5000).hexdigest(), 5000)


def test_the_build_instant_is_utc_to_the_second():
    stamp = refprovenance.now()
    assert stamp.endswith("+00:00")
    assert len(stamp) == 25


# ── normalisation ────────────────────────────────────────────────────────────────────


def test_both_manifest_families_normalise_onto_one_row_shape(reference):
    found = refprovenance.rows(reference, ())
    assert [row["name"] for row in found] == ["hpo", "structure_genes"]
    assert all(set(row) == ROW_KEYS for row in found)
    assert {row["kind"] for row in found} == {"reference"}


def test_a_mapping_style_output_is_digested_from_disk_and_keeps_its_row_count(reference):
    (hpo,) = [row for row in refprovenance.rows(reference, ()) if row["name"] == "hpo"]
    (output,) = hpo["outputs"]
    assert output["rows"] == 19836
    assert output["bytes"] == 8
    # Not recorded by that manifest, so it is measured now — a weaker but honest claim.
    assert output["sha256"] == refprovenance.digest(reference / "table.tsv")[0]


def test_a_list_style_output_keeps_the_digest_the_build_measured(reference):
    (row,) = [r for r in refprovenance.rows(reference, ()) if r["name"] == "structure_genes"]
    assert row["outputs"] == [
        {"path": "structure_genes.tsv", "sha256": "c" * 64, "bytes": 2569, "rows": 23}
    ]


def test_an_input_with_no_digest_is_null_rather_than_an_empty_string(reference):
    (row,) = [r for r in refprovenance.rows(reference, ()) if r["name"] == "structure_genes"]
    live, bed = row["inputs"]
    assert (live["release"], live["sha256"], live["bytes"]) == ("116", None, None)
    assert (bed["sha256"], bed["bytes"]) == ("b" * 64, 786)


def test_the_note_falls_back_to_the_method_for_a_manifest_with_no_note(reference):
    (hpo,) = [row for row in refprovenance.rows(reference, ()) if row["name"] == "hpo"]
    assert hpo["note"].startswith("Resnik similarity")


def test_a_corrupt_manifest_is_skipped_rather_than_raised(reference):
    """Listing what can be vouched for. A file that cannot be parsed vouches for nothing."""
    assert "broken" not in {row["name"] for row in refprovenance.rows(reference, ())}


def test_a_missing_directory_yields_no_rows(tmp_path):
    assert refprovenance.rows(tmp_path / "absent", (tmp_path / "gone",)) == []


def test_a_fixture_manifest_is_normalised_with_kind_fixture(tmp_path):
    directory = tmp_path / "protein"
    directory.mkdir()
    (directory / refprovenance.FIXTURE_MANIFEST).write_text(
        json.dumps(
            {
                "name": "protein-structure fixtures",
                "built_at": "2026-09-03T12:30:00+00:00",
                "built_by": "tools/build_protein_fixture.py",
                "code_version": "cb066b8",
                "note": "one real AlphaFold trace per coding gene",
                "inputs": [
                    {
                        "name": "AlphaFold DB",
                        "url": "https://alphafold.ebi.ac.uk/api/prediction/{accession}",
                        "version": "per gene",
                    }
                ],
                "outputs": [
                    {"path": "protein/BUB1B.json", "sha256": "d" * 64, "bytes": 57959, "rows": 1050}
                ],
            }
        ),
        encoding="utf-8",
    )
    (row,) = refprovenance.rows(tmp_path / "absent", (directory,))
    assert set(row) == ROW_KEYS
    assert row["kind"] == "fixture"
    # `version` and `release` are the same question, so they land in one field.
    assert row["inputs"][0]["release"] == "per gene"
    assert row["outputs"][0]["rows"] == 1050


# ── the endpoint ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """The whole app. Needs no database: this route reads manifests off disk."""
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    app = create_app(settings=None, cache=Cache(tmp_path / "cache"), origins=["http://x"])
    with TestClient(app) as running:
        yield running


def test_the_endpoint_answers_in_the_shared_envelope(client):
    body = client.get("/api/provenance/reference").json()
    assert set(body) == {"data", "cached_at", "source"}
    assert body["cached_at"] is None
    assert "provenance.json" in body["source"]


def test_the_endpoint_lists_this_repository_own_manifests(client):
    """Reads the committed files, so it is the one test here that is not hermetic to tmp."""
    names = {row["name"] for row in client.get("/api/provenance/reference").json()["data"]}
    assert {"hpo", "structure_genes"} <= names


def test_every_row_the_endpoint_returns_matches_the_client_contract(client):
    for row in client.get("/api/provenance/reference").json()["data"]:
        assert set(row) == ROW_KEYS
        assert row["kind"] in {"reference", "fixture"}
        assert all(set(entry) == {"path", "sha256", "bytes", "rows"} for entry in row["outputs"])
        assert all(
            set(entry) == {"name", "url", "release", "sha256", "bytes"} for entry in row["inputs"]
        )


def test_a_checkout_with_no_reference_data_is_an_empty_list_not_a_500(
    client, monkeypatch, tmp_path
):
    monkeypatch.setattr(refprovenance, "REFERENCE_DIR", tmp_path / "nothing")
    monkeypatch.setattr(refprovenance, "FIXTURE_DIRS", (tmp_path / "also-nothing",))
    reply = client.get("/api/provenance/reference")
    assert reply.status_code == 200
    assert reply.json()["data"] == []


def test_the_route_is_declared_on_the_provenance_tag(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert paths["/api/provenance/reference"]["get"]["tags"] == ["provenance"]


# ── no genomic position may reach a manifest ─────────────────────────────────────────


def test_no_committed_manifest_carries_a_genomic_coordinate():
    """The repository-wide perimeter rule, asserted on the files themselves.

    A manifest is publishable by construction — it names public upstreams. This is the
    guard that keeps a future build tool from recording "the reply for chr15:40,000,000"
    into one and quietly making it patient-informative.
    """
    for row in refprovenance.rows():
        text = json.dumps(row)
        assert "chr" not in text.replace("chromosome", "")
        assert "variants_raw" not in text


# ── the per-reply source line ────────────────────────────────────────────────────────


def test_describe_appends_each_concrete_fact_after_the_generic_source():
    assert (
        describe("ensembl rest", {"ensembl_release": "116"}) == "ensembl rest; ensembl_release=116"
    )


def test_describe_writes_unknown_for_a_fact_that_could_not_be_learnt():
    """Not knowing a fact and there being none are different statements."""
    assert describe("x", {"version": None}) == "x; version=unknown"


def test_describe_leaves_a_source_with_nothing_to_add_alone():
    assert describe("x", None) == "x"
    assert describe("x", {}) == "x"


def test_the_envelope_renders_the_stored_provenance_and_the_routes_own_extras(tmp_path):
    cache = Cache(tmp_path)
    entry = cache.write("k", Built({"gene": "TP53"}, {"alphafold_version": "6"}))
    body = cached(entry, "alphafold db", cache_key="protein-structure-TP53")
    assert body["data"] == {"gene": "TP53"}
    assert body["source"] == "alphafold db; alphafold_version=6, cache_key=protein-structure-TP53"


def test_provenance_survives_the_round_trip_through_the_disk_cache(tmp_path):
    """The case that matters: a cache *hit* must report what built the reply it serves."""
    cache = Cache(tmp_path)
    cache.write("k", Built([1, 2], {"model_url": "https://alphafold.test/AF-x-model_v6.cif"}))
    hit = cache.read("k")
    assert hit is not None
    assert hit.data == [1, 2]
    assert hit.provenance == {"model_url": "https://alphafold.test/AF-x-model_v6.cif"}


def test_a_cache_entry_written_before_provenance_existed_still_reads_back(tmp_path):
    """So no cache directory has to be cleared for this to ship."""
    cache = Cache(tmp_path)
    cache.path("k").parent.mkdir(parents=True, exist_ok=True)
    cache.path("k").write_text(json.dumps({"cached_at": "2026-01-01T00:00:00+00:00", "data": 7}))
    hit = cache.read("k")
    assert hit is not None
    assert (hit.data, hit.provenance) == (7, None)


# ── the release the build tools ask for ──────────────────────────────────────────────


def transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def _forget_releases():
    """The memo is process-wide, so each test starts from an unasked state."""
    ensembl._RELEASES.clear()
    yield
    ensembl._RELEASES.clear()


def test_the_release_is_the_highest_one_info_data_reports():
    with transport(lambda r: httpx.Response(200, json={"releases": [115, 116]})) as client:
        assert ensembl.release("https://ensembl.test", client=client) == "116"


def test_a_failed_release_lookup_is_none_and_never_an_exception():
    """Not knowing the release must not turn a working payload into a 502."""
    with transport(lambda r: httpx.Response(503, text="down")) as client:
        assert ensembl.release("https://ensembl.test", client=client) is None


def test_the_release_is_asked_once_per_process():
    calls: list[str] = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"releases": [116]})

    with transport(handler) as client:
        ensembl.release("https://ensembl.test", client=client)
        ensembl.release("https://ensembl.test", client=client)
    assert calls == ["https://ensembl.test/info/data"]


# ── what the gene set's own manifest contributes ─────────────────────────────────────


def test_the_gene_set_manifest_supplies_the_release_and_the_digest(tmp_path):
    path = tmp_path / "structure_genes.provenance.json"
    path.write_text(json.dumps(LIST_STYLE), encoding="utf-8")
    assert geneset.provenance(path) == {
        "ensembl_release": "116",
        "structure_genes_sha256": "c" * 64,
        "built_at": "2026-09-03T12:05:55+00:00",
        "code_version": "cb066b8",
    }


def test_a_missing_gene_set_manifest_leaves_every_fact_null(tmp_path):
    """A checkout with the TSV but no manifest still serves the set; it just says unknown."""
    assert set(geneset.provenance(tmp_path / "absent.json").values()) == {None}


# ── the three structure routes' source lines ─────────────────────────────────────────


#: A one-row stand-in gene set, so these assertions do not depend on the committed TSV.
STAND_IN_TSV = (
    "\t".join(geneset.COLUMNS)
    + "\nTP53\tENSG00000141510\tpanel\tprotein_coding\ttrue\tLi-Fraumeni differential\n"
)


@pytest.fixture()
def structure_client(tmp_path, monkeypatch):
    """The app with both builders stubbed, so only the ``source`` line is under test."""
    tsv = tmp_path / "structure_genes.tsv"
    tsv.write_text(STAND_IN_TSV, encoding="utf-8")
    manifest = tmp_path / "structure_genes.provenance.json"
    manifest.write_text(json.dumps(LIST_STYLE), encoding="utf-8")
    monkeypatch.setattr(geneset, "DEFAULT_TSV", tsv)
    monkeypatch.setattr(geneset, "DEFAULT_PROVENANCE", manifest)
    monkeypatch.setattr(readstore, "root", lambda: "s3://test/reads")
    monkeypatch.setattr(
        genestructure,
        "structure",
        lambda gene, config=None, **kw: {
            "gene": gene,
            "ensembl_id": "ENSG00000141510",
            "transcript": "ENST00000269305",
        },
    )
    monkeypatch.setattr(
        proteinstructure,
        "structure",
        lambda gene, config=None, **kw: {
            "gene": gene,
            "uniprot": "P04637",
            "model_url": "https://alphafold.test/files/AF-P04637-F1-model_v6.cif",
            "version": "6",
        },
    )
    app = create_app(settings=None, cache=Cache(tmp_path / "cache"), origins=["http://x"])
    with TestClient(app) as running:
        yield running


def test_the_gene_set_route_names_the_release_it_was_resolved_at(structure_client):
    source = structure_client.get("/api/panel/structure-genes").json()["source"]
    assert "structure_genes.tsv" in source
    assert "ensembl_release=116" in source
    assert f"structure_genes_sha256={'c' * 64}" in source


def test_the_gene_structure_reply_names_the_gene_record_and_the_cache_key(structure_client):
    source = structure_client.get("/api/panel/gene-structure?gene=TP53").json()["source"]
    assert "ensembl rest" in source
    assert "ensembl_gene=ENSG00000141510" in source
    assert "ensembl_transcript=ENST00000269305" in source
    assert "ensembl_release_at_gene_set_build=116" in source
    assert "cache_key=gene-structure-TP53" in source


def test_the_protein_structure_reply_names_the_exact_model_file_and_version(structure_client):
    source = structure_client.get("/api/panel/protein-structure?gene=TP53").json()["source"]
    assert "alphafold_model=https://alphafold.test/files/AF-P04637-F1-model_v6.cif" in source
    assert "alphafold_version=6" in source
    assert "uniprot=P04637" in source
    assert "cache_key=protein-structure-TP53" in source


def test_a_cache_hit_carries_the_same_provenance_as_the_build(structure_client, monkeypatch):
    """The reply a reader actually screenshots is the second one, off disk."""
    first = structure_client.get("/api/panel/protein-structure?gene=TP53").json()

    def refuse(*_args, **_kw):
        raise AssertionError("the second request must be served from disk")

    monkeypatch.setattr(proteinstructure, "structure", refuse)
    second = structure_client.get("/api/panel/protein-structure?gene=TP53").json()
    assert second["source"] == first["source"]
    assert second["cached_at"] == first["cached_at"]
