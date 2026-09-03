"""The gene-set build, driven end to end over a **foreign** two-gene spec.

The point of this module is not the MVA panel. It is the claim
``docs/notes/reusable-structure-toolkit.md`` makes: that
``tools/build_gene_set.py`` + :mod:`mva.viz.genesetbuild` + :mod:`mva.viz.geneset` transfer
to another N-of-1 case with **no code change** — a different spec file, group ids nothing
in the repository has ever seen, its own labels and its own ranks. So every symbol and
every group name here is invented, the panel BED is a two-line file written in the temp
directory, and Ensembl is an ``httpx.MockTransport`` that answers from a dict.

Nothing reaches the network and nothing reads a committed file. If this module passes, a
new case is a new TSV.
"""

import httpx
import pytest

from mva.viz import geneset, genesetbuild, genesetpanel

#: Two invented genes, one coding and one not, in two invented groups.
REPLIES = {
    "ZZTOP1": {
        "id": "ENSG09900000001",
        "display_name": "ZZTOP1",
        "biotype": "protein_coding",
        "canonical_transcript": "ENST09900000001.7",
        "Transcript": [
            {"id": "ENST09900000001", "Translation": {"id": "ENSP09900000001", "length": 400}},
            {"id": "ENST09900000002"},
        ],
    },
    "QQBAR2": {
        "id": "ENSG09900000002",
        "display_name": "QQBAR2",
        "biotype": "lncRNA",
        "canonical_transcript": "ENST09900000003.2",
        "Transcript": [{"id": "ENST09900000003"}],
    },
}


@pytest.fixture
def client() -> httpx.Client:
    """An Ensembl that only knows :data:`REPLIES`, and 404s anything else."""

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.path.rsplit("/", 1)[-1]
        if "/info/data" in request.url.path:
            return httpx.Response(200, json={"releases": [999]})
        if "/xrefs/symbol/" in request.url.path:
            found = REPLIES.get(symbol)
            return httpx.Response(200, json=[{"type": "gene", "id": found["id"]}] if found else [])
        if symbol in REPLIES:
            return httpx.Response(200, json=REPLIES[symbol])
        return httpx.Response(404, text=f"no such symbol {symbol}")

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://ensembl.test"
    ) as open_client:
        yield open_client


@pytest.fixture
def spec(tmp_path):
    """A foreign spec: two genes, two groups nothing in this repo names, explicit ranks.

    ``kinases`` is written *second* but ranked 0, so a test that read display order off the
    file rather than off ``group_order`` would fail here.
    """
    path = tmp_path / "foreign.spec.tsv"
    path.write_text(
        "# a spec for some other case entirely\n"
        "symbol\tgroup\tgroup_label\tgroup_order\tnote\n"
        "QQBAR2\tregulators\tRegulatory RNAs (no protein)\t1\ta note about QQBAR2\n"
        "ZZTOP1\tkinases\tKinases we can fold\t0\ta note about ZZTOP1\n",
        encoding="utf-8",
    )
    return path


def resolved(client: httpx.Client, spec):
    """Every spec row resolved against the mock, in spec order."""
    wanted = genesetbuild.read_spec(spec)
    return [genesetbuild.resolve(client, "https://ensembl.test", row) for row in wanted]


# ── the spec, and what the defaults are ──────────────────────────────────────────────


def test_spec_carries_free_form_groups(spec):
    wanted = genesetbuild.read_spec(spec)
    assert [(row.symbol, row.group, row.group_label, row.group_order) for row in wanted] == [
        ("QQBAR2", "regulators", "Regulatory RNAs (no protein)", 1),
        ("ZZTOP1", "kinases", "Kinases we can fold", 0),
    ]


def test_spec_needs_only_symbol_and_group(tmp_path):
    """A two-column spec is valid: the id becomes the label, first appearance the rank."""
    path = tmp_path / "minimal.spec.tsv"
    path.write_text("symbol\tgroup\nZZTOP1\tsecond\nQQBAR2\tfirst\n", encoding="utf-8")
    wanted = genesetbuild.read_spec(path)
    assert [(row.group, row.group_label, row.group_order) for row in wanted] == [
        ("second", "second", 0),
        ("first", "first", 1),
    ]


