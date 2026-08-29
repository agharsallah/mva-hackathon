"""The method itself, drawn: how a research goal becomes a scored submission row.

This is the first exhibit on the page for a reason. A reader meeting a hypothesis board
without meeting the loop first has no way to tell whether "confidence 0.62" is a measured
quantity or someone's mood. The diagram says where every number on the rest of the page
comes from, and the SVG is hand-written rather than plotted because the subject is a
process, not data.
"""

from ...render.figure import Exhibit
from ...render.theme import BAD, DECISION, GOOD, MACHINE, MUTED, RAW, legend_line
from ..record import Record

#: Reading order of the five stations, with the one-line job of each.
STATIONS = (
    ("Goal", "the one question a step exists to answer", RAW),
    ("Hypothesis", "a falsifiable claim, with what would refute it", MACHINE),
    ("Test", "an executed run, recorded as a methodology entry", MACHINE),
    ("Evidence", "one observation, tagged and sourced", MACHINE),
    ("Verdict", "the evidence weighed into a confidence", DECISION),
)


def _station_svg() -> str:
    """The five stations in a row, then the crossing into a submission."""
    width, box_w, gap, y = 1000, 168, 20, 30
    boxes = []
    for index, (name, job, hue) in enumerate(STATIONS):
        x = index * (box_w + gap)
        boxes.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="72" rx="8" '
            f'fill="{hue.fill}" stroke="{hue.line}" stroke-width="1.5"/>'
            f'<text x="{x + box_w / 2}" y="{y + 28}" text-anchor="middle" '
            f'font-size="15" font-weight="600" fill="#333333">{name}</text>'
            f'<text x="{x + box_w / 2}" y="{y + 50}" text-anchor="middle" '
            f'font-size="10.5" fill="#666666">{_wrap(job, 30)[0]}</text>'
            f'<text x="{x + box_w / 2}" y="{y + 62}" text-anchor="middle" '
            f'font-size="10.5" fill="#666666">{_wrap(job, 30)[1]}</text>')
        if index < len(STATIONS) - 1:
            arrow_x = x + box_w
            boxes.append(
                f'<path d="M{arrow_x + 3} {y + 36} L{arrow_x + gap - 5} {y + 36}" '
                f'stroke="#666666" stroke-width="1.5" marker-end="url(#tip)"/>')

    submission = (
        f'<rect x="{width / 2 - 130}" y="170" width="260" height="54" rx="8" '
        f'fill="{GOOD.fill}" stroke="{GOOD.line}" stroke-width="1.5"/>'
        f'<text x="{width / 2}" y="192" text-anchor="middle" font-size="14" '
        f'font-weight="600" fill="#333333">Submission row</text>'
        f'<text x="{width / 2}" y="211" text-anchor="middle" font-size="10.5" '
        f'fill="#666666">notes carry the hypothesis id</text>')

    down = (f'<path d="M{4 * (box_w + gap) + box_w / 2} 102 '
            f'L{4 * (box_w + gap) + box_w / 2} 140 L{width / 2 + 130} 140 '
            f'L{width / 2 + 130} 170" fill="none" stroke="{GOOD.line}" '
            f'stroke-width="1.5" marker-end="url(#tip-good)"/>'
            f'<text x="{width / 2 + 200}" y="134" font-size="10.5" '
            f'fill="{GOOD.line}">supported</text>')

    back = (f'<path d="M{width / 2 - 130} 197 L60 197 L60 138 L{box_w * 3 + gap * 3 + 40} '
            f'138 L{box_w * 3 + gap * 3 + 40} 102" fill="none" stroke="{DECISION.line}" '
            f'stroke-width="1.5" stroke-dasharray="5 3" marker-end="url(#tip-decision)"/>'
            f'<text x="72" y="164" font-size="10.5" fill="{DECISION.line}">'
            f'the oracle reply comes back as new evidence</text>')

    return (
        f'<svg viewBox="0 0 {width} 240" width="100%" role="img" '
        f'aria-label="How a research goal becomes a scored submission row">'
        f'<defs>'
        f'<marker id="tip" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="#666666"/></marker>'
        f'<marker id="tip-good" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="{GOOD.line}"/></marker>'
        f'<marker id="tip-decision" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8 z" '
        f'fill="{DECISION.line}"/></marker>'
        f'</defs>'
        f'{"".join(boxes)}{down}{submission}{back}</svg>')


def _wrap(text: str, width: int) -> tuple[str, str]:
    """Split a short label across exactly two lines, so the SVG boxes stay uniform."""
    words, first = text.split(), []
    while words and len(" ".join(first + words[:1])) <= width:
        first.append(words.pop(0))
    return " ".join(first), " ".join(words)


def the_loop(record: Record) -> Exhibit:
    """The method, drawn."""
    return Exhibit(
        slug="the-loop",
        title="How a claim becomes a score",
        caption=(
            "Every number on this page is produced by this loop. A step states one goal; a "
            "hypothesis under it says what must be true and what would prove it wrong; a "
            "test is an executed run; each observation from that run is one evidence row "
            "with a source; the verdict is those rows weighed. A supported claim becomes a "
            "submission row that carries its own hypothesis id, and the oracle's reply "
            "re-enters as evidence — so a probe does not merely score, it moves a belief."
        ),
        legend=legend_line(
            RAW, MACHINE, DECISION, GOOD,
            extra="the dashed arrow is the feedback edge: an oracle reply becomes evidence "
                  "against the claim it was fired to test"),
        html=f'<div class="table-wrap">{_station_svg()}</div>',
    )


def the_rules(record: Record) -> Exhibit:
    """What the register refuses to store, and why each refusal is worth its friction."""
    rules = (
        ("A hypothesis with no refutation condition", BAD,
         "A claim nothing could disprove is not a hypothesis. Writing the refutation "
         "sentence <em>before</em> the run is what stops a result being reinterpreted "
         "afterwards to fit."),
        ("An observation with no source", BAD,
         "Every evidence row names its receipt — a methodology entry, a table, a PMID, a "
         "ClinVar record, an oracle reply. An unsourced number is exactly what this "
         "register exists to make impossible."),
        ("A confidence with no stated reason", BAD,
         "The tool suggests a number and shows its arithmetic; committing it takes a human "
         "and a written reason. The suggestion is never written on its own."),
        ("A genomic position in an exported file", BAD,
         "The export scans for coordinates and refuses rather than trusting everyone to "
         "remember. Name the gene and the consequence; never the position."),
        ("An edit to anything already recorded", MUTED,
         "Both tables are append-only. A changed belief is a new revision, so the record "
         "of the belief moving survives."),
    )
    rows = "".join(
        f'<tr><td><span class="badge" style="background:{hue.fill};'
        f'border-color:{hue.line}">refused</span></td>'
        f"<td><strong>{what}</strong></td><td>{why}</td></tr>"
        for what, hue, why in rules
    )
    return Exhibit(
        slug="the-rules",
        title="What the register refuses to store",
        caption=(
            "Five rules enforced in code rather than asked for in a template, because a "
            "template is advice and a constructor is a gate. Each one costs friction at "
            "the moment of writing and buys a record that survives being disagreed with."
        ),
        legend=legend_line(BAD, MUTED,
                           extra="red is a hard refusal; grey is a shape the schema makes "
                                 "impossible rather than an error it raises"),
        html=('<div class="table-wrap"><table class="checks">'
              "<thead><tr><th></th><th>What</th><th>Why it is worth the friction</th></tr>"
              f"</thead><tbody>{rows}</tbody></table></div>"),
    )


def exhibits(record: Record) -> list[Exhibit]:
    return [the_loop(record), the_rules(record)]
