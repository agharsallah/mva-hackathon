"""Tests for the VEP REST annotator: batching, retries, parsing, and the contig bridge.

No test here reaches the network. The transport is an ``httpx.MockTransport`` and the
sleep function is a recorder, so a rate-limit test costs no wall-clock. The response
fixtures are trimmed copies of real replies from ``https://rest.ensembl.org`` (Ensembl
release 116, GRCh38), recorded in ``docs/step-0/methodology/031``; the positions in them
are public reference sites, not the proband's.
"""

import httpx
import pytest

from mva.pipeline.annotate_vep import (DEFAULT_BASE_URL, MAX_BATCH, VepError,
                                       VepRestAnnotator, batches)
from mva.pipeline.annotation import UNKNOWN
from mva.pipeline.variant import Variant
from mva.pipeline.vep_response import VepRecord, parse, query_line, vep_allele
from mva.warehouse.annotate import Interval, row_of, summarise

# ── fixtures, trimmed from live replies ──────────────────────────────────────────────

TP53_MISSENSE = {
    "input": "17 7676154 . G C . . .",
    "most_severe_consequence": "missense_variant",
    "assembly_name": "GRCh38",
    "transcript_consequences": [
        {"gene_symbol": "AC087388.1", "impact": "MODIFIER", "biotype": "lncRNA",
         "consequence_terms": ["downstream_gene_variant"]},
        {"gene_symbol": "TP53", "impact": "MODERATE", "biotype": "protein_coding",
         "canonical": 1, "consequence_terms": ["missense_variant"],
         "transcript_id": "ENST00000269305"},
        {"gene_symbol": "TP53", "impact": "MODERATE", "biotype": "protein_coding",
         "consequence_terms": ["missense_variant"], "transcript_id": "ENST00000445888"},
    ],
    "colocated_variants": [
        {"id": "COSV52666208", "somatic": 1, "allele_string": "COSMIC_MUTATION"},
        {"id": "rs1042522", "allele_string": "G/A/C/T",
         "clin_sig": ["uncertain_significance", "benign", "likely_benign", "pathogenic"],
         "clin_sig_allele": "C:benign;T:likely_benign;A:uncertain_significance",
         "frequencies": {"C": {"gnomadg": 0.6268, "gnomadg_afr": 0.3866,
                               "gnomadg_amr": 0.6995, "gnomadg_eas": 0.5756,
                               "gnomadg_nfe": 0.745, "gnomadg_sas": 0.5231,
                               "gnomadg_ami": 0.99, "gnomadg_remaining": 0.6521,
                               "gnomade": 0.7163}}},
    ],
}

BUB1B_INTRON = {
    "input": "15 40161282 . C T . . .",
    "most_severe_consequence": "intron_variant",
    "transcript_consequences": [
        {"gene_symbol": "BUB1B", "impact": "MODIFIER", "biotype": "protein_coding",
         "canonical": 1, "consequence_terms": ["intron_variant"]},
    ],
}

INTERGENIC = {
    "input": "1 1 . A T . . .",
    "most_severe_consequence": "intergenic_variant",
    "intergenic_consequences": [
        {"impact": "MODIFIER", "consequence_terms": ["intergenic_variant"]}],
}

EXOME_ONLY = {
    "input": "17 7676154 . G A . . .",
    "most_severe_consequence": "missense_variant",
    "transcript_consequences": [
        {"gene_symbol": "TP53", "impact": "MODERATE", "canonical": 1,
         "biotype": "protein_coding", "consequence_terms": ["missense_variant"]}],
    "colocated_variants": [
        {"id": "rs1042522",
         "frequencies": {"A": {"gnomade": 6.842e-07, "gnomade_nfe": 8.993e-07,
                               "gnomade_afr": 0.0, "gnomade_eas": 0.0}}}],
}

DELETION = {
    "input": "15 40161283 . CTT C . . .",
    "most_severe_consequence": "intron_variant",
    "transcript_consequences": [
        {"gene_symbol": "BUB1B", "impact": "MODIFIER", "canonical": 1,
         "biotype": "protein_coding", "consequence_terms": ["intron_variant"]}],
    "colocated_variants": [
        {"id": "rs999999999",
         "frequencies": {"-": {"gnomadg": 0.01, "gnomadg_nfe": 0.02}}}],
}

TP53 = Variant("chr17", 7676154, "G", "C")
BUB1B = Variant("chr15", 40161282, "C", "T")


def annotator(handler, **kwargs) -> VepRestAnnotator:
    """An annotator whose transport is a function and whose sleep is a no-op."""
    kwargs.setdefault("sleep", lambda seconds: None)
    kwargs.setdefault("genes", ["BUB1B", "TP53"])
    return VepRestAnnotator(client=httpx.Client(transport=httpx.MockTransport(handler)),
                            **kwargs)


