#!/usr/bin/env python3
"""Render step 8's Boltz-2 figures from the lane's own output under ``build/``.

Three figures, all from ``<case-dir>/reply.json`` and the CIF files beside it (written by
``src/mva/zoo/modal_apps/boltz2.py::fold_case``):

1. ``boltz2-plddt-profile`` — per-residue pLDDT (the model's 0–100 confidence), wild type
   against mutant: the whole protein on a fraction-of-length axis, and a zoom on the site
   with the axis in **residues from the site**. The site is shaded, never numbered: no
   residue number of the patient's substitution goes into a tracked file.
2. ``boltz2-local-delta`` — mean pLDDT change within ±radius residues of each variant's own
   site, mutant beside the two controls, against the wild-type sample-to-sample noise, the
   filed prediction (−5) and the refutation band (±1).
3. ``boltz2-ca-trace`` — the Cα trace (one point per residue) of wild type and mutant,
   projected on the wild type's two principal axes, coloured by pLDDT, the site ringed.

Every figure writes ``figures/it4/<slug>.svg`` + ``.html`` and one
``boltz2.provenance.json`` names the inputs (sha256), parameters and printed values.

    uv run python tools/render_step8_boltz2.py
    uv run python tools/render_step8_boltz2.py --case-dir build/it4/boltz2/smoke  # plumbing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, install_template

SCRIPT = "tools/render_step8_boltz2.py"
ZOOM = 60
ENTRY = "147"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--case-dir", type=Path, default=Path("build/it4/boltz2/case"))
    parser.add_argument("--out-dir", type=Path, default=Path("figures/it4"))
    parser.add_argument(
        "--replicate",
        type=Path,
        action="append",
        default=[],
        help="another run of the same case (e.g. a second seed) for the delta figure",
    )
    parser.add_argument("--mutant", default="mut", help="the fold holding the patient's change")
    return parser.parse_args(argv)


def mean_profile(samples: list[dict[str, Any]]) -> np.ndarray:
    return np.mean([s["plddt"] for s in samples], axis=0)


def ca_trace(cif: Path) -> np.ndarray:
    """Cα coordinates in residue order, read from an mmCIF ``atom_site`` loop."""
    columns: list[str] = []
    rows: list[list[str]] = []
    for line in cif.read_text().splitlines():
        if line.startswith("_atom_site."):
            columns.append(line.split(".", 1)[1].strip())
        elif columns and line.startswith(("ATOM", "HETATM")):
            rows.append(line.split())
    atom, x, y, z = (columns.index(c) for c in ("label_atom_id", "Cartn_x", "Cartn_y", "Cartn_z"))
    return np.array([[float(r[x]), float(r[y]), float(r[z])] for r in rows if r[atom] == "CA"])


def kabsch(mobile: np.ndarray, target: np.ndarray) -> np.ndarray:
    """``mobile`` rigidly superposed on ``target`` (both centred on ``target``'s centroid)."""
    mc, tc = mobile.mean(0), target.mean(0)
    u, _, vt = np.linalg.svd((mobile - mc).T @ (target - tc))
    d = np.sign(np.linalg.det(u @ vt))
    rot = u @ np.diag([1.0, 1.0, d]) @ vt
    return np.asarray((mobile - mc) @ rot + tc)


def site_window(n: int, site: int, radius: int) -> slice:
    return slice(max(site - 1 - radius, 0), min(site + radius, n))


def profile_figure(wt: np.ndarray, mut: np.ndarray, site: int, radius: int) -> go.Figure:
    n = len(wt)
    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.55, 0.45],
        subplot_titles=(
            "Whole protein (N → C terminus)",
            f"Zoom: ±{ZOOM} residues around the substituted residue",
        ),
    )
    frac = np.arange(n) / (n - 1)
    lo, hi = (site - 1 - radius) / (n - 1), (site - 1 + radius) / (n - 1)
    zoom = site_window(n, site, ZOOM)
    offsets = np.arange(zoom.start, zoom.stop) - (site - 1)
    for col, x, sl in ((1, frac, slice(0, n)), (2, offsets, zoom)):
        for arr, hue, name in ((wt, MACHINE, "wild type"), (mut, BAD, "mutant")):
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=np.round(arr[sl], 2),
                    mode="lines",
                    line=dict(color=hue.line, width=1.4 if col == 1 else 2),
                    name=name,
                    legendgroup=name,
                    showlegend=col == 1,
                    hoverinfo="skip" if col == 1 else "y",
                ),
                row=1,
                col=col,
            )
        x0, x1 = (lo, hi) if col == 1 else (-radius, radius)
        fig.add_vrect(
            x0=x0,
            x1=x1,
            fillcolor=RAW.fill,
            opacity=0.6,
            line_width=0,
            layer="below",
            row=1,
            col=col,
        )
    fig.update_xaxes(showticklabels=False, title_text="position along the protein", row=1, col=1)
    fig.update_xaxes(title_text="residues from the substituted residue", row=1, col=2)
    fig.update_yaxes(title_text="pLDDT (0–100, mean of samples)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(range=[0, 100], row=1, col=2)
    fig.update_layout(
        height=460,
        title="Boltz-2 per-residue confidence, wild type vs mutant BubR1 (shaded: site ± 5)",
        legend=dict(y=-0.22, orientation="h"),
        margin=dict(t=90),
    )
    return fig


def delta_figure(
    runs: list[tuple[str, dict[str, Any]]], noise: float, labels: dict[str, str]
) -> go.Figure:
    """One bar group per variant, one bar per replicate run (seed)."""
    fig = go.Figure()
    deltas: list[float] = []
    for i, (run, summary) in enumerate(runs):
        names = [n for n in labels if n in summary["folds"]]
        ys = [summary["folds"][n]["local_delta"] for n in names]
        deltas += ys
        colours = [
            BAD.line if n == "mut" else MACHINE.line if n == "wt_identity" else MUTED.line
            for n in names
        ]
        fig.add_trace(
            go.Bar(
                x=[labels[n] for n in names], y=ys, name=run, text=[f"{d:+.2f}" for d in ys],
                textposition="outside", marker=dict(color=colours, opacity=1.0 - 0.35 * i),
            )
        )  # fmt: skip
    fig.add_hrect(y0=-1, y1=1, fillcolor=MUTED.fill, opacity=0.7, line_width=0, layer="below")
    for y in (-noise, noise):
        fig.add_hline(y=y, line=dict(color=GOOD.line, dash="dot", width=1.5))
    fig.add_annotation(
        x=0, xref="paper", xanchor="left", y=noise, yshift=10, showarrow=False,
        text=f"dotted: wild-type sample-to-sample range (±{noise:.2f})",
        font=dict(color=GOOD.line),
    )  # fmt: skip
    fig.add_hline(y=-5, line=dict(color=DECISION.line, dash="dash", width=2))
    fig.add_annotation(
        x=1, xref="paper", xanchor="right", y=-5, yshift=-10, showarrow=False,
        text="filed prediction: ≤ −5", font=dict(color=DECISION.line),
    )  # fmt: skip
    fig.add_annotation(
        x=1, xref="paper", xanchor="right", y=1, yshift=10, showarrow=False,
        text="refuted if |Δ| < 1 (grey band)", font=dict(color=MUTED.line),
    )  # fmt: skip
    low = min([*deltas, -6.0])
    fig.update_layout(barmode="group", legend=dict(y=-0.3, orientation="h"))
    fig.update_xaxes(tickangle=0)
    fig.update_yaxes(title_text="mutant − wild type, mean pLDDT at the site", range=[low - 1, 3])
    fig.update_layout(
        height=480, title="Local confidence change at each variant's own site (±5 residues)"
    )
    return fig


def trace_figure(
    wt_xyz: np.ndarray, mut_xyz: np.ndarray, wt: np.ndarray, mut: np.ndarray, site: int
) -> go.Figure:
    centred = wt_xyz - wt_xyz.mean(0)
    axes = np.linalg.svd(centred, full_matrices=False)[2][:2].T
    fig = make_subplots(rows=1, cols=2, subplot_titles=("wild type", "mutant"))
    sl = site_window(len(wt), site, 5)
    scale = [[0, BAD.line], [0.5, DECISION.line], [1, GOOD.line]]
    for col, xyz, conf in ((1, wt_xyz, wt), (2, kabsch(mut_xyz, wt_xyz), mut)):
        p = (xyz - wt_xyz.mean(0)) @ axes
        fig.add_trace(
            go.Scatter(
                x=p[:, 0], y=p[:, 1], mode="lines", line=dict(color=MUTED.fill, width=1),
                hoverinfo="skip", showlegend=False,
            ),
            row=1, col=col,
        )  # fmt: skip
        fig.add_trace(
            go.Scatter(
                x=p[:, 0], y=p[:, 1], mode="markers", hoverinfo="skip", showlegend=False,
                marker=dict(
                    size=4, color=conf, cmin=0, cmax=100, colorscale=scale,
                    colorbar=dict(title="pLDDT") if col == 2 else None, showscale=col == 2,
                ),
            ),
            row=1, col=col,
        )  # fmt: skip
        fig.add_trace(
            go.Scatter(
                x=p[sl, 0], y=p[sl, 1], mode="markers", hoverinfo="skip",
                name="substituted residue ± 5", showlegend=col == 1,
                marker=dict(size=11, color="rgba(0,0,0,0)", line=dict(color=RAW.line, width=2)),
            ),
            row=1, col=col,
        )  # fmt: skip
    fig.update_xaxes(showticklabels=False, title_text="principal axis 1 (Å)")
    fig.update_yaxes(showticklabels=False, title_text="principal axis 2 (Å)", scaleanchor="x")
    fig.update_layout(
        height=460,
        title="Cα trace, projected on the wild type's principal axes",
        legend=dict(y=-0.15, orientation="h"),
    )
    return fig


def write(fig: go.Figure, out_dir: Path, slug: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg, html = out_dir / f"{slug}.svg", out_dir / f"{slug}.html"
    fig.write_image(svg, format="svg", width=1000, height=fig.layout.height or 420)
    fig.write_html(html, include_plotlyjs="cdn", full_html=True)
    return [svg, html]


def rmsd(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(((a - b) ** 2).sum(1).mean()))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    case = args.case_dir
    reply = json.loads((case / "reply.json").read_text())
    summary = json.loads((case / "summary.json").read_text())
    folds, radius = reply["folds"], int(summary["radius"])
    site = int(summary["folds"][args.mutant]["site"])  # stays in memory, never printed
    wt, mut = mean_profile(folds["wt"]), mean_profile(folds[args.mutant])
    wt_cif = next(case.glob("boltz_results_ref/wt/wt_model_0.cif"))
    mut_cif = next(case.glob(f"boltz_results_var/{args.mutant}/{args.mutant}_model_0.cif"))
    wt_xyz, mut_xyz = ca_trace(wt_cif), ca_trace(mut_cif)
    wt1_xyz = ca_trace(next(case.glob("boltz_results_ref/wt/wt_model_1.cif")))
    sup = kabsch(mut_xyz, wt_xyz)
    sl = site_window(len(wt), site, 10)
    install_template()
    labels = {
        args.mutant: "patient's substitution",
        "ctrl_conservative": "control:<br>conservative swap,<br>same residue",
        "ctrl_distal": "control:<br>same swap,<br>residue ≥ 100 away",
        "wt_identity": "control:<br>wild type again,<br>variants' path",
        "i44a": "ubiquitin I44A (smoke)",
    }
    runs = [(f"seed {summary['params']['seed']} (solid)", summary)] + [
        (f"seed {r['params']['seed']} (lighter)", r)
        for r in (json.loads((d / "summary.json").read_text()) for d in args.replicate)
    ]
    noise = max(float(r["noise_floor_wt_sample_range"]) for _, r in runs)
    written = [
        *write(profile_figure(wt, mut, site, radius), args.out_dir, "boltz2-plddt-profile"),
        *write(delta_figure(runs, noise, labels), args.out_dir, "boltz2-local-delta"),
        *write(trace_figure(wt_xyz, mut_xyz, wt, mut, site), args.out_dir, "boltz2-ca-trace"),
    ]
    values = {
        "local_delta": {
            run: {n: r.get("local_delta") for n, r in rs["folds"].items() if "site" in r}
            for run, rs in runs
        },
        "mean_plddt": {n: round(mean(r["mean_plddt"]), 2) for n, r in summary["folds"].items()},
        "ptm": {n: round(mean(r["ptm"]), 4) for n, r in summary["folds"].items()},
        "noise_floor_wt_sample_range": {run: rs["noise_floor_wt_sample_range"] for run, rs in runs},
        "ca_rmsd_global_A": round(rmsd(sup, wt_xyz), 2),
        "ca_rmsd_site_pm10_local_fit_A": round(
            rmsd(kabsch(mut_xyz[sl], wt_xyz[sl]), wt_xyz[sl]), 2
        ),
        "ca_rmsd_site_pm10_wt_sample1_vs_0_A": round(
            rmsd(kabsch(wt1_xyz[sl], wt_xyz[sl]), wt_xyz[sl]), 2
        ),
    }
    record = provenance.envelope("boltz2", SCRIPT)
    record["inputs"] = [
        {"path": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]}
        for p in (
            case / "reply.json", case / "summary.json", wt_cif, mut_cif,
            *(d / "summary.json" for d in args.replicate),
        )
    ]  # fmt: skip
    record["parameters"] = {
        "radius": radius,
        "zoom": ZOOM,
        "rmsd": (
            "Cα, mutant sample 0 on wild-type sample 0: global fit, and a local fit on the "
            "site ±10 window; baseline = wild-type sample 1 on sample 0, same window"
        ),
        "model": reply["version"],
        "weights": reply["weights"],
        "digest": reply["digest"],
        "msa": reply["msa"],
        "sampling": reply["params"],
    }
    record["values"] = values
    record["methodology_entry"] = ENTRY
    record["outputs"] = [
        {"path": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]} for p in written
    ]
    provenance.write(record, args.out_dir / "boltz2.provenance.json")
    print(json.dumps(values, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
