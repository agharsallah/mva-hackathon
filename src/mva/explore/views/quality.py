"""Filters, genotypes and phasing — what the caller kept, cut, and could resolve.

A variant caller emits far more than it believes. Hard filters then flag the records it
distrusts, and every downstream tool quietly drops them. That default is wrong for a
rare-disease search: a genuine variant sitting in repetitive or duplicated sequence is
precisely the kind of record that gets flagged, so the suppressed set is a search space
rather than a bin.

These exhibits are therefore built to be read in both directions — how clean is the callset,
and how much is being hidden by the cleaning.
"""

import plotly.graph_objects as go

from ..figure import Exhibit, sized
from ..profile import CallsetProfile
from ..theme import DECISION, GOOD, MACHINE, MUTED, legend_line

#: What each GATK hard filter is testing, in plain terms.
FILTER_MEANINGS = {
    "PASS": "no filter fired",
    "LowQual": "the caller's overall confidence in the site was low",
    "MQ40": "reads at the site aligned ambiguously — they fit elsewhere in the genome too",
    "QD2": "little confidence per unit of read depth — many reads, weak signal",
    "FS60": "the alternate allele appeared mostly on one DNA strand, a classic artefact",
    "MQRankSum-12.5": "reads carrying the alternate allele aligned worse than reference reads",
    "RPRS-8": "the alternate allele clustered at read ends, where errors concentrate",
}

#: What each genotype string means for one sample.
GENOTYPE_MEANINGS = {
    "0/1": "heterozygous — one reference copy, one alternate",
    "1/1": "homozygous alternate — both copies carry the variant",
    "1/2": "two different alternate alleles, one on each copy",
    "0|1": "heterozygous, phased onto a known copy",
    "1|1": "homozygous alternate, phased",
}


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """Every filter and genotype exhibit the profile can support."""
    out = []
    if profile.filter_counts:
        out.append(filter_funnel(profile))
        out.append(suppression_reasons(profile))
    if profile.genotype_counts:
        out.append(genotypes(profile))
    if profile.phased_records and profile.total_records:
        out.append(phasing(profile))
    return out


def filter_funnel(profile: CallsetProfile) -> Exhibit:
    """From every emitted record down to the ones a default pipeline would use.

    The gap between the two bars is the rescue space, and it is drawn deliberately large:
    a search that only ever looks at passing records has silently discarded it.
    """
    counts = profile.filter_counts
    total = sum(counts.values())
    passing = counts.get("PASS", 0)
    suppressed = total - passing

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=["emitted by the caller"],
            x=[total],
            orientation="h",
            name="all records",
            marker=dict(color=MUTED.fill, line=dict(color=MUTED.line, width=1)),
            hovertemplate="<b>emitted</b><br>%{x:,} records<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            y=["after hard filters"],
            x=[passing],
            orientation="h",
            name="PASS",
            marker=dict(color=GOOD.fill, line=dict(color=GOOD.line, width=1)),
            hovertemplate="<b>PASS</b><br>%{x:,} records<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            y=["after hard filters"],
            x=[suppressed],
            orientation="h",
            name="non-PASS",
            marker=dict(color=DECISION.fill, line=dict(color=DECISION.line, width=1)),
            hovertemplate="<b>non-PASS</b><br>%{x:,} records held back<extra></extra>",
        )
    )
    figure.update_layout(barmode="stack", xaxis_title="records", bargap=0.45)

    return Exhibit(
        slug="filter-funnel",
        title="The filtering funnel",
        caption=(
            f"The caller emitted {total:,} records and flagged {suppressed:,} of them "
            f"({suppressed / total:.1%}). Those flags are heuristics about read evidence, "
            "not verdicts about biology — they are tuned to keep a genome-wide callset "
            "clean, and a rare variant in awkward sequence trips them for the same reasons "
            "an artefact does. Treat the yellow band as a place to look, not a bin."
        ),
        legend=legend_line(
            MUTED,
            GOOD,
            DECISION,
            extra="grey is everything emitted, green is what survived the "
            "filters, yellow is what they held back",
        ),
        figure=sized(figure, 280),
        height=280,
    )


def suppression_reasons(profile: CallsetProfile) -> Exhibit:
    """Which filter fired, counted per flag rather than per combination.

    A record can trip several filters at once, so the raw tally is a list of combinations
    like ``LowQual;MQ40;QD2`` that hides how often any single filter is responsible.
    Splitting the combinations and counting each flag separately answers the question that
    actually matters: which heuristic is doing the suppressing.
    """
    per_flag: dict[str, int] = {}
    for combination, count in profile.filter_counts.items():
        if combination == "PASS":
            continue
        for flag in combination.split(";"):
            per_flag[flag] = per_flag.get(flag, 0) + count

    ordered = sorted(per_flag.items(), key=lambda kv: kv[1])
    labels = [k for k, _ in ordered]
    values = [v for _, v in ordered]

    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=DECISION.fill, line=dict(color=DECISION.line, width=1)),
            customdata=[
                [FILTER_MEANINGS.get(k, "no description in the VCF header")] for k in labels
            ],
            hovertemplate="<b>%{y}</b><br>%{x:,} records<br>%{customdata[0]}<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="records carrying this flag (combinations counted once per flag)",
        yaxis_title="",
        showlegend=False,
        bargap=0.35,
    )

    dominant = max(per_flag.items(), key=lambda kv: kv[1]) if per_flag else None
    notes = []
    if dominant:
        flag, count = dominant
        notes.append(
            f"`{flag}` dominates at {count:,} records — {FILTER_MEANINGS.get(flag, '')} "
            "Ambiguous alignment is a property of the reference genome, not of the patient, "
            "so a real variant in a duplicated region is flagged for the same reason a "
            "mapping artefact is."
        )

    return Exhibit(
        slug="suppression-reasons",
        title="Why records were held back",
        caption=(
            "Each flag counted separately, so a record tripping three filters contributes "
            "to all three bars. Hover any bar for what that filter is actually testing. "
            "The totals here exceed the non-PASS record count for exactly that reason."
        ),
        legend=legend_line(
            DECISION,
            extra="every bar is a suppressed set, sized by how many records "
            "that one heuristic touched",
        ),
        figure=sized(figure, 380),
        notes=notes,
    )


