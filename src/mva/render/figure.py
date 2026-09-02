"""A figure and the words that make it readable, kept together.

The repository rule is that a chart never travels alone: it carries a caption saying how
to read it and a ``**Legend**`` line decoding its own colours. Bundling all three in one
object is what makes that rule enforceable rather than aspirational — a view cannot emit a
chart without also emitting its explanation, and the report renders whatever it is handed.

Panels are also the unit of reuse. The same :class:`Exhibit` renders into the HTML report, a
standalone interactive file for sharing, and a static image for a written document, with
no view knowing which destination it is bound for.
"""

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

import plotly.graph_objects as go


@dataclass(frozen=True)
class Exhibit:
    """One figure, its caption, its legend, and where it belongs in a report."""

    slug: str
    title: str
    caption: str
    legend: str
    figure: go.Figure | None = None
    html: str = ""
    height: int = 420
    notes: list[str] = field(default_factory=list)

    def to_div(self, embed_runtime: bool = False) -> str:
        """Render as an HTML fragment.

        ``embed_runtime`` must be true for exactly one exhibit per page — the first one that
        actually carries a figure. Panels that render a table instead of a chart never
        carry the runtime, which is why the caller tracks this rather than counting
        exhibits: an overview table at the top of a report would otherwise swallow the
        and leave every chart on the page blank.
        """
        if self.figure is not None:
            body = self.figure.to_html(
                full_html=False,
                include_plotlyjs="cdn" if embed_runtime else False,
                config={
                    "displaylogo": False,
                    "responsive": True,
                    "toImageButtonOptions": {"scale": 2, "filename": self.slug},
                    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                },
                div_id=f"fig-{self.slug}",
            )
        else:
            body = self.html
        notes = "".join(f'<p class="note">{inline(n)}</p>' for n in self.notes)
        return (
            f'<figure class="exhibit" id="{self.slug}">'
            f"<h3>{escape(self.title)}</h3>"
            f'<p class="caption">{inline(self.caption)}</p>'
            f"{body}"
            f'<figcaption class="legend">{inline(self.legend)}</figcaption>'
            f"{notes}"
            f"</figure>"
        )

    def write_html(self, directory: str | Path) -> Path:
        """Write this exhibit as a standalone interactive page."""
        path = Path(directory) / f"{self.slug}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.figure is None:
            path.write_text(self.html, encoding="utf-8")
        else:
            self.figure.write_html(
                path, include_plotlyjs="cdn", config={"displaylogo": False, "responsive": True}
            )
        return path

    def write_image(self, directory: str | Path, scale: int = 2) -> Path | None:
        """Write a static image for print, or return ``None`` when no exporter is installed.

        Static export needs the optional ``kaleido`` engine. The report never depends on
        it: interactive HTML is the primary artifact and an image is a convenience for
        pasting into a document.
        """
        if self.figure is None:
            return None
        path = Path(directory) / f"{self.slug}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.figure.write_image(path, scale=scale, width=1100, height=self.height)
        except Exception:
            return None
        return path


@dataclass(frozen=True)
class Section:
    """A named group of exhibits — one section of the report."""

    slug: str
    title: str
    blurb: str
    exhibits: list[Exhibit] = field(default_factory=list)


def sized(figure: go.Figure, height: int, title: str = "") -> go.Figure:
    """Apply the height and optional title an exhibit wants, in one call."""
    figure.update_layout(height=height)
    if title:
        figure.update_layout(title_text=title)
    return figure


def inline(text: str) -> str:
    """Escape a caption, legend or note, then render its inline markup.

    Captions are written as prose with the two marks that carry meaning in this
    repository: ``**emphasis**`` for the finding a note is about, and backticks for a
    filter name, a field or a command. Without this they reach the page as literal
    asterisks and backticks, which reads as a broken template.

    Escaping happens first and unconditionally, so a gene symbol or a filter name
    containing ``<`` or ``&`` cannot become markup.
    """
    out = escape(text)
    out = _wrap(out, "**", "strong")
    return _wrap(out, "`", "code")


def _wrap(text: str, mark: str, tag: str) -> str:
    """Turn paired ``mark`` delimiters into ``tag`` elements, leaving an odd one alone."""
    parts = text.split(mark)
    if len(parts) % 2 == 0:
        # An unpaired delimiter: the author meant a literal character, not markup.
        return text
    return "".join(p if i % 2 == 0 else f"<{tag}>{p}</{tag}>" for i, p in enumerate(parts))
