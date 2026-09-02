"""Re-export of the shared palette, kept for the import path.

The real definitions moved to :mod:`mva.render.theme` when a second report needed the same
colours. See that module for the convention itself.

New code should import from :mod:`mva.render`.
"""

from ..render.theme import (
    BAD,
    DECISION,
    FONT,
    GOOD,
    GRID,
    INK,
    MACHINE,
    MONO,
    MUTED,
    PAPER,
    RAW,
    SEQUENCE,
    SUBTLE_INK,
    Hue,
    install_template,
    legend_line,
)

__all__ = [
    "BAD",
    "DECISION",
    "FONT",
    "GOOD",
    "GRID",
    "INK",
    "MACHINE",
    "MONO",
    "MUTED",
    "PAPER",
    "RAW",
    "SEQUENCE",
    "SUBTLE_INK",
    "Hue",
    "install_template",
    "legend_line",
]
