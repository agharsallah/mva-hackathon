"""Render the two-panel SVG figure for the external cellular-abundance calibration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

__all__ = ["render_svg"]


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_panel_a(lines: list[str], report: Mapping[str, Any]) -> None:
    proteins = sorted(report["per_protein"], key=lambda p: float(p["auroc_buried"]), reverse=True)
    summary = report["summary_all_11_proteins"]
    px0, py0, pw, ph = 32, 74, 530, 384
    lines.append(
        f'<rect x="{px0}" y="{py0}" width="{pw}" height="{ph}" rx="8" '
        'fill="#f8fafc" stroke="#e2e8f0"/>'
    )
    lines.append(
        f'<text x="{px0 + 16}" y="{py0 + 26}" font-size="13" font-weight="700" fill="#0f172a">'
        "A. Discrimination of Low Cellular Abundance in Buried Core (AUROC ± 95% CI)</text>"
    )

    x_min, x_max = 0.45, 0.95
    plot_l, plot_r = px0 + 195, px0 + pw - 68

    def x_pos(val: float) -> float:
        return plot_l + (val - x_min) / (x_max - x_min) * (plot_r - plot_l)

    for tick in (0.50, 0.60, 0.70, 0.80, 0.90):
        tx = x_pos(tick)
        stroke = "#94a3b8" if abs(tick - 0.50) < 1e-6 else "#e2e8f0"
        dash = ' stroke-dasharray="4,3"' if abs(tick - 0.50) < 1e-6 else ""
        lines.append(
            f'<line x1="{tx:.1f}" y1="{py0 + 42}" x2="{tx:.1f}" y2="{py0 + ph - 42}" '
            f'stroke="{stroke}" stroke-width="1"{dash}/>'
        )
        lines.append(
            f'<text x="{tx:.1f}" y="{py0 + ph - 24}" font-size="10" fill="#64748b" '
            f'text-anchor="middle">{tick:.2f}</text>'
        )

    med_auc = float(summary["median_auroc_buried"])
    med_ci_lo, med_ci_hi = (float(x) for x in summary["median_auroc_buried_ci95"])
    band_w = max(1.0, x_pos(med_ci_hi) - x_pos(med_ci_lo))
    lines.append(
        f'<rect x="{x_pos(med_ci_lo):.1f}" y="{py0 + 42}" width="{band_w:.1f}" '
        f'height="{ph - 84}" fill="#0284c7" fill-opacity="0.10"/>'
    )
    lines.append(
        f'<line x1="{x_pos(med_auc):.1f}" y1="{py0 + 42}" x2="{x_pos(med_auc):.1f}" '
        f'y2="{py0 + ph - 42}" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )

    row_top = py0 + 60
    row_step = 24.5
    for idx, p in enumerate(proteins):
        ry = row_top + idx * row_step
        auc = float(p["auroc_buried"])
        lo, hi = (float(x) for x in p["auroc_buried_ci95"])
        color = "#0284c7" if p["intracellular_abundance"] else "#6366f1"
        label = f"{p['gene']} ({p['uniprot']}, n={p['n_buried']:,})"
        lines.append(
            f'<text x="{plot_l - 10}" y="{ry + 4:.1f}" font-size="11" font-weight="500" '
            f'fill="#1e293b" text-anchor="end">{_esc(label)}</text>'
        )
        lines.append(
            f'<line x1="{x_pos(lo):.1f}" y1="{ry:.1f}" x2="{x_pos(hi):.1f}" y2="{ry:.1f}" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        lines.append(f'<circle cx="{x_pos(auc):.1f}" cy="{ry:.1f}" r="4.2" fill="{color}"/>')
        lines.append(
            f'<text x="{plot_r + 8}" y="{ry + 4:.1f}" font-size="10.5" font-weight="600" '
            f'fill="#0f172a">{auc:.3f}</text>'
        )

    ry_bub = row_top + len(proteins) * row_step + 6
    bub_auc = 0.600
    lines.append(
        f'<text x="{plot_l - 10}" y="{ry_bub + 4:.1f}" font-size="11" font-weight="600" '
        'fill="#b45309" text-anchor="end">BUB1B in-gene (n=8)</text>'
    )
    lines.append(
        f'<line x1="{x_pos(0.45):.1f}" y1="{ry_bub:.1f}" x2="{x_pos(0.95):.1f}" '
        f'y2="{ry_bub:.1f}" stroke="#d97706" stroke-width="1.5" stroke-dasharray="3,2"/>'
    )
    lines.append(f'<circle cx="{x_pos(bub_auc):.1f}" cy="{ry_bub:.1f}" r="4.2" fill="#d97706"/>')
    lines.append(
        f'<text x="{plot_r + 8}" y="{ry_bub + 4:.1f}" font-size="10.5" font-weight="600" '
        'fill="#b45309">0.600</text>'
    )
    lines.append(
        f'<text x="{px0 + 16}" y="{py0 + ph - 8}" font-size="10.5" fill="#0369a1" '
        f'font-weight="600">Across-protein median AUROC = {med_auc:.3f} '
        f"(95% CI {med_ci_lo:.3f}–{med_ci_hi:.3f}); "
        "blue = VAMP-seq/abundance, indigo = surface</text>"
    )


def _render_panel_b(lines: list[str], report: Mapping[str, Any]) -> None:
    cal = report["calibration_at_1_55"]
    ri = cal["random_intercept"]
    bx0, by0, bw, bh = 582, 74, 506, 384
    lines.append(
        f'<rect x="{bx0}" y="{by0}" width="{bw}" height="{bh}" rx="8" '
        'fill="#f8fafc" stroke="#e2e8f0"/>'
    )
    lines.append(
        f'<text x="{bx0 + 16}" y="{by0 + 26}" font-size="13" font-weight="700" fill="#0f172a">'
        "B. Calibrated P(Low Abundance | ΔΔG) at Child’s +1.55 kcal/mol</text>"
    )

    cx_l, cx_r = bx0 + 56, bx0 + bw - 26
    cy_t, cy_b = by0 + 48, by0 + bh - 56
    ddg_min, ddg_max = -1.0, 4.0

    def gx(ddg: float) -> float:
        return cx_l + (ddg - ddg_min) / (ddg_max - ddg_min) * (cx_r - cx_l)

    def gy(prob: float) -> float:
        return cy_b - prob * (cy_b - cy_t)

    for p_tick in (0.0, 0.25, 0.50, 0.75, 1.0):
        ty = gy(p_tick)
        dash = ' stroke-dasharray="4,3"' if abs(p_tick - 0.50) < 1e-6 else ""
        stroke = "#94a3b8" if abs(p_tick - 0.50) < 1e-6 else "#e2e8f0"
        lines.append(
            f'<line x1="{cx_l}" y1="{ty:.1f}" x2="{cx_r}" y2="{ty:.1f}" '
            f'stroke="{stroke}" stroke-width="1"{dash}/>'
        )
        lines.append(
            f'<text x="{cx_l - 8}" y="{ty + 3.5:.1f}" font-size="10" fill="#64748b" '
            f'text-anchor="end">{p_tick:.2f}</text>'
        )

    for d_tick in (-1.0, 0.0, 1.0, 1.55, 2.0, 3.0, 4.0):
        tx = gx(d_tick)
        is_child = abs(d_tick - 1.55) < 1e-6
        stroke = "#dc2626" if is_child else "#e2e8f0"
        dash = ' stroke-dasharray="5,3"' if is_child else ""
        sw = "1.5" if is_child else "1"
        lines.append(
            f'<line x1="{tx:.1f}" y1="{cy_t}" x2="{tx:.1f}" y2="{cy_b}" '
            f'stroke="{stroke}" stroke-width="{sw}"{dash}/>'
        )
        lbl = "+1.55" if is_child else f"{d_tick:+.0f}" if d_tick != 0 else "0"
        fill = "#dc2626" if is_child else "#64748b"
        weight = ' font-weight="700"' if is_child else ""
        lines.append(
            f'<text x="{tx:.1f}" y="{cy_b + 16}" font-size="10" fill="{fill}"{weight} '
            f'text-anchor="middle">{lbl}</text>'
        )

    grid = np.linspace(ddg_min, ddg_max, 80)
    b0_main = float(cal["beta0"])
    b1_main = float(cal["beta1"])
    beta1_ri = float(ri["beta1"])
    for p_at_155 in ri["per_protein_p"]:
        alpha_k = float(np.log(p_at_155 / (1.0 - p_at_155)) - beta1_ri * 1.55)
        pts = " ".join(
            f"{gx(float(d)):.1f},{gy(float(1.0 / (1.0 + np.exp(-(alpha_k + beta1_ri * d))))):.1f}"
            for d in grid
        )
        lines.append(
            '<polyline fill="none" stroke="#94a3b8" stroke-width="1.1" '
            f'stroke-opacity="0.45" points="{pts}"/>'
        )

    main_pts = " ".join(
        f"{gx(float(d)):.1f},{gy(float(1.0 / (1.0 + np.exp(-(b0_main + b1_main * d))))):.1f}"
        for d in grid
    )
    lines.append(f'<polyline fill="none" stroke="#0284c7" stroke-width="3" points="{main_pts}"/>')

    p_child = float(cal["p_low_abundance"])
    ci_lo, ci_hi = (float(x) for x in cal["cluster_bootstrap_ci95"])
    pr_lo, pr_hi = (float(x) for x in cal["random_intercept"]["new_protein_predictive_ci95"])
    cx_child = gx(1.55)
    cy_child = gy(p_child)
    lines.append(
        f'<line x1="{cx_child:.1f}" y1="{gy(pr_lo):.1f}" x2="{cx_child:.1f}" '
        f'y2="{gy(pr_hi):.1f}" stroke="#dc2626" stroke-width="1.5" stroke-dasharray="4 3"/>'
    )
    lines.append(
        f'<line x1="{cx_child:.1f}" y1="{gy(ci_lo):.1f}" x2="{cx_child:.1f}" '
        f'y2="{gy(ci_hi):.1f}" stroke="#dc2626" stroke-width="3.5"/>'
    )
    lines.append(
        f'<circle cx="{cx_child:.1f}" cy="{cy_child:.1f}" r="5.5" fill="#dc2626" '
        'stroke="#ffffff" stroke-width="1.5"/>'
    )
    lines.append(
        f'<circle cx="{cx_child:.1f}" cy="{gy(0.55):.1f}" r="4.2" fill="#f59e0b" '
        'stroke="#ffffff" stroke-width="1"/>'
    )
    lines.append(
        f'<text x="{cx_child + 10:.1f}" y="{cy_child - 6:.1f}" font-size="11" '
        f'font-weight="700" fill="#dc2626">Calibrated P = {p_child:.2f} '
        f"(95% CI {ci_lo:.2f}–{ci_hi:.2f})</text>"
    )
    lines.append(
        f'<text x="{cx_child + 10:.1f}" y="{cy_child + 10:.1f}" font-size="10.5" '
        f'fill="#dc2626">New protein (dashed): {pr_lo:.2f}–{pr_hi:.2f}'
        f"{', includes 0.50' if pr_lo < 0.5 < pr_hi else ''}</text>"
    )
    lines.append(
        f'<text x="{cx_child + 10:.1f}" y="{gy(0.55) + 12:.1f}" font-size="10.5" '
        'font-weight="600" fill="#b45309">Pre-calibration weight = 0.55</text>'
    )
    lines.append(
        f'<text x="{(cx_l + cx_r) / 2:.1f}" y="{by0 + bh - 22}" font-size="10.5" '
        'fill="#334155" text-anchor="middle">'
        "ThermoMPNN predicted ΔΔG (kcal/mol, positive = destabilising)</text>"
    )
    lopo_med = cal["lopo_median_p"]
    lopo_lo, lopo_hi = cal["lopo_range_p"]
    lines.append(
        f'<text x="{bx0 + 16}" y="{by0 + bh - 6}" font-size="10.5" fill="#0369a1" '
        f'font-weight="600">LOPO median = {lopo_med:.3f} (range {lopo_lo:.3f}–{lopo_hi:.3f}); '
        "grey curves = per-protein random intercepts</text>"
    )


def render_svg(report: Mapping[str, Any], out_path: Path) -> None:
    """Write ``figures/it6/abundance-calibration.svg`` from ``evaluation.json``."""
    width, height = 1120, 490
    lines = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" '
            'font-family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            '<text x="32" y="34" font-size="16" font-weight="700" fill="#0f172a">'
            "External Cellular-Abundance Calibration of ThermoMPNN ΔΔG "
            "Across 11 ProteinGym Expression DMS Proteins</text>"
        ),
        (
            '<text x="32" y="54" font-size="12" fill="#475569">'
            "Primary stratum: buried high-confidence core residues "
            "(RSA &lt; 0.20, AlphaFold pLDDT ≥ 90; n = 18,825 single-residue variants; "
            "zero ThermoMPNN split overlap)</text>"
        ),
    ]
    _render_panel_a(lines, report)
    _render_panel_b(lines, report)
    lines.append("</svg>\n")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
