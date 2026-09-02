"""The two HTTP routes behind the universal search box.

``GET /api/search?q=`` resolves a typed query to a window; ``GET /api/callset/region``
reads that window out of the raw callset. They are deliberately **two** requests rather
than one: resolution is cheap, cacheable and safe to share, while the region read is the
only user-steerable path in the service that touches ``variants_raw`` and carries real
patient positions. Keeping them apart means the page can show *what the query resolved to,
and by which resolver* before, and independently of, paying for the scan — and it means a
shareable ``/search?q=…`` URL replays through the same two steps.

Four failure modes, each with its own status, because collapsing them is what makes a
search box feel broken:

===== =============================================================================
422   the query is not one of the three forms, or the window is wider than the cap
404   the shape is valid but no authority knows the name
502   Ensembl was unreachable or refused — never a fabricated coordinate
200   resolved; the table below may still be empty, and that is a *finding*
===== =============================================================================
"""

from fastapi import APIRouter, HTTPException, Query

from ..warehouse.settings import Postgres
from . import search, search_resolve
from .cache import Cache, InvalidKey, safe_key
from .genestructure import EnsemblError
from .response import Envelope, cached, live


def add_routes(api: APIRouter, settings: Postgres, cache: Cache) -> None:
    """Register the search routes on the warehouse router.

    Mounted from :mod:`mva.viz.routes_warehouse` the same way the science routes are, so
    the whole ``/api`` surface still comes off one router and one prefix.
    """

    @api.get("/search", response_model=Envelope, tags=["search"])
    def search_endpoint(
        q: str = Query(
            description="a gene symbol (BUB1B), a region "
            "(15:40100000-40200000, either chr spelling) "
            "or an rsID (rs137852899)"
        ),
        refresh: bool = False,
    ) -> dict:
        """Resolve one typed query to a window of the callset, saying how it resolved.

        Answers ``{kind, chrom, start, end, label, source, note}``. ``kind`` is
        ``region``, ``gene`` or ``rsid``; ``chrom`` is **bare**, as the callset spells it;
        ``source`` names the resolver that answered — the query string itself, the
        candidate panel, the callset's own ``id`` column, or Ensembl — and is also the
        envelope's ``source``. ``note`` is a caveat the UI must render and is **null**
        when there is none.

        A region is parsed and returned with **no lookup at all**. A gene symbol tries the
        candidate panel (±20 kb padded, matching every other panel number in this repo)
        before Ensembl. An rsID scans the callset's ``id`` column first and only asks
        Ensembl on a miss — which is how *"unknown id"* (**404**) stays distinct from
        *"real variant this callset never called"* (**200**, then zero rows). Ensembl
        unreachable is a **502**, never a guessed position.
        """
        return _resolve(q, settings, cache, refresh)

    @api.get("/callset/region", response_model=Envelope, tags=["search"])
    def region_endpoint(
        chrom: str = Query(description='contig, either spelling: "15" or "chr15"'),
        start: int = Query(ge=1, description="1-based inclusive start"),
        end: int = Query(ge=1, description="1-based inclusive end"),
        refresh: bool = False,
    ) -> dict:
        """Every callset record in an arbitrary window, with its genotype evidence.

        The second route in the service that reads ``variants_raw``, and the only one a
        user aims. It constrains ``chrom`` first (measured 1.7 s against 5.5 s for the
        same 100 kb window unconstrained) and caches the answer on disk.

        ``data`` is ``{chrom, start, end, n, variants}`` — the echo is there so a cached
        payload still says which window it is. Each variant is ``{pos, id, ref, alt, qual,
        filter, gt, dp, ad_ref, ad_alt, vaf, gq}``. ``id`` is the record's dbSNP name and
        is **null** where the VCF wrote ``.``. ``ad_alt`` and ``vaf`` are **null** at a
        ``1/2`` multiallelic site, the same convention as ``/api/panel/locus``: a blank is
        a question, a halved VAF is a wrong answer.

        A window wider than the cap is a **422** naming the cap. The cap is a payload
        guard, not a latency one — the unindexed raw layer answers a whole chromosome in
        the same ~2 s and then weighs 11 MB over 101,130 rows.

        **This payload contains real patient positions.** It is cached under gitignored
        ``build/`` and must never be written anywhere the repository can pick it up.
        """
        return _region(settings, cache, chrom, start, end, refresh)


# ── the two bodies, kept out of the closures so they stay testable ───────────────────


def _resolve(q: str, settings: Postgres, cache: Cache, refresh: bool) -> dict:
    """Resolve, caching only the paths that cost a lookup."""
    with _translated():
        kind = search.classify(q)
        if kind == "region":
            # Nothing was consulted, so there is nothing to cache and nothing to stale.
            found = search.region_query(q).as_dict()
            return live(found, found["source"])
        key = _search_key(kind, q)
        build = lambda: search_resolve.resolve(q, settings).as_dict()  # noqa: E731
        if key is None:
            found = build()
            return live(found, found["source"])
        entry = cache.get_or_build(key, build, refresh)
        return cached(entry, entry.data["source"])


def _region(
    settings: Postgres, cache: Cache, chrom: str, start: int, end: int, refresh: bool
) -> dict:
    with _translated():
        bare = search.normalise_contig(chrom)
        search.check_span(start, end)
        key = safe_key("region", bare, start, end)
        entry = cache.get_or_build(key, lambda: search.region(settings, bare, start, end), refresh)
        return cached(entry, search.REGION_SOURCE)


def _search_key(kind: str, q: str) -> str | None:
    """A cache key for a resolution, or ``None`` when the query cannot make a safe one.

    Not caching is always a correct answer here — the resolvers are seconds, not minutes —
    so a symbol carrying a ``.`` (``C1orf109.1`` and friends) simply resolves live rather
    than being rewritten into a key that could collide with a different symbol.
    """
    try:
        return safe_key("search", kind, q.strip().upper())
    except InvalidKey:
        return None


class _translated:
    """Map this module's four failure modes onto their status codes, in one place."""

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if error is None:
            return False
        if isinstance(error, (search.Unparseable, search.SpanTooLarge)):
            raise HTTPException(status_code=422, detail=str(error)) from error
        if isinstance(error, search.NotFound):
            raise HTTPException(status_code=404, detail=str(error)) from error
        if isinstance(error, EnsemblError):
            raise HTTPException(status_code=502, detail=str(error)) from error
        return False
