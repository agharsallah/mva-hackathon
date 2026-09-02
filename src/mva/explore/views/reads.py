"""Raw sequencing views — the FastQC / fastp / MultiQC questions, answered in one page.

Before any variant exists there are only reads: short fragments of the patient's DNA, each
with a per-base confidence score. Four things decide whether they can support a diagnosis —
how many bases were sequenced, how accurate they are, how many are redundant copies of one
another, and how long the original fragments were. Everything downstream inherits those
four numbers, so they are checked first and checked visually.

The gauges use the FastQC convention of a green pass band, a yellow band worth a look, and
a red band that invalidates the run, with the thresholds stated in
:mod:`mva.explore.checks` rather than buried in the drawing code.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..checks import run_checks
from ..figure import Exhibit, sized
from ..profile import CallsetProfile
from ..theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, SUBTLE_INK, legend_line

#: Which checks earn a gauge, and how to draw each one's axis.
#:
#: The axis range is cropped to where the metric can plausibly land, not to its
#: mathematical range. A GC gauge drawn 0–100% is nine-tenths "fail" colour by
#: construction, which makes a perfectly normal 41% look like a near miss.
GAUGE_SPECS = [
    ("Q30 rate", 60, 100, 100, "%", "bases with a 1-in-1000 error chance"),
    ("GC content", 25, 60, 100, "%", "human expectation is about 41%"),
    ("Duplication rate", 0, 40, 100, "%", "redundant copies of one fragment"),
    ("Insert size peak", 0, 800, 1, " bp", "original fragment length"),
]

#: How thin the value bar is drawn, as a fraction of the ring. Thin on purpose: a bar
#: filling the ring hides the very bands it is supposed to be read against.
BAR_THICKNESS = 0.3


def exhibits(profile: CallsetProfile) -> list[Exhibit]:
    """Every sequencing exhibit the profile can support."""
    out = []
    if profile.reads:
        out.append(lane_yield(profile))
    if profile.read_qc:
        out.append(quality_gauges(profile))
        out.append(filtering_effect(profile))
    return out


def lane_yield(profile: CallsetProfile) -> Exhibit:
    """Sequenced bases per flow-cell lane, split by which end of the pair they came from.

    Lanes are independent physical runs of the same library. They should look alike; one
    that does not is a lane to exclude rather than a genome to distrust, which is why the
    files are kept separate this far into the pipeline instead of being concatenated.
    """
    lanes = sorted({f.lane for f in profile.reads})
    figure = go.Figure()
    for mate, hue in (("R1", MACHINE), ("R2", RAW)):
        values = [
            sum(f.gigabases for f in profile.reads if f.lane == lane and f.mate == mate)
            for lane in lanes
        ]
        figure.add_trace(
            go.Bar(
                x=lanes,
                y=values,
                name=f"{mate} — {'forward' if mate == 'R1' else 'reverse'} read",
                marker=dict(color=hue.fill, line=dict(color=hue.line, width=1)),
                hovertemplate="<b>%{x} " + mate + "</b><br>%{y:.1f} Gb<extra></extra>",
            )
        )
    figure.update_layout(
        barmode="stack",
        xaxis_title="flow-cell lane",
        yaxis_title="billions of bases sequenced (Gb)",
        bargap=0.4,
    )

    total = profile.total_gigabases or 0.0
    coverage = next((c for c in run_checks(profile) if c.name == "Estimated raw coverage"), None)
    notes = []
    if coverage and coverage.value:
        notes.append(
            f"{total:,.1f} Gb over a 3.1 Gb genome is about {coverage.value:.0f}× raw "
            "coverage — every position read roughly that many times independently. "
            "Duplicate removal and imperfect alignment take the usable figure below it."
        )
    spread = _lane_spread(profile, lanes)
    if spread is not None:
        notes.append(
            f"The lanes agree to within {spread:.1%} of each other, so no single lane is "
            "carrying or dragging the run."
        )

    return Exhibit(
        slug="lane-yield",
        title="Sequencing yield by lane",
        caption=(
            "Each fragment of DNA is read from both ends, giving a forward read (R1) and a "
            "reverse read (R2) that belong together. Bars are stacked per lane so the four "
            "physical runs can be compared at a glance — they are supposed to look "
            "identical, and a short lane is a fixable problem rather than a bad sample."
        ),
        legend=legend_line(
            MACHINE, RAW, extra="blue is the forward read of each pair, purple is the reverse read"
        ),
        figure=sized(figure, 400),
        notes=notes,
    )


def quality_gauges(profile: CallsetProfile) -> Exhibit:
    """The four library-quality numbers, each against its acceptable band.

    A number without a band is a number nobody can act on. Each gauge carries the
    community expectation for a germline short-read whole genome, so a reader with no
    sequencing background can tell acceptable from alarming without looking anything up.
    """
    graded = {c.name: c for c in run_checks(profile)}
    specs = [s for s in GAUGE_SPECS if s[0] in graded]
    if not specs:
        return Exhibit(slug="read-quality", title="Library quality", caption="", legend="")

    figure = make_subplots(
        rows=1,
        cols=len(specs),
        specs=[[{"type": "indicator"}] * len(specs)],
        horizontal_spacing=0.06,
    )
    for column, (name, low, high, scale, suffix, blurb) in enumerate(specs, start=1):
        check = graded[name]
        value = (check.value or 0) * scale
        figure.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=round(value, 1),
                number=dict(suffix=suffix, font=dict(size=26)),
                title=dict(
                    text=f"<b>{name}</b><br><span style='font-size:11px;color:{SUBTLE_INK}'>"
                    f"{blurb}</span>",
                    font=dict(size=13),
                ),
                gauge=dict(
                    axis=dict(range=[low, high], tickfont=dict(size=10)),
                    bar=dict(color=check.verdict.hue.line, thickness=BAR_THICKNESS),
                    bgcolor=MUTED.fill,
                    borderwidth=0,
                    steps=_steps(name, low, high, scale),
                ),
            ),
            row=1,
            col=column,
        )
    figure.update_layout(margin=dict(l=20, r=20, t=70, b=20))

    failing = [
        c.name for c in graded.values() if c.is_actionable and c.name in {s[0] for s in specs}
    ]
    notes = []
    if failing:
        notes.append("Outside the expected band: " + ", ".join(failing) + ".")
    if profile.read_qc_note:
        notes.append(
            f"Measured on a sample, not the full run — {profile.read_qc_note}. "
            "Adequate for quality, not for anything that depends on seeing every read."
        )

    return Exhibit(
        slug="read-quality",
        title="Library quality against expected bands",
        caption=(
            "Four numbers that decide whether the reads can support a diagnosis. Q30 is "
            "the share of bases the instrument is at least 99.9% sure of. GC content "
            "should match the human genome's 41% — a shifted value means something other "
            "than the patient was sequenced. Duplication counts redundant copies of one "
            "original fragment, which inflate apparent depth without adding evidence. "
            "Insert size is how long the original fragments were, which sets how far "
            "read-backed phasing can reach."
        ),
        legend=legend_line(
            GOOD,
            DECISION,
            BAD,
            extra="the outer arc is the pass, watch and fail bands; the inner "
            "bar is the measured value, in the colour of its own "
            "verdict. Each axis is cropped to where the metric can "
            "plausibly land, so read the bands, not the fill level",
        ),
        figure=sized(figure, 300),
        height=300,
        notes=notes,
    )


def filtering_effect(profile: CallsetProfile) -> Exhibit:
    """What adapter trimming and quality filtering removed, and what it bought.

    Read filtering is the one preprocessing step that is almost always worth running and
    almost never inspected. Showing the cost (reads discarded) beside the benefit (quality
    gained) makes it an inspectable decision instead of a default.
    """
    qc = profile.read_qc
    before = qc.get("before_filtering.total_reads", 0)
    after = qc.get("after_filtering.total_reads", 0)
    adapters = qc.get("adapter_trimmed_reads", 0)
    q30_before = qc.get("before_filtering.q30_rate")
    q30_after = qc.get("after_filtering.q30_rate")

    figure = make_subplots(
        rows=1,
        cols=2,
        horizontal_spacing=0.18,
        subplot_titles=("Reads kept and discarded", "Q30 rate before and after"),
    )
    figure.add_trace(
        go.Bar(
            x=["kept", "discarded", "adapter-trimmed"],
            y=[after, max(before - after, 0), adapters],
            marker=dict(
                color=[GOOD.fill, BAD.fill, DECISION.fill],
                line=dict(color=[GOOD.line, BAD.line, DECISION.line], width=1),
            ),
            text=[f"{after:,.0f}", f"{before - after:,.0f}", f"{adapters:,.0f}"],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} reads<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if q30_before is not None and q30_after is not None:
        figure.add_trace(
            go.Bar(
                x=["before", "after"],
                y=[q30_before * 100, q30_after * 100],
                marker=dict(
                    color=[MUTED.fill, GOOD.fill], line=dict(color=[MUTED.line, GOOD.line], width=1)
                ),
                text=[f"{q30_before:.2%}", f"{q30_after:.2%}"],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{y:.2f}% of bases at Q30<extra></extra>",
            ),
            row=1,
            col=2,
        )
        figure.update_yaxes(range=[80, 100], title_text="% of bases at Q30", row=1, col=2)
    figure.update_yaxes(title_text="reads", row=1, col=1)
    figure.update_layout(showlegend=False, bargap=0.45)

    notes = []
    if before and after:
        notes.append(
            f"{(before - after) / before:.2%} of reads were discarded to gain "
            f"{(q30_after - q30_before) * 100:+.2f} percentage points of Q30."
            if q30_before is not None and q30_after is not None
            else ""
        )
    if before and adapters:
        notes.append(
            f"{adapters / before:.2%} of reads ran past the end of their fragment and into "
            "the adapter sequence used to attach it to the flow cell. Trimming that off is "
            "mandatory: adapter bases are laboratory reagent, not patient DNA, and they "
            "align nowhere."
        )

    return Exhibit(
        slug="read-filtering",
        title="What read filtering removed",
        caption=(
            "Quality filtering trades reads for accuracy. The left chart is the cost, the "
            "right chart is what it bought. A large discard for a tiny quality gain means "
            "the filter is too aggressive; a tiny discard for a large gain means it caught "
            "a real problem."
        ),
        legend=legend_line(
            GOOD,
            BAD,
            DECISION,
            extra="green is kept or improved, red is discarded, yellow is "
            "trimmed rather than dropped",
        ),
        figure=sized(figure, 380),
        notes=[n for n in notes if n],
    )


def _steps(name: str, low: float, high: float, scale: float) -> list[dict]:
    """The coloured pass / watch / fail arcs behind a gauge needle."""
    bands = {
        "Q30 rate": [(low, 80, BAD), (80, 90, DECISION), (90, high, GOOD)],
        "GC content": [
            (low, 35, BAD),
            (35, 38, DECISION),
            (38, 44, GOOD),
            (44, 48, DECISION),
            (48, high, BAD),
        ],
        "Duplication rate": [(low, 15, GOOD), (15, 25, DECISION), (25, high, BAD)],
        "Insert size peak": [
            (low, 150, BAD),
            (150, 200, DECISION),
            (200, 600, GOOD),
            (600, high, DECISION),
        ],
    }
    return [dict(range=[a, b], color=hue.fill) for a, b, hue in bands.get(name, [])]


def _lane_spread(profile: CallsetProfile, lanes: list[str]) -> float | None:
    """Relative spread of per-lane yield — how far the worst lane sits from the mean."""
    totals = [sum(f.gigabases for f in profile.reads if f.lane == lane) for lane in lanes]
    totals = [t for t in totals if t]
    if len(totals) < 2:
        return None
    mean = sum(totals) / len(totals)
    return max(abs(t - mean) for t in totals) / mean
