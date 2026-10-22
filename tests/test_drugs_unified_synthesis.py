"""Tests for ``mva.drugs.unified_synthesis`` (Entry 163 cross-iteration synthesis)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mva.drugs.unified_clinical import (
    BENCHMARK_COLUMNS,
    PKPD_COLUMNS,
    POCKET_COLUMNS,
    build_clinical_tables,
)
from mva.drugs.unified_synthesis import (
    CANDIDATE_COLUMNS,
    COMPARISON_COLUMNS,
    SWEEP_COLUMNS,
    build_synthesis,
)

ATLAS = Path("ressources/track2/bub1b_atlas.parquet")
ALLELES = Path("ressources/track2/bub1b_published_alleles.tsv")
CONFIG = Path("ressources/track2/it5/decision_config.json")
CANDIDATES = (
    Path("ressources/track2/it5/readthrough_candidates.tsv"),
    Path("ressources/track2/it5/protein_candidates.tsv"),
    Path("ressources/track2/it5/literature_candidates.tsv"),
)
SAFETY = (
    Path("ressources/track2/candidate_safety.tsv"),
    Path("ressources/track2/it4/candidate_safety.tsv"),
    Path("ressources/track2/it5/candidate_safety.tsv"),
)
IT2_SHORTLIST = Path("ressources/track2/shortlist.tsv")
IT4_CANDIDATES = Path("ressources/track2/it4/candidates.tsv")


def test_build_synthesis_reproduces_r4_and_calibrates_hierarchy() -> None:
    res = build_synthesis(
        config_path=CONFIG,
        candidate_paths=CANDIDATES,
        safety_paths=SAFETY,
        it2_shortlist_path=IT2_SHORTLIST,
        it4_candidates_path=IT4_CANDIDATES,
    )
    ledger = {row["drug"]: row for row in res["ledger"]}
    assert len(ledger) == 52
    assert tuple(res["ledger"][0].keys()) == CANDIDATE_COLUMNS
    assert tuple(res["comparison"][0].keys()) == COMPARISON_COLUMNS
    assert tuple(res["sweep"][0].keys()) == SWEEP_COLUMNS

    # Uncalibrated R4 exact reproduction
    assert ledger["GLICLAZIDE"]["uncalibrated_u_unstable"] == pytest.approx(0.7000)
    assert ledger["GLICLAZIDE"]["uncalibrated_eu"] == pytest.approx(0.3850)
    assert ledger["DASATINIB"]["uncalibrated_u_inactive"] == pytest.approx(0.4000)
    assert ledger["DASATINIB"]["uncalibrated_eu"] == pytest.approx(0.2537)

    # Calibrated R5 (w_R2 = 0.25) hierarchy restoration
    assert ledger["NMN"]["calibrated_u_unstable"] == pytest.approx(0.4800)
    assert ledger["NMN"]["calibrated_eu"] == pytest.approx(0.2640)
    assert ledger["NIACIN"]["calibrated_u_unstable"] == pytest.approx(0.1920)
    assert ledger["NICOTINAMIDE"]["calibrated_u_unstable"] == pytest.approx(0.1920)
    assert ledger["GLICLAZIDE"]["calibrated_u_unstable"] == pytest.approx(0.1750)
    assert ledger["NIACIN"]["calibrated_u_unstable"] > ledger["GLICLAZIDE"]["calibrated_u_unstable"]
    assert ledger["NIACIN"]["iterations"] == "it2|it4|it5"
    assert ledger["DASATINIB"]["it4_generators"] == "twin|prism"

    # Tumour-context D4 leads restored from Iteration 2
    assert ledger["SIMVASTATIN"]["tumour_context_rung"] == 5
    assert ledger["LOVASTATIN"]["tumour_context_rung"] == 5
    assert ledger["SIMVASTATIN"]["clinical_role"] == "lead_tumour_context_post_pgx"

    # Sweep invariants across all 20 route weights
    sweep = res["sweep"]
    assert len(sweep) == 20
    for row in sweep:
        assert row["evpi"] == pytest.approx(0.1800)
        assert 0.59 <= row["evsi_share_of_evpi"] <= 0.70
        assert row["best_if_inactive"] == "DASATINIB"


def test_build_clinical_tables_pocket_benchmark_and_pkpd() -> None:
    tables = build_clinical_tables(ATLAS, ALLELES)
    assert len(tables["pocket_audit"]) == 5
    assert tuple(tables["pocket_audit"][0].keys()) == POCKET_COLUMNS
    assert "62/285" in tables["pocket_audit"][1]["pseudokinase_core_reference"]
    assert "72.2%" in tables["pocket_audit"][2]["pseudokinase_core_reference"]

    assert len(tables["benchmark"]) == 5
    assert tuple(tables["benchmark"][0].keys()) == BENCHMARK_COLUMNS
    assert tables["benchmark"][0]["archetype_id"] == "A1_target_lookup"

    assert len(tables["pkpd"]) == 8
    assert tuple(tables["pkpd"][0].keys()) == PKPD_COLUMNS
    pkpd_drugs = {r["drug"] for r in tables["pkpd"]}
    assert {"NICOTINAMIDE", "NIACIN", "NMN", "DASATINIB", "SIMVASTATIN", "LOVASTATIN"} <= pkpd_drugs
