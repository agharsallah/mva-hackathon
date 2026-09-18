"""The three population-reference manifests: the writer, and the committed files.

:mod:`mva.viz.referencemanifest` is the *writer* for ``gnomad_constraint``,
``clinvar_panel`` and ``qc_norms``. :mod:`mva.viz.refprovenance` — tested in
``tests/test_viz_refprovenance.py`` — is the reader. Two rules are under test here and
they are the two ways a manifest can lie:

* **A fact is measured or it is ``null``.** No digest, byte count, row count or release
  may be carried over from a previous run or copied out of a README. Every test below
  that asserts a digest writes the bytes it expects it for; every test that removes the
  input asserts ``null`` plus a ``known_gap`` saying which fact is missing.
* **The committed manifests still describe the committed files.** The drift test at the
  bottom re-digests every file the committed manifests claim and fails if a table was
  edited without its manifest being rewritten — which is the only failure mode a
  build-time manifest has.

Nothing here reaches the network. The two upstream inputs are the gitignored 95 MB and
193 MB downloads, so every test stands up a small stand-in in ``tmp_path``, including a
real gzip stream for the ClinVar header path. Nothing is patient-derived: a manifest
records public reference URLs, releases, digests, counts and citations, and the
perimeter rule — no genomic position, ever — is asserted on the committed files.
"""

import gzip
import json
from pathlib import Path

import pytest

from mva.viz import manifestbase, referencemanifest, refprovenance

#: The keys ``ReferenceProvenanceRow`` declares, duplicated from the reader's suite so a
#: writer that stops normalising fails here too rather than only there.
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

#: Two data rows plus a header, so ``rows`` must come out 2 and not 3.
TABLE = "gene\tloeuf\nBUB1B\t0.707\nCEP57\t0.740\n"

#: The three columns of ``qc_norms.tsv`` this manifest reads, and nothing else: the
#: numbers themselves are not the manifest's business.
QC_TABLE = (
    "metric\texpected_low\texpected_high\tsource\turl\n"
    "tstv_genome_wide\t2.0\t2.1\tBetschart 2024, PMID 38988195\thttps://example.org/a\n"
    "tstv_coding\t3.0\t4.0\tBetschart 2024, PMID 38988195\thttps://example.org/a\n"
    "snv_per_genome\t3.5e6\t4.0e6\tByrska-Bishop 2022, PMID 36055201\thttps://example.org/b\n"
)

BED = (
    "# MVA candidate panel, GRCh38\n"
    "# contig\tstart\tend\tsymbol\tensembl_id\tnote\n"
    "chr15\t1\t2\tBUB1B\tENSG00000156970\tMVA1\n"
    "chr11\t1\t2\tCEP57\tENSG00000166037\tMVA2\n"
)


@pytest.fixture()
def scene(tmp_path) -> dict[str, Path]:
    """A committed table, a committed BED, and a stand-in for each large upstream."""
    out = tmp_path / "table.tsv"
    out.write_text(TABLE, encoding="utf-8")
    bed = tmp_path / "panel.bed"
    bed.write_text(BED, encoding="utf-8")
    upstream = tmp_path / "upstream.tsv"
    upstream.write_bytes(b"x" * 1024)
    vcf = tmp_path / "clinvar.vcf.gz"
    with gzip.open(vcf, "wt") as stream:
        stream.write("##fileformat=VCFv4.1\n##fileDate=2026-08-29\n#CHROM\tPOS\n")
    index = tmp_path / "clinvar.vcf.gz.tbi"
    index.write_bytes(b"tbi")
    return {"out": out, "bed": bed, "upstream": upstream, "vcf": vcf, "index": index}


def written(manifest: dict, tmp_path: Path, name: str) -> dict:
    """Write `manifest` into a reference directory and read the row back out of it.

    Every assertion about shape goes through the reader, because the row shape the app
    consumes is the only shape that matters — a writer that produces a file the reader
    drops has produced nothing.
    """
    directory = tmp_path / "reference"
    directory.mkdir(exist_ok=True)
    manifestbase.write(manifest, directory / f"{name}.provenance.json")
    (row,) = refprovenance.rows(directory, ())
    return row


# ── the primitives ───────────────────────────────────────────────────────────────────


def test_a_path_inside_the_repository_is_recorded_relative_to_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ressources").mkdir()
    inside = tmp_path / "ressources" / "table.tsv"
    inside.write_text("x", encoding="utf-8")
    assert manifestbase.repo_relative(inside) == "ressources/table.tsv"


def test_a_path_outside_the_repository_keeps_the_path_it_has(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path / "..")
    assert manifestbase.repo_relative(Path("/var/data/clinvar.vcf.gz")) == (
        "/var/data/clinvar.vcf.gz"
    )


def test_the_row_count_excludes_the_header_line(scene, tmp_path):
    row = written(referencemanifest.gnomad(**_gnomad(scene)), tmp_path, "gnomad_constraint")
    assert row["outputs"][0]["rows"] == 2


