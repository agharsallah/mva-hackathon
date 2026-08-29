"""The step map and the hypothesis board — what is being asked, and where each answer stands.

Two exhibits that answer the two questions a reader arrives with: *what are you trying to
find out*, and *what do you currently believe*. Both are read straight off the record;
neither restates a number that lives elsewhere.
"""

from ...render.figure import Exhibit
from ...render.theme import DECISION, GOOD, MACHINE, MUTED, legend_line
from ..hypothesis import Status
from ..record import Record
from ..steps import PLATFORM

#: How a step's declared status is coloured. Distinct from a hypothesis status: a step can
#: be finished while the claims under it are still open.
_STEP_HUE = {"done": GOOD, "open": DECISION, "planned": MUTED}


def step_map(record: Record) -> Exhibit:
    """One card per step: the goal, and how far its claims have got."""
    cards = []
    for step in record.steps:
        hue = _STEP_HUE[step.status]
        counts = record.tally_for(step.slug)
        total = sum(counts.values())

        if step.kind == PLATFORM:
            hint = "machinery — records decisions, not claims"
        elif total == 0:
            hint = "no hypotheses recorded yet"
        else:
            hint = (f"{counts[Status.SUPPORTED]} supported · "
                    f"{counts[Status.REFUTED]} refuted · "
                    f"{total - counts[Status.SUPPORTED] - counts[Status.REFUTED]} open")

        cards.append(
            f'<div class="tile" style="border-left:4px solid {hue.line}">'
            f'<span class="tile-value" style="font-size:1.05rem">{step.title}</span>'
            f'<span class="tile-label">{step.goal}</span>'
            f'<span class="tile-hint">{step.slug} · {step.status} · {hint}</span></div>')

    return Exhibit(
        slug="step-map",
        title="The steps, and what each one is trying to find out",
        caption=(
            "Every hypothesis names one of these steps, so the record can be read by "
            "question rather than by date. A step is finished when its claims have "
            "verdicts — not when its code runs. Step 0 is the exception: it is machinery, "
            "and machinery is judged by whether it works, not by whether it is true."
        ),
        legend=legend_line(GOOD, DECISION, MUTED,
                           extra="the stripe is the step's own status: finished, being "
                                 "worked, or not yet opened"),
        html=f'<div class="tiles">{"".join(cards)}</div>',
    )


def _confidence_cell(dossier) -> str:
    """Committed confidence beside what the evidence suggests, when they differ."""
    committed = dossier.hypothesis.confidence
    suggested = dossier.weighing.confidence
    if committed is None:
        return f'<span style="color:#888888">— <small>({suggested:.2f} suggested)</small></span>'
    gap = dossier.confidence_gap
    if gap is not None and abs(gap) >= 0.15:
        return (f"{committed:.2f} <small style=\"color:{DECISION.line}\">"
                f"({suggested:.2f} suggested, {gap:+.2f})</small>")
    return f"{committed:.2f}"


def hypothesis_board(record: Record) -> Exhibit:
    """Every claim, its status, and the weight of evidence behind it."""
    if not record.dossiers:
        return Exhibit(
            slug="hypothesis-board",
            title="The hypothesis board",
            caption=(
                "No hypothesis has been recorded yet. That is a statement about the "
                "investigation, not a gap in the page: step 1 has not run, so there is "
                "nothing to believe or disbelieve. Claims appear here the moment one is "
                "proposed."
            ),
            legend=legend_line(MUTED, extra="an empty register renders as empty, never as "
                                            "a placeholder that implies work"),
            html='<div class="callout"><p>The register is empty. '
                 '<code>mva-science hypothesis-add</code> opens the first claim.</p></div>',
        )

    rows = []
    for dossier in record.dossiers:
        h = dossier.hypothesis
        hue = h.status.hue
        rows.append(
            f"<tr><td><code>{h.hypothesis_id}</code></td>"
            f"<td>{h.step}</td>"
            f'<td><span class="badge" style="background:{hue.fill};'
            f'border-color:{hue.line}">{h.status.value}</span></td>'
            f'<td class="numeric">{_confidence_cell(dossier)}</td>'
            f'<td class="numeric">{len(dossier.supports)}+ / {len(dossier.refutes)}−</td>'
            f"<td>{h.gene or '—'}</td>"
            f"<td><details><summary>{h.statement}</summary>"
            f'<div class="reasoning"><p><strong>Prediction if true.</strong> '
            f"{h.prediction}</p>"
            f"<p><strong>What would refute it.</strong> {h.refuted_by}</p>"
            + (f"<p><strong>Reasoning for the current verdict.</strong> {h.reasoning}</p>"
               if h.reasoning else "")
            + "</div></details></td></tr>")

    untested = len(record.untested_claims)
    callout = ""
    if untested:
        callout = (f'<div class="callout"><p>{untested} of {len(record.dossiers)} claims '
                   f"have no evidence recorded against them yet — they are proposed, not "
                   f"tested.</p></div>")

    return Exhibit(
        slug="hypothesis-board",
        title="The hypothesis board",
        caption=(
            "Every claim on the record, with the prediction that would confirm it and the "
            "observation that would kill it. Open a row to see both. Where a committed "
            "confidence differs from what the evidence arithmetic suggests, both are shown "
            "— the gap is a judgment someone made, and it should be visible rather than "
            "reconstructed."
        ),
        legend=legend_line(MACHINE, DECISION, GOOD, MUTED,
                           extra="badge colours are the claim's status: proposed, being "
                                 "tested, supported, refuted, or superseded (red is "
                                 "refuted, grey superseded)"),
        html=(f'{callout}<div class="table-wrap"><table class="checks">'
              "<thead><tr><th>ID</th><th>Step</th><th>Status</th><th>Confidence</th>"
              "<th>Evidence</th><th>Gene</th><th>Claim</th></tr></thead>"
              f"<tbody>{''.join(rows)}</tbody></table></div>"),
    )


def exhibits(record: Record) -> list[Exhibit]:
    return [step_map(record), hypothesis_board(record)]
