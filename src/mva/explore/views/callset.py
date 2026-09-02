"""What the callset is made of — the ``bcftools stats`` views, made interactive.

``plot-vcfstats`` has drawn these four views for a decade and they remain the fastest way
to tell a real callset from a noisy one: the mix of variant classes, the chemistry of the
substitutions, the length distribution of the indels, and the depth the calls rest on.

The one addition here is the strand-collapsed six-class spectrum used in mutational
signature work (COSMIC SBS), which folds each substitution together with its reverse
complement. Because a variant can be recorded from either DNA strand, ``G>A`` and ``C>T``
are the same chemical event; collapsing them is what makes the transition excess legible
instead of spread across twelve bars.
"""

import plotly.graph_objects as go

from ...io.readers import as_float, as_int
from ..checks import ts_tv
from ..figure import Exhibit, sized
from ..profile import CallsetProfile
from ..theme import BAD, GOOD, MACHINE, MUTED, RAW, SUBTLE_INK, legend_line

#: Pyrimidine-centric collapse: each substitution and its reverse complement are one event.
COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}
#: The two substitutions that swap a purine for a purine or a pyrimidine for a pyrimidine.
TRANSITIONS = {"C>T", "T>C"}


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """Every composition exhibit the ``bcftools stats`` sections can support."""
    out = []
    if profile.summary:
        out.append(composition(profile))
    if profile.stats.get("ST"):
        out.append(substitution_spectrum(profile))
    if profile.stats.get("IDD"):
        out.append(indel_lengths(profile))
    if profile.stats.get("DP"):
        out.append(depth_distribution(profile))
    return out


def composition(profile: CallsetProfile) -> Exhibit:
    """The variant classes, and how much of the callset each accounts for.

    The multiallelic count is drawn separately because it is not a class of variant but a
    representation problem: those records carry two alternate alleles on one row, and a
    scorer that compares allele strings exactly cannot be shown either of them until the
    record is split.
    """
    summary = profile.summary
    snps = summary.get("SNPs", 0)
    indels = summary.get("indels", 0)
    others = summary.get("others", 0) + summary.get("MNPs", 0)
    multiallelic = summary.get("multiallelic sites", 0)

    figure = go.Figure()
    for label, value, hue in (
        ("substitutions (SNP)", snps, MACHINE),
        ("insertions & deletions (indel)", indels, RAW),
        ("other", others, MUTED),
    ):
        if not value:
            continue
        figure.add_trace(
            go.Bar(
                y=["callset"],
                x=[value],
                name=label,
                orientation="h",
                marker=dict(color=hue.fill, line=dict(color=hue.line, width=1)),
                hovertemplate=f"<b>{label}</b><br>%{{x:,}} records<extra></extra>",
            )
        )
    if multiallelic:
        figure.add_trace(
            go.Bar(
                y=["needing normalization"],
                x=[multiallelic],
                name="multiallelic sites",
                orientation="h",
                marker=dict(color=BAD.fill, line=dict(color=BAD.line, width=1)),
                hovertemplate="<b>multiallelic</b><br>%{x:,} records carry two alternate "
                "alleles on one row<extra></extra>",
            )
        )
    figure.update_layout(
        barmode="stack", xaxis_title="records", yaxis_title="", height=260, bargap=0.45
    )

    total = profile.total_records or (snps + indels + others)
    return Exhibit(
        slug="callset-composition",
        title="What the callset contains",
        caption=(
            f"{total:,} records in all. The top bar splits them by what kind of change "
            "they describe: a substitution swaps one base for another, an indel inserts or "
            "removes bases and shifts everything downstream. The bottom bar is not a "
            "class but a defect — records holding two alternate alleles at once, which "
            "must be split into one allele per record before any exact comparison works."
        ),
        legend=legend_line(
            MACHINE,
            RAW,
            BAD,
            extra="blue is substitutions, purple is indels, red is the multiallelic backlog",
        ),
        figure=figure,
        height=260,
    )


