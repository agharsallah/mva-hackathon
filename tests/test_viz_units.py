"""The viz API's pieces below the routes: the cache, the genotype decoder, the overview.

No database and no object store. Everything here is either pure or handed a fake
connection, so a failure names the logic rather than the network. Every position in this
file is fabricated — the real ones are patient data and never enter the repository.
"""

from contextlib import contextmanager

import pytest

from mva.viz import genotype, panelbed
from mva.viz import overview as overview_module
from mva.viz.cache import Cache, InvalidKeyError, safe_key
from mva.warehouse import probes

# ── the disk cache ───────────────────────────────────────────────────────────────────


def test_a_hit_returns_the_payload_and_when_it_was_built(tmp_path):
    cache = Cache(tmp_path)
    written = cache.write("thing", [{"n": 1}])
    hit = cache.read("thing")
    assert hit.data == [{"n": 1}]
    assert hit.cached_at == written.cached_at


def test_a_miss_builds_once_and_a_second_call_does_not(tmp_path):
    calls = []
    cache = Cache(tmp_path)

    def build():
        calls.append(1)
        return {"built": len(calls)}

    assert cache.get_or_build("k", build).data == {"built": 1}
    assert cache.get_or_build("k", build).data == {"built": 1}
    assert len(calls) == 1


def test_refresh_rebuilds_and_replaces_the_entry(tmp_path):
    cache = Cache(tmp_path)
    cache.write("k", "old")
    assert cache.get_or_build("k", lambda: "new", refresh=True).data == "new"
    assert cache.read("k").data == "new"


def test_a_corrupt_entry_is_a_miss_not_an_error(tmp_path):
    cache = Cache(tmp_path)
    cache.write("k", "value")
    cache.path("k").write_text("{ this is not json")
    assert cache.read("k") is None
    assert cache.get_or_build("k", lambda: "rebuilt").data == "rebuilt"


def test_a_key_cannot_escape_the_cache_directory():
    # Keys are built from query parameters, so this is the path-traversal guard.
    for bad in ("../secret", "a/b", "", "gene name"):
        with pytest.raises(InvalidKeyError):
            safe_key(bad)
    assert safe_key("locus", "BUB1B") == "locus-BUB1B"
    assert safe_key("flowcell", 1, 2, 0) == "flowcell-1-2-0"


def test_a_failed_build_leaves_no_partial_entry(tmp_path):
    cache = Cache(tmp_path)

    def boom():
        raise RuntimeError("query died")

    with pytest.raises(RuntimeError):
        cache.get_or_build("k", boom)
    assert cache.read("k") is None
    assert list(tmp_path.glob("*")) == []


# ── the genotype decoder ─────────────────────────────────────────────────────────────


def test_a_biallelic_het_yields_a_variant_allele_fraction():
    call = genotype.decode("GT:AD:DP:GQ:PL", "0/1:30,18:22:99:400,0,600")
    assert (call.gt, call.ad_ref, call.ad_alt, call.dp, call.gq) == ("0/1", 30, 18, 22, 99)
    assert call.vaf == pytest.approx(18 / 48, abs=1e-4)


def test_a_multiallelic_site_refuses_to_guess_which_alt_is_the_alt():
    # AD has three depths at a 1/2 site. Attributing reads to "the" ALT would produce a
    # plausible, wrong allele fraction, so both fields stay null.
    call = genotype.decode("GT:AD:DP:GQ:PL", "1/2:2,15,14:31:99:0,0,0")
    assert call.gt == "1/2"
    assert call.ad_alt is None and call.vaf is None
    assert call.ad_ref == 2


def test_the_denominator_is_ref_plus_alt_not_dp():
    # DP counts reads supporting neither allele; using it would depress every VAF.
    call = genotype.decode("GT:AD:DP", "0/1:10,10:40")
    assert call.vaf == 0.5


def test_missing_and_placeholder_fields_become_nulls_not_errors():
    for fmt, packed in (("GT:AD:DP:GQ", "./.:.:.:."), ("GT", "0/1"), ("", ""), (None, None)):
        call = genotype.decode(fmt, packed)
        assert call.vaf is None and call.ad_alt is None


