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
from . import submissions_audit, submissions_lineage, submissions_reader
from .cache import Cache
from .response import Envelope, cached, live

#: Cache key for the whole payload. Named rather than derived: the route takes no parameter.
CACHE_KEY = "submissions"

#: Everything the payload was assembled from, for the envelope's ``source`` line.
SOURCE = (
    "submissions/*/iteration-*/ on disk + warehouse.data_lineage + "
    "warehouse.probe_ledger + docs/science-register.json"
)

#: A figure slug and a track name are path segments a client chooses, so they are validated
#: rather than escaped — the same discipline
#: :func:`mva.warehouse.postgres.safe_identifier` applies to table names. This shape cannot
#: contain a separator or a ``..``, so it cannot leave ``figures/<track>/``.
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def payload(settings: Postgres, root: Path | None = None) -> dict[str, Any]:
    """Every iteration folder, fully resolved. One ledger read and one probe read, total."""
    base = (root or submissions_reader.DEFAULT_ROOT).resolve()
    ledger = submissions_lineage.read_ledger(settings)
    probes = submissions_audit.read_probes(settings)
    register = submissions_audit.read_register(base)

    iterations = []
    for folder in submissions_reader.iteration_folders(base):
        iteration = submissions_reader.read(folder, base)
        tables = submissions_lineage.selector_tables(iteration["selectors"])
        iteration["lineage"] = submissions_lineage.build(
            ledger, base, folder, iteration["track"], iteration["number"], tables
        )
        iteration["audit"] = submissions_audit.build(
            probes,
            register,
            iteration["number"],
            iteration["csv"]["sha256"],
            iteration["hypotheses"],
        )
        iterations.append(iteration)
    return {"iterations": iterations}


def find(iterations: list[dict[str, Any]], track: str, number: int) -> dict[str, Any]:
    """One iteration out of the payload, or a 404 naming what was asked for."""
    for iteration in iterations:
        if iteration["track"] == track and iteration["number"] == number:
            return iteration
    raise HTTPException(status_code=404, detail=f"no iteration {number} for track {track!r}")


def figure_path(root: Path, track: str, slug: str) -> Path:
    """The PNG behind one figure slug, or a 404. Both segments are validated first."""
    for segment in (track, slug):
        if not SEGMENT.match(segment):
            raise HTTPException(status_code=404, detail=f"not a figure name: {segment!r}")
    path = root / submissions_reader.FIGURES_DIR / track / f"{slug}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"no figure {slug!r} for track {track!r}")
    return path


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
        summary="one rendered figure from figures/<track>/, as PNG",
        response_class=FileResponse,
    )
    def submission_figure(track: str, number: int, slug: str) -> FileResponse:
        """One PNG out of ``figures/<track>/``.

        Bytes, not an envelope: an ``<img src>`` cannot read JSON. ``number`` is in the
        path so a figure URL identifies the iteration it illustrates even though the
        figures directory is per track; it is validated, not used to pick the file.
        """
        find(built().data["iterations"], track, number)
        return FileResponse(figure_path(base, track, slug), media_type="image/png")
