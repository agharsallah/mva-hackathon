"""The chart shapes step 5's exhibits are drawn with, separated from what they mean.

One bounded concern: every function here takes rows from ``analysis.json`` and returns a
``plotly`` figure. The captions, the legends and the decisions about which exhibits exist
live in ``tools/render_it2_step5_figures.py``, because those are claims about the data and
these are only shapes.

Two axis conventions, both forced by the data rather than chosen:

* **Publication counts are logarithmic.** Across 815 genes the counts span five orders of
  magnitude, from genes nobody has written about to HLA loci in the tens of thousands. On a
  linear axis the whole comparison is one bar and 814 slivers.
* **The catalogue bars are counts, not percentages.** A single coverage percentage would
  merge "no dbSNP identifier, so never askable" with "askable, and nobody published", and
  only the second says anything about the literature.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go

from mva.render import theme

#: Left margin for the horizontal charts: a gene symbol plus its origin in brackets.
LABEL_MARGIN = 200

#: Genes drawn per horizontal chart. More rows than this is a download, not a figure.
ROWS = 20


def _log1p(value: float | None) -> float:
    return math.log10(max(float(value or 0.0) + 1.0, 1.0))


def _origin(row: dict) -> str:
    if row.get("is_decoy"):
        return "decoy"
    return "target" if row.get("is_target") else "neither"


def catalogue_figure(rows: list[dict]) -> go.Figure:
    """Per gene, the three counts a coverage claim needs, stacked and never merged.

    Grey is the band that matters most: alleles with no dbSNP identifier, which a
    literature index keyed on dbSNP could not have had an opinion about. Merging them into
    a percentage is how a gap in a public catalogue becomes a finding about a patient.
    """
    top = sorted(rows, key=lambda r: (-r.get("carried_pathogenic", 0), -r.get("described", 0)))[
        :ROWS
    ]
    top = list(reversed(top))
    labels = [f"{r['gene']} ({_origin(r)})" for r in top]
    published = [r.get("described", 0) for r in top]
    silent = [r.get("queryable", 0) - r.get("described", 0) for r in top]
    never = [r.get("unqueryable", 0) for r in top]
    figure = go.Figure(
        [
            go.Bar(
                y=labels,
                x=published,
                orientation="h",
                name="published",
                marker_color=theme.GOOD.fill,
            ),
            go.Bar(
                y=labels,
                x=silent,
                orientation="h",
                name="askable, nobody published",
                marker_color=theme.MACHINE.fill,
            ),
            go.Bar(
                y=labels,
                x=never,
                orientation="h",
                name="never askable (no dbSNP id)",
                marker_color=theme.MUTED.fill,
            ),
        ]
    )
    figure.update_layout(
        barmode="stack",
        xaxis_title="alleles this child carries in the gene",
        margin={"l": LABEL_MARGIN, "r": 40},
        height=560,
    )
    return figure


def anchors_figure(rows: list[dict]) -> go.Figure:
    """How many of the child's seven features the best paper for each gene covers.

    Targets and decoys on one axis. The comparison is the exhibit: a target column that
    looks tall means nothing until a decoy column is drawn beside it.
    """
    best: dict[str, dict] = {}
    for row in rows:
        gene = row["gene"]
        if row.get("terms_matched", 0) > best.get(gene, {}).get("terms_matched", -1):
            best[gene] = row
    top = sorted(best.values(), key=lambda r: -r.get("terms_matched", 0))[:ROWS]
    top = list(reversed(top))
    colours = [
        theme.BAD.fill
        if _origin(r) == "decoy"
        else theme.GOOD.fill
        if _origin(r) == "target"
        else theme.MACHINE.fill
        for r in top
    ]
    figure = go.Figure(
        go.Bar(
            y=[f"{r['gene']} ({_origin(r)})" for r in top],
            x=[r.get("terms_matched", 0) for r in top],
            orientation="h",
            marker_color=colours,
            text=[str(r.get("terms_matched", 0)) for r in top],
            textposition="outside",
        )
    )
    figure.update_layout(
        xaxis_title="clinical features the gene's best paper covers (of 7)",
        margin={"l": LABEL_MARGIN, "r": 60},
        height=560,
        showlegend=False,
    )
    return figure


def citations_figure(rows: list[dict]) -> go.Figure:
    """The knowledge ordering against the citation ordering, gene by gene.

    Points on the diagonal are genes the literature route placed exactly where publication
    volume alone would have. A route whose cloud lies on the diagonal has measured fame,
    and this is the figure that says so before any prose does.
    """
    figure = go.Figure()
    for origin, hue in (
        ("target", theme.GOOD),
        ("decoy", theme.BAD),
        ("neither", theme.MACHINE),
    ):
        subset = [row for row in rows if _origin(row) == origin]
        if not subset:
            continue
        figure.add_trace(
            go.Scatter(
                x=[row["citation_rank"] for row in subset],
                y=[row["knowledge_rank"] for row in subset],
                mode="markers",
                name=origin,
                marker={"color": hue.fill, "line": {"color": hue.line, "width": 1}, "size": 9},
                text=[f"{row['gene']} — {row.get('pubmed_count', 0):,} papers" for row in subset],
            )
        )
    span = max(
        [row["citation_rank"] for row in rows] + [row["knowledge_rank"] for row in rows] + [1]
    )
    figure.add_trace(
        go.Scatter(
            x=[1, span],
            y=[1, span],
            mode="lines",
            name="no reordering",
            line={"color": theme.MUTED.line, "dash": "dot"},
        )
    )
    figure.update_layout(
        xaxis_title="rank by PubMed hit count alone",
        yaxis_title="rank by the knowledge score",
        height=560,
    )
    return figure


def separation_figure(groups: list[dict]) -> go.Figure:
    """Where each class of gene sits, with the two the null is measured between first.

    The decoys are not a footnote on this chart. Step 2 measured targets and decoys as
    indistinguishable before any scoring, so any separation here was produced by these
    queries and by nothing else.
    """
    order = ["target", "decoy", "curated-other", "uncurated-other"]
    rows = [row for name in order for row in groups if row["grouping"] == name]
    colours = {
        "target": theme.GOOD.fill,
        "decoy": theme.BAD.fill,
        "curated-other": theme.MACHINE.fill,
        "uncurated-other": theme.RAW.fill,
    }
    figure = go.Figure(
        go.Bar(
            x=[row["grouping"] for row in rows],
            y=[float(row.get("mean_score") or 0) for row in rows],
            marker_color=[colours.get(row["grouping"], theme.MUTED.fill) for row in rows],
            text=[
                f"{int(row.get('genes_with_anchor') or 0)} of {int(row['genes'])} with an anchor"
                for row in rows
            ],
            textposition="outside",
        )
    )
    figure.update_layout(
        yaxis_title="mean knowledge score",
        height=460,
        showlegend=False,
    )
    return figure


def domains_figure(residues: list[dict], domains: list[dict]) -> go.Figure:
    """Each leading protein as a rule, its InterPro domains as bars, the allele as a tick.

    Positions are fractions of each protein's own length — the picture needs nothing else,
    and a residue number is not something this repository commits.
    """
    genes = [row["gene"] for row in residues]
    figure = go.Figure()
    for index, gene in enumerate(genes):
        figure.add_shape(
            type="line", x0=0, x1=1, y0=index, y1=index, line={"color": theme.MUTED.line}
        )
        for track in [row for row in domains if row["gene"] == gene]:
            is_domain = track.get("entry_type") == "domain"
            figure.add_shape(
                type="rect",
                x0=track["start_fraction"],
                x1=track["end_fraction"],
                y0=index - (0.28 if is_domain else 0.12),
                y1=index + (0.28 if is_domain else 0.12),
                fillcolor=theme.DECISION.fill if is_domain else theme.MACHINE.fill,
                line={"width": 0},
                opacity=0.95 if is_domain else 0.5,
            )
    figure.add_trace(
        go.Scatter(
            x=[row.get("fraction") or 0 for row in residues],
            y=list(range(len(residues))),
            mode="markers",
            marker={
                "symbol": "line-ns",
                "size": 26,
                "line": {
                    "width": 3,
                    "color": [
                        theme.GOOD.line if row.get("in_domain") else theme.BAD.line
                        for row in residues
                    ],
                },
            },
            text=[
                f"{row['gene']} · pLDDT {row.get('plddt')} · {row.get('am_class') or 'no class'}"
                for row in residues
            ],
            name="the missense allele",
        )
    )
    figure.update_layout(
        xaxis={"title": "position along the protein (fraction of its length)", "range": [0, 1]},
        yaxis={"tickmode": "array", "tickvals": list(range(len(genes))), "ticktext": genes},
        height=max(320, 70 * len(genes)),
        showlegend=False,
    )
    return figure


def sources_figure(coverage: dict, anchors: dict, protein: dict) -> go.Figure:
    """What each public source was asked and what it was able to answer.

    The grey bar on each row is the part of the question the source could not reach, which
    is the number a reader needs before any of the coloured bars mean anything.
    """
    rows = [
        (
            "LitVar 2.0 — alleles",
            int(coverage.get("described") or 0),
            int(coverage.get("queryable") or 0) - int(coverage.get("described") or 0),
            int(coverage.get("unqueryable") or 0),
        ),
        (
            "PubTator 3.0 — genes",
            len(anchors.get("genes_reaching_five_terms") or []),
            int(anchors.get("genes") or 0) - len(anchors.get("genes_reaching_five_terms") or []),
            0,
        ),
        (
            "UniProt/InterPro/AlphaFold — alleles",
            int(protein.get("in_domain") or 0),
            int(protein.get("resolved_residue") or 0) - int(protein.get("in_domain") or 0),
            int(protein.get("alleles") or 0) - int(protein.get("resolved_residue") or 0),
        ),
    ]
    labels = [row[0] for row in rows]
    figure = go.Figure(
        [
            go.Bar(
                y=labels,
                x=[row[1] for row in rows],
                orientation="h",
                name="answered yes",
                marker_color=theme.GOOD.fill,
            ),
            go.Bar(
                y=labels,
                x=[row[2] for row in rows],
                orientation="h",
                name="answered no",
                marker_color=theme.MACHINE.fill,
            ),
            go.Bar(
                y=labels,
                x=[row[3] for row in rows],
                orientation="h",
                name="could not be asked",
                marker_color=theme.MUTED.fill,
            ),
        ]
    )
    figure.update_layout(
        barmode="stack", margin={"l": 280, "r": 40}, height=360, xaxis_title="items"
    )
    return figure
