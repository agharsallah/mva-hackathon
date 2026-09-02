"""`POST /api/probe/build`: the rules it enforces, and the bytes it emits.

Hermetic — the endpoint reads no table, so the router is mounted on a bare FastAPI app
and nothing is faked. One test mounts the real `create_app` instead, to catch the
registration being dropped.

**Every coordinate here is synthetic.** Position 12345 is not a patient position and
never will be; the real ones exist only in HTTP payloads and in the downloaded file.
"""

import csv
from io import StringIO
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mva.pipeline import scorer, submission
from mva.pipeline.variant import Variant
from mva.viz import probebuild
from mva.viz.app import create_app
from mva.viz.cache import Cache
from mva.warehouse.settings import Postgres

#: The header the challenge template ships, transcribed from intel §10.1. Byte-for-byte:
#: a submission whose header differs by one character is a submission the scorer rejects.
TEMPLATE_HEADER = (
    "proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes"
)

#: The template as the challenge actually ships it. Transcription is not evidence, so the
#: conformance test reads the file itself. It carries no patient data — its two example
#: rows are the organisers' own placeholders (chr1:100000 and the like).
TEMPLATE_FILE = (
    Path(__file__).resolve().parents[1]
    / "ressources"
    / "hackathon-rules"
    / "track1_submission_template.csv"
)

A = {"chrom": "15", "pos": 12345, "ref": "C", "alt": "T"}
B = {"chrom": "15", "pos": 12399, "ref": "G", "alt": "A"}
C = {"chrom": "7", "pos": 54321, "ref": "A", "alt": "G"}


def pair_row(epcr: float = 0.99, **overrides) -> dict:
    row = {"variant_1": A, "variant_2": B, "epcr": epcr, "finding_type": "primary", "notes": ""}
    return {**row, **overrides}


def single_row(variant: dict = C, epcr: float = 0.98, **overrides) -> dict:
    row = {"variant_1": variant, "epcr": epcr, "finding_type": "secondary", "notes": ""}
    return {**row, **overrides}


@pytest.fixture(name="client")
def _client() -> TestClient:
    app = FastAPI()
    app.include_router(probebuild.router())
    return TestClient(app)


def post(client: TestClient, rows: list[dict]):
    return client.post("/api/probe/build", json={"rows": rows})


def built(client: TestClient, rows: list[dict]) -> dict:
    response = post(client, rows)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def messages(payload: dict, severity: str = "error") -> list[str]:
    return [p["message"] for p in payload["problems"] if p["severity"] == severity]


# --- the emitted file --------------------------------------------------------


def test_header_is_the_template_header_byte_for_byte(client):
    text = built(client, [pair_row()])["csv"]
    assert text.splitlines()[0] == TEMPLATE_HEADER


@pytest.mark.skipif(not TEMPLATE_FILE.exists(), reason="the shipped template is not checked out")
def test_the_header_matches_the_shipped_template_file_byte_for_byte():
    """Against the organisers' own file, not against a transcription of it."""
    shipped = TEMPLATE_FILE.read_bytes().split(b"\r\n")[0]
    assert shipped == TEMPLATE_HEADER.encode()


@pytest.mark.skipif(not TEMPLATE_FILE.exists(), reason="the shipped template is not checked out")
def test_the_emitted_rows_have_the_template_column_count(client):
    """The template ships CRLF and this writer emits LF — every *field* still lines up.

    `csv.reader` strips either terminator, and a scorer that split on "\\n" by hand would
    leave a stray CR in the last field of the *template*, never of a file written here. So
    LF is the safe direction and the difference is recorded rather than copied.
    """
    with TEMPLATE_FILE.open(newline="") as handle:
        template = list(csv.reader(handle))
    emitted = list(csv.reader(StringIO(built(client, [pair_row(), single_row()])["csv"])))
    assert template[0] == emitted[0]
    assert {len(row) for row in template} == {len(row) for row in emitted} == {12}


