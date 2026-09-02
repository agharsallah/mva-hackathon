"""The view registry for the research report, in reading order.

Same shape as :mod:`mva.explore.views` — a section is a title, a sentence saying what
question it answers, and a builder that turns the record into exhibits — but over a
:class:`~mva.science.record.Record` instead of a callset profile. Adding a section means
adding a module and one entry here.

Reading order runs from method to result: how the record works, what is being asked, what
is believed, why, what the irreversible spends bought, and finally the form the challenge
asks for.

**Empty sections are kept.** The profile report drops a section whose exhibits are all
empty, because a missing input means there is nothing to say. Here an empty section *is*
the statement — "no hypothesis has been recorded" is a true and important thing for the
page to say, and a blank page that silently omits it reads like a bug.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ...render.figure import Exhibit, Section
from ..record import Record
from . import board, ledger, loop, methods, submission


@dataclass(frozen=True)
class ViewSpec:
    """One section of the report: its identity and the builder that fills it."""

    slug: str
    title: str
    blurb: str
    build: Callable[[Record], list[Exhibit]]


#: Every section, in the order a reader should meet them.
SECTIONS: list[ViewSpec] = [
    ViewSpec("method", "The method",
             "How a research goal becomes a scored submission row, and what the register "
             "refuses to store.",
             loop.exhibits),
    ViewSpec("questions", "The questions",
             "What each step is trying to find out, and where every claim under it "
             "currently stands.",
             board.exhibits),
    ViewSpec("evidence", "The evidence",
             "Every observation on the record, which way it cut, and the receipt behind "
             "it.",
             ledger.exhibits),
    ViewSpec("oracle", "The oracle",
             "The finite submission budget, and what each irreversible spend bought.",
             submission.exhibits),
    ViewSpec("form", "The methods form",
             "The challenge's own questions, answered from the record — and marked where "
             "they cannot be.",
             methods.exhibits),
]


def build_sections(record: Record) -> list[Section]:
    """Run every registered view, keeping every section that produced an exhibit."""
    sections = []
    for spec in SECTIONS:
        built = [e for e in spec.build(record) if e.figure is not None or e.html]
        if built:
            sections.append(Section(spec.slug, spec.title, spec.blurb, built))
    return sections