def json_ok(payload):
    return lambda request: httpx.Response(200, json=payload)


# ── the query line, and the contig bridge it depends on ──────────────────────────────

class TestQueryLine:
    def test_the_contig_is_emitted_bare(self):
        # Ensembl has no chr prefix; sending one matches nothing and looks like an
        # unannotated variant rather than a bug.
        assert query_line(BUB1B) == "15 40161282 . C T . . ."

    def test_a_bare_input_stays_bare(self):
        assert query_line(Variant.from_vcf("15", 40161282, "C", "T")).startswith("15 ")

    def test_the_mitochondrion_uses_the_callsets_spelling(self):
        assert query_line(Variant("chrM", 100, "A", "G")).startswith("M ")

    def test_the_line_has_the_eight_vcf_fields(self):
        assert len(query_line(TP53).split(" ")) == 8


class TestVepAllele:
    def test_a_snv_is_its_own_alt(self):
        assert vep_allele("A", "T") == "T"

    def test_a_deletion_becomes_a_dash(self):
        assert vep_allele("CTT", "C") == "-"

    def test_an_insertion_drops_the_anchor_base(self):
        assert vep_allele("C", "CTT") == "TT"

    def test_an_mnp_keeps_both_bases(self):
        assert vep_allele("AT", "GC") == "GC"

    def test_it_is_case_insensitive(self):
        assert vep_allele("ctt", "c") == "-"


# ── batching ─────────────────────────────────────────────────────────────────────────

class TestBatches:
    def test_an_exact_multiple_makes_no_short_batch(self):
        assert [len(chunk) for chunk in batches(list(range(400)), 200)] == [200, 200]

    def test_the_remainder_becomes_a_final_short_batch(self):
        assert [len(chunk) for chunk in batches(list(range(401)), 200)] == [200, 200, 1]

    def test_a_request_above_the_endpoint_ceiling_is_clamped(self):
        assert [len(chunk) for chunk in batches(list(range(300)), 5000)] == [MAX_BATCH, 100]

    def test_nothing_in_nothing_out(self):
        assert batches([], 200) == []

    def test_a_non_positive_size_is_refused(self):
        with pytest.raises(ValueError):
            batches([1, 2], 0)

    def test_the_annotator_sends_one_request_per_batch(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json
            seen.append(len(json.loads(request.content)["variants"]))
            return httpx.Response(200, json=[])

        wanted = [Variant("chr15", 40140000 + n, "A", "G") for n in range(7)]
        annotator(handler, batch_size=3).annotate_many(wanted)
        assert seen == [3, 3, 1]


# ── retries ──────────────────────────────────────────────────────────────────────────

class TestRetries:
    def test_a_429_is_retried_after_the_header_says_so(self):
        waits, calls = [], []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={"Retry-After": "7"}, json={})
            return httpx.Response(200, json=[BUB1B_INTRON])

        client = annotator(handler, sleep=waits.append)
        assert client.annotate_many([BUB1B])[0].gene == "BUB1B"
        assert waits == [7.0]
        assert len(calls) == 2

    def test_a_429_without_the_header_falls_back_to_the_backoff(self):
        waits = []
        calls = []

        def handler(request):
            calls.append(request)
            return (httpx.Response(429, json={}) if len(calls) == 1
                    else httpx.Response(200, json=[]))

        annotator(handler, sleep=waits.append, backoff=1.0).annotate_many([BUB1B])
        assert waits == [1.0]

    def test_a_5xx_backs_off_exponentially(self):
        waits, calls = [], []

        def handler(request):
            calls.append(request)
            if len(calls) < 3:
                return httpx.Response(503, json={})
            return httpx.Response(200, json=[BUB1B_INTRON])

        client = annotator(handler, sleep=waits.append, backoff=0.5)
        client.annotate_many([BUB1B])
        assert waits == [0.5, 1.0]

    def test_a_timeout_is_retried_too(self):
        calls = []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                raise httpx.ReadTimeout("too slow", request=request)
            return httpx.Response(200, json=[BUB1B_INTRON])

        assert annotator(handler).annotate_many([BUB1B])[0].gene == "BUB1B"

    def test_retries_are_bounded(self):
        client = annotator(lambda request: httpx.Response(503, json={}), max_attempts=3)
        with pytest.raises(VepError):
            client.annotate_many([BUB1B])
        assert client.requests == 3

    def test_a_400_is_not_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(400, text="bad input")

        with pytest.raises(VepError):
            annotator(handler).annotate_many([BUB1B])
        assert len(calls) == 1

    def test_the_port_contract_holds_even_when_the_server_is_down(self):
        # The protocol says annotate() returns UNKNOWN rather than raising: a genome-wide
        # run that dies on one allele loses every good answer before it.
        client = annotator(lambda request: httpx.Response(503, json={}), max_attempts=2)
        assert client.annotate(BUB1B) is UNKNOWN