def test_the_decoder_reads_the_keys_rather_than_assuming_positions():
    # Same values, different declared order: a positional decoder would swap DP and GQ.
    reordered = genotype.decode("GT:DP:GQ:AD", "0/1:22:99:30,18")
    assert (reordered.dp, reordered.gq, reordered.ad_alt) == (22, 99, 18)


# ── the panel BED annotation ─────────────────────────────────────────────────────────


def test_the_bed_supplies_the_two_columns_staging_drops(tmp_path):
    bed = tmp_path / "panel.bed"
    bed.write_text(
        "# comment\tignored\n"
        "chr15\t100\t200\tBUB1B\tENSG00000156970\tMVA1, checkpoint\n"
        "chr17\t300\t400\tTP53\tENSG00000141510\tdifferential\n"
    )
    found = panelbed.annotations(bed)
    assert found["BUB1B"] == {"ensembl_id": "ENSG00000156970", "note": "MVA1, checkpoint"}
    assert found["TP53"]["ensembl_id"] == "ENSG00000141510"


def test_a_four_column_bed_still_yields_names_with_null_annotation(tmp_path):
    bed = tmp_path / "panel.bed"
    bed.write_text("chr15\t100\t200\tBUB1B\n")
    assert panelbed.annotations(bed) == {"BUB1B": {"ensembl_id": None, "note": None}}


def test_a_missing_bed_is_empty_not_fatal(tmp_path):
    assert panelbed.annotations(tmp_path / "nope.bed") == {}


# ── the overview assembly ────────────────────────────────────────────────────────────


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


OVERVIEW_ANSWERS = [
    (
        "stats_sn",
        ("metric", "value"),
        [
            ("number of records", 5012204),
            ("number of SNPs", 4086641),
            ("number of indels", 930181),
            ("number of multiallelic sites", 66860),
            ("number of samples", 1),
        ],
    ),
    ("stats_tstv", ("ratio",), [(1.94,)]),
    ("contig_counts", ("all_contigs", "canonical_contigs"), [(1690, 25)]),
    ("filter_gt_counts", ("pass_variants",), [(4740790,)]),
    ("profile_scalars", ("est_coverage_x",), [(51.9,)]),
    ("allele_balance_flags", ("mean_depth_x",), [(44.3,)]),
    (
        "source_objects",
        ("delivery_objects", "delivery_bytes", "all_hashes_verified"),
        [(12, 84668433664, True)],
    ),
    ("probe_ledger", ("probe_budget_spent",), [(0,)]),
]


@pytest.fixture()
def fake_warehouse(monkeypatch):
    fake = FakePostgres(OVERVIEW_ANSWERS)

    @contextmanager
    def attached(settings, read_only=False):
        yield fake

    monkeypatch.setattr(overview_module, "attached", attached)
    return fake


def test_the_overview_reads_every_field_from_a_table(fake_warehouse, monkeypatch):
    from mva.viz import readstore

    monkeypatch.setattr(
        readstore, "totals", lambda: {"total_reads": 1071835104, "read_length": 149}
    )
    found = overview_module.overview(settings=None)
    assert found["total_variants"] == 5012204
    assert found["pass_variants"] == 4740790
    assert found["tstv"] == 1.94
    assert found["canonical_contigs"] == 25 and found["all_contigs"] == 1690
    assert found["total_reads"] == 1071835104
    assert found["all_hashes_verified"] is True
    # the budget is imported from the module that owns it, never restated
    assert found["probe_budget_total"] == probes.BUDGET and found["probe_budget_spent"] == 0


def test_one_attach_serves_the_whole_overview(fake_warehouse, monkeypatch):
    """Nine separate connections would spend the request authenticating."""
    from mva.viz import readstore

    monkeypatch.setattr(readstore, "totals", lambda: {"total_reads": 1, "read_length": 1})
    overview_module.overview(settings=None)
    assert len(fake_warehouse.seen) == len(OVERVIEW_ANSWERS)


def test_an_unreachable_object_store_leaves_the_callset_readable(fake_warehouse, monkeypatch):
    from mva.viz import readstore

    def down():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(readstore, "totals", down)
    found = overview_module.overview(settings=None)
    assert found["total_reads"] is None
    assert found["total_variants"] == 5012204
