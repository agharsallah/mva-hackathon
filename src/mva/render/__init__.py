"""One report shell, one palette, for every subject in the repository.

Extracted out of ``mva.explore`` once a second report needed it. Nothing in here knows
what it is drawing: :class:`~mva.render.figure.Exhibit` is a figure plus the words that
make it readable, :class:`~mva.render.figure.Section` is a group of them, and
:func:`~mva.render.report.render` turns a list of sections into a self-contained page.

The layers:

``theme``
    The one place a colour is chosen. Green is good, red is broken, yellow is a decision,
    blue is neutral machinery, purple is raw input — the convention fixed in `CLAUDE.md`,
    carried into Plotly by :func:`~mva.render.theme.install_template`.
``figure``
    The rule that a chart never travels alone: it carries a caption saying how to read it
    and a ``**Legend**`` line decoding its own colours.
``report``
    Sections assembled into one navigable HTML file — sidebar, scrollspy, keyword filter,
    everything inlined but the Plotly runtime.

The quick path::

    from mva.render import Exhibit, Section, render

    page = render([Section("s", "Title", "What this shows", [exhibit])],
                  title="A report", subject="where it came from")

Consumers: :mod:`mva.explore` (the data profile) and :mod:`mva.science` (the research
record). Both draw on the same palette, so a reader moving between them does not have to
relearn what a colour means.
"""

from .figure import Exhibit, Section, inline, sized
from .report import DEFAULT_BLURB, SCRIPT, STYLE, export_exhibits, render
from .theme import (
    BAD,
    DECISION,
    GOOD,
    MACHINE,
    MUTED,
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
    "DEFAULT_BLURB",
    "GOOD",
    "MACHINE",
    "MUTED",
    "RAW",
    "SCRIPT",
    "SEQUENCE",
    "STYLE",
    "SUBTLE_INK",
    "Exhibit",
    "Hue",
    "Section",
    "export_exhibits",
    "inline",
    "install_template",
    "legend_line",
    "render",
    "sized",
]