def genotypes(profile: CallsetProfile) -> Exhibit:
    """The mix of genotype calls, which fixes what kind of answer is even possible.

    A compound heterozygote is two heterozygous calls in one gene. The size of the
    heterozygous set is therefore the size of the search space, and the ratio against
    homozygous calls is a sanity check on the sample's ancestry and purity.
    """
    counts = profile.genotype_counts
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    labels = [k for k, _ in ordered]
    values = [v for _, v in ordered]
    hues = [
        GOOD
        if k.replace("|", "/") == "0/1"
        else MACHINE
        if k.replace("|", "/") == "1/1"
        else DECISION
        for k in labels
    ]

    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker=dict(
                color=[h.fill for h in hues], line=dict(color=[h.line for h in hues], width=1)
            ),
            text=[f"{v:,}" for v in values],
            textposition="outside",
            customdata=[[GENOTYPE_MEANINGS.get(k, "unrecognised genotype")] for k in labels],
            hovertemplate="<b>%{x}</b><br>%{customdata[0]}<br>%{y:,} records<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="genotype", yaxis_title="records", showlegend=False, bargap=0.45
    )

    het = counts.get("0/1", 0)
    hom = counts.get("1/1", 0)
    multi = counts.get("1/2", 0)
    notes = []
    if het and hom:
        notes.append(
            f"{het:,} heterozygous calls against {hom:,} homozygous-alternate "
            f"({het / hom:.2f}:1). Only heterozygous calls can form half of a compound "
            "heterozygote, so this is the size of the search space."
        )
    if multi:
        notes.append(
            f"The {multi:,} `1/2` records are already compound-heterozygous in miniature — "
            "two different alternate alleles, one on each copy — and each must reach the "
            "pair finder as two separate calls."
        )

    return Exhibit(
        slug="genotype-composition",
        title="Genotype composition",
        caption=(
            "How the two inherited copies differ at each called site. `0/1` means one "
            "copy carries the reference base and one carries the variant; `1/1` means both "
            "do; `1/2` means each copy carries a different variant. Only the first and "
            "third can contribute an allele to a compound heterozygote."
        ),
        legend=legend_line(
            GOOD,
            MACHINE,
            DECISION,
            extra="green is heterozygous — the searchable set; blue is "
            "homozygous; yellow is the multiallelic case",
        ),
        figure=sized(figure, 380),
        notes=notes,
    )


def phasing(profile: CallsetProfile) -> Exhibit:
    """How much of the callset carries read-backed phasing, and why it is so little.

    Two variants can only be phased from short reads when they sit close enough to be
    spanned by the same fragment. That reach is a few hundred bases, so phasing confirms a
    compound heterozygote it happens to catch and can never be the filter that finds one.
    """
    phased = profile.phased_records or 0
    total = profile.total_records or 0
    unphased = max(total - phased, 0)

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            y=["records"],
            x=[phased],
            orientation="h",
            name="in a phasing group",
            marker=dict(color=GOOD.fill, line=dict(color=GOOD.line, width=1)),
            hovertemplate="<b>phased</b><br>%{x:,} records share a group with a neighbour"
            "<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            y=["records"],
            x=[unphased],
            orientation="h",
            name="unknown phase",
            marker=dict(color=MUTED.fill, line=dict(color=MUTED.line, width=1)),
            hovertemplate="<b>unknown phase</b><br>%{x:,} records<extra></extra>",
        )
    )
    figure.update_layout(barmode="stack", xaxis_title="records", bargap=0.5)

    insert = profile.read_qc.get("insert_size_peak")
    notes = []
    if insert:
        notes.append(
            f"The sequencing fragments peak at {insert:.0f} bp, which is the hard ceiling "
            "on how far apart two variants can be and still be phased from these reads. "
            "Long reads or a sequenced parent are the only ways past it."
        )

    return Exhibit(
        slug="phasing-coverage",
        title="How much of the callset is phased",
        caption=(
            f"{phased:,} of {total:,} records ({phased / total:.1%}) sit in a group where "
            "the caller could tell which of the two chromosome copies they belong to, "
            "because a single sequenced fragment covered them together. Everything else is "
            "of unknown phase — which is a state of ignorance, never a rejection."
        ),
        legend=legend_line(
            GOOD, MUTED, extra="green is resolved onto a copy, grey is unknown phase"
        ),
        figure=sized(figure, 260),
        height=260,
        notes=notes,
    )
