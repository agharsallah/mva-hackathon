"""Turning a *name* — a gene symbol or an rsID — into a window of the callset.

:mod:`mva.viz.search` decides what a query *is*. This module answers the harder half: a
name is not coordinates, and the honest answer to "where is X" has three outcomes, not
two — **here**, **nowhere anyone knows** (404), and **a real place this callset never
called** (resolved, zero rows). Collapsing the last two is the failure this module exists
to prevent, because a search box that shows an empty table for both teaches the user that
absence means "not sequenced" when it may mean "misspelt".

## The rsID bake-off, measured live

Two mechanisms were timed against the hosted warehouse and the public Ensembl REST server:

================================ ================ ==========================================
mechanism                        cost             what it can say
================================ ================ ==========================================
scan ``variants_raw.id``         0.7–1.4 s        "it is in the callset, here"; silent
                                                  otherwise
Ensembl ``variation/human/rs…``  0.5–0.9 s cold,  "here is where it is", or 400 with
                                 0.02–0.09 s warm ``{"error": "… not found for human"}``
================================ ================ ==========================================

The scan being fast at all was the surprise — ``variants_raw`` carries **no index**
(verified against ``pg_indexes``: zero rows), so this is a sequential pass over 5,012,204
rows, and it costs under a second only because PostgreSQL holds the table in its buffer
cache and ships back one row.

Neither mechanism alone is enough, so **both run, in order**:

1. **The callset first.** 4,408,823 of the 5,012,204 records carry an rsID, so the common
   case hits, costs no network, and keeps working while Ensembl is down.
2. **Ensembl only on a miss**, purely to separate "dbSNP has never heard of this" from
   "real variant, absent from this callset".

Every non-``.`` id in this callset is a bare ``rs…`` and none packs a second name behind a
``;`` (both counted: 0), so exact match is the correct test rather than a ``LIKE`` that
could not use an index even if one existed.

## Gene symbols

The committed panel BED is consulted first, for two reasons: it is the case's own source
of truth and needs no third party, and its intervals are **padded ±20 kb**, which is the
window every other panel number in this repo was measured over. Answering a panel gene
from Ensembl instead would quietly return a *narrower* window than the Panel page shows
for the same name. Everything off-panel goes to Ensembl ``lookup/symbol`` (measured 5.0 s
cold, 0.06 s warm) behind the same disk cache the gene-structure route uses.

**The browser never calls Ensembl** — same three reasons as
:mod:`mva.viz.genestructure`: no usable CORS header, key discipline belongs on one server,
and a user's query is not something to hand a third party's logs from every tab.
"""

from typing import Any

import httpx

from ..pipeline.variant import to_vcf_contig
from ..warehouse.settings import Postgres
from . import queries, search
from .genestructure import ENSEMBL_BASE, EnsemblError
from .search import CONTIG_RE, FLANK, NotFound, Resolved, check_span

#: Provenance strings, one per resolver path, so the page can say *how* it resolved.
SOURCE_PANEL = ("ressources/data-profile/mva_panel_grch38.bed "
                "via pg.warehouse.mva_panel_grch38")
SOURCE_CALLSET = "pg.warehouse.variants_raw (id scan)"
SOURCE_ENSEMBL_SYMBOL = "ensembl rest /lookup/symbol/homo_sapiens"
SOURCE_ENSEMBL_RSID = "ensembl rest /variation/human"


def resolve(query: str, settings: Postgres | None = None, *,
            client: httpx.Client | None = None, base_url: str | None = None,
            timeout: float = 20.0) -> Resolved:
    """Turn one search string into a window. Raises rather than guessing.

    A region never opens a connection of any kind — it is parsed and returned — so the
    HTTP client is built only on the two paths that might need it. ``base_url`` defaults
    to :data:`ENSEMBL_BASE` *at call time* rather than in the signature, so a test can
    point the whole service at an unroutable host and exercise the real outage path.
    """
    base_url = base_url or ENSEMBL_BASE
    kind = search.classify(query)
    if kind == "region":
        return search.region_query(query)

    own = client is None
    client = client or httpx.Client(timeout=timeout)
    try:
        if kind == "rsid":
            return resolve_rsid(query.strip(), settings, client, base_url)
        return resolve_gene(query.strip(), settings, client, base_url)
    finally:
        if own:
            client.close()


def resolve_gene(symbol: str, settings: Postgres | None, client: httpx.Client,
                 base_url: str) -> Resolved:
    """A gene symbol's interval: the candidate panel first, then Ensembl."""
    panel = panel_gene(settings, symbol)
    if panel is not None:
        chrom, start, end = panel
        return Resolved("gene", chrom, start, end,
                        label=f"{symbol.upper()} — {chrom}:{start:,}-{end:,}",
                        source=SOURCE_PANEL,
                        note="candidate-panel interval, padded 20 kb each side")

    body = _get(client, base_url, f"/lookup/symbol/homo_sapiens/{symbol}", symbol)
    chrom = to_vcf_contig(str(body.get("seq_region_name") or ""))
    start, end = _int(body.get("start")), _int(body.get("end"))
    if not chrom or start is None or end is None:
        raise NotFound(f"Ensembl returned no interval for {symbol!r}")
    check_span(start, end)
    return Resolved("gene", chrom, start, end,
                    label=f"{body.get('display_name') or symbol} — "
                          f"{chrom}:{start:,}-{end:,}",
                    source=SOURCE_ENSEMBL_SYMBOL,
                    note=f"Ensembl gene span for {body.get('id')}, unpadded — narrower "
                         f"than the ±20 kb the candidate panel uses")