# ── response parsing ─────────────────────────────────────────────────────────────────

class TestParse:
    def test_the_panel_gene_wins_over_a_neighbouring_transcript(self):
        record = parse(TP53_MISSENSE, TP53, frozenset({"TP53"}))
        assert record.gene == "TP53"
        assert record.impact == "MODERATE"

    def test_the_most_severe_consequence_is_the_one_reported(self):
        assert parse(TP53_MISSENSE, TP53).consequence == "missense_variant"

    def test_gnomad_genomes_are_preferred_over_exomes(self):
        assert parse(TP53_MISSENSE, TP53).gnomad_af == 0.6268

    def test_grpmax_is_the_highest_eligible_group(self):
        # nfe 0.745 is the maximum of the grpmax-eligible groups. ami 0.99 is higher and
        # must be excluded, exactly as gnomAD excludes it from its own grpmax.
        assert parse(TP53_MISSENSE, TP53).gnomad_af_grpmax == 0.745

    def test_exomes_are_used_when_genomes_are_absent(self):
        record = parse(EXOME_ONLY, Variant("chr17", 7676154, "G", "A"))
        assert record.gnomad_af == pytest.approx(6.842e-07)
        assert record.gnomad_af_grpmax == pytest.approx(8.993e-07)

    def test_clin_sig_is_allele_specific(self):
        # The site carries a pathogenic submission, but not for this allele.
        assert parse(TP53_MISSENSE, TP53).clin_sig == ("benign",)

    def test_clin_sig_falls_back_to_the_site_when_the_allele_is_unlisted(self):
        unlisted = Variant("chr17", 7676154, "G", "T")
        assert "likely_benign" in parse(
            {**TP53_MISSENSE, "colocated_variants": [
                {"id": "rs1042522", "clin_sig": ["likely_benign", "benign"]}]},
            unlisted).clin_sig

    def test_the_rsid_is_picked_out_of_a_mixed_identifier_list(self):
        assert parse(TP53_MISSENSE, TP53).rsid == "rs1042522"

    def test_a_variant_absent_from_gnomad_reports_no_frequency(self):
        record = parse(BUB1B_INTRON, BUB1B)
        assert (record.gnomad_af, record.gnomad_af_grpmax, record.clin_sig) == (
            None, None, ())
        assert record.rsid is None

    def test_a_deletion_finds_its_frequency_under_the_dash_key(self):
        record = parse(DELETION, Variant("chr15", 40161283, "CTT", "C"))
        assert record.gnomad_af == 0.01

    def test_an_intergenic_hit_has_an_impact_but_no_gene(self):
        record = parse(INTERGENIC, Variant("chr1", 1, "A", "T"))
        assert (record.gene, record.impact) == (None, "MODIFIER")

    def test_the_narrow_port_record_is_derived_from_the_wide_one(self):
        annotation = parse(TP53_MISSENSE, TP53, frozenset({"TP53"})).annotation
        assert (annotation.gene, annotation.consequence) == ("TP53", "missense_variant")
        assert annotation.is_protein_altering


class TestAnnotateMany:
    def test_results_are_matched_by_the_echoed_input_not_by_position(self):
        # The server returns results in whatever order it finishes them.
        client = annotator(json_ok([TP53_MISSENSE, BUB1B_INTRON]))
        genes = [record.gene for record in client.annotate_many([BUB1B, TP53])]
        assert genes == ["BUB1B", "TP53"]

    def test_an_allele_the_server_skipped_comes_back_empty_not_missing(self):
        client = annotator(json_ok([BUB1B_INTRON]))
        found = client.annotate_many([BUB1B, TP53])
        assert len(found) == 2
        assert found[1] == VepRecord(variant=TP53)

    def test_an_error_object_instead_of_a_list_is_not_iterated_as_results(self):
        client = annotator(json_ok({"error": "something went wrong"}))
        assert client.annotate_many([BUB1B]) == [VepRecord(variant=BUB1B)]

    def test_the_frequency_parameters_are_actually_requested(self):
        import json
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return httpx.Response(200, json=[])

        annotator(handler).annotate_many([BUB1B])
        assert seen["af_gnomadg"] == 1 and seen["af_gnomade"] == 1

    def test_annotate_caches_so_a_repeat_costs_no_request(self):
        client = annotator(json_ok([BUB1B_INTRON]))
        client.annotate(BUB1B)
        before = client.requests
        client.annotate(BUB1B)
        assert client.requests == before

    def test_version_reads_the_release_and_assembly_from_the_server(self):
        def handler(request):
            if request.url.path == "/info/software":
                return httpx.Response(200, json={"release": 116})
            return httpx.Response(200, json={"default_coord_system_version": "GRCh38",
                                             "assembly_accession": "GCA_000001405.29"})

        assert annotator(handler).version() == {
            "release": "116", "assembly": "GRCh38", "accession": "GCA_000001405.29"}

    def test_the_default_server_is_the_grch38_one(self):
        assert DEFAULT_BASE_URL == "https://rest.ensembl.org"


