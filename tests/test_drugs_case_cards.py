"""The three seams that let iteration 5's routes take a second disease as configuration.

Each route had one constant that was really a case parameter, and each is now supplied by a
**case card**. A test here fails if a route starts hard-coding the first case again:

* R3 vocabulary — ``litmine_verify.intervention_enums``: what an extracted row may be *about*.
* R3 rubric — ``litmine_translate.strength``/``candidates``: how directly an effect speaks to
  the gene's amount.
* R1 prose — ``readthrough_manifests.*(case_notes=...)``: the assumptions a manifest carries.

Plus the second case's own R1 card, checked as arithmetic: a carrier must land at the healthy
rung and the modelled homozygote at the syndrome rung.

Offline by construction: no fetcher, no file read, no socket. The vocabularies used for the
seam tests are invented, so a test that passed only because the code hard-codes this repo's
real cases would fail here.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mva.drugs import readthrough_case, readthrough_case_blm, readthrough_manifests
from mva.drugs.litmine_translate import RUBRIC, candidates, strength
from mva.drugs.litmine_verify import (
    INTERVENTION_ENUMS,
    INTERVENTION_FIELDS,
    intervention_enums,
    verify_rows,
)

INVENTED = ("widget_level", "sprocket", "other")
TEXTS = {"9": {"abstract": "Removing the widget raised the sprocket count in every replicate."}}


def _row(effect_on: str) -> dict[str, str]:
    return {
        "intervention": "invented compound",
        "intervention_type": "drug",
        "mode": "loss",
        "target": "widget",
        "effect_on": effect_on,
        "direction": "increase",
        "model_system": "human_cells",
        "pmid": "9",
        "quote": "Removing the widget raised the sprocket count in every replicate.",
    }


# ── R3 seam 1: the effect vocabulary is the card's, not the module's ─────────────────────


def test_card_vocabulary_replaces_the_default_and_keeps_the_rest() -> None:
    enums = intervention_enums(INVENTED)
    assert enums["effect_on"] == frozenset(INVENTED)
    for key, allowed in INTERVENTION_ENUMS.items():
        if key != "effect_on":
            assert enums[key] == allowed


def test_a_second_case_vocabulary_is_accepted_and_the_first_still_rejects_it() -> None:
    """The same row is evidence under its own card and a schema error under the other."""
    kept, rejected = verify_rows(
        [_row("sprocket")],
        TEXTS,
        required=INTERVENTION_FIELDS,
        enums=intervention_enums(INVENTED),
    )
    assert len(kept) == 1 and not rejected
    kept, rejected = verify_rows(
        [_row("sprocket")], TEXTS, required=INTERVENTION_FIELDS, enums=INTERVENTION_ENUMS
    )
    assert not kept
    assert rejected[0]["reject_reason"] == "bad_value:effect_on"


# ── R3 seam 2: the directness rubric is the card's ───────────────────────────────────────


def test_strength_uses_the_card_directness_scale() -> None:
    rows = [_row("sprocket")]
    # model human_cells 0.6 × directness × replication (one pmid) 0.6 × translation 1.0
    assert strength(rows, "direct_approved", {"sprocket": 1.0}) == 0.36
    assert strength(rows, "direct_approved", {"sprocket": 0.5}) == 0.18
    # Absent from the map means "this effect says nothing about the amount": score 0.
    assert strength(rows, "direct_approved", {"widget_level": 1.0}) == 0.0
    # No map at all falls back to the first case's rubric, which does not know "sprocket".
    assert strength(rows, "direct_approved") == 0.0
    assert "sprocket" not in RUBRIC["directness"]


def test_candidates_pick_the_lead_row_by_the_card_scale() -> None:
    mapped = [
        {
            "intervention": "invented compound",
            "intervention_type": "drug",
            "mode": "loss",
            "target": "widget",
            "benefit_rows": [_row("sprocket"), _row("other")],
            "drugs": [
                {
                    "drug_name": "invented drug",
                    "mapping": "direct",
                    "max_phase": 4,
                    "direction_check": "match",
                    "molecule_chembl_id": "CHEMBL0",
                }
            ],
        }
    ]
    rows = candidates(
        mapped,
        branch_by_effect={"sprocket": "branch_a", "other": "branch_b"},
        control_passed=True,
        directness={"sprocket": 1.0, "other": 0.1},
    )
    assert [r["branch"] for r in rows] == ["branch_a"]
    assert rows[0]["evidence_strength"] == 0.36


# ── R1 seam: the manifest's prose comes from the card ────────────────────────────────────


#: A stand-in case card's prose block: the same attribute names ``readthrough_notes`` has.
_Notes = SimpleNamespace(
    READTHROUGH_ASSUMPTIONS="invented assumption",
    READTHROUGH_LIMITATIONS="invented limitation",
    READTHROUGH_COLUMN_NOTES={"col": "invented column note"},
    SOURCES={"literature": "invented source"},
)


def test_readthrough_manifest_takes_its_prose_from_the_card(tmp_path: Path) -> None:
    table = tmp_path / "table.tsv"
    table.write_text("a\tb\n1\t2\n", encoding="utf-8")
    kwargs = {
        "entry": "entry",
        "output_path": table,
        "rows": 1,
        "workbook": tmp_path / "absent.xlsx",
        "workbook_url": "https://example.invalid/x",
        "stop_facts": tmp_path / "absent.json",
        "parameters": {},
    }
    swapped = readthrough_manifests.readthrough_manifest(**kwargs, case_notes=_Notes)
    assert swapped["assumptions"] == "invented assumption"
    assert swapped["sources"] == {"literature": "invented source"}
    default = readthrough_manifests.readthrough_manifest(**kwargs)
    assert default["assumptions"] != "invented assumption"


# ── the second case's R1 card, as arithmetic ─────────────────────────────────────────────


def test_blm_card_carrier_is_healthy_and_the_homozygote_is_at_the_syndrome_rung() -> None:
    from mva.drugs.readthrough_dosage import evaluate, nearest_threshold

    scenarios = {s.label: s for s in readthrough_case_blm.scenarios({}, {})}
    carrier = evaluate(scenarios["heterozygous carrier (a parent)"])
    homozygote = evaluate(scenarios["Bloom syndrome, homozygous p.Gln548Ter (untreated)"])
    assert carrier.percent == 50.0
    assert homozygote.percent == 0.0
    assert nearest_threshold(carrier, readthrough_case_blm.THRESHOLDS).percent == 50.0
    assert nearest_threshold(homozygote, readthrough_case_blm.THRESHOLDS).percent == 0.0


def test_blm_card_keeps_the_dossier_off_and_names_its_own_allele() -> None:
    """The BUB1B dossier is hand-written content, so the transfer case must not inherit it."""
    assert readthrough_case_blm.DOSSIER is False
    assert getattr(readthrough_case, "DOSSIER", True) is True
    assert readthrough_case_blm.ALLELE["consequence"] == "stop_gained"
    assert "BLM_Q548X" in readthrough_case_blm.HOLDOUT_CONTEXTS
    assert not hasattr(readthrough_case, "ALLELE")


def test_a_readthrough_agent_moves_the_homozygote_off_zero() -> None:
    from mva.drugs.readthrough_dosage import evaluate

    scenarios = {s.label: s for s in readthrough_case_blm.scenarios({}, {"INVENTED": 0.5})}
    treated = evaluate(scenarios["homozygote + INVENTED (readthrough only)"])
    assert treated.percent > 0.0
    assert treated.gain == treated.total
