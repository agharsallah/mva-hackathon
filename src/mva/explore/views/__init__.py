"""The view registry — every section the report can render, in reading order.

A section is a title, a sentence saying what question it answers, and a function that
turns a profile into exhibits. Adding a view means adding a module and one entry here;
nothing else in the toolkit changes, and a section whose data is absent contributes
nothing rather than failing.

Reading order is deliberate and runs outward from the answer: what the data is, whether it
can be trusted, what was sequenced, what was called, how the genome looks chromosome by
chromosome, and finally the candidate genes the search starts from.
"""

from dataclasses import dataclass
from typing import Callable

from ..figure import Exhibit, Section
from ..profile import CallsetProfile
from . import callset, karyotype, overview, panel, quality, reads


@dataclass(frozen=True)
class ViewSpec:
    """One section of the report: its identity and the builder that fills it."""

    slug: str
    title: str
    blurb: str
    build: Callable[[CallsetProfile], list[Exhibit]]


#: Every profile-driven section, in the order a reader should meet them.
SECTIONS: list[ViewSpec] = [
    ViewSpec("overview", "Overview",
             "What this dataset is, and whether anything about it should worry us.",
             overview.exhibits),
    ViewSpec("sequencing", "Sequencing",
             "The raw reads: how much DNA was read, how accurately, and how redundantly.",
             reads.exhibits),
    ViewSpec("callset", "Callset",
             "What the variant caller produced, and whether its shape looks like real "
             "human variation.",
             callset.exhibits),
    ViewSpec("filters", "Filters & phase",
             "What the caller held back, and how much of the callset can be placed onto a "
             "specific copy of a chromosome.",
             quality.exhibits),
    ViewSpec("chromosomes", "Chromosomes",
             "The genome one chromosome at a time — where an extra or missing copy would "
             "show itself.",
             karyotype.exhibits),
    ViewSpec("panel", "Candidate genes",
             "The genes already known to cause this condition, and the size of the search "
             "inside them.",
             panel.exhibits),
]


def build_sections(profile: CallsetProfile) -> list[Section]:
    """Run every registered view, keeping only the sections that produced exhibits."""
    sections = []
    for spec in SECTIONS:
        built = [e for e in spec.build(profile) if e.figure is not None or e.html]
        if built:
            sections.append(Section(spec.slug, spec.title, spec.blurb, built))
    return sections