def test_the_file_ends_in_a_newline_and_uses_unix_line_endings(client):
    text = built(client, [pair_row(), single_row()])["csv"]
    assert "\r" not in text
    assert text.endswith("\n")
    assert len(text.splitlines()) == 3


def test_bare_contigs_go_in_and_chr_prefixed_ones_come_out(client):
    text = built(client, [pair_row(), single_row()])["csv"]
    first, second = text.splitlines()[1:]
    assert first.startswith("PROBAND01,chr15,12345,C,T,chr15,12399,G,A,0.99,primary,")
    assert second.startswith("PROBAND01,chr7,54321,A,G,,,,,0.98,secondary,")


def test_an_already_prefixed_contig_is_not_prefixed_twice(client):
    text = built(client, [pair_row(variant_1={**A, "chrom": "chr15"})])["csv"]
    assert ",chr15," in text
    assert "chrchr" not in text


def test_the_mitochondrion_is_spelled_chrM(client):  # noqa: N802 - chrM is GRCh38's contig name
    text = built(client, [single_row({"chrom": "MT", "pos": 12345, "ref": "A", "alt": "G"})])
    assert ",chrM," in text["csv"]


def test_a_single_leaves_the_pair_columns_blank(client):
    fields = built(client, [single_row()])["csv"].splitlines()[1].split(",")
    assert fields[5:9] == ["", "", "", ""]


def test_notes_carrying_a_comma_are_quoted_and_read_back_whole(client):
    note = "ClinVar: pathogenic, two submitters"
    text = built(client, [pair_row(notes=note)])["csv"]
    assert submission.read_submission(StringIO(text))[0].notes == note


def test_the_proband_id_is_constant_and_never_taken_from_the_request(client):
    text = built(client, [pair_row(), single_row()])["csv"]
    for line in text.splitlines()[1:]:
        assert line.startswith(f"{submission.PROBAND_ID},")


# --- the rules ---------------------------------------------------------------


def test_eleven_rows_is_an_error_and_ten_is_not(client):
    ten = [pair_row(epcr=0.99 - 0.01 * i) for i in range(10)]
    assert built(client, ten)["valid"]
    payload = built(client, [*ten, pair_row(epcr=0.88)])
    assert not payload["valid"]
    assert any("at most 10 rows" in m for m in messages(payload))


def test_equal_epcr_is_an_error_because_the_rank_becomes_unreadable(client):
    payload = built(client, [pair_row(epcr=0.9), single_row(epcr=0.9)])
    assert not payload["valid"]
    assert any("distinct" in m for m in messages(payload))


def test_ascending_epcr_is_an_error_even_though_the_scorer_would_sort_it(client):
    payload = built(client, [pair_row(epcr=0.5), single_row(epcr=0.9)])
    assert not payload["valid"]
    assert any("rank order" in m and m.startswith("row 2:") for m in messages(payload))


@pytest.mark.parametrize("epcr", [0.0, -0.1, 1.5])
def test_epcr_outside_the_half_open_unit_interval_is_an_error(client, epcr):
    payload = built(client, [pair_row(epcr=epcr)])
    assert not payload["valid"]
    assert any("epcr must lie in (0, 1]" in m for m in messages(payload))


def test_epcr_of_exactly_one_is_allowed(client):
    assert built(client, [pair_row(epcr=1.0)])["valid"]


def test_an_unknown_finding_type_is_an_error_naming_its_row(client):
    payload = built(client, [pair_row(), single_row(finding_type="incidental")])
    assert not payload["valid"]
    assert any(m.startswith("row 2:") and "finding_type" in m for m in messages(payload))


def test_no_rows_is_an_error_rather_than_an_empty_file(client):
    payload = built(client, [])
    assert not payload["valid"]
    assert payload["csv"] == ""
    assert payload["self_test"] is None


def test_every_problem_is_reported_at_once_not_just_the_first(client):
    payload = built(client, [pair_row(epcr=1.5), single_row(finding_type="bogus", epcr=1.6)])
    assert len(messages(payload)) >= 3  # two epcr, one finding_type, one ordering


