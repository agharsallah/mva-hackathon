"""Candidate-gene views — where the search actually starts.

A whole genome holds five million variants and the answer is two of them. No ranking
survives that ratio on its own, so every rare-disease pipeline begins by asking a much
smaller question first: what does the callset look like inside the genes already known to
cause this phenotype?

These panels answer it three ways — where those genes sit in the genome, how many calls
landed in each, and how big the resulting pair search is. The last one is the reason this
project ranks pairs rather than variants, made visible.
"""

import math

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..figure import Exhibit, sized
from ..profile import CallsetProfile
from ..theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, legend_line


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """Every candidate-gene exhibit the profile can support."""
    if not profile.panel:
        return []
    out = [gene_counts(profile), search_space(profile)]
    if profile.contigs:
        out.insert(0, gene_map(profile))
    return out


def gene_map(profile: CallsetProfile) -> Exhibit:
    """Where the candidate genes sit on the chromosomes — a karyogram with the panel marked.

    A gene name is an abstraction; a position is a coordinate you can query. Drawing the
    panel against the real chromosome lengths makes two things obvious at once: how tiny
    the searched fraction of the genome is, and that the candidates are scattered rather
    than clustered, so no single region query covers them.
    """
    contigs = [c for c in profile.primary_contigs if c.name.removeprefix("chr") != "M"]
    names = [f"chr{c.name.removeprefix('chr')}" for c in contigs]
    lengths = {n: c.length / 1e6 for n, c in zip(names, contigs)}

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=names,
            x=[lengths[n] for n in names],
            orientation="h",
            name="chromosome",
            marker=dict(color=MUTED.fill, line=dict(color=MUTED.line, width=0.5)),
            hovertemplate="<b>%{y}</b><br>%{x:,.1f} Mb<extra></extra>",
            showlegend=False,
            width=0.55,
        )
    )

    genes = profile.panel
    figure.add_trace(
        go.Scatter(
            x=[(g.start + g.end) / 2e6 for g in genes],
            y=[f"chr{g.chrom.removeprefix('chr')}" for g in genes],
            mode="markers+text",
            name="candidate gene",
            # Beside the marker, not above it: a label placed above sits at the height of the
            # chromosome one row up and reads as belonging to that chromosome instead.
            text=[f" {g.symbol}" for g in genes],
            textposition="middle right",
            textfont=dict(size=11, color=RAW.line),
            marker=dict(
                symbol="diamond", size=13, color=RAW.fill, line=dict(color=RAW.line, width=1.5)
            ),
            customdata=[(g.symbol, g.start, g.end, g.variants, g.note) for g in genes],
            hovertemplate="<b>%{customdata[0]}</b><br>%{y}:%{customdata[1]:,}-%{customdata[2]:,}"
            "<br>%{customdata[3]:,} variants called<br>%{customdata[4]}<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="position along the chromosome (megabases)",
        yaxis=dict(autorange="reversed", title=""),
        bargap=0.35,
        showlegend=False,
    )

    panel_bases = sum(g.end - g.start for g in genes)
    genome_bases = sum(c.length for c in contigs)
    return Exhibit(
        slug="panel-gene-map",
        title="Where the candidate genes sit",
        caption=(
            "Each grey bar is a chromosome drawn to scale; each diamond is a gene on the "
            "candidate panel, placed at its real coordinates. Chromosomes are numbered by "
            "size, which is why chromosome 1 is longest. Hover a diamond for why that gene "
            "is on the list."
        ),
        legend=legend_line(
            MUTED,
            RAW,
            extra="grey bars are chromosomes at true scale, purple diamonds "
            "are the candidate genes",
        ),
        figure=sized(figure, 560),
        height=560,
        notes=[
            f"The panel spans {panel_bases / 1e6:.2f} Mb of a {genome_bases / 1e9:.2f} Gb "
            f"genome — {panel_bases / genome_bases:.4%} of it. Searching there first costs "
            "almost nothing and is where a known disease gene is most likely to be; "
            "searching there *only* is how a novel gene gets missed."
        ],
    )


def gene_counts(profile: CallsetProfile) -> Exhibit:
    """Calls per candidate gene, split by whether the caller trusted them.

    Two views of the same eight genes. The left bars are raw counts, which mostly track
    gene length. The right bars divide by length, which is the comparison that means
    something. A gene with an unusual share of suppressed calls is worth opening
    regardless of where it lands on either.
    """
    genes = sorted(profile.panel, key=lambda g: g.variants)
    labels = [g.symbol for g in genes]

    figure = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.14,
        shared_yaxes=True,
        subplot_titles=("Calls per gene", "Calls per kilobase of gene"),
    )
    figure.add_trace(
        go.Bar(
            y=labels,
            x=[g.passing for g in genes],
            orientation="h",
            name="PASS",
            marker=dict(color=GOOD.fill, line=dict(color=GOOD.line, width=1)),
            hovertemplate="<b>%{y}</b><br>%{x:,} passing calls<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            y=labels,
            x=[g.suppressed for g in genes],
            orientation="h",
            name="non-PASS",
            marker=dict(color=DECISION.fill, line=dict(color=DECISION.line, width=1)),
            hovertemplate="<b>%{y}</b><br>%{x:,} suppressed calls<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            y=labels,
            x=[g.variants_per_kb for g in genes],
            orientation="h",
            name="per kilobase",
            showlegend=False,
            marker=dict(color=MACHINE.fill, line=dict(color=MACHINE.line, width=1)),
            customdata=[(g.kilobases, g.variants) for g in genes],
            hovertemplate="<b>%{y}</b><br>%{x:.2f} calls per kb"
            "<br>%{customdata[1]:,} calls over %{customdata[0]:,.0f} kb<extra></extra>",
        ),
        row=1,
        col=2,
    )
    figure.update_layout(barmode="stack", bargap=0.35)
    figure.update_xaxes(title_text="calls", row=1, col=1)
    figure.update_xaxes(title_text="calls per kb", row=1, col=2)

    flagged = max(genes, key=lambda g: g.suppressed_fraction)
    notes = []
    if flagged.suppressed:
        notes.append(
            f"**{flagged.symbol}** carries the highest suppressed share — "
            f"{flagged.suppressed} of {flagged.variants} calls ({flagged.suppressed_fraction:.0%}) "
            "are flagged. That is either a gene sitting in awkward sequence or a gene whose "
            "real variant was filtered out, and the two look identical from here. Opening "
            "the suppressed records is minutes of work; re-calling the region is a day."
        )
    return Exhibit(
        slug="panel-gene-counts",
        title="Calls in each candidate gene",
        caption=(
            "Left: how many variants the caller placed inside each gene, stacked by whether "
            "it trusted them. Right: the same counts divided by gene length, because a long "
            "gene collects more variants for no interesting reason. Compare a gene against "
            "its neighbours on the right, not on the left."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            MACHINE,
            extra="green is passing calls, yellow is suppressed ones, blue is "
            "the length-normalised rate",
        ),
        figure=sized(figure, 440),
        notes=notes,
    )


