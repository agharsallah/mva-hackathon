"""The research report: the exhibit contract, and that an empty record renders honestly.

The exhibit rules are the same ones the profile report is held to — every figure travels
with a caption and a legend, slugs are unique, exactly one Plotly runtime — because both
pages come off the same renderer and a reader moves between them.

The empty-record tests exist because this report will spend most of its life nearly empty,
and "nothing has been tested yet" has to read as a statement rather than a bug.
"""

import re

import pytest

from mva.science import Record, build_report, build_sections
from mva.science.dossier import Dossier
from mva.science.evidence import Direction, Evidence, weigh
from mva.science.hypothesis import Hypothesis, Status
from mva.science.record import SpentProbe
from mva.science.views import SECTIONS

CLAIM = dict(
    step="step-1",
    statement="The causal pair sits in BUB1B.",
    prediction="Two rare damaging alleles in BUB1B, one on each copy.",
    refuted_by="Both alleles turn out common in gnomAD.",
)

EMPTY = Record(budget_total=18, subject="an empty register")


def _dossier(status=Status.TESTING, confidence=None, rows=()):
    claim = Hypothesis(**CLAIM, hypothesis_id="H001", gene="BUB1B", status=status,
                       confidence=confidence, reasoning="Two paths agreed.")
    return Dossier(hypothesis=claim, history=(claim,), evidence=tuple(rows),
                   weighing=weigh(list(rows), "H001"))


def _observation(direction=Direction.SUPPORTS, strength=0.7):
    return Evidence(hypothesis_id="H001", direction=direction, strength=strength,
                    claim="BUB1B is depleted of loss-of-function variants.",
                    source_ref="methodology/003", lineage_ref="data_lineage:7")


POPULATED = Record(
    dossiers=(_dossier(rows=(_observation(),
                             _observation(Direction.REFUTES, 0.3),
                             _observation(Direction.NEUTRAL, 0.0))),),
    probes=(SpentProbe(probe_id=1, probe_type="S", submitted_by="a member", n_rows=10,
                       score=50.0, response="partial_match_rank=2", rationale="",
                       hypothesis_ids=("H001",)),),
    budget_total=18, subject="a populated register")

RECORDS = {"empty": EMPTY, "populated": POPULATED}


# --- the exhibit contract ---------------------------------------------------------------

@pytest.mark.parametrize("name", list(RECORDS))
def test_every_exhibit_carries_a_title_a_caption_and_a_legend(name):
    for section in build_sections(RECORDS[name]):
        for exhibit in section.exhibits:
            assert exhibit.title.strip(), f"{exhibit.slug} has no title"
            assert exhibit.caption.strip(), f"{exhibit.slug} has no caption"
            assert exhibit.legend.strip(), f"{exhibit.slug} has no legend"


@pytest.mark.parametrize("name", list(RECORDS))
def test_every_legend_decodes_its_own_colours(name):
    for section in build_sections(RECORDS[name]):
        for exhibit in section.exhibits:
            assert exhibit.legend.startswith("**Legend** — "), exhibit.slug
            assert exhibit.legend.rstrip().endswith("."), exhibit.slug


@pytest.mark.parametrize("name", list(RECORDS))
def test_an_exhibit_carries_a_figure_or_html_but_never_both(name):
    for section in build_sections(RECORDS[name]):
        for exhibit in section.exhibits:
            assert bool(exhibit.figure is not None) != bool(exhibit.html), exhibit.slug


@pytest.mark.parametrize("name", list(RECORDS))
def test_slugs_are_lowercase_and_unique_across_the_page(name):
    slugs = [e.slug for s in build_sections(RECORDS[name]) for e in s.exhibits]
    assert all(re.fullmatch(r"[a-z0-9-]+", slug) for slug in slugs), slugs
    assert len(slugs) == len(set(slugs)), slugs


@pytest.mark.parametrize("name", list(RECORDS))
def test_exactly_one_plotly_runtime_is_loaded(name):
    page = build_report(RECORDS[name])
    assert page.count("plotly.min.js") <= 1


def test_the_sidebar_lists_every_exhibit_rendered():
    page = build_report(POPULATED)
    for section in build_sections(POPULATED):
        for exhibit in section.exhibits:
            assert f'data-target="{exhibit.slug}"' in page, exhibit.slug


# --- what the page must say ---------------------------------------------------------------

def test_the_method_section_comes_first():
    """A confidence met before the loop that produced it reads as an opinion."""
    assert build_sections(EMPTY)[0].slug == "method"


def test_every_registered_section_renders_even_when_the_record_is_empty():
    """An empty section is the statement here, not a missing input to be dropped."""
    assert [s.slug for s in build_sections(EMPTY)] == [spec.slug for spec in SECTIONS]


def test_an_empty_register_says_so_rather_than_rendering_a_blank_page():
    page = build_report(EMPTY)
    assert "The register is empty" in page
    assert "No evidence recorded" in page
    assert "No submissions spent" in page


def test_the_blurb_says_where_the_numbers_come_from():
    assert "receipt" in build_report(EMPTY)


def test_the_page_states_the_refutation_condition_for_every_claim():
    page = build_report(POPULATED)
    assert CLAIM["refuted_by"] in page
    assert "What would refute it" in page


def test_the_evidence_ledger_shows_the_source_of_every_observation():
    page = build_report(POPULATED)
    assert "methodology/003" in page
    assert "data_lineage:7" in page


def test_the_budget_shows_what_is_left_of_a_finite_allowance():
    page = build_report(POPULATED)
    assert "submissions left" in page
    assert POPULATED.budget_left == 17


def test_an_intact_budget_warns_against_firing_early():
    assert "coin flip" in build_report(EMPTY)


def test_a_probe_tied_to_no_hypothesis_is_called_out():
    untied = Record(probes=(SpentProbe(2, "S", "a member", 10, None, "", ""),),
                    budget_total=18)
    assert "no hypothesis" in build_report(untied)


def test_the_methods_form_marks_what_it_cannot_answer():
    page = build_report(EMPTY)
    assert "not answerable from the record yet" in page
    assert "worse than a blank" in page


def test_the_weighing_chart_appears_only_once_there_is_evidence():
    empty_slugs = [e.slug for s in build_sections(EMPTY) for e in s.exhibits]
    full_slugs = [e.slug for s in build_sections(POPULATED) for e in s.exhibits]
    assert "weighing" not in empty_slugs
    assert "weighing" in full_slugs


def test_a_gap_between_committed_and_suggested_confidence_is_shown_on_the_board():
    discounted = Record(dossiers=(_dossier(confidence=0.1, rows=(_observation(),)),),
                        budget_total=18)
    assert "suggested" in build_report(discounted)


# --- the record object ---------------------------------------------------------------------

def test_an_empty_record_knows_it_is_empty():
    assert EMPTY.is_empty
    assert not POPULATED.is_empty


def test_claims_group_by_step():
    assert len(POPULATED.for_step("step-1")) == 1
    assert POPULATED.for_step("step-2") == []


def test_the_tally_counts_statuses_for_one_step():
    assert POPULATED.tally_for("step-1")[Status.TESTING] == 1
    assert POPULATED.tally_for("step-1")[Status.SUPPORTED] == 0


def test_an_untested_claim_is_reported_as_untested():
    record = Record(dossiers=(_dossier(),), budget_total=18)
    assert len(record.untested_claims) == 1
    assert record.dossiers[0].is_untested
