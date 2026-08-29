"""Re-export of the shared palette, kept for the import path.

The real definitions moved to :mod:`mva.render.theme` when a second report needed the same
colours. See that module for the convention itself.

New code should import from :mod:`mva.render`.
"""

from ..render.theme import (
    BAD, DECISION, GOOD, GRID, INK, MACHINE, MUTED, PAPER, RAW, SEQUENCE, SUBTLE_INK,
    FONT, MONO, Hue, install_template, legend_line,
)

__all__ = [
    "Hue", "install_template", "legend_line", "SEQUENCE",
    "GOOD", "BAD", "DECISION", "MACHINE", "MUTED", "RAW",
    "INK", "SUBTLE_INK", "GRID", "PAPER", "FONT", "MONO",
]