def test_the_output_digest_is_the_digest_of_the_file_on_disk(scene, tmp_path):
    row = written(referencemanifest.gnomad(**_gnomad(scene)), tmp_path, "gnomad_constraint")
    sha, size = refprovenance.digest(scene["out"])
    assert (row["outputs"][0]["sha256"], row["outputs"][0]["bytes"]) == (sha, size)


def test_bcftools_version_is_a_string_or_none_and_never_raises(monkeypatch):
    monkeypatch.setattr(referencemanifest.subprocess, "run", _raises)
    assert referencemanifest.bcftools_version() is None


def _raises(*_args, **_kwargs):
    raise OSError("no bcftools here")


def _gnomad(scene: dict) -> dict:
    return {"out": scene["out"], "source": scene["upstream"], "bed": scene["bed"]}


def _clinvar(scene: dict) -> dict:
    return {
        "out": scene["out"],
        "source": scene["vcf"],
        "index": scene["index"],
        "bed": scene["bed"],
    }


# ── gnomAD ───────────────────────────────────────────────────────────────────────────


def test_the_gnomad_manifest_normalises_onto_the_row_shape(scene, tmp_path):
    row = written(referencemanifest.gnomad(**_gnomad(scene)), tmp_path, "gnomad_constraint")
    assert set(row) == ROW_KEYS
    assert row["name"] == "gnomad_constraint"
    assert row["kind"] == "reference"
    assert row["built_by"] == "tools/build_reference_data.py gnomad"


def test_the_gnomad_release_is_the_versioned_path_segment(scene, tmp_path):
    row = written(referencemanifest.gnomad(**_gnomad(scene)), tmp_path, "gnomad_constraint")
    upstream, bed = row["inputs"]
    assert upstream["release"] == referencemanifest.GNOMAD_RELEASE == "4.1"
    assert upstream["url"] == referencemanifest.GNOMAD_URL
    assert f"release/{referencemanifest.GNOMAD_RELEASE}/" in upstream["url"]
    assert bed["url"].startswith("file://")


def test_the_gnomad_upstream_is_digested_when_the_scratch_copy_is_on_disk(scene, tmp_path):
    row = written(referencemanifest.gnomad(**_gnomad(scene)), tmp_path, "gnomad_constraint")
    sha, size = refprovenance.digest(scene["upstream"])
    assert (row["inputs"][0]["sha256"], row["inputs"][0]["bytes"]) == (sha, size)


def test_a_missing_upstream_is_null_and_says_which_fact_is_missing(scene, tmp_path):
    scene["upstream"].unlink()
    manifest = referencemanifest.gnomad(**_gnomad(scene))
    assert manifest["inputs"][0]["sha256"] is None
    assert manifest["inputs"][0]["bytes"] is None
    assert "was not on disk" in manifest["inputs"][0]["known_gap"]
    row = written(manifest, tmp_path, "gnomad_constraint")
    assert row["inputs"][0]["sha256"] is None


# ── ClinVar ──────────────────────────────────────────────────────────────────────────


def test_the_clinvar_release_is_read_from_the_vcf_header(scene, tmp_path):
    row = written(referencemanifest.clinvar(**_clinvar(scene)), tmp_path, "clinvar_panel")
    assert [entry["release"] for entry in row["inputs"]] == ["2026-08-29", "2026-08-29", None]
    assert "release 2026-08-29" in row["note"]


def test_the_release_is_none_rather_than_a_guess_when_the_header_has_no_file_date(tmp_path):
    vcf = tmp_path / "clinvar.vcf.gz"
    with gzip.open(vcf, "wt") as stream:
        stream.write("##fileformat=VCFv4.1\n#CHROM\tPOS\n")
    assert referencemanifest.clinvar_release(vcf) is None


def test_the_release_is_none_rather_than_an_exception_when_the_vcf_is_absent(tmp_path):
    assert referencemanifest.clinvar_release(tmp_path / "absent.vcf.gz") is None


def test_a_missing_vcf_loses_both_the_digest_and_the_release_and_says_so(scene, tmp_path):
    scene["vcf"].unlink()
    manifest = referencemanifest.clinvar(**_clinvar(scene))
    vcf = manifest["inputs"][0]
    assert (vcf["sha256"], vcf["release"]) == (None, None)
    assert "the release could not be read" in vcf["known_gap"]
    assert "was not on disk" in vcf["known_gap"]
    assert "release unknown" in manifest["note"]


def test_the_clinvar_manifest_records_the_binary_that_produced_the_extract(scene):
    manifest = referencemanifest.clinvar(**_clinvar(scene))
    # A region query is not a pure function of the VCF alone, so the tool is provenance.
    assert "tool" in manifest


def test_the_clinvar_digest_states_what_it_is_a_digest_of(scene):
    manifest = referencemanifest.clinvar(**_clinvar(scene))
    assert "scratch copy" in manifest["inputs"][0]["digest_scope"]


def test_the_note_counts_the_panel_intervals_not_the_bed_comment_lines(scene):
    manifest = referencemanifest.clinvar(**_clinvar(scene))
    assert "2 panel intervals" in manifest["note"]


