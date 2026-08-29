"""The evidence ledger: every observation, which way it cut, and where it came from.

The board says what is believed. This says why, one row at a time, with the receipt
attached — which is the part a reviewer actually audits. The weighing chart beside it shows
the arithmetic as a shape, so a claim resting on one strong observation is visibly
different from one resting on five weak ones that happen to agree.
"""

import plotly.graph_objects as go

from ...render.figure import Exhibit, sized
from ...render.theme import BAD, GOOD, MUTED, SUBTLE_INK, legend_line
from ..record import Record


def evidence_ledger(record: Record) -> Exhibit:
    """Every observation on the record, grouped by the claim it bears on."""
    rows = []
    for dossier in record.dossiers:
        if not dossier.evidence:
            continue
        rows.append(
            f'<tr><td colspan="6" style="background:#fafafa;font-weight:600">'
            f"<code>{dossier.hypothesis.hypothesis_id}</code> — "
            f"{dossier.hypothesis.statement}</td></tr>")
        for row in dossier.evidence:
            hue = row.direction.hue
            lineage = (f'<br><small style="color:{SUBTLE_INK}">lineage '
                       f"<code>{row.lineage_ref}</code></small>"
                       if row.lineage_ref else "")
            rows.append(
                f'<tr><td class="numeric"><code>{row.evidence_id}</code></td>'
                f'<td><span class="badge" style="background:{hue.fill};'
                f'border-color:{hue.line}">{row.direction.value}</span></td>'
                f'<td class="numeric">{row.strength:.2f}</td>'
                f"<td>{row.kind}</td><td>{row.claim}</td>"
                f"<td><code>{row.source_ref}</code>{lineage}</td></tr>")

    if not rows:
        return Exhibit(
            slug="evidence-ledger",
            title="The evidence ledger",
            caption=(
                "Nothing has been observed yet. Every row that appears here will name its "
                "own receipt — a methodology entry, a warehouse table, a publication, a "
                "database record, or an oracle reply — because an observation nobody can "
                "check is not evidence."
            ),
            legend=legend_line(MUTED, extra="an empty ledger is the honest rendering of an "
                                            "investigation that has not run yet"),
            html='<div class="callout"><p>No evidence recorded. '
                 '<code>mva-science evidence-add</code> records the first observation.</p>'
                 "</div>",
        )

    return Exhibit(
        slug="evidence-ledger",
        title="The evidence ledger",
        caption=(
            "Every observation on the record, grouped by the claim it bears on. Strength is "
            "a human judgment on a 0–1 scale, not a computed statistic; the source column "
            "is what makes that judgment checkable. Neutral rows carry zero weight and are "
            "recorded anyway, because \"we looked and it told us nothing\" is a finding."
        ),
        legend=legend_line(GOOD, BAD, MUTED,
                           extra="green supports the claim, red refutes it, grey is "
                                 "neutral; the source column is the receipt"),
        html=('<div class="table-wrap"><table class="checks">'
              "<thead><tr><th>#</th><th>Direction</th><th>Strength</th><th>Kind</th>"
              "<th>Observation</th><th>Source</th></tr></thead>"
              f"<tbody>{''.join(rows)}</tbody></table></div>"),
    )


def weighing_chart(record: Record) -> Exhibit:
    """Supporting against refuting weight, per claim."""
    scored = [d for d in record.dossiers if d.evidence]
    if not scored:
        return Exhibit(slug="weighing", title="", caption="", legend="")

    labels = [d.hypothesis.hypothesis_id for d in scored]
    supporting = [sum(e.strength for e in d.supports) for d in scored]
    refuting = [-sum(e.strength for e in d.refutes) for d in scored]

    figure = go.Figure()
    figure.add_bar(x=supporting, y=labels, orientation="h", name="supporting",
                   marker_color=GOOD.fill, marker_line_color=GOOD.line,
                   marker_line_width=1,
                   hovertemplate="%{y}: %{x:.2f} supporting<extra></extra>")
    figure.add_bar(x=refuting, y=labels, orientation="h", name="refuting",
                   marker_color=BAD.fill, marker_line_color=BAD.line,
                   marker_line_width=1,
                   hovertemplate="%{y}: %{customdata:.2f} refuting<extra></extra>",
                   customdata=[abs(v) for v in refuting])
    figure.update_layout(barmode="relative", xaxis_title="summed strength",
                         legend_title_text="")
    figure.add_vline(x=0, line_color=SUBTLE_INK, line_width=1)

    return Exhibit(
        slug="weighing",
        title="How much weight sits on each claim",
        caption=(
            "Summed evidence strength, supporting to the right and refuting to the left. "
            "This is the shape of the arithmetic, not its result: a bar shows how much "
            "was observed, while the confidence on the board shows where that lands after "
            "the log-odds accumulation. A long bar in both directions is a contested "
            "claim, and worth more attention than a short one either way."
        ),
        legend=legend_line(GOOD, BAD,
                           extra="length is summed strength, not a count — one strong "
                                 "observation outweighs three weak ones"),
        figure=sized(figure, height=max(240, 46 * len(labels) + 120)),
    )


def exhibits(record: Record) -> list[Exhibit]:
    return [evidence_ledger(record), weighing_chart(record)]
