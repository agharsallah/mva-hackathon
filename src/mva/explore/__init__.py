"""Exploration and visualisation for genomic callsets.

Two layers so far, each usable on its own:

``readers``
    Parsers for the plain-text formats bioinformatics tools emit — TSV tables,
    ``bcftools stats``, BED intervals, VCF headers. Case-agnostic.
``profile``
    A directory of profiling artifacts loaded into one typed object, with the filename
    mapping in a swappable :class:`~mva.explore.profile.ProfileLayout`.

The quick path::

    from mva.explore import CallsetProfile

    profile = CallsetProfile.load("ressources/data-profile")
    print(profile.available, profile.total_records)
"""

from .profile import CallsetProfile, ProfileLayout

__all__ = ["CallsetProfile", "ProfileLayout"]