def substitution_spectrum(profile: CallsetProfile) -> Exhibit:
    """The six strand-collapsed substitution classes, with transitions marked.

    Real human variation is dominated by ``C>T``: methylated cytosine deaminates to
    thymine spontaneously, which is the single most common way a genome changes. Sequencing
    error carries no such preference, so a spectrum that flattens toward six equal bars is
    a spectrum full of artefacts.
    """
    raw = {cells[0]: as_int(cells[1]) or 0 for cells in profile.stats["ST"] if len(cells) > 1}
    collapsed: dict[str, int] = {}
    for change, count in raw.items():
        ref, _, alt = change.partition(">")
        if ref in ("A", "G"):
            ref, alt = COMPLEMENT.get(ref, ref), COMPLEMENT.get(alt, alt)
        collapsed[f"{ref}>{alt}"] = collapsed.get(f"{ref}>{alt}", 0) + count

    order = ["C>A", "C>G", "C>T", "T>A", "T>C", "T>G"]
    labels = [k for k in order if k in collapsed]
    values = [collapsed[k] for k in labels]
    total = sum(values) or 1

    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker=dict(
                color=[GOOD.fill if k in TRANSITIONS else MACHINE.fill for k in labels],
                line=dict(
                    color=[GOOD.line if k in TRANSITIONS else MACHINE.line for k in labels], width=1
                ),
            ),
            text=[f"{v / total:.1%}" for v in values],
            textposition="outside",
            customdata=[["transition" if k in TRANSITIONS else "transversion"] for k in labels],
            hovertemplate="<b>%{x}</b> (%{customdata[0]})<br>%{y:,} substitutions<extra></extra>",
        )
    )
    figure.update_layout(
        xaxis_title="substitution, collapsed onto the pyrimidine strand",
        yaxis_title="substitutions",
        showlegend=False,
        bargap=0.4,
    )

    ratio = ts_tv(profile)
    notes = []
    if ratio is not None:
        notes.append(
            f"Transition/transversion ratio {ratio:.2f}. Transitions outnumber "
            "transversions about two to one in real human variation; random error would "
            "push this toward 0.5."
        )

    return Exhibit(
        slug="substitution-spectrum",
        title="Substitution spectrum",
        caption=(
            "Which base changed into which, with each substitution folded together with "
            "its mirror image on the opposite DNA strand — a variant recorded as G>A on "
            "one strand is the same event as C>T on the other, so counting them separately "
            "splits one signal in half. The two green bars are transitions."
        ),
        legend=legend_line(
            GOOD,
            MACHINE,
            extra="green marks transitions (purine↔purine, pyrimidine↔"
            "pyrimidine), blue marks transversions",
        ),
        figure=sized(figure, 400),
        notes=notes,
    )


def indel_lengths(profile: CallsetProfile) -> Exhibit:
    """Insertion and deletion lengths, negative for deletions, on a log count axis.

    Short indels dominate by orders of magnitude, so the count axis has to be logarithmic
    or everything past a few bases disappears. The long tail matters anyway: a deletion of
    tens of bases inside a gene is exactly the kind of second hit that a substitution-first
    search misses.
    """
    points = []
    for cells in profile.stats["IDD"]:
        length, count = as_int(cells[0]), as_int(cells[1])
        if length is not None and count:
            points.append((length, count))
    points.sort()

    deletions = [(length, c) for length, c in points if length < 0]
    insertions = [(length, c) for length, c in points if length > 0]

    figure = go.Figure()
    for label, data, hue in (("deletions", deletions, BAD), ("insertions", insertions, MACHINE)):
        if not data:
            continue
        figure.add_trace(
            go.Bar(
                x=[length for length, _ in data],
                y=[c for _, c in data],
                name=label,
                marker=dict(color=hue.fill, line=dict(color=hue.line, width=0.5)),
                hovertemplate="<b>%{x} bp</b><br>%{y:,} records<extra></extra>",
            )
        )
    figure.update_yaxes(type="log", title_text="records (log scale)")
    figure.update_xaxes(title_text="length change in bases — negative deletes, positive inserts")
    figure.add_vline(x=0, line=dict(color=MUTED.line, width=1))
    figure.update_layout(bargap=0.1)

    total = sum(c for _, c in points)
    del_count = sum(c for _, c in deletions)
    ins_count = sum(c for _, c in insertions)
    notes = [
        f"{del_count:,} deletions against {ins_count:,} insertions ({del_count / ins_count:.2f}:1)."
        if ins_count
        else "",
        _overflow_note(points),
        (
            "Lengths not divisible by three shift the reading frame of a coding sequence and "
            "usually destroy the protein; lengths divisible by three remove or add whole amino "
            "acids and are often survivable. That distinction is what makes indel length a "
            "consequence prediction and not merely a size."
        ),
    ]

    return Exhibit(
        slug="indel-length-spectrum",
        title="Indel length spectrum",
        caption=(
            f"{total:,} insertions and deletions by how many bases they add or remove. "
            "The steep drop away from ±1 base is expected — short indels arise constantly "
            "in repetitive sequence — and the tail out to tens of bases is where "
            "gene-disrupting events live."
        ),
        legend=legend_line(
            BAD,
            MACHINE,
            extra="red bars left of zero are deletions, blue bars right of "
            "zero are insertions; the count axis is logarithmic",
        ),
        figure=sized(figure, 420),
        notes=[n for n in notes if n],
    )


