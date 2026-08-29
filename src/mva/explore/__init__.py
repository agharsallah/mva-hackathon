"""Exploration and visualisation for genomic callsets.

A layered toolkit, each layer usable on its own:

``readers``
    Parsers for the plain-text formats bioinformatics tools emit — TSV tables,
    ``bcftools stats``, BED intervals, VCF headers. Case-agnostic.
``profile``
    A directory of profiling artifacts loaded into one typed object, with the filename
    mapping in a swappable :class:`~mva.explore.profile.ProfileLayout`.
``checks``
    Measured numbers graded against stated expectations, each with the reasoning behind
    its band.
``theme`` / ``figure``
    One palette for the whole repository, and the rule that a figure travels with its
    caption and its legend.
``views``
    Plotly exhibits grouped into report sections — sequencing, callset, filters,
    chromosomes, candidate genes, and a locus browser over live calls.
``report``
    Those exhibits assembled into a single self-contained interactive HTML page.

The quick path::

    from mva.explore import CallsetProfile, write_report

    profile = CallsetProfile.load("ressources/data-profile")
    write_report(profile, "figures/explore-report.html", "Callset exploration")

Or from the command line::

    uv run mva-explore report ressources/data-profile -o figures/explore-report.html
    uv run mva-explore checks ressources/data-profile
"""

from .checks import Check, Verdict, run_checks
from .figure import Exhibit, Section
from .profile import CallsetProfile, ProfileLayout
from .report import build_report, export_exhibits, render, write_report
from .theme import install_template
from .views import SECTIONS, build_sections

# Every figure in the package inherits the repository's palette and axes without each
# view having to ask for them.
install_template()

__all__ = [
    "CallsetProfile", "ProfileLayout", "Check", "Verdict", "run_checks",
    "Exhibit", "Section", "SECTIONS", "build_sections",
    "build_report", "write_report", "render", "export_exhibits", "install_template",
]