def panel_gene(settings: Postgres | None, symbol: str) -> tuple[str, int, int] | None:
    """A candidate-panel gene's interval, or ``None`` when the panel does not carry it.

    Delegates to :func:`mva.viz.queries.gene_region`, the existing owner of "panel gene →
    interval", rather than reading the BED a second time. A second reader of that file is
    exactly the drift ``docs/step-0/notes/chr-prefix-bridge.md`` warns about.
    """
    if settings is None:
        return None
    try:
        return queries.gene_region(settings, symbol)
    except LookupError:
        return None


def resolve_rsid(rsid: str, settings: Postgres | None, client: httpx.Client,
                 base_url: str) -> Resolved:
    """An rsID's window: the callset's own ``id`` column first, then Ensembl.

    Both stages exist because they answer different questions — see the bake-off in the
    module docstring. The callset is authoritative for "it is here" and cannot speak at
    all for "it is not"; Ensembl closes that gap.
    """
    name = rsid.lower()
    hit = callset_rsid(settings, name) if settings is not None else None
    if hit is not None:
        chrom, at = hit
        return Resolved("rsid", chrom, max(at - FLANK, 1), at + FLANK,
                        label=f"{name} — {chrom}:{at:,}",
                        source=SOURCE_CALLSET,
                        note=f"the callset names this record itself; window is "
                             f"±{FLANK:,} bp for context")

    body = _get(client, base_url, f"/variation/human/{name}", name)
    mapping = grch38_mapping(body)
    if mapping is None:
        raise NotFound(f"Ensembl knows {name} but places it on no GRCh38 chromosome")
    chrom, at = mapping
    return Resolved("rsid", chrom, max(at - FLANK, 1), at + FLANK,
                    label=f"{name} — {chrom}:{at:,}",
                    source=SOURCE_ENSEMBL_RSID,
                    note=f"no record in the callset carries this id — the position comes "
                         f"from dbSNP, so an empty table below means the site was never "
                         f"called, not that the id is wrong. Window is ±{FLANK:,} bp.")


def callset_rsid(settings: Postgres, rsid: str) -> tuple[str, int] | None:
    """``(chrom, pos)`` for an rsID the callset carries, or ``None``.

    The first record wins: dbSNP names a *site*, and a multiallelic site is one row here.
    """
    found = queries.fetch(settings,
                          "SELECT chrom, pos FROM pg.warehouse.variants_raw "
                          "WHERE id = ? LIMIT 1", [rsid])
    if not found:
        return None
    return str(found[0]["chrom"]), int(found[0]["pos"])


def grch38_mapping(body: Any) -> tuple[str, int] | None:
    """The GRCh38 chromosome placement out of a ``/variation/human`` reply.

    dbSNP maps a variant onto patches and scaffolds as well as chromosomes, so the
    assembly and the coordinate system are both checked rather than taking
    ``mappings[0]`` — which on a patched region is the wrong place by megabases.
    """
    for mapping in (body or {}).get("mappings") or []:
        if str(mapping.get("assembly_name") or "") != "GRCh38":
            continue
        if str(mapping.get("coord_system") or "chromosome") != "chromosome":
            continue
        chrom = to_vcf_contig(str(mapping.get("seq_region_name") or ""))
        start = _int(mapping.get("start"))
        if chrom and CONTIG_RE.match(chrom) and start is not None:
            return chrom, start
    return None


# ── Ensembl, with "no such name" told apart from "the service is down" ───────────────

def _get(client: httpx.Client, base_url: str, path: str, name: str) -> Any:
    """One Ensembl GET. A 400/404 naming the query is :class:`NotFound`, not an outage.

    This is the one behaviour :func:`mva.viz.genestructure._get` cannot be reused for.
    There, every non-200 is an :class:`EnsemblError`, because every id it sends came from
    the committed panel and a rejection really *is* a fault. Here the name was typed by a
    user, so ``400 {"error": "rs99999999 not found for human"}`` — Ensembl's verified
    reply for an unknown rsID, and it uses **400**, not 404 — is the normal answer to a
    normal question, and the page must say "no such id" rather than "Ensembl is down".
    """
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError as error:
        raise EnsemblError(f"GET {url}: {type(error).__name__}: {error}") from error
    if response.status_code in (400, 404):
        raise NotFound(f"Ensembl does not know {name!r}: "
                       f"{_error_text(response) or response.status_code}")
    if response.status_code != 200:
        raise EnsemblError(f"GET {url} -> {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as bad:
        raise EnsemblError(f"GET {url}: reply was not JSON") from bad


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:120]
    return str(body.get("error") or "")[:200] if isinstance(body, dict) else ""


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
