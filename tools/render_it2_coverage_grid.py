#!/usr/bin/env python3
"""The exon-coverage exhibit: how much evidence stands behind every absence, exon by exon.

Its own module because it is one bounded concern with its own colour ramp and its own
input file, and because `render_it2_step2_figures.py` crossed the 400-line limit —
the repository's rule (`docs/notes/python-quality-gates.md`) is to split by concern rather
than raise the limit.

**Why a grid and not a histogram.** `results.it2_exon_depth` is named for exons and holds
the *merged baited intervals* coverage was measured over; for 126 of the 128 core and
mechanism-term genes that is one interval spanning the whole gene. A gene-level mean of 44x
hides an exon at 0x completely, and "no second allele in this gene" has to be read against
the depth of the exon it is claimed about. So `tools/measure_it2_exon_depth.py` re-measures
depth per coding exon and this draws the result as a gene x exon grid, where a thin exon is
one red cell that cannot be averaged away.

The input carries **no coordinate**: a gene, an exon's ordinal within that gene, its length
and its mean depth.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme
from mva.render.figure import Exhibit

#: The depth an exon is expected to clear. Below it, "no second allele here" is a statement
#: about the data rather than about the child.
DEPTH_FLOOR = 10.0

#: Top of the colour range. Depth is capped rather than scaled to the maximum so one 106x
#: outlier cannot wash out the band the whole figure is about (0-10x).
DEPTH_CEILING = 80.0

#: The tiers the grid is drawn for. `net` is 268 genes and would make the figure a texture;
#: the two tiers step 2 draws conclusions from fit on one page.
GRID_TIERS = ("core", "mechanism-term")

#: Pixel height. One row per gene, so this is set by the number of genes, not by taste.
GRID_HEIGHT = 1400


def _depth_scale() -> list[list]:
    """Red below the floor, yellow at it, blue above — the repository's palette, as a ramp.

    The break is placed at ``DEPTH_FLOOR / DEPTH_CEILING`` so the colour changes exactly
    where the interpretation changes, rather than wherever a continuous scale happens to
    put it.
    """
    break_at = DEPTH_FLOOR / DEPTH_CEILING
    return [
        [0.0, theme.BAD.line],
        [break_at - 1e-6, theme.BAD.fill],
        [break_at, theme.DECISION.fill],
        [0.35, theme.MACHINE.fill],
        [1.0, theme.MACHINE.line],
    ]


def exon_grid_figure(rows: list[dict[str, str]]) -> go.Figure:
    """Gene x exon mean depth, one cell per coding exon of every gene in ``rows``.

    Rows are ordered by each gene's **thinnest** exon, so the genes where an absence cannot
    be interpreted sort to the top instead of hiding inside a gene-level average.
    """
    by_gene: dict[str, dict[int, float]] = {}
    for row in rows:
        by_gene.setdefault(row["symbol"], {})[int(row["exon_index"])] = float(row["mean_depth"])
    width = max((max(exons) for exons in by_gene.values()), default=1)
    genes = sorted(by_gene, key=lambda gene: (min(by_gene[gene].values()), gene), reverse=True)
    z = [[by_gene[gene].get(index) for index in range(1, width + 1)] for gene in genes]
    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=list(range(1, width + 1)),
            y=genes,
            zmin=0,
            zmax=DEPTH_CEILING,
            colorscale=_depth_scale(),
            colorbar={"title": "mean depth", "ticksuffix": "x"},
            hovertemplate="%{y}, exon %{x}: %{z:.1f}x<extra></extra>",
            hoverongaps=False,
            xgap=1,
            ygap=1,
        )
    )
    figure.update_xaxes(title="coding exon, in order along the gene", dtick=5)
    figure.update_yaxes(tickfont={"size": 8}, title="")
    figure.update_layout(margin={"l": 110, "t": 40, "b": 56})
    return figure


def coverage_exhibit(exon_depths: list[dict[str, str]]) -> Exhibit:
    """The grid plus the caption, legend and limitations it is required to carry."""
    grid = [row for row in exon_depths if row["tier"] in GRID_TIERS]
    thin = [row for row in grid if float(row["mean_depth"]) < DEPTH_FLOOR]
    genes = {row["symbol"] for row in grid}
    thin_genes = {row["symbol"] for row in thin}
    elsewhere = [
        row
        for row in exon_depths
        if row["tier"] not in GRID_TIERS and float(row["mean_depth"]) < DEPTH_FLOOR
    ]
    return Exhibit(
        slug="exon-coverage",
        title="How much evidence there is behind every absence, exon by exon",
        caption=(
            f"Mean depth over each of {len(grid):,} coding exons in the {len(genes)} core "
            "and mechanism-term genes, measured from the same alignment the callers read. "
            f"**{len(thin):,} exons in {len(thin_genes)} genes sit below "
            f"{DEPTH_FLOOR:.0f}x**, where 'no second allele here' is a gap in the data "
            "rather than a finding about the child. A per-gene average hides every one of "
            "them, which is why this is a grid and not a histogram."
        ),
        legend=(
            f"**red** = below the {DEPTH_FLOOR:.0f}x floor, **yellow** = at it, **blue, "
            "darker with depth** = above it; **white** = that gene has no exon at that "
            f"ordinal. Depth is capped at {DEPTH_CEILING:.0f}x so one outlier cannot wash "
            "out the band the figure is about. Genes are ordered by their own thinnest exon."
        ),
        figure=exon_grid_figure(grid),
        height=GRID_HEIGHT,
        notes=[
            (
                f"{len(elsewhere):,} further exons below the floor sit in `net`-tier genes, "
                "which are not drawn: 61 of them are in four genes with a known paralogue "
                "or pseudogene (`NEB`, `GTF2I`, `GTF2IRD2`, `ANAPC1`), where the uniqueness "
                "filter removed the bait and the aligner then cannot place a read uniquely. "
                "Entry 092."
            ),
            (
                "Exon ordinals are over the union of coding intervals in "
                "`warehouse.coding_regions`, so exon *n* is the gene's *n*-th coding "
                "interval and not a named transcript's exon *n*."
            ),
            (
                "mosdepth at `--mapq 20`, the same cut the calling stage used, so these "
                "depths are comparable with `results.it2_exon_depth` and not with a raw "
                "pileup."
            ),
        ],
    )
