"""Step 7's modules, offline: names, the ladder, the shortlist, the decoy comparison, the
decoy card and the drug-level literature terms.

Every card here is the invented ``GENEA`` fixture or a second invented card built in the test,
so a passing test cannot be passing because the code knows the real case. No genomic position
appears anywhere: gene symbols, drug names, PMIDs and counts only.
"""

from __future__ import annotations

import json
from pathlib import Path

from mva.drugs import compare, ladder, mechlit, shortlist
from mva.drugs.decoy import DecoySpec, decoy_card
from mva.drugs.mechanism import MechanismCard, load
from mva.drugs.names import base_name
from test_drugs_support import FIXTURES

CARD = load(FIXTURES / "card.json")


def card_with(extra: dict, tmp_path: Path) -> MechanismCard:
    """The fixture card plus a few blocks step 7 reads, written to disk and re-loaded."""
    raw = json.loads((FIXTURES / "card.json").read_text(encoding="utf-8"))
    raw.update(extra)
    path = tmp_path / "card.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load(path)


STEP7_BLOCKS = {
    "anti_directions": [
        {
            "id": "A1",
            "name": "weaken it further",
            "moa_pattern": r"KINASEX inhibitor",
            "status": "do not",
        },
        {"id": "A2", "name": "spindle poisons", "moa_pattern": r"tubulin", "status": "caution"},
    ],
    "case": {
        "disease": "Fabricated syndrome",
        "tumour_context": "sarcomaX (a fabricated tumour)",
        "context_standard_of_care": {"drugs": ["OLDCYTOTOXIN"]},
    },
}


def candidates() -> list[dict]:
    return [
        # approved, on a seed target of D2, salt spelling
        {
            "drug_name": "DRUGA HYDROCHLORIDE",
            "target_symbol": "GENEB",
            "direction_ids": "D2",
            "approved": "true",
            "fda_label": "true",
            "action_type": "INHIBITOR",
            "interaction_or_moa": "GENEB inhibitor",
        },
        {
            "drug_name": "DRUGA",
            "target_symbol": "GENEB",
            "direction_ids": "D2",
            "approved": "true",
            "fda_label": "",
            "action_type": "INHIBITOR",
            "interaction_or_moa": "",
        },
        # approved anti-direction drug
        {
            "drug_name": "POISON",
            "target_symbol": "TUBB",
            "direction_ids": "",
            "approved": "true",
            "fda_label": "true",
            "action_type": "INHIBITOR",
            "interaction_or_moa": "tubulin binder",
        },
        # approved standard-of-care drug in the tumour context
        {
            "drug_name": "OLDCYTOTOXIN",
            "target_symbol": "GENEC",
            "direction_ids": "D4",
            "approved": "true",
            "fda_label": "true",
            "action_type": "INHIBITOR",
            "interaction_or_moa": "",
        },
        # not approved: never enters the ladder
        {
            "drug_name": "TOOLCOMPOUND",
            "target_symbol": "GENEB",
            "direction_ids": "D2",
            "approved": "false",
            "fda_label": "",
            "action_type": "INHIBITOR",
            "interaction_or_moa": "",
        },
    ]


def trials() -> list[dict]:
    context = "sarcomaX"
    return [
        {"nct_id": "NCT0", "query": f"cond={context} intr=OLDCYTOTOXIN"},
        {"nct_id": "NCT1", "query": f"cond={context} intr=DRUGA HYDROCHLORIDE"},
        {"nct_id": "NCT2", "query": "cond=Fabricated syndrome"},
    ]


def evidence() -> list[dict]:
    return [
        {
            "drug_name": "DRUGA",
            "direction_id": "D2",
            "rung": "2",
            "model": "cell",
            "pmid": "1",
            "target": "GENEB",
            "claim": "x",
            "proxy": "false",
            "proxy_of": "",
        },
        {
            "drug_name": "CURATEDONLY",
            "direction_id": "D3",
            "rung": "3",
            "model": "in vivo",
            "pmid": "2",
            "target": "GENED",
            "claim": "y",
            "proxy": "true",
            "proxy_of": "PRECURSOR",
        },
    ]


# ── names ────────────────────────────────────────────────────────────────────────────


def test_a_salt_is_folded_off_and_a_leading_salt_word_is_kept() -> None:
    assert base_name("Metformin Hydrochloride") == "METFORMIN"
    assert base_name("ATORVASTATIN CALCIUM") == "ATORVASTATIN"
    assert base_name("SODIUM PHENYLBUTYRATE") == "SODIUM PHENYLBUTYRATE"
    assert base_name("paclitaxel protein-bound") == "PACLITAXEL"


# ── the ladder ───────────────────────────────────────────────────────────────────────


def test_the_rung_is_the_higher_of_automated_and_curated_and_both_are_printed(
    tmp_path: Path,
) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    labels = {"DRUGA": {"has_label": True, "pediatric_use": True}}
    rows = ladder.assign(
        ladder.LadderInputs(card, candidates(), trials(), [], [], labels, evidence())
    )
    druga = next(r for r in rows if r["drug_name"] == "DRUGA")
    # approved + context trial + paediatric label → automated 5; curated 2; rung 5
    assert druga["automated_rung"] == 5
    assert druga["curated_rung"] == 2
    assert druga["rung"] == 5
    assert druga["curated_pmids"] == ("1",)
    assert druga["proxy"] is False
    assert druga["targets"] == ("GENEB",)
    assert druga["fda_label"] is True  # the salt row carried the label, the base row did not


