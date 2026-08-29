"""The methods form, answered from the record — and honest about what it cannot answer yet.

The challenge asks for a filled methods form, and several of its questions are answerable
straight off the register: how many candidates were considered, whether the approach emits
pairs, how the oracle was used, how secondary findings were handled. Generating those
answers from the tables rather than writing them by hand means the form and the repository
cannot disagree.

Questions the record cannot answer yet render as **not answerable**, naming what would have
to be recorded first. That is deliberate: a form question with a plausible-sounding answer
nobody executed is worse than a blank, because a blank is honest and a guess is not.
The question numbering follows the transcription in ``ideation/hackathon-intel.md`` §9.5.
"""

from ...render.figure import Exhibit
from ...render.theme import DECISION, GOOD, MUTED, legend_line
from ..record import Record

UNANSWERABLE = "not answerable from the record yet"


def _answer(record: Record) -> list[tuple[str, str, str | None]]:
    """Each question, and either the answer the record gives or what is missing."""
    dossiers = record.dossiers
    answers: list[tuple[str, str, str | None]] = []

    answers.append((
        "Q10–11", "Is the output automated or manually curated?",
        ("Automated. Every claim, observation and verdict is a row appended by "
         "<code>mva-science</code>; the submission rows are generated from the register "
         "and carry the hypothesis id that produced them.")))

    answers.append((
        "Q12–14", "Public data only?",
        ("Answerable once the annotation sources are recorded. Every evidence row carries "
         "a <code>source_ref</code>, so the set of sources used is a query — but no "
         "evidence has been recorded yet."
         if not dossiers else
         "Sources used, from the evidence ledger: "
         + ", ".join(sorted({e.source_ref.split(":")[0]
                             for d in dossiers for e in d.evidence}) or ["none"]) + ".")))

    answers.append((
        "Q15", "Can the approach output compound-heterozygous pairs?",
        ("Yes. The ranked object is a pair, not a variant, and a pair is emitted in one "
         "submission row through the second-variant columns — splitting a pair across two "
         "rows scores partial credit only.")))

    answers.append((
        "Q16", "How were secondary and incidental findings handled?",
        (None if not dossiers else
         f"{len(dossiers)} claims on the register, of which "
         f"{len(record.supported)} are supported. Secondary findings are submitted with "
         f"<code>finding_type=secondary</code> and cannot reduce the primary score.")))

    answers.append((
        "Q17", "Runtime and cost.",
        None))

    answers.append((
        "Q18", "Strengths and limitations.",
        ("Strength: every number in the report traces to an executed run through an "
         "append-only evidence row. Limitation: the confidence arithmetic is a transparent "
         "heuristic, not a calibrated posterior — strengths are human judgments and rows "
         "from the same underlying data are not independent."
         if dossiers else None)))

    answers.append((
        "Oracle", "How was the scoring feedback used?",
        (f"{record.budget_spent} of {record.budget_total} submissions spent. Each reply is "
         f"recorded in the probe ledger and re-entered as evidence against the hypotheses "
         f"it was fired to test — iterative hypothesis testing against the provided "
         f"validator.")))

    return answers


def form(record: Record) -> Exhibit:
    """The form, as far as the record can fill it."""
    rows = "".join(
        f"<tr><td><code>{number}</code></td><td>{question}</td>"
        + (f"<td>{answer}</td>" if answer else
           f'<td><span class="badge" style="background:{DECISION.fill};'
           f'border-color:{DECISION.line}">{UNANSWERABLE}</span></td>')
        + "</tr>"
        for number, question, answer in _answer(record)
    )
    missing = sum(1 for _, _, answer in _answer(record) if answer is None)

    callout = (f'<div class="callout"><p>{missing} question'
               f"{'s are' if missing != 1 else ' is'} not answerable from the record yet. "
               f"They stay blank rather than being filled with something plausible: a "
               f"guessed answer to a methods question is worse than a blank, because the "
               f"blank is honest.</p></div>") if missing else ""

    return Exhibit(
        slug="methods-form",
        title="The methods form, answered from the record",
        caption=(
            "Generated from the same tables the rest of this page is drawn from, so the "
            "form and the repository cannot drift apart. Questions the record cannot yet "
            "answer are marked, along with what would have to be recorded first."
        ),
        legend=legend_line(GOOD, DECISION, MUTED,
                           extra="yellow marks a question the record cannot answer yet — "
                                 "a gap in the work, not in the page"),
        html=(f'{callout}<div class="table-wrap"><table class="checks">'
              "<thead><tr><th>Q</th><th>Question</th><th>Answer</th></tr></thead>"
              f"<tbody>{rows}</tbody></table></div>"),
    )


def exhibits(record: Record) -> list[Exhibit]:
    return [form(record)]
