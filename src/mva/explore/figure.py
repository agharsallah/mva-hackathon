"""Re-export of the shared figure primitives, kept for the import path.

The real definitions moved to :mod:`mva.render.figure` when a second report — the research
record in :mod:`mva.science` — needed the same ``Exhibit``/``Section`` pair. Nothing about
them was ever specific to a callset profile.

New code should import from :mod:`mva.render`. This module stays so that
``from mva.explore.figure import Exhibit`` keeps meaning what it has always meant.
"""

from ..render.figure import Exhibit, Section, inline, sized

__all__ = ["Exhibit", "Section", "inline", "sized"]
