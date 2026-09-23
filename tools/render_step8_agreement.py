#!/usr/bin/env python3
"""Step 8: does ESM-C agree with the other protein language models? One figure, two panels.

**What it shows.** A density plot (a 2-D histogram: how many alleles fall in each cell) of the
ESM-C score against ESM2's, and against ESM1b's, over the missense alleles both lanes scored.
Spearman ρ (rank correlation: 1 = the two models order the alleles identically) and the
shared count *n* are printed in each panel title. The confirmed pair's missense allele — the
``[case]`` rule's gene, its one missense record — is one green marker, unlabelled.

**Where the numbers come from.** Scores are read from the warehouse score cache
(``warehouse.allele_scores``, :func:`mva.zoo.cache.read`), so every lane is on the zoo's one
convention (higher = more damaging). The confirmed allele is found from
``build/it4/records.parquet`` (gene + consequence), never from a typed id.

**What never leaves ``build/``.** Allele ids and coordinates: the figure carries scores only,
and the stats JSON with the confirmed allele's id is written to ``build/it4/esmc/``.

Usage::

    uv run python tools/render_step8_agreement.py
    uv run python tools/render_step8_agreement.py --out-dir build/it4/figures-fixture

Outputs: ``figures/it4/esmc-vs-esm2.{svg,html}``, a ``.provenance.json`` beside them, and
``build/it4/esmc/agreement.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import spearmanr

from mva.render.theme import GOOD, MACHINE, install_template, legend_line
from mva.zoo import cache
from mva.zoo.case_config import Config

SCRIPT = "tools/render_step8_agreement.py"
SLUG = "esmc-vs-esm2"
SUBJECT = "esmc"
OTHERS = ("esm2", "esm1b")
LABEL = {"esmc": "ESM-C", "esm2": "ESM2", "esm1b": "ESM1b"}
DEFAULT_CONFIG = Path("src/mva/zoo/zoo.example.toml")
DEFAULT_RECORDS = Path("build/it4/records.parquet")
DEFAULT_OUT = Path("figures/it4")
STATS = Path("build/it4/esmc/agreement.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


# ── inputs ───────────────────────────────────────────────────────────────────────────────


def lane_scores(connection: Any, schema: str, model: str) -> dict[str, float]:
    """One score per allele for ``model``; a repeated allele (two modes) keeps the last row."""
    rows = cache.read(connection, schema, model=model)
    return {row.allele_id: float(row.score) for row in rows if row.score is not None}


def missense_ids(records: Path) -> set[str]:
    con = duckdb.connect()
    sql = "SELECT allele_id FROM read_parquet(?) WHERE consequence LIKE '%missense%'"
    return {str(r[0]) for r in con.execute(sql, [str(records)]).fetchall()}


def confirmed_missense(records: Path, gene: str) -> str | None:
    """The confirmed gene's missense allele, if the record set has exactly one."""
    if not gene:
        return None
    con = duckdb.connect()
    sql = "SELECT allele_id FROM read_parquet(?) WHERE gene = ? AND consequence LIKE '%missense%'"
    found = [str(r[0]) for r in con.execute(sql, [str(records), gene]).fetchall()]
    return found[0] if len(found) == 1 else None


# ── arithmetic ───────────────────────────────────────────────────────────────────────────


def agreement(left: dict[str, float], right: dict[str, float], keep: set[str]) -> dict[str, Any]:
    """Spearman ρ over the alleles both lanes scored (and ``keep`` admits)."""
    shared = sorted(set(left) & set(right) & keep)
    if len(shared) < 3:
        return {"n": len(shared), "rho": None}
    rho = float(spearmanr([left[a] for a in shared], [right[a] for a in shared]).statistic)
    return {"n": len(shared), "rho": round(rho, 4)}


def standing(scores: dict[str, float], allele: str | None, keep: set[str]) -> dict[str, Any]:
    """Where one allele sits among ``keep``: rank from the top, and its percentile."""
    pool = sorted((v for a, v in scores.items() if a in keep), reverse=True)
    if allele is None or allele not in scores or not pool:
        return {"scored": False}
    value = scores[allele]
    above = sum(1 for v in pool if v > value)
    return {
        "scored": True,
        "score": round(value, 4),
        "rank": above + 1,
        "of": len(pool),
        "top_percent": round(100.0 * (above + 1) / len(pool), 2),
        "percentile": round(100.0 * sum(1 for v in pool if v <= value) / len(pool), 2),
    }


# ── the figure ───────────────────────────────────────────────────────────────────────────


