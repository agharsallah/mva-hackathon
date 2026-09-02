"""Locus views over live calls — what an analyst opens IGV to see.

The other view modules read summary tables. These read the calls themselves, through
:mod:`mva.pipeline.vcf`, and answer the questions that are normally answered by loading a BAM into
a genome browser and squinting: where in this gene are the variants, how well supported is
each one, and which of them can be placed on the same or opposite copies of the chromosome.

IGV shows the reads. These exhibits show the *conclusions* from the reads — allele balance,
support depth, phase-group membership, and the classified pair matrix — which is what
actually drives a compound-heterozygote decision, and which a screenshot cannot be
searched, diffed or regenerated from.

They are also the one part of the toolkit that touches patient coordinates, so nothing
here writes to the repository by default; the report renders them only when it is pointed
at a VCF explicitly.
"""

from collections import Counter

import plotly.graph_objects as go

from ...pipeline import Call, Phase, candidate_pairs
from ..figure import Exhibit, sized
from ..theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, SUBTLE_INK, legend_line

#: The allele balance a true heterozygous site is expected to show.
DIPLOID_VAF = 0.5


def exhibits(calls: list[Call], label: str = "locus") -> list[Exhibit]:
    """Every locus exhibit a list of calls can support."""
    if not calls:
        return []
    out = [variant_track(calls, label)]
    if any(c.phase_set for c in calls):
        out.append(phase_map(calls, label))
    hets = [c for c in calls if c.is_het]
    if len(hets) > 1:
        out.append(pair_phase_matrix(calls, label))
    return out


def variant_track(calls: list[Call], label: str = "locus") -> Exhibit:
    """Every call across the locus, positioned by coordinate and placed by allele balance.

    Reading it: a well-supported heterozygous variant sits on the 0.5 line with a large
    marker. One that drifts low is supported by fewer alternate reads than its depth
    implies — a mosaic variant present in only some cells, a mapping artefact, or a call
    that should not be trusted. Homozygous calls sit at 1.0 by construction and carry no
    information about pairing, because they are their own second hit.
    """
    figure = go.Figure()
    groups = [
        ("heterozygous, PASS", [c for c in calls if c.is_het and c.is_pass], GOOD, "circle"),
        (
            "heterozygous, non-PASS",
            [c for c in calls if c.is_het and not c.is_pass],
            DECISION,
            "circle-open",
        ),
        ("homozygous alternate", [c for c in calls if c.is_hom_alt], MACHINE, "square"),
    ]
    for name, group, hue, symbol in groups:
        subset = [c for c in group if c.vaf is not None]
        if not subset:
            continue
        figure.add_trace(
            go.Scatter(
                x=[c.variant.pos for c in subset],
                y=[c.vaf for c in subset],
                mode="markers",
                name=name,
                marker=dict(
                    symbol=symbol,
                    color=hue.fill,
                    line=dict(color=hue.line, width=1.5),
                    size=[_marker_size(c.depth) for c in subset],
                ),
                customdata=[
                    (
                        c.variant.ref,
                        c.variant.alt,
                        c.depth,
                        c.alt_depth,
                        ";".join(c.filters) or "none",
                        c.phase_set or "unphased",
                    )
                    for c in subset
                ],
                hovertemplate="<b>%{x:,}</b> %{customdata[0]}→%{customdata[1]}"
                "<br>allele balance %{y:.3f}"
                "<br>%{customdata[3]} alternate of %{customdata[2]} reads"
                "<br>filters: %{customdata[4]}"
                "<br>phase group: %{customdata[5]}<extra></extra>",
            )
        )
    figure.add_hline(
        y=DIPLOID_VAF,
        line=dict(color=GOOD.line, width=1, dash="dot"),
        annotation_text="0.5 — one copy of two",
        annotation_font=dict(size=11, color=SUBTLE_INK),
    )
    figure.add_hrect(
        y0=0,
        y1=0.2,
        fillcolor=BAD.fill,
        opacity=0.14,
        line_width=0,
        layer="below",
        annotation_text="too few alternate reads to trust",
        annotation_position="bottom left",
        annotation_font=dict(size=11, color=SUBTLE_INK),
    )
    figure.update_layout(
        xaxis_title=f"position on {calls[0].variant.chrom}",
        yaxis=dict(title="alternate reads / all reads", range=[0, 1.05]),
    )

    hets = sum(1 for c in calls if c.is_het)
    suppressed = sum(1 for c in calls if not c.is_pass)
    return Exhibit(
        slug=f"locus-track-{_slug(label)}",
        title=f"Variant track — {label}",
        caption=(
            f"{len(calls):,} calls across {label}, of which {hets:,} "
            f"{_agree(hets, 'is', 'are')} heterozygous and {suppressed:,} "
            f"{_agree(suppressed, 'was', 'were')} flagged by the caller. "
            "Horizontal position is the "
            "coordinate on the chromosome; vertical position is the fraction of reads "
            "carrying the variant; marker area grows with read depth, so a large marker on "
            "the 0.5 line is a call worth believing."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            MACHINE,
            BAD,
            extra="filled green circles are trusted heterozygous calls, "
            "hollow yellow ones were flagged, blue squares are "
            "homozygous, and the red strip is the untrustworthy floor",
        ),
        figure=sized(figure, 460),
    )


