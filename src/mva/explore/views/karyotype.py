"""Chromosome-level views — the shape of the genome, one bar per chromosome.

This is where a whole-chromosome abnormality becomes visible. Dedicated copy-number tools
(CNVkit, GATK gCNV, mosdepth) draw the same family of plots from alignment depth; these
draw them from the variant callset alone, which costs one pass over a VCF instead of a day
of alignment and is enough to answer the question this project opens with.

The headline is :func:`allele_balance` — for a proband with suspected Mosaic Variegated
Aneuploidy, it is the direct test, and a flat profile is a real negative result rather
than a failed plot.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..figure import Exhibit, sized
from ..profile import CallsetProfile
from ..theme import BAD, DECISION, GOOD, MACHINE, MUTED, SUBTLE_INK, Hue, legend_line

#: A diploid chromosome puts a heterozygous site at half alternate reads.
DIPLOID_VAF = 0.5
#: Width around that expectation treated as unremarkable.
BAND = 0.02


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """Every chromosome-level exhibit the profile can support."""
    out = []
    if profile.balance:
        out.append(allele_balance(profile))
        out.append(depth(profile))
    if profile.contigs:
        out.append(density(profile))
    return out


def allele_balance(profile: CallsetProfile) -> Exhibit:
    """Mean heterozygous allele balance per chromosome, over the spread of those sites.

    Two rows, one story. The top row asks *where is the centre* — a chromosome present in
    three copies in some cells pulls its mean away from 0.5. The bottom row asks *how
    tight is the spread* — mosaicism widens the distribution before it moves the mean far,
    so a chromosome can look almost normal above and clearly abnormal below.
    """
    rows = sorted(profile.balance, key=_order)
    names = [f"chr{r.chrom.removeprefix('chr')}" for r in rows]
    vafs = [r.mean_vaf for r in rows]
    tight = [r.pct_in_band for r in rows]

    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.09,
        subplot_titles=(
            "Mean alternate-allele fraction at heterozygous sites",
            "Share of those sites inside 0.40 – 0.60",
        ),
    )

    # Bars grow from the diploid line rather than from zero. Anchored at zero they would
    # be twenty-four near-identical full-height bars with the interesting variation
    # compressed into their last two percent — and they would cover the expectation band
    # they are supposed to be compared against.
    figure.add_trace(
        go.Bar(
            x=names,
            y=[r.deviation for r in rows],
            base=DIPLOID_VAF,
            name="mean allele balance",
            marker=dict(
                color=[_fill(r) for r in rows],
                line=dict(color=[_outline(r) for r in rows], width=1),
            ),
            customdata=[(r.n_het, r.deviation, r.mean_vaf) for r in rows],
            hovertemplate="<b>%{x}</b><br>mean balance %{customdata[2]:.4f}"
            "<br>deviation from diploid %{customdata[1]:+.4f}"
            "<br>%{customdata[0]:,} het sites<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Reference lines go on after the bars, not before: Plotly resolves `row`/`col` on a
    # shape against the axes the traces created, and silently drops a shape added to a
    # subplot that is still empty. Boundary lines rather than a shaded band, because the
    # bars are anchored at 0.5 and would hide a fill drawn behind them.
    figure.add_hline(y=DIPLOID_VAF, row=1, col=1, line=dict(color=GOOD.line, width=1.5))
    for edge in (DIPLOID_VAF - BAND, DIPLOID_VAF + BAND):
        figure.add_hline(y=edge, row=1, col=1, line=dict(color=GOOD.line, width=1, dash="dot"))
    figure.add_annotation(
        row=1,
        col=1,
        x=1,
        xref="x domain",
        y=DIPLOID_VAF + BAND,
        text=f"diploid band {DIPLOID_VAF - BAND:.2f}–{DIPLOID_VAF + BAND:.2f}",
        showarrow=False,
        xanchor="right",
        yanchor="bottom",
        font=dict(size=11, color=SUBTLE_INK),
    )

    figure.add_trace(
        go.Scatter(
            x=names,
            y=tight,
            name="inside the diploid band",
            mode="lines+markers",
            line=dict(color=MACHINE.line, width=2),
            marker=dict(size=8, color=MACHINE.fill, line=dict(color=MACHINE.line, width=1.5)),
            hovertemplate="<b>%{x}</b><br>%{y:.1f}% of het sites inside 0.40–0.60<extra></extra>",
        ),
        row=2,
        col=1,
    )

    autosomes = [r.pct_in_band for r in rows if r.chrom.removeprefix("chr").isdigit()]
    if autosomes:
        median = sorted(autosomes)[len(autosomes) // 2]
        figure.add_hline(
            y=median,
            row=2,
            col=1,
            line=dict(color=MUTED.line, width=1, dash="dash"),
            annotation_text=f"autosomal median {median:.1f}%",
            annotation_font=dict(size=11, color=SUBTLE_INK),
        )

    lo, hi = min(vafs), max(vafs)
    figure.update_yaxes(
        range=[min(lo, 0.45) - 0.015, max(hi, 0.52) + 0.015],
        title_text="alt reads / all reads",
        row=1,
        col=1,
    )
    figure.update_yaxes(range=[0, 100], title_text="% of sites", row=2, col=1)
    figure.update_xaxes(title_text="chromosome", row=2, col=1)
    figure.update_layout(showlegend=False, bargap=0.35)

    return Exhibit(
        slug="allele-balance-by-chromosome",
        title="Allele balance by chromosome — the aneuploidy fingerprint",
        caption=(
            "Every heterozygous position has two chromosome copies, one carrying the "
            "reference base and one carrying the alternate, so about half the reads "
            "covering it should show the alternate. A chromosome present in three copies "
            "in some fraction of cells breaks that symmetry, and the break shows up here "
            "before any copy-number tool is run. Read the top row for a shifted centre and "
            "the bottom row for a widened spread; mosaicism reaches the bottom row first."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            BAD,
            MUTED,
            extra=f"bars grow from the diploid line, not from zero; the "
            f"dotted lines bound the expectation "
            f"{DIPLOID_VAF - BAND:.2f}–{DIPLOID_VAF + BAND:.2f}; "
            "grey marks the sex chromosomes, which are not graded",
        ),
        figure=sized(figure, 620),
        height=620,
        notes=[
            (
                "The sex chromosomes are drawn in grey and deliberately not graded. A male "
                "sample carries one X and one Y, so a heterozygous call on either is either "
                "in the small region the two chromosomes share or is an error — in both "
                "cases the allele balance says nothing about aneuploidy."
            )
        ],
    )


def depth(profile: CallsetProfile) -> Exhibit:
    """Mean read depth at heterozygous sites, per chromosome.

    Depth is the sanity check underneath the allele-balance plot. A chromosome whose
    balance looks odd *and* whose depth is unremarkable is a candidate; one where both
    move together is usually a coverage artefact — a capture bias, a mapping problem, or a
    genuinely different copy number.
    """
    rows = sorted(profile.balance, key=_order)
    names = [f"chr{r.chrom.removeprefix('chr')}" for r in rows]
    depths = [r.mean_depth for r in rows]
    autosomal = [r.mean_depth for r in rows if r.chrom.removeprefix("chr").isdigit()]
    reference = sum(autosomal) / len(autosomal) if autosomal else 0.0

    figure = go.Figure(
        go.Bar(
            x=names,
            y=depths,
            marker=dict(color=MACHINE.fill, line=dict(color=MACHINE.line, width=1)),
            hovertemplate="<b>%{x}</b><br>%{y:.1f}× mean depth<extra></extra>",
        )
    )
    if reference:
        figure.add_hline(
            y=reference,
            line=dict(color=GOOD.line, width=1.5, dash="dot"),
            annotation_text=f"autosomal mean {reference:.1f}×",
            annotation_font=dict(size=11, color=SUBTLE_INK),
        )
        figure.add_hline(
            y=reference / 2,
            line=dict(color=DECISION.line, width=1, dash="dash"),
            annotation_text="half — one copy",
            annotation_font=dict(size=11, color=SUBTLE_INK),
        )
    figure.update_layout(
        xaxis_title="chromosome", yaxis_title="mean read depth (×)", showlegend=False, bargap=0.35
    )

    return Exhibit(
        slug="depth-by-chromosome",
        title="Read depth by chromosome",
        caption=(
            "How many reads covered a typical heterozygous site on each chromosome. A "
            "chromosome present in one copy instead of two collects roughly half the "
            "reads, so this is the coverage-side view of the same question the allele "
            "balance asks from the genotype side. Agreement between the two is what "
            "turns a suspicion into a finding."
        ),
        legend=legend_line(
            MACHINE,
            GOOD,
            DECISION,
            extra="bars are per-chromosome mean depth; the dotted line is "
            "the autosomal mean and the dashed line is half of it",
        ),
        figure=sized(figure, 420),
    )


def density(profile: CallsetProfile) -> Exhibit:
    """Variants called per megabase, which is the length-normalised comparison.

    Raw counts track chromosome length and say nothing. Per-megabase density is flat
    across a healthy genome, so a chromosome that stands out is reporting either real
    excess heterozygosity or a region the caller struggled with.
    """
    contigs = profile.primary_contigs
    names = [f"chr{c.name.removeprefix('chr')}" for c in contigs]
    values = [c.density_per_mb for c in contigs]

    figure = go.Figure(
        go.Bar(
            x=names,
            y=values,
            marker=dict(color=MACHINE.fill, line=dict(color=MACHINE.line, width=1)),
            customdata=[(c.records, c.length / 1e6) for c in contigs],
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} variants per Mb"
            "<br>%{customdata[0]:,} variants over %{customdata[1]:,.1f} Mb"
            "<extra></extra>",
        )
    )
    autosomal = [c.density_per_mb for c in contigs if c.name.removeprefix("chr").isdigit()]
    if autosomal:
        mean = sum(autosomal) / len(autosomal)
        figure.add_hline(
            y=mean,
            line=dict(color=GOOD.line, width=1.5, dash="dot"),
            annotation_text=f"autosomal mean {mean:,.0f}/Mb",
            annotation_font=dict(size=11, color=SUBTLE_INK),
        )
    figure.update_layout(
        xaxis_title="chromosome", yaxis_title="variants per megabase", showlegend=False, bargap=0.35
    )

    scaffolds = profile.scaffold_records
    notes = []
    if scaffolds:
        others = len(profile.contigs) - len(contigs)
        notes.append(
            f"{scaffolds:,} further variants sit on {others:,} unplaced scaffolds, "
            "alternate haplotypes and decoy sequences, which are excluded here because "
            "they are assembly bookkeeping rather than chromosomes."
        )

    return Exhibit(
        slug="variant-density-by-chromosome",
        title="Variant density by chromosome",
        caption=(
            "Variants per megabase, so a long chromosome and a short one can be compared "
            "directly. A flat profile is the expected result and is worth confirming: it "
            "means no chromosome is contributing a suspicious excess of calls before any "
            "filtering is applied."
        ),
        legend=legend_line(MACHINE, GOOD, extra="the dotted line is the autosomal mean density"),
        figure=sized(figure, 400),
        notes=notes,
    )


def _order(row) -> tuple[int, str]:
    """Assembly order: 1–22, then X, Y, M."""
    name = row.chrom.removeprefix("chr")
    if name.isdigit():
        return (int(name), name)
    return ({"X": 23, "Y": 24, "M": 25, "MT": 25}.get(name, 99), name)


def _grade(row) -> Hue:
    """The hue for one chromosome's deviation from the diploid expectation.

    Sex chromosomes are drawn in the neutral hue whatever their balance. A male sample has
    one X and one Y, so both sit far off 0.5 by construction; grading them against an
    autosomal expectation would paint the most predictable fact in the dataset as its most
    alarming finding.
    """
    if not row.chrom.removeprefix("chr").isdigit():
        return MUTED
    deviation = abs(row.mean_vaf - DIPLOID_VAF)
    if deviation <= BAND:
        return GOOD
    if deviation <= BAND * 2:
        return DECISION
    return BAD


def _fill(row) -> str:
    return _grade(row).fill


def _outline(row) -> str:
    return _grade(row).line