def figure(
    lanes: dict[str, dict[str, float]], keep: set[str], stats: dict[str, Any], mark: str | None
) -> go.Figure:
    titles = [
        f"ESM-C vs {LABEL[other]} — ρ = {stats[other]['rho']}, n = {stats[other]['n']:,}"
        for other in OTHERS
    ]
    fig = make_subplots(rows=1, cols=2, subplot_titles=titles, horizontal_spacing=0.1)
    subject = lanes[SUBJECT]
    for col, other in enumerate(OTHERS, start=1):
        shared = sorted(set(subject) & set(lanes[other]) & keep)
        fig.add_trace(
            go.Histogram2d(
                x=[lanes[other][a] for a in shared],
                y=[subject[a] for a in shared],
                nbinsx=60,
                nbinsy=60,
                colorscale=[[0, "#ffffff"], [0.02, MACHINE.fill], [1, MACHINE.line]],
                showscale=col == 2,
                colorbar={"title": "alleles"},
                name=other,
            ),
            row=1,
            col=col,
        )
        if mark and mark in subject and mark in lanes[other]:
            fig.add_trace(
                go.Scatter(
                    x=[lanes[other][mark]],
                    y=[subject[mark]],
                    mode="markers",
                    marker={"color": GOOD.line, "size": 12, "line": {"color": "#fff", "width": 2}},
                    name="confirmed pair's missense allele",
                    showlegend=col == 1,
                ),
                row=1,
                col=col,
            )
        fig.update_xaxes(title_text=f"{LABEL[other]} score (higher = more damaging)", row=1,
                         col=col)  # fmt: skip
    fig.update_yaxes(title_text="ESM-C score (higher = more damaging)", row=1, col=1)
    fig.update_layout(
        title="Does ESM-C 600M agree with ESM2 and ESM1b on the case's missense alleles?",
        height=520,
        margin={"t": 90, "b": 110},
        legend={"orientation": "h", "y": -0.22, "x": 0},
        meta={"script": SCRIPT, "source": "warehouse.allele_scores", "stats": stats},
    )
    return fig


def write(fig: go.Figure, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg, html = out_dir / f"{SLUG}.svg", out_dir / f"{SLUG}.html"
    fig.write_image(svg, format="svg", width=1100, height=520)
    fig.write_html(html, include_plotlyjs="cdn", full_html=True)
    return [svg, html]


def provenance(out_dir: Path, records: Path, config: Path, stats: dict[str, Any]) -> Path:
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    body = {
        "name": SLUG,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "built_by": SCRIPT,
        "code_version": commit,
        "inputs": [
            {"table": "warehouse.allele_scores", "models": [SUBJECT, *OTHERS]},
            {"path": str(records), "sha256": digest(records), "use": "missense filter, gene"},
            {"path": str(config), "sha256": digest(config), "use": "[case] confirmed_gene"},
        ],
        "stats": {k: v for k, v in stats.items() if k in OTHERS},
        "assumptions": "one score per allele per lane; scores already on 'higher = damaging'",
        "limitations": "Spearman over alleles both lanes scored; ESM1b covers fewer alleles",
    }
    path = out_dir / f"{SLUG}.provenance.json"
    path.write_text(json.dumps(body, indent=2) + "\n")
    return path


def main() -> None:
    from mva.warehouse.postgres import attached
    from mva.warehouse.settings import Postgres

    args = parse_args()
    config = Config.load(args.config)
    settings = replace(Postgres.from_env(), schema=config.warehouse_schema)
    # Not read-only: `cache.read` runs a no-op `CREATE TABLE IF NOT EXISTS` first.
    with attached(settings) as connection:
        lanes = {m: lane_scores(connection, settings.schema, m) for m in (SUBJECT, *OTHERS)}
    keep = missense_ids(args.records)
    mark = confirmed_missense(args.records, config.confirmed_gene)
    stats: dict[str, Any] = {o: agreement(lanes[SUBJECT], lanes[o], keep) for o in OTHERS}
    stats["esm2_vs_esm1b"] = agreement(lanes["esm2"], lanes["esm1b"], keep)
    stats["scored"] = {m: len(set(v) & keep) for m, v in lanes.items()}
    stats["confirmed"] = {m: standing(lanes[m], mark, keep) for m in (SUBJECT, *OTHERS)}
    install_template()
    written = write(figure(lanes, keep, stats, mark), args.out_dir)
    written.append(provenance(args.out_dir, args.records, args.config, stats))
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps({**stats, "confirmed_allele": mark}, indent=2) + "\n")
    print(json.dumps(stats, indent=2))
    print("wrote", *written, STATS)
    print(
        legend_line(
            MACHINE,
            GOOD,
            extra="shade = alleles per cell; green marker = the confirmed pair's missense allele",
        )
    )


if __name__ == "__main__":
    main()
