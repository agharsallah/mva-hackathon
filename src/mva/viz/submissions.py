"""The submissions surface: every upload-ready iteration, with its provenance and its audit.

``submissions/<track>/iteration-<n>/`` is the unit the organisers receive and the judges
read — the report, the methods form, the decode table, the coordinate-free selector spec —
and until now it existed only as files. This is the route that turns one into an object a
page can render: what the folder claims (:mod:`mva.viz.submissions_reader`), what the
warehouse says it was built from (:mod:`mva.viz.submissions_lineage`), and what was spent
and believed around it (:mod:`mva.viz.submissions_audit`).

**The predictions CSV is not here and must never be.** It holds real patient coordinates
and lives under gitignored ``build/``. What this route serves is the folder's *claim* about
it — the path, the sha256 and the row count — which is exactly what a reader needs to check
that the bytes uploaded are the bytes described, and carries no position.

**Cached, because most of the cost is the database.** One entry under the key
``submissions`` holds the whole payload: reading four small files per folder is
microseconds, but the lineage walk is a round trip to a hosted PostgreSQL and the probe
ledger is another. ``?refresh=true`` rebuilds, the same as every other cached route here.

**The lineage degrades rather than fails.** On a checkout with no credentials the walk
returns ``available: false`` with the exception class in ``note``, and the sources that are
knowable from disk — the clinical document, the selector file, the table names — are still
listed. The page renders; it just says less, and says that it is saying less.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..warehouse.settings import Postgres
from . import (
    iteration_catalog,
    iterations_io,
    submissions_audit,
    submissions_lineage,
    submissions_reader,
)
from .cache import Cache
from .response import Envelope, cached, live

#: Cache key for the whole payload. Named rather than derived: the route takes no parameter.
CACHE_KEY = "submissions"

#: Everything the payload was assembled from, for the envelope's ``source`` line.
SOURCE = (
    "submissions/*/iteration-*/ on disk + warehouse.data_lineage + "
    "warehouse.probe_ledger + docs/science-register.json"
)

#: A figure slug is a path segment a client chooses, so it is validated rather than escaped —
#: the same discipline :func:`mva.warehouse.postgres.safe_identifier` applies to table names —
#: and then only looked up in the payload, never joined into a path.
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def payload(
    settings: Postgres,
    root: Path | None = None,
    *,
    ledger: submissions_lineage.Ledger | None = None,
    known: set[str] | None = None,
    tracked: set[str] | None = None,
) -> dict[str, Any]:
    """Every iteration folder, fully resolved. One ledger read and one probe read, total.

    ``ledger``, ``known`` (the database's tables) and ``tracked`` (``git ls-files``) may be
    passed in by a caller that already read them — :mod:`mva.viz.iterations` does.
    """
    base = (root or submissions_reader.DEFAULT_ROOT).resolve()
    ledger = ledger if ledger is not None else submissions_lineage.read_ledger(settings)
    known = known if known is not None else iterations_io.known_tables(settings)
    tracked = tracked if tracked is not None else iterations_io.tracked_files(base)
    probes = submissions_audit.read_probes(settings)
    register = submissions_audit.read_register(base)

    iterations = []
    for folder in submissions_reader.iteration_folders(base):
        iteration = submissions_reader.read(folder, base)
        entries = submissions_lineage.contribution_entries(iteration["contributions"])
        # The catalogue first: the tables its entries name extend the lineage walk, which is
        # what lets a panel-judged folder with no selectors trace itself.
        iteration["catalog"] = iteration_catalog.build(base, entries, ledger, known, tracked)
        tables = submissions_lineage.selector_tables(iteration["selectors"])
        cited = sorted(
            set(submissions_lineage.entry_tables(ledger, entries))
            | set(iteration_catalog.tables_of(iteration["catalog"]))
        )
        iteration["lineage"] = submissions_lineage.build(
            ledger, base, folder, iteration["track"], iteration["number"], tables, cited
        )
        iteration["audit"] = submissions_audit.build(
            probes,
            register,
            iteration["number"],
            iteration["csv"]["sha256"],
            iteration["hypotheses"],
            iteration["track"],
        )
        iterations.append(iteration)
    return {"iterations": iterations}


def find(iterations: list[dict[str, Any]], track: str, number: int) -> dict[str, Any]:
    """One iteration out of the payload, or a 404 naming what was asked for."""
    for iteration in iterations:
        if iteration["track"] == track and iteration["number"] == number:
            return iteration
    raise HTTPException(status_code=404, detail=f"no iteration {number} for track {track!r}")


#: What an ``<img>`` is told a figure is. The reader lists only these two suffixes.
MEDIA_TYPES = {".png": "image/png", ".svg": "image/svg+xml"}


def figure_path(root: Path, iteration: dict[str, Any], slug: str) -> Path:
    """The file behind one figure slug of one iteration, or a 404.

    The slug is validated, then looked up in the iteration's own ``figures`` list — the
    files its report cites — so a client can only ever reach a file the payload already
    names. No path is built from the request.
    """
    if not SEGMENT.match(slug):
        raise HTTPException(status_code=404, detail=f"not a figure name: {slug!r}")
    for figure in iteration["figures"]:
        path = root / figure["path"]
        if figure["slug"] == slug and path.suffix in MEDIA_TYPES and path.is_file():
            return path
    raise HTTPException(
        status_code=404,
        detail=f"no figure {slug!r} for {iteration['track']} iteration {iteration['number']}",
    )


def add_routes(api: APIRouter, settings: Postgres, cache: Cache, root: Path | None = None) -> None:
    """Register the three submission routes on the warehouse router."""
    base = (root or submissions_reader.DEFAULT_ROOT).resolve()

    def built(refresh: bool = False) -> Any:
        return cache.get_or_build(CACHE_KEY, lambda: payload(settings, base), refresh)

    @api.get(
        "/submissions",
        response_model=Envelope,
        tags=["submissions"],
        summary="every upload-ready iteration, with its lineage and its audit trail",
    )
    def submissions(refresh: bool = False) -> dict:
        """Every ``submissions/<track>/iteration-<n>/`` folder as one object.

        ``state`` is the folder's own declaration — ``draft``, ``ready`` (built, not
        uploaded) or ``frozen`` (uploaded and never edited again) — read from the README's
        ``**Standing:**`` line by the same rule ``tools/check_iteration.py`` enforces, so
        the page and the gate can never disagree.

        ``csv`` describes the predictions file **without containing it**: the file holds
        real patient coordinates and is gitignored, so ``path``, ``sha256`` and ``rows``
        are the claim a reader checks it against. ``selectors`` is the coordinate-free
        spec it was resolved from; an allele there carrying a position is refused rather
        than served.

        ``lineage.available`` is **false** on a checkout with no database. ``edges`` is
        then empty and ``note`` names the exception class, but ``sources`` still lists what
        disk alone proves — the clinical document, the selector file, the table names.

        ``audit.register`` carries **one row per claim**, not its history: the exported
        record holds each claim's current state plus a revision count, so ``revision`` is
        that count and ``recorded_at`` is empty rather than invented.
        """
        return cached(built(refresh), SOURCE)

    @api.get(
        "/submissions/{track}/{number}/report",
        response_model=Envelope,
        tags=["submissions"],
        summary="one iteration's report.md, verbatim",
    )
    def submission_report(track: str, number: int) -> dict:
        """The report as it is on disk — no rewriting, no summarising.

        Served separately from ``/api/submissions`` so a page can render the report without
        re-fetching every iteration's lineage and audit trail with it.
        """
        iteration = find(built().data["iterations"], track, number)
        return live(iteration["report"], iteration["report"]["path"])

    @api.get(
        "/submissions/{track}/{number}/figure/{slug}",
        tags=["submissions"],
        summary="one figure the iteration's report cites, as PNG or SVG",
        response_class=FileResponse,
    )
    def submission_figure(track: str, number: int, slug: str) -> FileResponse:
        """One figure out of the iteration's ``figures`` list.

        Bytes, not an envelope: an ``<img src>`` cannot read JSON. The list is the files the
        report cites (``figures/<track>/*.png`` for a report citing none), so ``number``
        picks which list the slug is resolved against.
        """
        iteration = find(built().data["iterations"], track, number)
        path = figure_path(base, iteration, slug)
        return FileResponse(path, media_type=MEDIA_TYPES[path.suffix])
