#!/usr/bin/env python3
"""Render the graph walk's overlap figure: the walk vs its decoy vs the literature list.

Two panels, built only from files the walk already wrote (``tools/track2_walk.py``):

A. **Top-N composition.** For the real walk and the decoy walk, the distinct drug base names
   in the top N, split into: also in the literature/API candidate list, shared with the other
   walk, neither. The dashed line is the pre-registered "agreement" threshold. When the decoy
   clears it as easily as the real walk, the agreement test had no power.
B. **Where the score enters.** Each disease gene's share of the real walk's top-N path weight
   (the second node of every path in ``<name>.paths.tsv``). The card's own gene is green.

Case-agnostic: every path is a parameter; labels come from each walk's provenance manifest.
Counts are cross-checked against the walk's ``comparison.json`` when one is given, and the
render stops on a mismatch rather than drawing a number the entry does not state.

Writes ``<out-dir>/<slug>.png``, ``<slug>.svg`` and ``<slug>.provenance.json`` (inputs with
sha256, parameters, every plotted value). No genomic position: drug and gene names only.

Usage::

    uv run python tools/render_track2_walk_figures.py
    uv run python tools/render_track2_walk_figures.py --walk-dir other/case \\
        --decoy-dir other/case/decoys/GENE --out-dir figures/other --slug walk-overlap
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mva.drugs import provenance
from mva.drugs.names import base_name
from mva.drugs.walk_table import candidate_names
from mva.render import theme

SCRIPT = "tools/render_track2_walk_figures.py"
NAME = "ranking-walk"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--walk-dir", type=Path, default=Path("ressources/track2"))
    parser.add_argument("--decoy-dir", type=Path, default=Path("ressources/track2/decoys/XDH"))
    parser.add_argument(
        "--candidates", type=Path, default=Path("ressources/track2/drug_candidates.tsv")
    )
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--threshold", type=int, default=2, help="pre-registered agreement bar")
    parser.add_argument("--claim", default="H075 / P4-12", help="the claim the bar belongs to")
    parser.add_argument("--entry", default="142", help="methodology entry the numbers belong to")
    parser.add_argument("--out-dir", type=Path, default=Path("figures/it4"))
    parser.add_argument("--slug", default="track2-walk-overlap")
    return parser.parse_args(argv)


# ── reading ─────────────────────────────────────────────────────────────────────────────


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))


def top_names(path: Path, top: int) -> list[str]:
    """Distinct base names of the first ``top`` rows, in rank order."""
    seen: list[str] = []
    for row in read_tsv(path)[:top]:
        name = base_name(row["drug_name"])
        if name not in seen:
            seen.append(name)
    return seen


def walk_label(manifest: dict[str, Any]) -> str:
    """``BUB1B walk · mosaic variegated aneuploidy syndrome`` from a walk manifest."""
    card = manifest.get("card", {})
    nodes = manifest.get("source", {}).get("resolved_nodes", [])
    disease = nodes[0]["name"] if nodes else card.get("disease", "?")
    role = "decoy" if card.get("decoy") else "walk"
    return f"{card.get('gene', '?')} {role}<br>{disease}"


def gene_shares(paths_tsv: Path) -> dict[str, float]:
    """Share of the summed path weight entering through each disease gene (path node 2)."""
    weight: dict[str, float] = defaultdict(float)
    for row in read_tsv(paths_tsv):
        weight[row["path"].split(" > ")[1]] += float(row["weight"])
    total = sum(weight.values()) or 1.0
    return dict(sorted(((g, w / total) for g, w in weight.items()), key=lambda kv: kv[1]))


def composition(names: list[str], other: set[str], candidates: set[str]) -> dict[str, list[str]]:
    """Split one top-N list; a name in both the candidate list and the other walk counts once."""
    parts: dict[str, list[str]] = {"candidates": [], "shared": [], "neither": []}
    for name in names:
        key = "candidates" if name in candidates else "shared" if name in other else "neither"
        parts[key].append(name)
    return parts


def cross_check(comparison: Path, real: dict[str, list[str]], decoy_shared: list[str]) -> None:
    """Stop when the figure's counts differ from the walk's own comparison record."""
    if not comparison.is_file():
        return
    record = json.loads(comparison.read_text(encoding="utf-8"))
    if sorted(real["candidates"]) != sorted(record["candidate_matched"]):
        raise SystemExit(f"candidate matches differ from {comparison}")
    if sorted(decoy_shared) != sorted(record["decoy_shared"]):
        raise SystemExit(f"decoy overlap differs from {comparison}")


# ── drawing ─────────────────────────────────────────────────────────────────────────────

SEGMENTS = (
    ("candidates", "also in the candidate list", theme.MACHINE),
    ("shared", "shared with the other walk", theme.DECISION),
    ("neither", "neither", theme.MUTED),
)


def build(data: dict[str, Any], args: argparse.Namespace) -> go.Figure:
    rows = data["walks"]
    shares = data["gene_shares"]
    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.62, 0.38],
        horizontal_spacing=0.2,
        subplot_titles=(
            f"A · top {args.top}: the decoy meets the list as often as the walk",
            f"B · who carries the walk's top-{args.top} score",
        ),
    )
    labels = [f"{r['label']}<br>{len(r['names'])} distinct names" for r in rows]
    for key, legend, hue in SEGMENTS:
        values = [len(r["parts"][key]) for r in rows]
        fig.add_bar(
            row=1,
            col=1,
            orientation="h",
            name=legend,
            y=labels,
            x=values,
            marker={"color": hue.fill, "line": {"color": theme.PAPER, "width": 2}},
            text=[str(v) if v else "" for v in values],
            textposition="inside",
            insidetextfont={"color": theme.INK},
            customdata=[", ".join(r["parts"][key]) or "—" for r in rows],
            hovertemplate="%{x}: %{customdata}<extra>" + legend + "</extra>",
        )
    fig.add_vline(
        x=args.threshold,
        row=1,
        col=1,
        line={"color": theme.DECISION.line, "dash": "dash", "width": 2},
    )
    fig.add_annotation(
        x=args.threshold,
        y=0.5,
        xref="x",
        yref="paper",
        yanchor="middle",
        xanchor="left",
        showarrow=False,
        text=f" {args.claim}: ≥ {args.threshold} = 'agrees'",
        font={"size": 11, "color": theme.DECISION.line},
    )
    gene = data["card_gene"]
    fig.add_bar(
        row=1,
        col=2,
        orientation="h",
        showlegend=False,
        y=list(shares),
        x=[round(v * 100, 1) for v in shares.values()],
        marker={
            "color": [theme.GOOD.fill if g == gene else theme.MUTED.fill for g in shares],
            "line": {"color": theme.PAPER, "width": 2},
        },
        text=[f"{v * 100:.1f} %" for v in shares.values()],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f} % of top-N path weight<extra></extra>",
    )
    fig.update_layout(
        template=theme.TEMPLATE_NAME,
        barmode="stack",
        height=480,
        bargap=0.45,
        margin={"l": 290, "r": 40, "t": 110, "b": 120},
        legend={"y": 1.18, "traceorder": "normal"},
        meta=data["meta"],
    )
    fig.update_xaxes(row=1, col=1, title="distinct approved drug base names", dtick=2)
    fig.update_yaxes(row=1, col=1, autorange="reversed")
    fig.update_xaxes(
        row=1,
        col=2,
        title="share of summed path weight (%)",
        range=[0, max(30, 100 * max(shares.values()) + 6)],
    )
    fig.add_annotation(
        x=-0.28,
        y=-0.36,
        xref="paper",
        yref="paper",
        xanchor="left",
        showarrow=False,
        align="left",
        text=(
            f"Source: {', '.join(data['meta']['inputs'][:2])},<br>"
            f"{', '.join(data['meta']['inputs'][2:])} · script {SCRIPT} · "
            f"entry {args.entry} · code {data['meta']['code_version']}"
        ),
        font={"size": 9, "color": theme.SUBTLE_INK},
    )
    return fig


def collect(args: argparse.Namespace) -> dict[str, Any]:
    walk_tsv = args.walk_dir / f"{NAME}.tsv"
    decoy_tsv = args.decoy_dir / f"{NAME}.tsv"
    paths_tsv = args.walk_dir / f"{NAME}.paths.tsv"
    manifests = [
        json.loads((d / f"{NAME}.provenance.json").read_text(encoding="utf-8"))
        for d in (args.walk_dir, args.decoy_dir)
    ]
    real, decoy = top_names(walk_tsv, args.top), top_names(decoy_tsv, args.top)
    candidates = candidate_names(args.candidates)
    real_parts = composition(real, set(decoy), candidates)
    decoy_parts = composition(decoy, set(real), candidates)
    shared = sorted(set(real) & set(decoy))
    comparison = args.walk_dir / f"{NAME}.comparison.json"
    cross_check(comparison, real_parts, shared)
    inputs = [walk_tsv, paths_tsv, decoy_tsv, args.candidates]
    return {
        "card_gene": manifests[0].get("card", {}).get("gene", ""),
        "walks": [
            {"label": walk_label(m), "names": n, "parts": p}
            for m, n, p in zip(manifests, (real, decoy), (real_parts, decoy_parts), strict=True)
        ],
        "shared": shared,
        "gene_shares": gene_shares(paths_tsv),
        "inputs": inputs,
        "comparison": comparison if comparison.is_file() else None,
        "meta": {
            "script": SCRIPT,
            "inputs": [provenance.repo_relative(p) for p in inputs],
            "code_version": provenance.code_version(),
            "entry": args.entry,
        },
    }


def manifest(data: dict[str, Any], args: argparse.Namespace, written: list[Path]) -> dict:
    record = provenance.envelope(args.slug, SCRIPT)
    record["inputs"] = [provenance.output(p, len(read_tsv(p))) for p in data["inputs"]]
    if data["comparison"] is not None:
        record["cross_checked_against"] = provenance.repo_relative(data["comparison"])
    record["parameters"] = {
        "top": args.top,
        "threshold": args.threshold,
        "claim": args.claim,
        "matching": "mva.drugs.names.base_name, distinct names within the top N",
        "segment_rule": "candidate list wins over 'shared'; each name counted once",
        "gene_share": "summed path weight grouped by the path's second node (the disease gene)",
    }
    record["values"] = {
        "walks": [
            {"label": w["label"], "distinct": len(w["names"]), **w["parts"]} for w in data["walks"]
        ],
        "walk_decoy_shared": data["shared"],
        "gene_share_pct": {g: round(v * 100, 1) for g, v in data["gene_shares"].items()},
    }
    record["methodology_entry"] = args.entry
    record["outputs"] = [
        {"path": provenance.repo_relative(p), "sha256": provenance.digest(p)[0]} for p in written
    ]
    return record


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    theme.install_template()
    data = collect(args)
    fig = build(data, args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt, scale in (("png", 2), ("svg", 1)):
        path = args.out_dir / f"{args.slug}.{fmt}"
        fig.write_image(path, format=fmt, width=1300, height=480, scale=scale)
        written.append(path)
    sidecar = args.out_dir / f"{args.slug}.provenance.json"
    provenance.write(manifest(data, args, written), sidecar)
    for w in data["walks"]:
        counts = {k: len(v) for k, v in w["parts"].items()}
        print(f"{w['label']}: {len(w['names'])} distinct, {counts}")
    print("shared:", data["shared"])
    print({g: f"{v * 100:.1f} %" for g, v in data["gene_shares"].items()})
    print("wrote", *(provenance.repo_relative(p) for p in [*written, sidecar]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