# ── the warehouse half ───────────────────────────────────────────────────────────────

class TestMultiallelicSplit:
    """``variants_raw`` keeps ALT comma-packed; the annotator must see one allele each."""

    def test_a_packed_alt_becomes_one_variant_per_allele(self):
        from mva.warehouse import annotate as warehouse

        rows = [("15", 40208689, "G", "A,C"), ("15", 40200000, "A", "G")]
        wanted = warehouse.alleles(_FakeConnection(rows), "warehouse",
                                   [Interval("BUB1B", "15", 40140984, 40241137)])
        assert wanted == [Variant("chr15", 40200000, "A", "G"),
                          Variant("chr15", 40208689, "G", "A"),
                          Variant("chr15", 40208689, "G", "C")]

    def test_the_missing_alt_placeholder_is_dropped(self):
        from mva.warehouse import annotate as warehouse

        wanted = warehouse.alleles(_FakeConnection([("15", 40200000, "A", ".")]),
                                   "warehouse",
                                   [Interval("BUB1B", "15", 40140984, 40241137)])
        assert wanted == []

    def test_duplicate_rows_collapse_to_one_query(self):
        from mva.warehouse import annotate as warehouse

        rows = [("15", 40200000, "A", "G")] * 3
        wanted = warehouse.alleles(_FakeConnection(rows), "warehouse",
                                   [Interval("BUB1B", "15", 40140984, 40241137)])
        assert len(wanted) == 1

    def test_no_intervals_means_no_query_at_all(self):
        from mva.warehouse import annotate as warehouse

        connection = _FakeConnection([])
        assert warehouse.alleles(connection, "warehouse", []) == []
        assert connection.statements == []

    def test_the_predicate_names_the_bare_contig_once_per_interval(self):
        from mva.warehouse import annotate as warehouse

        connection = _FakeConnection([])
        warehouse.alleles(connection, "warehouse",
                          [Interval("BUB1B", "15", 1, 2), Interval("TP53", "17", 3, 4)])
        sql, params = connection.statements[0]
        assert sql.count("chrom = ?") == 2
        assert params == ["15", 1, 2, "17", 3, 4]


class TestIntervals:
    def test_the_bed_contig_is_stripped_and_the_start_made_one_based(self):
        from mva.warehouse import annotate as warehouse

        rows = [("BUB1B", "chr15", 40140983, 40241137)]
        found = warehouse.intervals(_FakeConnection(rows), "warehouse")
        assert found == [Interval("BUB1B", "15", 40140984, 40241137)]


class TestRow:
    def test_the_stored_contig_matches_the_callsets_spelling(self):
        from datetime import datetime

        record = parse(TP53_MISSENSE, TP53, frozenset({"TP53"}))
        row = row_of(record, datetime(2026, 1, 1), "ensembl-vep-rest release=116")
        assert row[0] == "17"
        assert row[:4] == ["17", 7676154, "G", "C"]
        assert row[10] == "benign"

    def test_an_empty_clin_sig_is_null_not_an_empty_string(self):
        from datetime import datetime

        row = row_of(VepRecord(variant=BUB1B), datetime(2026, 1, 1), "x")
        assert row[10] is None


class TestSummarise:
    def test_it_counts_only_what_was_actually_returned(self):
        records = [
            parse(TP53_MISSENSE, TP53, frozenset({"TP53"})),
            parse(BUB1B_INTRON, BUB1B),
            VepRecord(variant=Variant("chr5", 900000, "A", "T")),
        ]
        assert summarise(records) == {
            "rows": 3, "annotated": 2, "with_gnomad_af": 1, "with_grpmax": 1,
            "with_clin_sig": 1, "with_rsid": 1, "genes": ["BUB1B", "TP53"]}


class _FakeConnection:
    """The two-method surface :mod:`mva.warehouse.annotate` uses of a DuckDB connection."""

    def __init__(self, rows):
        self.rows = rows
        self.statements: list[tuple[str, list]] = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        return self

    def fetchall(self):
        return self.rows
