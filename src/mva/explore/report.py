"""The profile-driven report: which sections it contains, and what it says about itself.

The page shell — sidebar, scrollspy, keyword filter, the inlined stylesheet — is
subject-agnostic and lives in :mod:`mva.render.report`. What is left here is the part that
is genuinely about a callset: which views make up the page, and the two opening sentences
that orient a reader.

``render`` and ``export_exhibits`` are re-exported so the import path callers already use
keeps working.
"""

from pathlib import Path

from ..render.figure import Exhibit, Section
from ..render.report import SCRIPT, STYLE, export_exhibits, render
from .profile import CallsetProfile
from .views import build_sections

__all__ = [
    "LOCUS_BLURB",
    "PROFILE_BLURB",
    "SCRIPT",
    "STYLE",
    "Exhibit",
    "Section",
    "build_report",
    "export_exhibits",
    "render",
    "write_report",
]

#: What the profile-driven report is built from. The locus report is built from records
#: instead, so the sentence is a parameter rather than a fixture of the shell.
PROFILE_BLURB = (
    "An exploration of a genomic dataset, built from committable summary statistics "
    "rather than from the patient records themselves. Every exhibit states how to read it "
    "and decodes its own colours; every graded number states the band it was judged "
    "against and why that band is the right one."
)

LOCUS_BLURB = (
    "Every call the caller made across this region, read from the variant records "
    "themselves rather than from a summary. These coordinates are patient data: keep this "
    "page outside the repository."
)


def build_report(
    profile: CallsetProfile, title: str, subject: str = "", extra: list[Section] | None = None
) -> str:
    """Render a complete HTML page for one profile, plus any extra sections."""
    sections = build_sections(profile) + list(extra or [])
    return render(
        sections, title=title, subject=subject or str(profile.source), blurb=PROFILE_BLURB
    )


def write_report(
    profile: CallsetProfile,
    destination: str | Path,
    title: str,
    subject: str = "",
    extra: list[Section] | None = None,
) -> Path:
    """Write the report to ``destination`` and return the path written."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(profile, title, subject, extra), encoding="utf-8")
    return path
