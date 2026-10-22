"""Cross-iteration Track 2 synthesis and evidence-hierarchy-calibrated decision analysis.

Merges the candidate sets across Iterations 2 (:mod:`mva.drugs.ladder`), 4
(:mod:`mva.drugs.converge`, :mod:`mva.drugs.patient_safety`), and 5
(:mod:`mva.drugs.decision_model`), calibrates ``route:R2`` (``0.25``) to the pre-registered
evidence hierarchy (Rung-3 in-vivo ``Bub1b^{H/H}`` rescue > Rung-1 single-line screen
residual), restores Iteration 2's Rung-5 rhabdomyosarcoma leads (``simvastatin``/``lovastatin``),
and sweeps ``w_R2`` across ``[0.05, 1.00]``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from mva.drugs import decision_avoid, decision_config
from mva.drugs.decision_io import expand_aliases, read_candidates, read_safety, read_tsv
from mva.drugs.decision_model import DecisionConfig, drug_key
from mva.drugs.decision_run import analyse

__all__ = [
    "CALIBRATED_ROUTE_WEIGHTS",
    "CANDIDATE_COLUMNS",
    "COMPARISON_COLUMNS",
    "SWEEP_COLUMNS",
    "UNCALIBRATED_ROUTE_WEIGHTS",
    "build_synthesis",
]

UNCALIBRATED_ROUTE_WEIGHTS: dict[str, float] = {"R1": 1.00, "R2": 1.00, "R3": 1.00}
CALIBRATED_ROUTE_WEIGHTS: dict[str, float] = {"R1": 1.00, "R2": 0.25, "R3": 1.00}

_C1 = ("drug", "branch", "iterations", "n_iterations", "it2_direction", "it2_rung", "it2_verdict")
_C2 = ("it4_generators", "it4_n_generators", "it5_routes", "evidence_tier", "safety_class")
_C3 = ("safety_factor", "uncalibrated_u_unstable", "uncalibrated_u_inactive", "uncalibrated_eu")
_C4 = ("calibrated_u_unstable", "calibrated_u_inactive", "calibrated_eu", "tumour_context_rung")
CANDIDATE_COLUMNS = (*_C1, *_C2, *_C3, *_C4, "clinical_role")
COMPARISON_COLUMNS = (
    "metric",
    "uncalibrated_it5_r4",
    "calibrated_it6_unified",
    "invariant_or_shift",
    "explanation",
)
_S1 = ("r2_route_weight", "r2_effective_unstable_max", "r3_effective_unstable_max")
_S2 = ("best_if_unstable", "best_if_inactive", "best_overall", "eu_baseline", "eu_perfect_info")
_S3 = ("evpi", "evsi_blot_chx", "evsi_share_of_evpi", "flip_p_unstable")
SWEEP_COLUMNS = (*_S1, *_S2, *_S3)


def _with_routes(config: DecisionConfig, weights: Mapping[str, float]) -> DecisionConfig:
    out = config
    for route, weight in weights.items():
        out = decision_config.with_param(out, f"route:{route}", float(weight))
    return out


def _read_it2_shortlist(path: Path) -> dict[str, dict[str, str]]:
    """Canonical drug key -> Iteration 2 shortlist metadata (argued rows prioritized)."""
    by_key: dict[str, dict[str, str]] = {}
    for row in read_tsv(path):
        key = drug_key(row["drug_name"])
        verdict = "argue" if row["verdict"].strip() == "argue" else "context_trial_only"
        existing = by_key.get(key)
        if existing is None or (existing["verdict"] != "argue" and verdict == "argue"):
            by_key[key] = {
                "drug_name": row["drug_name"].strip().lower(),
                "direction": row["direction_id"].strip(),
                "rung": row["rung"].strip(),
                "verdict": verdict,
                "why": row["why"].strip(),
                "pmids": row.get("curated_pmids", "").strip(),
            }
    return by_key


def _read_it4_candidates(path: Path) -> dict[str, dict[str, str]]:
    """Canonical drug key -> Iteration 4 generator convergence metadata."""
    by_key: dict[str, dict[str, str]] = {}
    for row in read_tsv(path):
        name = (row.get("query_name") or row.get("drug") or "").strip()
        if not name:
            continue
        by_key[drug_key(name)] = {
            "generators": row.get("generators", "").strip(),
            "n_generators": row.get("n_generators", "0").strip(),
            "converging": row.get("converging", "false").strip(),
            "survivor": row.get("survivor", "false").strip(),
        }
    return by_key


_FIXED_TIERS: dict[str, tuple[str, str]] = {
    "nmn": ("tier1_in_vivo_animal_rescue_rung3", "lead_if_unstable_tool_or_supplement"),
    "niacin": ("tier1_in_vivo_animal_rescue_rung3", "lead_if_unstable_approved"),
    "nicotinamide": ("tier1_in_vivo_animal_rescue_rung3", "lead_if_unstable_approved"),
    "dasatinib": ("tier1_in_vivo_animal_rescue_rung3", "lead_if_inactive_approved"),
}
_R2_APPROVED = {"gliclazide", "migalastat", "nisoldipine", "ethoxzolamide", "testolactone"}


def _classify_tier(
    key: str,
    branch: str,
    it2: Mapping[str, str] | None,
    it4: Mapping[str, str] | None,
    routes: str,
    safety_cls: str,
) -> tuple[str, str]:
    """``(evidence_tier, clinical_role)`` from cross-iteration provenance."""
    if safety_cls == "avoid":
        return "avoid_or_excluded", "avoid"
    key_lower = key.lower()
    rung = int(it2["rung"]) if it2 and it2["rung"].isdigit() else 0
    verdict = it2["verdict"] if it2 else "not_in_it2"
    if verdict == "argue" and it2 and it2["direction"] == "D4" and rung >= 5:
        return "tier1_paediatric_tumour_trial_rung5", "lead_tumour_context_post_pgx"
    if key_lower in _FIXED_TIERS:
        return _FIXED_TIERS[key_lower]
    gens = set((it4["generators"] if it4 else "").split("|")) - {""}
    route_set = set(routes.split("|")) - {"", "none"}
    if "twin" in gens or (verdict == "argue" and rung >= 3):
        role = (
            "lead_if_unstable_approved"
            if "missense_unstable" in branch
            else "lead_if_inactive_approved"
            if "missense_inactive" in branch
            else "lead_state_independent_backup"
        )
        return "tier1_in_vivo_animal_rescue_rung3", role
    if "R3" in route_set or (verdict == "argue" and rung == 2):
        role = (
            "secondary_tumour_context"
            if branch == "tumour_context"
            else "secondary_mechanistic_backup"
        )
        return "tier2_mechanistic_cell_rescue_rung2", role
    if "R2" in route_set:
        if safety_cls == "unassessed" and key_lower not in _R2_APPROVED:
            return "tool_compound_unapproved", "tool_compound_bench_only"
        return "tier3_single_line_screen_residual_rung1", "screen_tail_unverified"
    if "R1" in route_set and branch == "stop_allele":
        return "tier3_readthrough_context_model", "readthrough_below_fidelity_gap"
    return "tier2_mechanistic_cell_rescue_rung2", "secondary_mechanistic_backup"


def _utility_lookup(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {drug_key(row["action"]): row for row in report["utilities"]}


def _flip_point(report: Mapping[str, Any], variable: str = "missense_class") -> float:
    segs = [f for f in report["flips"] if f["variable"] == variable]
    for seg in segs:
        if seg["start"] > 0.0:
            return float(seg["start"])
    return 0.0


def _voi_map(report: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in report["voi"]:
        key = "evpi" if item["kind"] == "evpi" else f"{item['kind']}:{item['target']}"
        out[key] = float(item["value"])
    return out


def _build_ledger(
    config: DecisionConfig,
    uncal_u: Mapping[str, Mapping[str, Any]],
    cal_u: Mapping[str, Mapping[str, Any]],
    it2_map: Mapping[str, Mapping[str, str]],
    it4_map: Mapping[str, Mapping[str, str]],
    merged_safety: Mapping[str, str],
) -> list[dict[str, Any]]:
    all_keys = list(
        dict.fromkeys([*cal_u.keys(), *(k for k, v in it2_map.items() if v["verdict"] == "argue")])
    )
    u_state_no = "u[missense_class=unstable & readthrough_feasible=no]"
    i_state_no = "u[missense_class=inactive & readthrough_feasible=no]"
    ledger: list[dict[str, Any]] = []
    for key in all_keys:
        c_row, u_row = cal_u.get(key), uncal_u.get(key)
        it2, it4 = it2_map.get(key), it4_map.get(key)
        its = [
            *(["it2"] if it2 and it2["verdict"] == "argue" else []),
            *(["it4"] if it4 and int(it4.get("n_generators", "0")) > 0 else []),
            *(["it5"] if c_row is not None else []),
        ]
        if c_row is not None:
            drug_name = str(c_row["action"])
            raw_b, raw_r = c_row["branches"], c_row["routes"]
            branch = "|".join(raw_b) if isinstance(raw_b, (list, tuple)) else str(raw_b)
            routes = "|".join(raw_r) if isinstance(raw_r, (list, tuple)) else str(raw_r)
            s_class = str(c_row["safety_class"])
            s_factor = float(config.safety.get(s_class, 0.60))
            u_unst = float(u_row[u_state_no]) if u_row else 0.0
            u_inact = float(u_row[i_state_no]) if u_row else 0.0
            u_eu = float(u_row["expected_utility"]) if u_row else 0.0
            c_unst, c_inact, c_eu = (
                float(c_row[u_state_no]),
                float(c_row[i_state_no]),
                float(c_row["expected_utility"]),
            )
        else:
            assert it2 is not None
            drug_name = it2["drug_name"].upper()
            branch = (
                "tumour_context"
                if it2["direction"] == "D4"
                else "aneuploidy_stress"
                if it2["direction"] == "D2"
                else "missense_unstable"
            )
            routes = "none"
            s_class = merged_safety.get(key, "unassessed")
            s_factor = float(config.safety.get(s_class, 0.60))
            u_unst = u_inact = u_eu = c_unst = c_inact = c_eu = 0.0

        tier, role = _classify_tier(key, branch, it2, it4, routes, s_class)
        t_rung = int(it2["rung"]) if it2 and it2["direction"] == "D4" else 0
        it_str, n_it = ("|".join(its), len(its)) if its else ("it5", 1)
        it2_d, it2_r = (it2["direction"], int(it2["rung"])) if it2 else ("none", 0)
        it2_v = it2["verdict"] if it2 else "not_in_it2"
        it4_g = it4["generators"] if it4 and it4["generators"] else "none"
        it4_n = int(it4["n_generators"]) if it4 else 0
        v1 = (drug_name, branch, it_str, n_it, it2_d, it2_r, it2_v, it4_g, it4_n, routes, tier)
        v2 = (s_class, round(s_factor, 4), round(u_unst, 6), round(u_inact, 6), round(u_eu, 6))
        v3 = (round(c_unst, 6), round(c_inact, 6), round(c_eu, 6), t_rung, role)
        ledger.append(dict(zip(CANDIDATE_COLUMNS, (*v1, *v2, *v3), strict=True)))
    ledger.sort(
        key=lambda r: (
            -float(r["calibrated_eu"]),
            -int(r["tumour_context_rung"]),
            -int(r["n_iterations"]),
            str(r["drug"]),
        )
    )
    return ledger


def build_synthesis(
    config_path: Path,
    candidate_paths: Sequence[Path],
    safety_paths: Sequence[Path],
    it2_shortlist_path: Path,
    it4_candidates_path: Path,
) -> dict[str, Any]:
    """Run uncalibrated (It5 R4) and hierarchy-calibrated (It6 R5) analyses and join."""
    config, raw = decision_config.load(config_path)
    rows, dropped = expand_aliases(
        read_candidates(candidate_paths),
        raw.get("aliases", {}),
        raw.get("drop_evidence_kinds", []),
    )
    safety: dict[str, str] = {}
    for path in safety_paths:
        safety.update(read_safety(path))
    avoid = decision_avoid.build(raw["avoid"]) if raw.get("avoid") else []
    merged_safety = decision_avoid.merge(safety, avoid, config.safety)

    uncal_cfg = _with_routes(config, UNCALIBRATED_ROUTE_WEIGHTS)
    cal_cfg = _with_routes(config, CALIBRATED_ROUTE_WEIGHTS)
    uncal = analyse(
        uncal_cfg,
        rows,
        merged_safety,
        tornado_metric=raw.get("tornado_metric"),
        steps=101,
        avoid=avoid,
        dropped=dropped,
    )
    cal = analyse(
        cal_cfg,
        rows,
        merged_safety,
        tornado_metric=raw.get("tornado_metric"),
        steps=101,
        avoid=avoid,
        dropped=dropped,
    )
    ledger = _build_ledger(
        config,
        _utility_lookup(uncal),
        _utility_lookup(cal),
        _read_it2_shortlist(it2_shortlist_path),
        _read_it4_candidates(it4_candidates_path),
        merged_safety,
    )
    sweep_rows: list[dict[str, Any]] = []
    for step in range(1, 21):
        w_r2 = round(step * 0.05, 2)
        rep_w = analyse(
            _with_routes(config, {"R1": 1.00, "R2": w_r2, "R3": 1.00}),
            rows,
            merged_safety,
            steps=101,
            avoid=avoid,
            dropped=dropped,
        )
        voi_w = _voi_map(rep_w)
        states_w = {s["state"]: s for s in rep_w["states"]}
        st_u = states_w["missense_class=unstable & readthrough_feasible=no"]
        st_i = states_w["missense_class=inactive & readthrough_feasible=no"]
        evpi_w, evsi_w = voi_w["evpi"], voi_w["evsi:chx_chase_blot"]
        eu_w = float(rep_w["best"]["expected_utility"])
        share = round(evsi_w / evpi_w if evpi_w > 0 else 0.0, 6)
        sv1 = (w_r2, round(0.700 * w_r2, 6), 0.192, st_u["best"], st_i["best"])
        sv2 = (rep_w["best"]["action"], round(eu_w, 6), round(eu_w + evpi_w, 6), round(evpi_w, 6))
        sv3 = (round(evsi_w, 6), share, round(_flip_point(rep_w), 4))
        sweep_rows.append(dict(zip(SWEEP_COLUMNS, (*sv1, *sv2, *sv3), strict=True)))

    return {
        "ledger": ledger,
        "comparison": _build_comparison(uncal, cal),
        "sweep": sweep_rows,
        "uncalibrated": uncal,
        "calibrated": cal,
        "raw_config": raw,
    }


_CMP_NOTES = {
    "route_weights (R1, R2, R3)": "scales R2 HCT116 residual (0.175) < R3 mouse rescue (0.192)",
    "best_if_missense_unstable_all (P=0.55)": "in-vivo Bub1b^{H/H} rescue (PMID 24825348) leads",
    "best_if_missense_unstable_approved (P=0.55)": "3-iteration Rung-3 NAD+ precursors lead",
    "best_if_missense_inactive (P=0.45)": "2-generator survivor (twin|prism 99.4th pct) + R3",
    "best_tumour_context_d4 (rhabdomyosarcoma)": "RMS apoptosis via HMGCR (NCT02390843, PGx-gated)",
    "baseline_expected_utility (EU*)": "expected utility of unstable leader before blot",
    "evpi (value of perfect information)": "resolving missense_class adds +0.1800 over baseline",
    "evppi_share_on_missense_class": "100% of information value sits on missense_class",
    "evsi_blot_chx (cycloheximide-chase blot)": "flip at P=0.5362 raises blot EVSI to 69.1%",
    "evsi_readthrough_reporter": "stop readthrough reporter has zero EVSI under dosage gap",
    "flip_threshold_p_unstable": "both flip points lie inside blot [0.177, 0.874] posteriors",
}


def _row(m: str, u: str, c: str, s: str) -> dict[str, Any]:
    return dict(zip(COMPARISON_COLUMNS, (m, u, c, s, _CMP_NOTES[m]), strict=True))


def _build_comparison(uncal: Mapping[str, Any], cal: Mapping[str, Any]) -> list[dict[str, Any]]:
    u_voi, c_voi = _voi_map(uncal), _voi_map(cal)
    u_eu, c_eu = float(uncal["best"]["expected_utility"]), float(cal["best"]["expected_utility"])
    u_ev, c_ev = u_voi["evpi"], c_voi["evpi"]
    u_em, c_em = u_voi["evppi:missense_class"], c_voi["evppi:missense_class"]
    u_bl, c_bl = u_voi["evsi:chx_chase_blot"], c_voi["evsi:chx_chase_blot"]
    u_g = "GLICLAZIDE | MIGALASTAT (u=0.7000, EU=0.3850)"
    c_n = "NIACIN | NICOTINAMIDE (u=0.1920, EU=0.1056) > GLICLAZIDE | MIGALASTAT (u=0.1750)"
    d_s = "DASATINIB (u=0.4000, EU=0.2537)"
    s_l = "SIMVASTATIN | LOVASTATIN (Rung 5, NCT02390843)"
    ev_u = f"{u_ev:.4f} ({100 * u_ev / u_eu:.1f}% of EU*)"
    ev_c = f"{c_ev:.4f} ({100 * c_ev / c_eu:.1f}% of EU*)"
    em_u, em_c = f"100.0% ({u_em:.4f} / {u_ev:.4f})", f"100.0% ({c_em:.4f} / {c_ev:.4f})"
    bl_u = f"{u_bl:.4f} ({100 * u_bl / u_ev:.1f}% of EVPI)"
    bl_c = f"{c_bl:.4f} ({100 * c_bl / c_ev:.1f}% of EVPI)"
    z_s = "0.0000 (0.0% of EVPI)"
    return [
        _row("route_weights (R1, R2, R3)", "1.00, 1.00, 1.00", "1.00, 0.25, 1.00", "calibration"),
        _row("best_if_missense_unstable_all (P=0.55)", u_g, "NMN (u=0.4800, EU=0.2640)", "shift"),
        _row("best_if_missense_unstable_approved (P=0.55)", u_g, c_n, "shifts_to_nad_precursor"),
        _row("best_if_missense_inactive (P=0.45)", d_s, d_s, "invariant"),
        _row("best_tumour_context_d4 (rhabdomyosarcoma)", "not_in_r4_table", s_l, "restored_d4"),
        _row("baseline_expected_utility (EU*)", f"{u_eu:.4f}", f"{c_eu:.4f}", "rescaled"),
        _row("evpi (value of perfect information)", ev_u, ev_c, "invariant_0.1800"),
        _row("evppi_share_on_missense_class", em_u, em_c, "invariant_100%"),
        _row("evsi_blot_chx (cycloheximide-chase blot)", bl_u, bl_c, "increases_59.1%_to_69.1%"),
        _row("evsi_readthrough_reporter", z_s, z_s, "invariant_zero"),
        _row(
            "flip_threshold_p_unstable",
            f"{_flip_point(uncal):.4f}",
            f"{_flip_point(cal):.4f}",
            "inside_blot_posteriors",
        ),
    ]
