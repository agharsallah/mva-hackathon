"""Derived submission rows: facts from a table, epcr from a register anchor, priors from rows."""

from __future__ import annotations

import duckdb
import pytest

from mva.warehouse.submission_facts import AlleleFacts, fetch_facts
from mva.warehouse.submission_rows import DerivationError, derive
from mva.warehouse.submission_spec import Selector

TABLE = "results.coding_candidates"


@pytest.fixture
def connection():
    con = duckdb.connect()
    con.execute("ATTACH ':memory:' AS pg")
    con.execute("CREATE SCHEMA pg.results")
    con.execute(
        f"CREATE TABLE pg.{TABLE} (gene VARCHAR, chrom VARCHAR, pos BIGINT, ref VARCHAR, "
        "alt VARCHAR, gt VARCHAR, filter VARCHAR, dp INTEGER, vaf DOUBLE, consequence VARCHAR, "
        "gnomad_af DOUBLE, clin_sig VARCHAR, rsid VARCHAR, is_clinvar_plp BOOLEAN)"
    )
    con.execute(
        f"INSERT INTO pg.{TABLE} VALUES "
        "('GENEA', '15', 1001, 'T', 'G', '0/1', 'PASS', 44, 0.48, 'stop_gained', 3e-5, "
        "'Pathogenic', 'rs1', true), "
        "('GENEA', '15', 1002, 'T', 'G', '0/1', 'PASS', 40, 0.51, "
        "'missense_variant,splice_region_variant', NULL, NULL, NULL, false), "
        "('GENEA', '15', 1003, 'A', 'C', '0/1', 'PASS', 30, 0.5, 'intron_variant', 0.002, "
        "NULL, NULL, false), "
        "('GENEB', '2', 2001, 'C', 'A', '0/1', 'PASS', 35, 0.5, 'stop_gained', 1e-6, "
        "'Pathogenic/Likely_pathogenic', 'rs2', true)"
    )
    return con


def selector(*where):
    return Selector.from_json("x", {"table": TABLE, "where": list(where)})


def facts_of(connection):
    return {
        "stop": fetch_facts(
            connection, "stop", selector(["gene", "=", "GENEA"], ["consequence", "like", "%stop%"])
        ),
        "mis": fetch_facts(
            connection,
            "mis",
            selector(["gene", "=", "GENEA"], ["consequence", "like", "%missense%"]),
        ),
        "intron": fetch_facts(
            connection, "intron", selector(["consequence", "=", "intron_variant"])
        ),
        "other": fetch_facts(connection, "other", selector(["gene", "=", "GENEB"])),
    }


def spec(**overrides):
    base = {
        "derivation": {"anchor": {"row": "stop+mis", "hypothesis": "H009"}},
        "rows": [
            {"variant": "stop", "partner": "mis", "hypothesis": "H009"},
            {"variant": "stop", "partner": "intron"},
            {"variant": "mis", "partner": "intron"},
            {"variant": "other", "finding_type": "secondary", "rationale": "carrier state"},
        ],
        "hypotheses": [
            {"label": "stop+mis", "alleles": ["stop", "mis"]},
            {"label": "stop+intron", "alleles": ["stop", "intron"]},
            {"label": "mis+intron", "alleles": ["mis", "intron"]},
            {"label": "stop+unseen", "alleles": ["stop", "_unknown_1"], "prior": 0.2},
        ],
    }
    base.update(overrides)
    return base


def test_facts_come_from_the_table_and_carry_no_position(connection):
    facts = facts_of(connection)["stop"]
    assert facts.gene == "GENEA"
    assert facts.zygosity == "het"
    assert facts.dp == 44
    assert facts.clin_sig == "Pathogenic"
    assert facts.score == 1.0  # rare (3e-5) × loss of function
    assert "1001" not in facts.describe()
    assert "1001" not in str(facts.to_json())


def test_most_severe_consequence_is_the_first_vep_term(connection):
    mis = facts_of(connection)["mis"]
    assert mis.most_severe == "missense_variant"
    assert mis.score == pytest.approx(0.5 * 0.6)  # gnomAD-absent × protein-altering


def test_epcr_anchors_on_the_register_and_shares_the_residual(connection):
    found = derive(spec(), facts_of(connection), anchor_confidence=0.9)
    by_label = {row.label: row for row in found.rows}
    assert by_label["stop+mis"].epcr == 0.9
    # stop+intron scores 1.0 + 0.05×0.1; mis+intron scores 0.3 + 0.005; residual 0.1 split
    stop_intron, mis_intron = by_label["stop+intron"], by_label["mis+intron"]
    assert stop_intron.epcr > mis_intron.epcr > by_label["other"].epcr > 0
    assert stop_intron.epcr + mis_intron.epcr == pytest.approx(0.1, abs=1e-3)
    assert [row.epcr for row in found.rows] == sorted((r.epcr for r in found.rows), reverse=True)


