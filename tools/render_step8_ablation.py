#!/usr/bin/env python3
"""Step 8: what the GPU lanes did to the consensus. One figure, two panels.

**Left — leave-one-in.** The confirmed pair's catalogue-free RRF percentile (lower = nearer the
top) for the six laptop lanes, the six plus each GPU lane alone, and all nine. Blue = the
baseline; red = a configuration that ranks the pair *worse* than the baseline, green = better.

**Right — who votes.** The confirmed pair's percentile in each lane's own pair ranking; a lane
that cannot score both halves (a missense-only lane, and the pair is missense + stop-gained) has
**no opinion** and is drawn hatched, never as zero. RRF adds a vote only from lanes that rank
the pair, which is why abstaining lanes can push it down.

**Sources.** ``build/it4/ablation/<config>.merged.json`` (one per ``mva-zoo run`` of the
leave-one-in, configs in ``build/it4/ablation/*.toml``) and ``build/it4/merged.json`` (run
``it4-81ec74fb9f9a``, config ``docs/iteration4/step-8/zoo.step8.toml``). Entry 148.

Usage::

    uv run python tools/render_step8_ablation.py

Outputs ``figures/it4/step8-consensus-ablation.{svg,html}`` and a ``.provenance.json``; prints
the legend line to paste under the figure.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ABLATION = Path("build/it4/ablation")
FINAL = Path("build/it4/merged.json")
OUT = Path("figures/it4/step8-consensus-ablation.svg")
#: A PNG preview for eyeballing the figure, under build/ (not committed).
PREVIEW = Path("build/it4/modal/step8-consensus-ablation.png")
CONFIGS = (
    ("six laptop lanes", ABLATION / "six.merged.json"),
    ("+ Evo 2", ABLATION / "six-evo2.merged.json"),
    ("+ NT-v2", ABLATION / "six-ntv2.merged.json"),
    ("+ ESM-C", ABLATION / "six-esmc.merged.json"),
    ("all nine", FINAL),
)


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from mva.render.theme import BAD, GOOD, MACHINE, MUTED, install_template, legend_line

    install_template()
    runs = [(label, _load(path)) for label, path in CONFIGS]
    free = [(label, run["consensus"]["catalogue_free"]) for label, run in runs]
    base = free[0][1]["percentile"]
    fig = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.18,
        subplot_titles=(
            "Leave-one-in: every GPU lane alone ranks the pair lower",
            "Who votes for the pair (catalogue-free lanes)",
        ),
    )
    values = [row["percentile"] for _, row in free]
    hues = [MACHINE] + [BAD if v > base else GOOD for v in values[1:]]
    fig.add_trace(
        go.Bar(
            y=[label for label, _ in free],
            x=values,
            orientation="h",
            marker={"color": [h.fill for h in hues], "line": {"color": [h.line for h in hues]}},
            text=[f"{row['rank']:,} / {row['n_pairs']:,}" for _, row in free],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    lanes = [lane for lane in runs[-1][1]["lanes"] if not lane["catalogue_adjacent"]]
    pct = [lane["confirmed"]["percentile"] for lane in lanes]
    lane_hues = [MUTED if p is None else (GOOD if p <= 10 else MACHINE) for p in pct]
    fig.add_trace(
        go.Bar(
            y=[lane["model"] for lane in lanes],
            x=[100.0 if p is None else p for p in pct],
            orientation="h",
            marker={
                "color": [h.fill for h in lane_hues],
                "line": {"color": [h.line for h in lane_hues]},
                "pattern": {"shape": ["/" if p is None else "" for p in pct]},
            },
            text=["no opinion" if p is None else f"{p:.1f}" for p in pct],
            textposition="outside",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_vline(x=10, line={"color": GOOD.line, "dash": "dash"}, row=1, col=2)
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(margin={"l": 150, "r": 40, "t": 70, "b": 60})
    fig.update_xaxes(title_text="consensus percentile (lower = better)", row=1, col=1,
                     range=[0, max(values) * 1.45])  # fmt: skip
    fig.update_xaxes(title_text="percentile in the lane's own ranking", row=1, col=2,
                     range=[0, 130])  # fmt: skip
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(OUT, format="svg", width=1100, height=460)
    if PREVIEW:
        fig.write_image(PREVIEW, format="png", width=1100, height=460)
    fig.write_html(OUT.with_suffix(".html"), include_plotlyjs="cdn", full_html=True)
    print(
        legend_line(
            MACHINE,
            BAD,
            GOOD,
            MUTED,
            extra="hatched = no opinion (the lane cannot score both alleles); dashed = top decile",
        )
    )

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    provenance = {
        "name": OUT.stem,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": "tools/render_step8_ablation.py",
        "code_version": commit,
        "inputs": [{"path": str(path), "sha256": _sha(path)} for _, path in CONFIGS],
        "run_id": runs[-1][1]["run_id"],
        "entry": "docs/iteration4/step-8/methodology/148-the-gpu-lanes-and-the-consensus.md",
    }
    OUT.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