def search_space(profile: CallsetProfile) -> Exhibit:
    """How many variant pairs each gene could form — why pairs are the ranked unit.

    A compound heterozygote is a *pair* of variants, so the thing that has to be ranked is
    a pair. That squares the problem: a gene with eighty calls offers thousands of possible
    pairs, and the count grows quadratically while the evidence per pair does not.

    The bars are an upper bound, computed as every two-variant combination of the calls in
    the gene. The real figure is smaller because only heterozygous calls can pair, and it
    is not derivable from the counts alone — the bound is the honest number to draw.
    """
    genes = sorted(profile.panel, key=lambda g: _pairs(g.variants))
    labels = [g.symbol for g in genes]
    bound = [_pairs(g.variants) for g in genes]

    figure = go.Figure(
        go.Bar(
            y=labels,
            x=bound,
            orientation="h",
            marker=dict(color=BAD.fill, line=dict(color=BAD.line, width=1)),
            text=[f"{b:,}" for b in bound],
            textposition="outside",
            customdata=[(g.variants,) for g in genes],
            hovertemplate="<b>%{y}</b><br>up to %{x:,} pairs from %{customdata[0]:,} calls"
            "<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="possible variant pairs (upper bound)",
        yaxis_title="",
        showlegend=False,
        bargap=0.35,
    )

    total = sum(bound)
    return Exhibit(
        slug="panel-search-space",
        title="The pair search space",
        caption=(
            "The answer is two variants in one gene, so the unit that has to be ranked is a "
            "pair — and pairs grow as the square of the calls. These bars count every "
            "two-call combination inside each gene: an upper bound, since only heterozygous "
            "calls can actually pair, but the right order of magnitude. Ten submission rows "
            f"against roughly {total:,} candidate pairs is the whole problem in one number."
        ),
        legend=legend_line(
            BAD,
            extra="each bar is one gene's pair count, an upper bound computed "
            "from every two-call combination",
        ),
        figure=sized(figure, 400),
        notes=[
            "This is why annotation is the critical path rather than a refinement. Without "
            "a consequence prediction and a population frequency, nothing separates one "
            "pair in this space from another, and ten rows chosen from thousands of "
            "indistinguishable candidates is a lottery ticket."
        ],
    )


def _pairs(n: int) -> int:
    """Two-element combinations of ``n`` items — the pair count for one gene."""
    return math.comb(n, 2) if n > 1 else 0
