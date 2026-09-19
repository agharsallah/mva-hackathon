"""The seven-section template: every section present, every number faithful to the JSON.

"Number-faithful" is the property worth testing hardest. The renderer must not compute — so
these tests change a number in the JSON and assert the Markdown changes with it, and assert
that a number never in the JSON is never in the Markdown.
"""

from __future__ import annotations

import json
import re

import duckdb
import pytest

from mva.zoo import rank, report
from mva.zoo.pairs import Pair
from mva.zoo.report_sections import SECTION_TITLES, coverage_json, hpo_sentence

CARD = {
    "key": "demo",
    "name": "Demo model",
    "version": "2.1",
    "tier": 1,
    "licence": "MIT",
    "catalogue_adjacent": False,
    "pmid": "12345678",
    "notes": "A synthetic card for tests.",
}

COVERAGE = {
    "model": "demo",
    "scored": 4,
    "total": 6,
    "by_consequence": {"missense_variant": (3, 4), "stop_gained": (1, 2)},
}

SCORES = {"a1": 0.9, "a2": 0.1, "b1": 0.8, "b2": 0.7}

PAIRS = [
    Pair("GA", "a1", "a2", "trans"),
    Pair("GB", "b1", "b2", "trans", is_confirmed=True),
]


@pytest.fixture
def model_rank() -> rank.ModelRank:
    return rank.rank_per_model(PAIRS, {"demo": SCORES})["demo"]


@pytest.fixture
def payload(model_rank) -> dict:
    return report.model_report_json(
        CARD,
        COVERAGE,
        SCORES,
        model_rank,
        hpo_sentence(
            {"rank": 3, "genes_considered": 4812, "score": 0.87}, gene="BUB1B", model="demo"
        ),
        report.Runtime(seconds=12.5, venue="laptop", dollars=0.0),
        run_id="run-1",
        mode="catalogue-free",
        interpretation_dated="2026-09-18",
    )


# ── the JSON ─────────────────────────────────────────────────────────────────────────────


def test_every_section_is_in_the_json(payload):
    assert set(payload["sections"]) == {
        "card",
        "inputs",
        "distribution",
        "confirmed_pair",
        "clinical",
        "interpretation",
        "limitations",
    }


def test_the_confirmed_pair_block_holds_rank_and_both_percentiles(payload):
    block = payload["sections"]["confirmed_pair"]
    assert block["gene"] == "GB"
    assert block["rank"] == 1
    assert block["n_ranked"] == 2
    assert block["percentile"] == pytest.approx(50.0)
    assert block["left_percentile"] == pytest.approx(50.0)
    assert block["right_percentile"] == pytest.approx(75.0)


def test_the_distribution_marks_both_halves_of_the_confirmed_pair(payload):
    marks = payload["sections"]["distribution"]["marks"]
    assert [m["allele_id"] for m in marks] == ["b1", "b2"]
    assert [m["role"] for m in marks] == ["left", "right"]
    assert marks[0]["score"] == pytest.approx(0.8)


def test_the_histogram_path_is_the_one_the_figure_script_writes(payload):
    assert payload["sections"]["distribution"]["figure"] == report.histogram_path("demo")


def test_quantiles_are_present_and_ordered(payload):
    values = list(payload["sections"]["distribution"]["quantiles"].values())
    assert values == sorted(values)


def test_coverage_json_computes_the_fraction_per_class():
    block = coverage_json(COVERAGE)
    assert block["fraction"] == pytest.approx(4 / 6, abs=1e-4)
    assert block["by_consequence"][0]["consequence"] == "missense_variant"
    assert block["by_consequence"][0]["fraction"] == pytest.approx(0.75)


def test_an_empty_lane_produces_a_report_rather_than_an_exception(model_rank):
    empty = report.model_report_json(CARD, {"scored": 0, "total": 6}, {}, model_rank, "x")
    assert empty["sections"]["distribution"]["n"] == 0
    assert empty["sections"]["distribution"]["quantiles"] == {}
    assert "## 3." in report.render_model_report(empty)


# ── section 5, the clinical half ─────────────────────────────────────────────────────────


def test_the_clinical_sentence_names_the_rank_the_term_set_and_the_table():
    text = hpo_sentence(
        {"rank": 3, "genes_considered": 4812, "score": 0.87}, gene="BUB1B", model="demo"
    )
    assert "#3 of 4812" in text
    assert "with-parental" in text
    assert "warehouse.hpo_gene_scores" in text