def test_spec_refuses_a_group_that_disagrees_with_itself(tmp_path):
    path = tmp_path / "conflict.spec.tsv"
    path.write_text(
        "symbol\tgroup\tgroup_label\nZZTOP1\tk\tKinases\nQQBAR2\tk\tSomething else\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="two labels"):
        genesetbuild.read_spec(path)


def test_spec_refuses_a_missing_required_column(tmp_path):
    path = tmp_path / "bad.spec.tsv"
    path.write_text("symbol\tnote\nZZTOP1\thello\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        genesetbuild.read_spec(path)


# ── the resolution and the TSV ───────────────────────────────────────────────────────


def test_render_writes_the_eight_columns_in_order(client, spec):
    text = genesetbuild.render(resolved(client, spec))
    lines = text.strip().split("\n")
    assert lines[0].split("\t") == list(genesetbuild.COLUMNS)
    assert lines[1].split("\t") == [
        "QQBAR2",
        "ENSG09900000002",
        "regulators",
        "Regulatory RNAs (no protein)",
        "1",
        "lncRNA",
        "false",
        "a note about QQBAR2",
    ]
    # `coding` is "the canonical transcript translates", not "the biotype string says so".
    assert lines[2].split("\t")[6] == "true"


def test_alias_is_confirmed_by_membership(client):
    assert genesetbuild.check_alias(client, "https://ensembl.test", "ZZTOP1", "ZZTOP1")


def test_an_unknown_symbol_is_a_stated_failure(client, tmp_path):
    path = tmp_path / "unknown.spec.tsv"
    path.write_text("symbol\tgroup\nNOSUCHGENE\tkinases\n", encoding="utf-8")
    with pytest.raises(genesetbuild.EnsemblLookupError, match="404"):
        resolved(client, path)


# ── what the route then serves ───────────────────────────────────────────────────────


def test_route_output_carries_the_foreign_groups(client, spec, tmp_path):
    """``geneset.genes`` — what ``GET /panel/structure-genes`` returns — over the TSV above.

    The whole reuse claim in one assertion: labels and ranks come back as the foreign spec
    wrote them, and ``in_panel`` is ``False`` for every row because this project's BED
    names neither gene.
    """
    out = tmp_path / "foreign.tsv"
    out.write_text(genesetbuild.render(resolved(client, spec)), encoding="utf-8")
    bed = tmp_path / "empty.bed"
    bed.write_text("", encoding="utf-8")

    rows = geneset.genes(out, bed)
    assert [(r["symbol"], r["group"], r["group_label"], r["group_order"]) for r in rows] == [
        ("QQBAR2", "regulators", "Regulatory RNAs (no protein)", 1),
        ("ZZTOP1", "kinases", "Kinases we can fold", 0),
    ]
    assert [r["coding"] for r in rows] == [False, True]
    assert [r["in_panel"] for r in rows] == [False, False]


def test_route_falls_back_when_the_table_states_no_group_columns(tmp_path):
    """A hand-written table with only the original six columns still serves correctly."""
    out = tmp_path / "old.tsv"
    out.write_text(
        "symbol\tensembl_id\tgroup\tbiotype\tcoding\tnote\n"
        "QQBAR2\tENSG1\tregulators\tlncRNA\tfalse\t\n"
        "ZZTOP1\tENSG2\tkinases\tprotein_coding\ttrue\t\n",
        encoding="utf-8",
    )
    bed = tmp_path / "empty.bed"
    bed.write_text("", encoding="utf-8")
    rows = geneset.genes(out, bed)
    # Label falls back to the id, rank to first appearance in the file.
    assert [(r["group_label"], r["group_order"]) for r in rows] == [
        ("regulators", 0),
        ("kinases", 1),
    ]


def test_in_panel_comes_from_the_bed_the_caller_names(client, spec, tmp_path):
    """``in_panel`` is derived, never a column — and the BED it derives from is a parameter."""
    out = tmp_path / "foreign.tsv"
    out.write_text(genesetbuild.render(resolved(client, spec)), encoding="utf-8")
    bed = tmp_path / "foreign.bed"
    # chrom start end name score strand-ish: `panelbed` reads the name and the note.
    bed.write_text("chr1\t100\t200\tZZTOP1\tENSG09900000001\tthe one annotated gene\n", "utf-8")

    rows = {row["symbol"]: row for row in geneset.genes(out, bed)}
    assert rows["ZZTOP1"]["in_panel"] is True
    assert rows["QQBAR2"]["in_panel"] is False


# ── the panel assertion, which is the one case-specific step ─────────────────────────


def test_check_panel_refuses_a_disagreeing_gene_id(client, spec, tmp_path):
    bed = tmp_path / "stale.bed"
    bed.write_text("chr1\t100\t200\tZZTOP1\tENSG00000000000\tstale id\n", encoding="utf-8")
    problems = genesetpanel.check_panel(resolved(client, spec), bed, "kinases")
    assert len(problems) == 1
    assert "ENSG00000000000" in problems[0] and "ENSG09900000001" in problems[0]


def test_check_panel_asserts_nothing_without_a_panel_group(client, spec, tmp_path):
    """A project with no annotated panel passes an empty group name and loses nothing."""
    assert genesetpanel.check_panel(resolved(client, spec), tmp_path / "none.bed", "") == []


# ── the offline relabel ──────────────────────────────────────────────────────────────


def test_reuse_rewrites_curation_and_carries_the_measured_columns(client, spec, tmp_path):
    out = tmp_path / "foreign.tsv"
    out.write_text(genesetbuild.render(resolved(client, spec)), encoding="utf-8")
    bed = tmp_path / "empty.bed"
    bed.write_text("", encoding="utf-8")

    renamed = tmp_path / "renamed.spec.tsv"
    renamed.write_text(
        "symbol\tgroup\tgroup_label\tgroup_order\tnote\n"
        "ZZTOP1\tfolds\tThings with a fold\t0\tstill ZZTOP1\n"
        "QQBAR2\tno-folds\tThings without one\t1\tstill QQBAR2\n",
        encoding="utf-8",
    )
    carried = genesetbuild.reuse(genesetbuild.read_spec(renamed), geneset.genes(out, bed))
    rows = [entry.row() for entry in carried]
    assert [row[2] for row in rows] == ["folds", "no-folds"]
    assert [row[3] for row in rows] == ["Things with a fold", "Things without one"]
    # The measured columns are byte-identical to the live build's.
    assert [(row[1], row[5], row[6]) for row in rows] == [
        ("ENSG09900000001", "protein_coding", "true"),
        ("ENSG09900000002", "lncRNA", "false"),
    ]


def test_reuse_refuses_a_symbol_it_has_no_measurement_for(tmp_path):
    wanted = genesetbuild.read_flags(["kinases=NEWGENE"], [], [])
    with pytest.raises(LookupError, match="no resolved gene id"):
        genesetbuild.reuse(wanted, [])
