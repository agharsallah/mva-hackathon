"""The oracle budget and what each spend bought.

Eighteen submissions exist and no more. That makes a probe the one genuinely irreversible
act in the whole project, and the only part of the record where the cost of a mistake is
fixed in advance and cannot be re-earned. So it gets its own section: how much is left,
what each spend was aimed at, and what came back.
"""

from ...render.figure import Exhibit
from ...render.theme import BAD, DECISION, GOOD, MUTED, legend_line
from ..record import Record


def budget(record: Record) -> Exhibit:
    """How much of the oracle allowance is gone, drawn as the finite thing it is."""
    spent, total = record.budget_spent, record.budget_total
    left = record.budget_left

    pips = "".join(
        f'<span style="display:inline-block;width:22px;height:30px;margin:2px;'
        f"border-radius:4px;background:{(BAD if i < spent else GOOD).fill};"
        f'border:1px solid {(BAD if i < spent else GOOD).line}"></span>'
        for i in range(total)
    )

    tiles = (
        f'<div class="tiles">'
        f'<div class="tile"><span class="tile-value">{left}</span>'
        f'<span class="tile-label">submissions left</span>'
        f'<span class="tile-hint">of {total} the team will ever have</span></div>'
        f'<div class="tile"><span class="tile-value">{spent}</span>'
        f'<span class="tile-label">spent</span>'
        f'<span class="tile-hint">each one is irreversible</span></div>'
        f"</div>"
    )

    note = ""
    if spent == 0:
        note = (
            '<div class="callout"><p>Nothing has been spent. The budget is intact, and '
            "a probe fired before at least two independent paths agree on a candidate "
            "is a coin flip that costs a fixed fraction of everything the team has."
            "</p></div>"
        )

    return Exhibit(
        slug="oracle-budget",
        title="The oracle budget",
        caption=(
            "The scorer answers every submission immediately with rank points, F-max, and "
            "which row matched — which makes it an instrument, not just a grader. It is "
            "also finite. Each pip is one submission; red is spent and cannot be recovered."
        ),
        legend=legend_line(
            GOOD, BAD, extra="green is a submission still available, red one already spent"
        ),
        html=f'{tiles}<div style="margin-top:12px">{pips}</div>{note}',
    )


def trace(record: Record) -> Exhibit:
    """Each spend, what it was aimed at, and what came back."""
    if not record.probes:
        return Exhibit(
            slug="probe-trace",
            title="What each probe bought",
            caption=(
                "No probe has been fired, so there is nothing to decode. When one is, it "
                "appears here tied to the hypotheses it was aimed at, and the reply is "
                "recorded twice: once in the probe ledger as what happened, and once in "
                "the evidence ledger as what it means."
            ),
            legend=legend_line(
                MUTED,
                extra="empty because the budget is intact, not because the section is unfinished",
            ),
            html='<div class="callout"><p>No submissions spent. '
            "<code>mva-warehouse probe-log</code> records one.</p></div>",
        )

    rows = "".join(
        f'<tr><td class="numeric"><code>{p.probe_id}</code></td>'
        f"<td>{p.probe_type}</td><td>{p.submitted_by}</td>"
        f'<td class="numeric">{p.n_rows}</td>'
        f'<td class="numeric">{"—" if p.score is None else f"{p.score:g}"}</td>'
        f"<td>{', '.join(f'<code>{h}</code>' for h in p.hypothesis_ids) or '—'}</td>"
        f"<td>{p.response or '—'}</td></tr>"
        for p in record.probes
    )
    untied = sum(1 for p in record.probes if not p.hypothesis_ids)
    callout = ""
    if untied:
        callout = (
            f'<div class="callout"><p>{untied} spent submission'
            f"{'s name' if untied > 1 else ' names'} no hypothesis. The spend is "
            f"still recorded — the ledger records what happened — but the reply "
            f"cannot be decoded against a belief.</p></div>"
        )

    return Exhibit(
        slug="probe-trace",
        title="What each probe bought",
        caption=(
            "Every spent submission, the claims it was fired to test, and the reply. A "
            "probe aimed at no hypothesis still costs a submission but buys no belief, "
            "which is the failure mode this table exists to make visible."
        ),
        legend=legend_line(DECISION, extra="one row per irreversible spend, oldest first"),
        html=(
            f'{callout}<div class="table-wrap"><table class="checks">'
            "<thead><tr><th>#</th><th>Type</th><th>By</th><th>Rows</th><th>Score</th>"
            "<th>Hypotheses</th><th>Reply</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        ),
    )


def exhibits(record: Record) -> list[Exhibit]:
    return [budget(record), trace(record)]