# ── qc_norms ─────────────────────────────────────────────────────────────────────────


def test_the_qc_norms_inputs_are_the_tables_own_citations(tmp_path):
    table = tmp_path / "qc_norms.tsv"
    table.write_text(QC_TABLE, encoding="utf-8")
    manifest = referencemanifest.qc_norms(table)
    assert [entry["name"] for entry in manifest["inputs"]] == [
        "Betschart 2024, PMID 38988195",
        "Byrska-Bishop 2022, PMID 36055201",
    ]
    assert manifest["inputs"][0]["metrics"] == ["tstv_genome_wide", "tstv_coding"]
    assert manifest["inputs"][1]["url"] == "https://example.org/b"


def test_a_citation_carries_no_digest_and_no_release_because_it_is_a_paper(tmp_path):
    table = tmp_path / "qc_norms.tsv"
    table.write_text(QC_TABLE, encoding="utf-8")
    manifest = referencemanifest.qc_norms(table)
    assert all(entry["sha256"] is None for entry in manifest["inputs"])
    assert all(entry["bytes"] is None for entry in manifest["inputs"])
    assert all(entry["release"] is None for entry in manifest["inputs"])
    assert "not a download" in manifest["known_gap"]


def test_the_qc_norms_manifest_normalises_onto_the_row_shape(tmp_path):
    table = tmp_path / "reference" / "qc_norms.tsv"
    table.parent.mkdir()
    table.write_text(QC_TABLE, encoding="utf-8")
    row = written(referencemanifest.qc_norms(table), tmp_path, "qc_norms")
    assert set(row) == ROW_KEYS
    assert row["outputs"][0]["rows"] == 3
    assert len(row["inputs"]) == 2


# ── the written file ─────────────────────────────────────────────────────────────────


def test_write_produces_indented_json_with_a_trailing_newline(tmp_path):
    path = manifestbase.write({"name": "x"}, tmp_path / "deep" / "x.provenance.json")
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert json.loads(text) == {"name": "x"}


# ── the committed manifests ──────────────────────────────────────────────────────────

#: What ``ressources/reference/`` must hold. One manifest per committed table, so a new
#: reference table cannot be added without declaring where it came from.
COMMITTED = {
    "gnomad_constraint": "gnomad_constraint.provenance.json",
    "clinvar_panel": "clinvar_panel.provenance.json",
    "qc_norms": "qc_norms.provenance.json",
}


@pytest.mark.parametrize(("name", "filename"), sorted(COMMITTED.items()))
def test_every_committed_reference_table_has_a_manifest(name, filename):
    path = refprovenance.REFERENCE_DIR / filename
    assert path.is_file(), f"{name} has no manifest at {path}"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["name"] == name
    assert manifest["built_by"].startswith("tools/build_reference_data.py")
    assert manifest["patient_data"].startswith("none")
    assert manifest["licence"]


def test_the_committed_manifests_still_describe_the_committed_files():
    """The drift gate: a table edited without its manifest rewritten fails here.

    Only outputs that *claim* a digest are checked. ``hpo_provenance.json`` records row
    counts and no digest, and the reader computes one off disk for it — comparing that
    against itself would assert nothing.
    """
    checked = 0
    for row in refprovenance.rows(fixture_dirs=()):
        for output in row["outputs"]:
            path = Path(output["path"])
            if not output["sha256"] or not path.is_file():
                continue
            sha, size = refprovenance.digest(path)
            assert output["sha256"] == sha, f"{path} has changed since {row['path']} was written"
            assert output["bytes"] == size
            checked += 1
    assert checked >= len(COMMITTED)


def test_every_input_a_committed_manifest_names_inside_the_tree_still_hashes_the_same():
    """A recorded input digest must still name the bytes in the repository.

    Every manifest family is walked — the ``ressources/reference`` ones *and* the two
    fixture directories' ``_provenance.json``. Scoping this to the reference manifests is
    how ``structure_genes.tsv`` went stale in both fixture manifests unnoticed: the TSV
    was rebuilt by ``tools/build_gene_set.py`` after the fixture run recorded its digest,
    and nothing re-checked it (``docs/step-0/methodology/063``). A ``file://`` input is
    the only kind that can be re-checked — the two large upstreams are gitignored by
    design.

    The counter is the second half of the guard: a reader change that silently stops
    yielding fixture rows would make the loop vacuous, so the test also asserts it saw at
    least one input from each family.
    """
    checked: set[str] = set()
    for row in refprovenance.rows():
        for entry in row["inputs"]:
            if not entry["url"].startswith("file://") or not entry["sha256"]:
                continue
            path = Path(entry["url"].removeprefix("file://"))
            assert path.is_file(), f"{row['path']} names a missing input {path}"
            assert entry["sha256"] == refprovenance.digest(path)[0], (
                f"{path} has changed since {row['path']} was written"
            )
            checked.add(row["kind"])
    assert checked == {"reference", "fixture"}, f"only checked {sorted(checked)}"
