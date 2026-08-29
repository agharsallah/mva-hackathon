"""The research record as one self-contained page.

The shell — sidebar, scrollspy, keyword filter, the inlined stylesheet — is
:mod:`mva.render.report`, shared with the data-profile report. What is here is what is
specific to this subject: which sections make up the page, and the sentence that orients a
reader arriving at it.
"""

from pathlib import Path

from ..render.figure import Section
from ..render.report import render
from .record import Record
from .views import build_sections

#: The opening sentence. It has one job: stop a reader treating a confidence on this page
#: as an opinion, by saying up front where every number comes from.
SCIENCE_BLURB = (
    "The research record: what is being asked, what is claimed, what was observed, and "
    "what that adds up to. Every claim states what would refute it before it is tested, "
    "every observation names the run it came from, and every confidence shows the "
    "arithmetic behind it. Nothing here is asserted without a receipt, and what has not "
    "been established yet says so."
)


def build_report(record: Record, title: str = "The research record",
                 extra: list[Section] | None = None) -> str:
    """Render the whole record into one HTML page."""
    sections = build_sections(record) + list(extra or [])
    return render(sections, title=title, subject=record.subject, blurb=SCIENCE_BLURB)


def write_report(record: Record, destination: str | Path,
                 title: str = "The research record",
                 extra: list[Section] | None = None) -> Path:
    """Write the report to ``destination`` and return the path written."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(record, title, extra), encoding="utf-8")
    return path