def test_a_curated_only_drug_gets_a_row_and_says_so(tmp_path: Path) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    rows = ladder.assign(ladder.LadderInputs(card, candidates(), trials(), [], [], {}, evidence()))
    row = next(r for r in rows if r["drug_name"] == "CURATEDONLY")
    assert row["rung"] == 3
    assert row["automated_rung"] == 1
    assert "curated_only" in row["flags"]
    assert "approval_unverified" in row["flags"]  # no label answer was supplied
    assert row["targets"] == ("GENED",)
    assert row["proxy"] is True


def test_anti_direction_and_standard_of_care_are_flagged_not_dropped(tmp_path: Path) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    rows = ladder.assign(ladder.LadderInputs(card, candidates(), trials(), [], [], {}, evidence()))
    poison = next(r for r in rows if r["drug_name"] == "POISON")
    assert "A2" in poison["flags"]
    assert poison["direction_id"] == "pathway"
    old = next(r for r in rows if r["drug_name"] == "OLDCYTOTOXIN")
    assert "standard_of_care" in old["flags"]
    assert old["automated_rung"] == 4  # a context trial, but no paediatric evidence supplied
    assert all(r["drug_name"] != "TOOLCOMPOUND" for r in rows)


def test_rows_come_highest_rung_first() -> None:
    rows = ladder.assign(ladder.LadderInputs(CARD, candidates(), trials(), [], [], {}, evidence()))
    rungs = [r["rung"] for r in rows]
    assert rungs == sorted(rungs, reverse=True)


# ── the shortlist and the do-not table ──────────────────────────────────────────────


def test_the_shortlist_keeps_rung_2_plus_and_sets_aside_anti_and_standard_of_care(
    tmp_path: Path,
) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    rows = ladder.assign(ladder.LadderInputs(card, candidates(), trials(), [], [], {}, evidence()))
    short = shortlist.shortlist(rows, card)
    names = {r["drug_name"] for r in short}
    assert names == {"DRUGA", "CURATEDONLY"}
    assert "POISON" not in names  # an anti-direction flag
    assert "OLDCYTOTOXIN" not in names  # the standard of care, rung 4 and still set aside
    assert all(r["rung"] >= shortlist.MIN_RUNG for r in short)


def test_the_shortlist_orders_by_rung_then_molecule_level_evidence(tmp_path: Path) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    rows = ladder.assign(ladder.LadderInputs(card, candidates(), trials(), [], [], {}, evidence()))
    short = shortlist.shortlist(rows, card)
    assert short[0]["rank"] == 1
    assert short[0]["drug_name"] == "DRUGA" and short[0]["rung"] == 4
    assert short[1]["drug_name"] == "CURATEDONLY" and short[1]["rung"] == 3
    assert "rung 4" in short[0]["why"]
    assert short[1]["verdict"] == "argue - approval to verify"


def test_the_do_not_table_names_the_anti_direction_status_and_the_standard_of_care(
    tmp_path: Path,
) -> None:
    card = card_with(STEP7_BLOCKS, tmp_path)
    rows = ladder.assign(ladder.LadderInputs(card, candidates(), trials(), [], [], {}, evidence()))
    table = shortlist.do_not_table(rows, card)
    by_name = {r["drug_name"]: r for r in table}
    assert by_name["POISON"]["verdict"] == "caution"
    assert by_name["POISON"]["why"].startswith("A2")
    assert by_name["OLDCYTOTOXIN"]["verdict"] == "standard of care"
    assert "DRUGA" not in by_name


# ── the decoy comparison ────────────────────────────────────────────────────────────


def test_jaccard_counts_base_names_once_and_lists_the_shared_drugs() -> None:
    decoy_rows = [
        {
            "drug_name": "DRUGA CALCIUM",
            "approved": "true",
            "fda_label": "true",
            "direction_ids": "D1",
        },
        {"drug_name": "OTHER", "approved": "true", "fda_label": "", "direction_ids": "D1"},
        {"drug_name": "NOTAPPROVED", "approved": "false", "fda_label": "", "direction_ids": "D1"},
    ]
    rows = compare.compare(CARD, candidates(), "DECOYGENE", decoy_rows, [])
    d2 = next(r for r in rows if r["direction_id"] == "D2")
    assert d2["direction_approved"] == 1  # DRUGA, two spellings, once
    assert d2["decoy_approved"] == 2
    assert d2["shared"] == 1 and d2["shared_drugs"] == ("DRUGA",)
    assert d2["jaccard"] == 0.5
    assert d2["decoy_with_fda_label"] == 1
    assert rows[-1]["direction_id"] == "all"


# ── the decoy card ──────────────────────────────────────────────────────────────────


def test_a_decoy_card_keeps_the_clinical_side_and_replaces_the_gene() -> None:
    spec = DecoySpec("GENEZ", "P99999", "a fabricated enzyme", "purine", "picked by a stated rule")
    card = decoy_card(CARD, spec, today="2099-01-01")
    assert card["gene"]["symbol"] == "GENEZ"
    assert card["case"] == CARD.raw.get("case", {})
    assert card["alleles"] == []
    assert card["decoy"]["control_for"] == CARD.gene_symbol
    assert card["repurposing_directions"][0]["seed_targets"] == ["GENEZ"]
    assert "DECOY" in card["_standing"]
    assert card["history"][0]["date"] == "2099-01-01"


# ── the drug-level literature terms ─────────────────────────────────────────────────


def test_the_mechanism_term_is_built_from_the_card_and_never_typed() -> None:
    term = mechlit.mechanism_term(CARD)
    assert term.startswith("(") and term.endswith(")")
    assert CARD.gene_symbol in term
    assert " OR " in term
