#!/usr/bin/env python3
"""Render the Track-1 report's figures from the warehouse's result schema.

Writes ``figures/track1/<slug>.png`` (static, for the Markdown report) and
``figures/track1-report.html`` (one interactive page). Every figure is built from counts
and gene names; the only input that holds coordinates is the submission spec under
gitignored ``build/``, and only its labels reach the page.

Usage::

    uv run python tools/render_track1_figures.py [--spec build/submission/spec.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mva.render.figure import Section
from mva.render.report import render
from mva.report import data, figures
from mva.warehouse.settings import Postgres

HIGHLIGHT = "BUB1B"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", type=Path, default=Path("build/submission/spec.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("figures/track1"))
    parser.add_argument("--html", type=Path, default=Path("figures/track1-report.html"))
    parser.add_argument("--highlight", default=HIGHLIGHT, help="the gene to mark as the answer")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Postgres.from_env()
    counts = data.funnel(settings)
    rows = data.gene_rows(settings)
    exhibits = [figures.funnel_chart(counts), figures.gene_scatter(rows, args.highlight)]
    if args.spec.is_file():
        found, labels = data.decode_design(args.spec)
        exhibits.append(figures.decode_table(found, labels))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for exhibit in exhibits:
        png = exhibit.write_image(args.out_dir)
        print(f"{exhibit.slug:<24} {'png ' + str(png) if png else 'png: kaleido missing'}")
    (args.out_dir / "funnel.json").write_text(
        json.dumps(dict(counts.stages()), indent=2) + "\n", encoding="utf-8"
    )
    html = render(
        [
            Section(
                "track1",
                "The Track-1 submission",
                "The funnel, the gene table, the decode table.",
                exhibits,
            )
        ],
        title="Track 1 — the submission, in figures",
        subject=str(settings.database),
    )
    args.html.write_text(html, encoding="utf-8")
    print(f"wrote {args.html} ({len(html) // 1024} KB) and {args.out_dir}/funnel.json")


if __name__ == "__main__":
    main()