# --- §8.2: a row holds a SET of alleles --------------------------------------


def test_a_pair_of_the_same_allele_collapses_to_a_single_row_with_a_warning(client):
    payload = built(client, [pair_row(variant_2=A)])
    assert payload["valid"]
    assert payload["csv"].splitlines()[1].split(",")[5:9] == ["", "", "", ""]
    assert any("single-variant row" in m for m in messages(payload, "warning"))


def test_the_same_pair_written_in_the_other_order_is_warned_as_a_repeat(client):
    payload = built(client, [pair_row(), pair_row(variant_1=B, variant_2=A, epcr=0.98)])
    assert payload["valid"]  # the scorer accepts it; it just wastes a rank
    assert any("same allele set as row 1" in m for m in messages(payload, "warning"))


def test_two_different_rows_raise_no_repeat_warning(client):
    assert messages(built(client, [pair_row(), single_row()]), "warning") == []


# --- the self-test -----------------------------------------------------------


def test_a_valid_payload_self_tests_at_the_maximum_score(client):
    payload = built(client, [pair_row(), single_row()])
    assert payload["self_test"] == {
        "rank_points": 100.0,
        "f_max": 1.0,
        "full_match_rank": 1,
        "passed": True,
    }


def test_the_self_test_scores_the_bytes_not_the_request(client):
    """Re-scoring the emitted CSV by hand must reproduce what the endpoint reported."""
    payload = built(client, [pair_row(), single_row()])
    parsed = submission.read_submission(StringIO(payload["csv"]))
    truth = frozenset({Variant("chr15", 12345, "C", "T"), Variant("chr15", 12399, "G", "A")})
    result = scorer.score(parsed, truth)
    assert (result.rank_points, result.f_max) == (100.0, 1.0)


def test_a_bare_contig_in_the_truth_would_fail_the_self_test(client):
    """The check that gives the self-test its teeth: chr15 and 15 are different strings."""
    payload = built(client, [pair_row()])
    parsed = submission.read_submission(StringIO(payload["csv"]))
    bare = frozenset({Variant("15", 12345, "C", "T"), Variant("15", 12399, "G", "A")})
    assert scorer.score(parsed, bare).rank_points == 0.0


def test_a_single_row_one_first_still_self_tests_at_the_maximum(client):
    payload = built(client, [single_row(epcr=0.99), pair_row(epcr=0.9)])
    assert payload["self_test"]["passed"]


# --- the request shape -------------------------------------------------------


@pytest.mark.parametrize(
    "rows",
    [
        [{"variant_1": A}],  # no epcr
        [{"epcr": 0.9}],  # no variant_1
        [{"variant_1": {**A, "pos": 0}, "epcr": 0.9}],  # VCF positions are 1-based
        [{"variant_1": {**A, "pos": "somewhere"}, "epcr": 0.9}],  # not a number
        [{"variant_1": {**A, "ref": ""}, "epcr": 0.9}],  # empty allele
        [{"variant_1": {**A, "chrom": ""}, "epcr": 0.9}],  # empty contig
    ],
)
def test_a_malformed_body_is_a_422_and_never_reaches_the_rules(client, rows):
    assert post(client, rows).status_code == 422


def test_a_body_that_is_not_an_object_is_a_422(client):
    assert client.post("/api/probe/build", json=[pair_row()]).status_code == 422


def test_the_response_carries_the_standard_envelope(client):
    body = post(client, [pair_row()]).json()
    assert body["cached_at"] is None
    assert body["source"] == probebuild.SOURCE
    assert set(body["data"]) == {"csv", "valid", "problems", "self_test"}


def test_the_route_is_registered_on_the_real_application(tmp_path):
    """Wiring, not logic: create_app must expose the route the browser posts to."""
    app = create_app(settings=Postgres(), cache=Cache(tmp_path), origins=[])
    assert "post" in app.openapi()["paths"]["/api/probe/build"]