def test_notes_quote_table_columns_and_the_rationale(connection):
    found = derive(spec(), facts_of(connection), anchor_confidence=0.9)
    top = found.rows[0]
    assert top.notes.startswith("H:H009 | primary | GENEA stop_gained, het PASS DP 44 VAF 0.48")
    assert "gnomAD 3e-05" in top.notes
    assert "ClinVar Pathogenic" in top.notes
    assert "not a calibrated posterior" in top.notes
    secondary = found.rows[-1]
    assert "carrier state" in secondary.notes
    assert "not scored" in secondary.notes


def test_priors_follow_the_rows_and_leave_the_declared_unseen_mass(connection):
    found = derive(spec(), facts_of(connection), anchor_confidence=0.9)
    priors = {h["label"]: h["prior"] for h in found.hypotheses}
    assert priors["stop+unseen"] == 0.2
    assert sum(priors.values()) == pytest.approx(1.0, abs=1e-3)
    assert priors["stop+mis"] > priors["stop+intron"] > priors["mis+intron"]
    assert (
        next(h for h in found.hypotheses if h["label"] == "stop+mis")["prior_source"]
        == "row stop+mis"
    )


def test_hand_typed_values_are_refused(connection):
    facts = facts_of(connection)
    with pytest.raises(DerivationError, match="'epcr' is derived"):
        derive(spec(rows=[{"variant": "stop", "partner": "mis", "epcr": 0.9}]), facts, 0.9)
    with pytest.raises(DerivationError, match="contains a number"):
        rows = spec()["rows"]
        rows[0] = {**rows[0], "rationale": "CADD 24.5"}
        derive(spec(rows=rows), facts, 0.9)
    rows = spec()["rows"]
    rows[0] = {**rows[0], "rationale": "BUB1B first among biallelic genes, rs6025 nearby"}
    derive(spec(rows=rows), facts, 0.9)  # identifiers with digits are words, not numbers
    with pytest.raises(DerivationError, match="prior is derived"):
        hyps = spec()["hypotheses"]
        hyps[0] = {**hyps[0], "prior": 0.7}
        derive(spec(hypotheses=hyps), facts, 0.9)
    with pytest.raises(DerivationError, match="must declare a prior"):
        hyps = spec()["hypotheses"]
        hyps[3] = {"label": "stop+unseen", "alleles": ["stop", "_unknown_1"]}
        derive(spec(hypotheses=hyps), facts, 0.9)


def test_the_anchor_must_be_the_row_the_ranker_prefers(connection):
    facts = facts_of(connection)
    bad = spec(derivation={"anchor": {"row": "mis+intron", "hypothesis": "H009"}})
    with pytest.raises(DerivationError, match="the register and the ranker disagree"):
        derive(bad, facts, 0.9)
    with pytest.raises(DerivationError, match="exactly one primary row"):
        derive(spec(derivation={"anchor": {"row": "nope"}}), facts, 0.9)


def test_a_tie_in_the_data_is_an_error_not_a_file_order(connection):
    facts = facts_of(connection)
    facts["mis2"] = AlleleFacts(
        name="mis2", table=TABLE, gene="GENEA", consequence="missense_variant"
    )
    rows = [
        *spec()["rows"][:1],
        {"variant": "stop", "partner": "intron"},
        {"variant": "stop", "partner": "mis2", "label": "twin"},
    ]
    facts["intron"] = AlleleFacts(
        name="intron", table=TABLE, gene="GENEA", consequence="missense_variant"
    )
    with pytest.raises(DerivationError, match="both derive epcr"):
        derive(spec(rows=rows, hypotheses=[]), facts, 0.9)


def test_derivation_json_is_coordinate_free_and_carries_the_arithmetic(connection):
    found = derive(spec(), facts_of(connection), anchor_confidence=0.9)
    payload = found.to_json()
    assert payload["anchor"] == {"row": "stop+mis", "hypothesis": "H009", "confidence": 0.9}
    assert {"stop", "mis", "intron", "other"} == set(payload["alleles"])
    assert any(line.startswith("anchor:") for line in payload["arithmetic"])
    assert any(line.startswith("prior stop+mis") for line in payload["arithmetic"])
    assert "1001" not in str(payload) and "2001" not in str(payload)
