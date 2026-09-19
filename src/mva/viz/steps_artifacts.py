"""The files a step produced, addressable: its figures and its methodology entries.

``/api/steps`` has always listed what a step drew and what it wrote — as bare filenames,
which a reader cannot open. Three quarters of the rendered evidence in this repository
(~75 files under ``figures/``) therefore existed only on the filesystem of whoever ran the
renderer. This module turns those names into rows with URLs, and serves the bytes behind
them.

**Why a whitelist rather than a sanitised path.** Every servable file is named by a step —
either by the convention ``figures/track1/<iteration>/<slug>/`` or by the step's own
``figures`` tuple — or is a methodology entry the blind gate already walked. A request is
answered by *looking the name up in that list*, so no request can address a file the step
map did not declare. There is no path arithmetic to get wrong.

**Positions.** Figures and methodology entries are tracked files, which
``tools/check_coordinates.py`` forbids from carrying a patient position. Nothing served
here can hold a coordinate that is not already committed.
"""

from __future__ import annotations

import re
from pathlib import Path

#: What a browser should be told each figure extension is.
MEDIA_TYPES = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".html": "text/html",
    ".json": "application/json",
}

#: The leading number of a methodology entry: ``084-the-blind-target-set.md`` -> ``084``.
ENTRY_NUMBER = re.compile(r"^(\d+)[-_]")

#: The entry's own ``# `` heading, which is the sentence it wants to be cited by.
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.M)


def figure_title(name: str) -> str:
    """A filename as a caption: ``recall-at-n.png`` -> ``recall at n``.

    Derived, not typed. A caption that restates the filename is honest about being one;
    inventing prose for a figure nobody has described would not be.
    """
    return Path(name).stem.replace("-", " ").replace("_", " ")


def figure_rows(iteration: str, slug: str, declared: tuple[str, ...], root: Path) -> list[dict]:
    """Every figure of one step: the convention directory first, then what it declared.

    A step that drew nothing has no rows, which is a true statement about the step rather
    than an error. ``declared`` paths are repository-relative and exist for the steps that
    ran before the per-step directory convention did.
    """
    found: dict[str, Path] = {}
    folder = root / "figures" / "track1" / iteration / slug
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                found[path.name] = path
    for relative in declared:
        path = root / relative
        if path.is_file():
            found.setdefault(path.name, path)
    return [
        {
            "name": name,
            # The citable id the lightbox and the ``?figure=`` parameter use. The filename,
            # not the stem: step 8 renders every figure twice (``x.png`` and interactive
            # ``x.html``), and two rows that share an id cannot both be addressed.
            "slug": name,
            "title": figure_title(name),
            "kind": path.suffix.lstrip("."),
            "path": path.relative_to(root).as_posix(),
            "url": f"/api/steps/{iteration}/{slug}/figure/{name}",
            "bytes": path.stat().st_size,
        }
        for name, path in sorted(found.items())
    ]


def entry_number(name: str) -> str:
    """The global methodology number, or an empty string for a file that carries none."""
    match = ENTRY_NUMBER.match(name)
    return match.group(1) if match else ""


def entry_title(path: Path) -> str:
    """The entry's own heading, with its number stripped — what a card should show.

    Read from the file rather than composed from the filename: the heading is the sentence
    the author chose, and the filename is a slug of it.
    """
    if not path.is_file():
        return ""
    heading = HEADING.search(path.read_text(encoding="utf-8"))
    if heading is None:
        return ""
    return re.sub(r"^(?:entry\s+)?\d+\s*[-—:.]\s*", "", heading.group(1), flags=re.I)