def _group_index(index: dict[str, int], call: Call) -> int:
    """A phased call's group position. ``phase_set`` is set — ``phased`` filtered on it."""
    assert call.phase_set is not None, "caller must pre-filter to calls with a phase_set"
    return index[call.phase_set]


def phase_map(calls: list[Call], label: str = "locus") -> Exhibit:
    """Which calls the caller could place on which copy of the chromosome.

    A phase group is a run of variants covered by common read pairs, so the caller can say
    which ones travel together. Within a group, ``0|1`` and ``1|0`` are opposite copies —
    and two variants on opposite copies in one gene is exactly the compound heterozygote
    being searched for. Across groups nothing can be said, which is why most of a gene ends
    up unresolved.
    """
    phased = [c for c in calls if c.phase_set and c.phase_gt]
    groups = sorted({c.phase_set for c in phased if c.phase_set is not None})
    index = {g: i for i, g in enumerate(groups)}

    figure = go.Figure()
    for haplotype, hue in (("0|1", MACHINE), ("1|0", RAW)):
        subset = [c for c in phased if c.phase_gt == haplotype]
        if not subset:
            continue
        figure.add_trace(
            go.Scatter(
                x=[c.variant.pos for c in subset],
                y=[_group_index(index, c) for c in subset],
                mode="markers",
                name=f"copy {'A' if haplotype == '0|1' else 'B'} ({haplotype})",
                marker=dict(
                    symbol="line-ns", size=22, color=hue.line, line=dict(color=hue.line, width=3)
                ),
                customdata=[(c.variant.ref, c.variant.alt, c.phase_set) for c in subset],
                hovertemplate="<b>%{x:,}</b> %{customdata[0]}→%{customdata[1]}"
                "<br>group %{customdata[2]}<extra></extra>",
            )
        )
    for group in groups:
        members = [c.variant.pos for c in phased if c.phase_set == group]
        figure.add_shape(
            type="line",
            x0=min(members),
            x1=max(members),
            y0=index[group],
            y1=index[group],
            line=dict(color=MUTED.line, width=1.5),
            layer="below",
        )

    figure.update_layout(
        xaxis_title=f"position on {calls[0].variant.chrom}",
        yaxis=dict(
            title="phase group",
            tickmode="array",
            tickvals=list(index.values()),
            ticktext=[g.split("_")[0] for g in groups],
            autorange="reversed",
        ),
    )

    spans = [
        max(c.variant.pos for c in phased if c.phase_set == g)
        - min(c.variant.pos for c in phased if c.phase_set == g)
        for g in groups
    ]
    reach = max(spans) if spans else 0
    return Exhibit(
        slug=f"phase-map-{_slug(label)}",
        title=f"Phase groups — {label}",
        caption=(
            f"{len(phased):,} calls fall into {len(groups):,} phase groups. Each grey line "
            "is one group; each tick is a variant, coloured by which of the two chromosome "
            "copies it sits on. Two ticks of different colours in the same group are on "
            "opposite copies — the definition of a compound heterozygote. Two ticks in "
            "different groups cannot be compared at all."
        ),
        legend=legend_line(
            MACHINE,
            RAW,
            MUTED,
            extra="blue and purple are the two chromosome copies, grey lines "
            "are the reach of each phase group",
        ),
        figure=sized(figure, 380),
        notes=[
            (
                f"The widest group here spans {reach:,} bp. That reach is set by how long the "
                "sequenced fragments were, not by how far apart the interesting variants are, "
                "which is why phasing confirms a pair it happens to catch and can never be the "
                "filter that finds one."
            )
        ],
    )


