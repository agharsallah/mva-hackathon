"""Tests for ``mva.drugs.unified_synthesis`` (Entry 163 cross-iteration synthesis)."""

from __future__ import annotations

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

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

    sensitivity = res["sensitivity"]
    summary = sensitivity["summary"]
    canonical = summary["canonical"]
    assert canonical["eu_baseline"] == pytest.approx(float(Fraction(48, 100) * Fraction(55, 100)))
    assert canonical["positive_p_unstable"] == pytest.approx(float(Fraction(187, 214)))
    assert canonical["negative_p_unstable"] == pytest.approx(float(Fraction(11, 62)))
    # Joint-positive NMN + joint-negative dasatinib minus pre-test NMN.
    exact_evsi = (
        Fraction(55, 100) * Fraction(85, 100) * Fraction(48, 100)
        + Fraction(55, 100) * Fraction(15, 100) * Fraction(134, 1000)
        + Fraction(45, 100) * Fraction(85, 100) * Fraction(4, 10)
        - Fraction(264, 1000)
    )
    assert canonical["evsi_blot"] == pytest.approx(float(exact_evsi))
    assert canonical["evsi_blot"] == pytest.approx(0.124455)
    assert summary["n_grid"] == 11 * 5 * 5 * 3 * 3 * 3 == 7425
    assert summary["n_captures_half_evpi"] == 3815
    assert summary["fraction_grid_captures_half_evpi"] == pytest.approx(3815 / 7425)
    assert summary["n_recommendation_changed_from_canonical"] == 4525
    assert summary["n_assay_changes_recommendation"] == 5996
    assert summary["ranges"]["evpi"] == pytest.approx([0.012, 0.24])
    assert summary["ranges"]["evsi_blot"] == pytest.approx([0.0, 0.2352])
    assert summary["ranges"]["evsi_share_of_evpi"] == pytest.approx([0.0, 0.98])
    assert summary["prior_flip_threshold_range"] == pytest.approx(
        [0.37523452157598497, 0.9090909090909092]
    )
    assert summary["canonical_parameters"]["blot_specificity"] == 0.85
    assert summary["canonical_parameters"]["blot_sensitivity"] == 0.85
    assert len(summary["exact_prior_recommendation_segments"]) == 27
    assert all(0 <= r["evsi_blot"] <= r["evpi"] + 1e-12 for r in sensitivity["rows"])
    assert all(abs(r["evsi_readthrough"]) < 1e-12 for r in sensitivity["rows"])
    _assert_grid_rows(sensitivity["rows"], canonical)


def _assert_grid_rows(rows: list[dict[str, Any]], canonical: dict[str, Any]) -> None:
    baseline_rows = []
    for row in rows:
        p = row["prior:missense_class=unstable"]
        se = row["test:chx_chase_blot:sensitivity"]
        sp = row["test:chx_chase_blot:specificity"]
        positive = p * se + (1 - p) * (1 - sp)
        negative = p * (1 - se) + (1 - p) * sp
        assert positive + negative == pytest.approx(1)
        assert row["positive_p_unstable"] == pytest.approx(p * se / positive)
        assert row["negative_p_unstable"] == pytest.approx(p * (1 - se) / negative)
        assert (
            positive * row["positive_p_unstable"] + negative * row["negative_p_unstable"]
        ) == pytest.approx(p)
        assert row["recommendation_changed_from_canonical"] == (
            row["best_action"] != canonical["best_action"]
        )
        assert row["assay_changes_recommendation"] == (
            row["positive_action"] != row["best_action"]
            or row["negative_action"] != row["best_action"]
        )
        if (
            p == 0.55
            and se == sp == 0.85
            and row["route:R2"] == 0.25
            and row["safety:unassessed"] == 0.6
            and row["applicability:missense_inactive:missense_class=unstable"] == 0
        ):
            baseline_rows.append(row)
    assert len(baseline_rows) == 1
    for key, value in canonical.items():
        if isinstance(value, float):
            assert baseline_rows[0][key] == pytest.approx(value, abs=1e-12)
        else:
            assert baseline_rows[0][key] == value


def test_unified_generator_persists_joint_grid() -> None:
    subprocess.run([sys.executable, "tools/it5_unified_synthesis.py"], check=True)
    out = Path("ressources/track2/it5/unified")
    summary = json.loads((out / "sensitivity_summary.json").read_text())
    unified = json.loads((out / "unified_summary.json").read_text())
    assert summary == unified["sensitivity"]
    lines = (out / "multidimensional_sensitivity.tsv").read_text().splitlines()
    assert len(lines) == summary["n_grid"] + 1
    from mva.drugs.unified_sensitivity import SENSITIVITY_COLUMNS

    assert lines[0].split("\t") == list(SENSITIVITY_COLUMNS)
    assert summary["grid"]["test:chx_chase_blot:specificity"] == [0.6, 0.75, 0.85, 0.95, 0.99]
    manifest = json.loads((out / "multidimensional_sensitivity.provenance.json").read_text())
    assert manifest["method"]["n_grid"] == 7425


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
    mechanisms = {r["drug"]: r["structural_or_target_mechanism"] for r in tables["pkpd"]}
    assert "raw +0.22 log2FC" in mechanisms["GLICLAZIDE"]
    assert "raw +0.20 log2FC" in mechanisms["MIGALASTAT"]
    assert "no independent replication" in mechanisms["GLICLAZIDE"]
    assert "no independent replication" in mechanisms["MIGALASTAT"]