def depth_distribution(profile: CallsetProfile) -> Exhibit:
    """How many reads sit under a typical call, and where the usable floor is.

    Depth is the currency of confidence. Below roughly ten reads a heterozygous site can
    lose one of its two alleles to chance alone, which is the failure mode that would hide
    exactly the second variant this project is hunting.
    """
    bins, shares = [], []
    for cells in profile.stats["DP"]:
        depth, share = as_int(cells[0]), as_float(cells[-1])
        if depth is not None and share is not None:
            bins.append(depth)
            shares.append(share)

    peak = bins[shares.index(max(shares))] if shares else None
    figure = go.Figure(
        go.Bar(
            x=bins,
            y=shares,
            marker=dict(
                color=[BAD.fill if b < 10 else MACHINE.fill for b in bins], line=dict(width=0)
            ),
            hovertemplate="<b>%{x}× depth</b><br>%{y:.2f}% of sites<extra></extra>",
        )
    )
    figure.add_vrect(
        x0=0,
        x1=10,
        fillcolor=BAD.fill,
        opacity=0.18,
        line_width=0,
        layer="below",
        annotation_text="under 10× — a copy can be missed",
        annotation_position="top left",
        annotation_font=dict(size=11, color=SUBTLE_INK),
    )
    if peak is not None:
        figure.add_vline(
            x=peak,
            line=dict(color=GOOD.line, width=1.5, dash="dot"),
            annotation_text=f"peak {peak}×",
            annotation_font=dict(size=11, color=SUBTLE_INK),
        )
    figure.update_layout(
        xaxis_title="read depth at the site (×)",
        yaxis_title="% of sites",
        showlegend=False,
        bargap=0.05,
    )

    low = sum(s for b, s in zip(bins, shares, strict=True) if b < 10)
    return Exhibit(
        slug="depth-distribution",
        title="Depth distribution across called sites",
        caption=(
            "The share of called sites at each read depth. The bulk should sit in a single "
            f"mound around the sequencing target; {low:.1f}% of sites here fall below ten "
            "reads, where a heterozygous site can lose one of its two alleles to sampling "
            "chance and be called homozygous."
        ),
        legend=legend_line(
            MACHINE,
            BAD,
            GOOD,
            extra="the shaded strip below 10× is the unreliable region; the "
            "dotted line marks the modal depth",
        ),
        figure=sized(figure, 400),
    )


def _overflow_note(points: list[tuple[int, int]]) -> str:
    """Warn when the outermost bins are catch-alls rather than exact lengths.

    ``bcftools stats`` reports indel lengths up to a limit and folds everything longer
    into the first and last bin. Those bins then stand up as spikes at the edges of the
    plot, and a reader who does not know this concludes there is a real peak at exactly
    that length. Saying so is cheaper than a footnote nobody reads.
    """
    if len(points) < 6:
        return ""
    lengths = [length for length, _ in points]
    counts = dict(points)
    edges = [lengths[0], lengths[-1]]
    for edge in edges:
        neighbour = counts.get(edge + (1 if edge < 0 else -1))
        # A genuine tail decays; a catch-all bin towers over the bin beside it.
        if neighbour and counts[edge] > neighbour * 3:
            return (
                f"The bars at {lengths[0]} and {lengths[-1]} bases are not a real peak. "
                "`bcftools stats` reports lengths only out to that limit and folds "
                "everything longer into the outermost bin, so those two bars are "
                "catch-alls holding the entire long tail."
            )
    return ""
