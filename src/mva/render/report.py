"""Assembling exhibits into one self-contained, navigable page.

The output is a single HTML file with the interactivity intact — zoom a chart, hover a
point for its exact value, filter the exhibit list by keyword. It opens from the
filesystem with no server and no build step, which is what makes it something to actually
look at during analysis rather than a deliverable produced once at the end.

Only Plotly's runtime is fetched from a CDN; everything else is inlined, so the file
survives being emailed, committed or opened offline apart from the charts' interactivity.

**This module knows nothing about its subject.** It takes a list of
:class:`~mva.render.figure.Section` and renders it. What those sections contain — a data
profile, a hypothesis board, a locus browser — is the caller's business, which is what
lets one shell serve every report in the repository.
"""

import html
from datetime import UTC, datetime
from pathlib import Path

from .figure import Exhibit, Section

STYLE = (Path(__file__).parent / "report.css").read_text(encoding="utf-8")

SCRIPT = """
const filter = document.getElementById('filter');
const exhibits = Array.from(document.querySelectorAll('figure.exhibit'));
const navLinks = Array.from(document.querySelectorAll('.exhibit-link'));

/* Type to narrow the page to the exhibits whose title, caption or legend mentions the
   term. Everything is already in the DOM, so this is a display toggle, not a search. */
filter?.addEventListener('input', () => {
  const term = filter.value.trim().toLowerCase();
  exhibits.forEach(exhibit => {
    const hit = !term || exhibit.innerText.toLowerCase().includes(term);
    exhibit.classList.toggle('hidden', !hit);
  });
  document.querySelectorAll('section.report-section').forEach(section => {
    const visible = section.querySelectorAll('figure.exhibit:not(.hidden)').length;
    section.style.display = visible ? '' : 'none';
  });
  navLinks.forEach(link => {
    const target = document.getElementById(link.dataset.target);
    link.style.display = target && target.classList.contains('hidden') ? 'none' : '';
  });
});

/* Highlight the exhibit currently in view, so the sidebar tracks the scroll position. */
const spy = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    const link = navLinks.find(l => l.dataset.target === entry.target.id);
    if (link) link.classList.toggle('active', entry.isIntersecting);
  });
}, {rootMargin: '-45% 0px -45% 0px'});
exhibits.forEach(exhibit => spy.observe(exhibit));

/* "/" focuses the filter, the way every tool with a search box behaves. */
document.addEventListener('keydown', event => {
  if (event.key === '/' && document.activeElement !== filter) {
    event.preventDefault();
    filter?.focus();
  }
  if (event.key === 'Escape' && document.activeElement === filter) {
    filter.value = '';
    filter.dispatchEvent(new Event('input'));
    filter.blur();
  }
});
"""


#: What a report says about itself when the caller does not say it. A real report
#: replaces this: the sentence is the reader's first orientation, and a generic one wastes
#: it. Kept here only so ``render`` has a working default.
DEFAULT_BLURB = (
    "Every exhibit states how to read it and decodes its own colours; every graded number "
    "states the band it was judged against and why that band is the right one."
)


def render(sections: list[Section], title: str, subject: str, blurb: str = DEFAULT_BLURB) -> str:
    """Render arbitrary sections into the report shell."""
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    runtime = _RuntimeFlag()
    body = "\n".join(_section_html(section, runtime) for section in sections)
    total = sum(len(section.exhibits) for section in sections)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="layout">
{_sidebar(sections, title, subject)}
<main>
<header class="masthead">
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(blurb)}</p>
  <p class="meta">{total} exhibits across {len(sections)} sections &middot; source
  {html.escape(subject)} &middot; generated {generated} &middot; press <code>/</code> to
  filter</p>
</header>
{body or '<p class="empty">No artifacts found to render.</p>'}
</main>
</div>
<script>{SCRIPT}</script>
</body>
</html>
"""


def _sidebar(sections: list[Section], title: str, subject: str) -> str:
    items = []
    for section in sections:
        links = "".join(
            f'<li><a class="exhibit-link" href="#{e.slug}" data-target="{e.slug}">'
            f"{html.escape(e.title)}</a></li>"
            for e in section.exhibits
        )
        items.append(
            f'<li><a class="section-link" href="#section-{section.slug}">'
            f"{html.escape(section.title)}</a><ol>{links}</ol></li>"
        )
    return f"""<nav class="sidebar">
  <h1>{html.escape(title)}</h1>
  <p class="subject">{html.escape(subject)}</p>
  <input id="filter" type="search" placeholder="Filter exhibits  ( / )" autocomplete="off">
  <ol>{"".join(items)}</ol>
</nav>"""


def _section_html(section: Section, runtime: "_RuntimeFlag") -> str:
    rendered = "\n".join(e.to_div(runtime.claim(e)) for e in section.exhibits)
    return f"""<section class="report-section" id="section-{section.slug}">
  <h2>{html.escape(section.title)}</h2>
  <p class="blurb">{html.escape(section.blurb)}</p>
  {rendered}
</section>"""


def export_exhibits(
    sections: list[Section], directory: str | Path, images: bool = False
) -> list[Path]:
    """Write each exhibit as its own file, for pasting one figure into a document.

    Returns the paths written. Image export is attempted only when asked for and is
    skipped silently when the optional static-export engine is not installed, because the
    interactive page is the primary artifact and an image is a convenience.
    """
    root = Path(directory)
    written: list[Path] = []
    for section in sections:
        for exhibit in section.exhibits:
            written.append(exhibit.write_html(root / section.slug))
            if images:
                image = exhibit.write_image(root / section.slug)
                if image is not None:
                    written.append(image)
    return written


class _RuntimeFlag:
    """Grants the Plotly runtime to the first exhibit that actually carries a figure.

    A report opens with tables, not charts, so "the first exhibit" and "the first figure"
    are different exhibits. Attaching the runtime to the former leaves every chart on the
    page blank with no error anywhere.
    """

    def __init__(self) -> None:
        self.claimed = False

    def claim(self, exhibit: Exhibit) -> bool:
        if self.claimed or exhibit.figure is None:
            return False
        self.claimed = True
        return True