def test_a_model_that_ignores_the_phenotype_says_so_in_one_sentence():
    blind = hpo_sentence(None, gene="BUB1B", model="demo")
    aware = hpo_sentence(None, gene="BUB1B", model="demo", uses_phenotype=True)
    assert "never sees the phenotype" in blind
    assert "takes the phenotype as an input" in aware
    assert "never sees the phenotype" not in aware


def test_a_missing_hpo_row_is_stated_rather_than_invented():
    text = hpo_sentence(None, gene="BUB1B", model="demo")
    assert "produced no `BUB1B` row" in text


# ── the Markdown ─────────────────────────────────────────────────────────────────────────


def test_all_seven_sections_render_in_order(payload):
    text = report.render_model_report(payload)
    positions = [text.index(f"## {i}. {title}") for i, title in enumerate(SECTION_TITLES, 1)]
    assert positions == sorted(positions)


def test_the_interpretation_slot_is_marked_with_the_date_and_the_llm_mode(payload):
    text = report.render_model_report(payload)
    assert "<!-- interpretation: hand-written 2026-09-18 | llm:none -->" in text


def test_the_markdown_prints_the_rank_the_json_holds(payload):
    text = report.render_model_report(payload)
    assert "| `GB` | 1 | 2 | 50.00 % | 0.7 | 0.8 |" in text


def test_changing_a_number_in_the_json_changes_the_markdown(payload):
    payload["sections"]["confirmed_pair"]["rank"] = 42
    assert "| 42 |" in report.render_model_report(payload)


def test_the_renderer_computes_nothing_of_its_own(payload):
    """Blank every number in one section; nothing numeric may survive into its Markdown."""
    payload["sections"]["limitations"].update(
        {
            "seconds": None,
            "dollars": None,
            "licence": "",
            "venue": "",
            "run_id": "",
            "limitations": [],
        }
    )
    text = report.render_model_report(payload)
    section = text.split("## 7.")[1]
    assert not re.search(r"\d", section.split("| run id")[0].replace("|", ""))


def test_a_catalogue_adjacent_lane_says_so_in_its_limitations(model_rank):
    adjacent = report.model_report_json(
        {**CARD, "catalogue_adjacent": True}, COVERAGE, SCORES, model_rank, "x"
    )
    text = report.render_model_report(adjacent)
    assert "Catalogue-adjacent" in text
    assert "with and without this lane" in text


def test_the_unscored_pair_count_reaches_the_limitations(model_rank):
    partial = rank.rank_per_model(PAIRS, {"demo": {"a1": 0.1, "a2": 0.2}})["demo"]
    payload = report.model_report_json(CARD, COVERAGE, {"a1": 0.1, "a2": 0.2}, partial, "x")
    assert any(
        "left this ranking" in item for item in payload["sections"]["limitations"]["limitations"]
    )


def test_no_coordinate_ever_reaches_the_rendered_page(payload):
    text = report.render_model_report(payload)
    assert not re.search(r"chr\d", text)
    assert "pos" not in text.lower().split("## 1.")[0]


# ── the warehouse table ──────────────────────────────────────────────────────────────────


@pytest.fixture
def connection():
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    # The real warehouse has two schemas: `results` holds what a stage writes,
    # `warehouse` holds the append-only data_lineage edge list. Emulating only one
    # let a writer point its lineage at `results` and pass here while failing on the
    # first real run (entry 128).
    con.execute("CREATE SCHEMA pg.warehouse")
    from mva.warehouse.lineage import ensure_lineage_table

    ensure_lineage_table(con, "results")
    return con


def test_write_reports_stores_the_json_and_one_lineage_edge(connection, payload):
    assert report.write_reports(connection, "results", [payload], run_id="run-1") == 1
    row = connection.execute(
        f"SELECT model, version, run_id, report_json FROM pg.results.{report.MODEL_REPORTS_TABLE}"
    ).fetchone()
    assert row[:3] == ("demo", "2.1", "run-1")
    assert json.loads(row[3])["sections"]["confirmed_pair"]["rank"] == 1
    edge = connection.execute(
        "SELECT target_table, target_rows FROM pg.warehouse.data_lineage"
    ).fetchone()
    assert edge == (report.MODEL_REPORTS_TABLE, 1)


def test_write_markdown_names_the_file_after_the_lane(tmp_path, payload):
    written = report.write_markdown([payload], tmp_path)
    assert [p.name for p in written] == ["demo.md"]
    assert written[0].read_text(encoding="utf-8").startswith("# demo")