def pair_phase_matrix(calls: list[Call], label: str = "locus") -> Exhibit:
    """Every heterozygous pair in the locus, classified by phase.

    This is the search space made literal. Each cell is one hypothesis: two heterozygous
    variants proposed as the two broken copies of the gene. Red cells are refuted — both
    variants are on the same copy, leaving the other intact. Green cells are confirmed on
    opposite copies. Everything grey is undecided, and in a real gene almost everything is
    grey, which is why phase is a confirmation step rather than a filter.
    """
    pairs = candidate_pairs(calls)
    positions = sorted({c.variant.pos for c in calls if c.is_het})
    index = {p: i for i, p in enumerate(positions)}

    #: 0 unknown, 1 trans, -1 cis, None for the untested diagonal and mirror.
    grid: list[list[int | None]] = [[None] * len(positions) for _ in positions]
    for pair in pairs:
        i, j = index[pair.left.variant.pos], index[pair.right.variant.pos]
        value = {Phase.TRANS: 1, Phase.CIS: -1, Phase.UNKNOWN: 0}[pair.phase]
        grid[i][j] = value
        grid[j][i] = value

    labels = [f"{p:,}" for p in positions]
    figure = go.Figure(
        go.Heatmap(
            z=grid,
            x=labels,
            y=labels,
            colorscale=[[0.0, BAD.fill], [0.5, MUTED.fill], [1.0, GOOD.fill]],
            zmin=-1,
            zmax=1,
            showscale=False,
            xgap=2,
            ygap=2,
            hovertemplate="<b>%{y}</b> with <b>%{x}</b><br>%{text}<extra></extra>",
            text=[[_phase_word(v) for v in row] for row in grid],
        )
    )
    figure.update_layout(
        xaxis=dict(title="position", tickangle=-45),
        yaxis=dict(title="position", autorange="reversed"),
    )

    tally = Counter(p.phase for p in pairs)
    live = sum(1 for p in pairs if p.is_compound_het_candidate)
    return Exhibit(
        slug=f"pair-matrix-{_slug(label)}",
        title=f"Pair phase matrix — {label}",
        caption=(
            f"{len(pairs):,} heterozygous pairs across {label}. Each cell asks whether "
            "those two variants sit on opposite copies of the chromosome — the only "
            "arrangement that leaves no working gene. The matrix is symmetric because a "
            "pair has no order."
        ),
        legend=legend_line(
            GOOD,
            BAD,
            MUTED,
            extra="green cells are confirmed on opposite copies (trans), red "
            "cells are refuted on the same copy (cis), grey cells have "
            "no phase evidence either way",
        ),
        figure=sized(figure, 520),
        height=520,
        notes=[
            (
                f"{tally[Phase.TRANS]:,} confirmed trans, {tally[Phase.CIS]:,} rejected cis, "
                f"{tally[Phase.UNKNOWN]:,} of unknown phase — {live:,} pairs stay in play. "
                "Unknown phase is the common verdict and is never a rejection: with no parental "
                "samples sequenced, there is simply no evidence either way."
            )
        ],
    )


def _agree(count: int, singular: str, plural: str) -> str:
    """Pick the verb form that agrees with a generated count.

    Captions are assembled from live numbers, so "1 calls were flagged" is a real output
    and not a hypothetical. One helper is cheaper than noticing it later in a screenshot.
    """
    return singular if count == 1 else plural


def _phase_word(value: int | None) -> str:
    if value is None:
        return "not a pair"
    return {
        1: "opposite copies — trans",
        -1: "same copy — cis, refuted",
        0: "no phase evidence",
    }[value]


def _marker_size(depth: int | None) -> float:
    """Marker area grows with read depth, floored so a shallow call is still visible."""
    return 8 + min((depth or 0) ** 0.5 * 1.6, 22)


def _slug(label: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in label.lower()).strip("-")
