"""The search grammar: what a typed query means, and what reading that window costs.

Every other panel in the app starts from a list the server chose — the eight panel genes,
the 25 contigs, the 38 tables. The search box is the one place a *user-chosen* locus
enters the system, so two questions have to be answered that the rest of the API never
asks: **what did the user mean**, and **what does it cost to look there**. This module
owns both. Turning a *name* into coordinates lives next door in
:mod:`mva.viz.search_resolve`.

## What the user meant

Three forms, told apart by shape alone before anything is queried or fetched:

* ``15:40100000-40200000`` (either ``chr`` spelling, commas and spaces tolerated) — a
  **region**. Parsed, never looked up: the query already *is* the answer. A bare
  ``15:40100000`` is a point, widened by :data:`FLANK`.
* ``BUB1B`` — a **gene symbol**.
* ``rs137852899`` — an **rsID**, dbSNP's stable name for one variant site.

Anything else is refused by name rather than guessed at.

## What it costs, measured live against the hosted warehouse

``variants_raw`` is 5,012,204 rows of text with **no index of any kind** — verified, not
assumed: ``SELECT … FROM pg_indexes WHERE tablename = 'variants_raw'`` returns zero rows.
Every read here is therefore a sequential scan, and the surprise is that the scan is *not*
the cost. PostgreSQL holds the table in its buffer cache, so scan time is flat and the
wire is the bottleneck:

===================== ============ ============ ==============
window on one contig  latency      rows         JSON payload
===================== ============ ============ ==============
1 kb                  1.6 s        6            <1 kB
100 kb                1.7–2.0 s    80           ~9 kB
1 Mb                  1.4–1.8 s    1,143        0.13 MB
5 Mb                  1.4–2.7 s    5,766        0.64 MB
102 Mb (a whole arm+) 2.2 s        101,130      **11.3 MB**
===================== ============ ============ ==============

So :data:`MAX_SPAN` is **not** a latency guard. A whole-chromosome answer costs the same
second and a half and then hands the browser eleven megabytes and a hundred thousand table
rows. 5 Mb is the widest window that stays under a megabyte of JSON, and it comfortably
contains any human gene (the longest, RBFOX1, is ~2.5 Mb).

Dropping the ``chrom`` constraint costs 5.5 s instead of 1.7 s for the same 100 kb window,
so the contig is always pushed down first, exactly as ``/api/panel/locus`` does.

**The payload holds real patient positions.** Same rule as the locus route: served to the
browser, cached only under gitignored ``build/``, never written where git can see it.
"""

import re
from dataclasses import asdict, dataclass
from typing import Any

from ..pipeline.variant import to_vcf_contig
from ..warehouse.settings import Postgres
from . import genotype, queries

#: Largest window the region endpoint will read, in base pairs. A payload guard, not a
#: latency one — see the measurements in the module docstring.
MAX_SPAN = 5_000_000

#: Padding put around a single point (an rsID, or a bare ``chrom:pos``). One record is not
#: a table; 1 kb of context is a handful of records here and reads as a neighbourhood.
FLANK = 1_000

#: Numbers get pasted with separators. Stripped before the region patterns are tried,
#: which is why the patterns themselves only have to know about digits.
_SEPARATORS = re.compile(r"[,_\s]")

#: The canonical contigs, spelled out rather than ``\d{1,2}``: this genome has 22
#: autosomes, so ``chr99`` is a typo to reject, not a contig to scan for.
_CONTIG = r"(?:chr)?(?:[1-9]|1\d|2[0-2]|X|Y|MT|M)"

#: ``chr15:40100000-40200000`` and its spellings, against the separator-stripped query.
#: ``..`` and an en-dash are accepted because both get pasted out of papers and browsers.
REGION_RE = re.compile(
    rf"^(?P<chrom>{_CONTIG})"
    r":(?P<start>\d+)(?:-|–|\.\.)(?P<end>\d+)$", re.IGNORECASE)

#: ``chr15:40100000`` — a single point, widened by :data:`FLANK`.
POINT_RE = re.compile(rf"^(?P<chrom>{_CONTIG}):(?P<pos>\d+)$", re.IGNORECASE)

#: dbSNP's stable name for a variant site. Case-insensitive because people type ``RS…``.
RSID_RE = re.compile(r"^rs(\d+)$", re.IGNORECASE)

#: A HGNC-shaped gene symbol. Deliberately permissive — Ensembl is the authority on
#: whether a symbol exists, and this only has to reject what is plainly not one.
SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,30}$")

#: A canonical contig name, in either prefix convention.
CONTIG_RE = re.compile(rf"^{_CONTIG}$", re.IGNORECASE)

#: What the region endpoint reports as its provenance.
REGION_SOURCE = "pg.warehouse.variants_raw (chrom pushdown)"

#: Provenance of a region query: nothing was looked up, the string said it.
SOURCE_QUERY = "the query string (parsed, no lookup)"

#: The three forms, as the ``/docs`` page and the placeholder text spell them.
EXAMPLES = ("BUB1B", "15:40100000-40200000", "rs137852899")


class Unparseable(ValueError):
    """The query is not a region, a gene symbol or an rsID. Never guessed at."""


class SpanTooLarge(ValueError):
    """The requested window is wider than :data:`MAX_SPAN`."""


class NotFound(LookupError):
    """The query has a valid shape, but nothing anywhere knows the name."""


@dataclass(frozen=True)
class Resolved:
    """Where a query points, and which resolver said so."""

    kind: str
    chrom: str
    start: int
    end: int
    label: str
    source: str
    #: A caveat the page must show, or ``None``. Never a place to hide a failure.
    note: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# ── classification ───────────────────────────────────────────────────────────────────

def classify(query: str) -> str:
    """``'region'``, ``'rsid'`` or ``'gene'`` — by shape alone, with nothing looked up.

    Order matters and is not arbitrary: a region and an rsID have unmistakable syntax, so
    anything left that *could* be a symbol is treated as one and handed to a resolver that
    can say "no such gene" with authority.
    """
    text = (query or "").strip()
    if not text:
        raise Unparseable("empty query")
    compact = _SEPARATORS.sub("", text)
    if REGION_RE.match(compact) or POINT_RE.match(compact):
        return "region"
    if RSID_RE.match(text):
        return "rsid"
    if SYMBOL_RE.match(text):
        return "gene"
    raise Unparseable(
        f"{text!r} is not a gene symbol ({EXAMPLES[0]}), a region ({EXAMPLES[1]}) "
        f"or an rsID ({EXAMPLES[2]})")


def parse_region(query: str) -> tuple[str, int, int]:
    """A region query as ``(bare chrom, start, end)``. A bare point is widened by FLANK.

    The contig goes through :func:`~mva.pipeline.variant.to_vcf_contig`, the repo's single
    owner of the ``chr`` bridge, so both spellings land on the one the callset uses.
    """
    compact = _SEPARATORS.sub("", (query or "").strip())
    span = REGION_RE.match(compact)
    if span:
        start, end = int(span["start"]), int(span["end"])
        if start > end:
            raise Unparseable(f"start {start:,} is past end {end:,}")
        return to_vcf_contig(span["chrom"]), max(start, 1), end
    point = POINT_RE.match(compact)
    if point:
        at = int(point["pos"])
        return to_vcf_contig(point["chrom"]), max(at - FLANK, 1), at + FLANK
    raise Unparseable(f"{query!r} is not a region")


def check_span(start: int, end: int) -> None:
    """Refuse a window wider than :data:`MAX_SPAN`, naming the cap in the message."""
    width = end - start + 1
    if width > MAX_SPAN:
        raise SpanTooLarge(
            f"{width:,} bp is wider than the {MAX_SPAN:,} bp cap. The raw callset layer "
            f"has no index, so a whole chromosome answers in the same ~2 s but weighs "
            f"11 MB over 101,130 rows; narrow the region and search again.")


def region_query(query: str) -> Resolved:
    """A region query, resolved without touching anything. The cheap path."""
    chrom, start, end = parse_region(query)
    check_span(start, end)
    return Resolved("region", chrom, start, end,
                    label=f"{chrom}:{start:,}-{end:,}", source=SOURCE_QUERY)


# ── the region read ──────────────────────────────────────────────────────────────────

def region(settings: Postgres, chrom: str, start: int, end: int) -> dict:
    """Every callset record in one window, with its genotype evidence decoded.

    The same shape as :func:`mva.viz.queries.locus` plus the record's ``id`` — its dbSNP
    name — which the locus route has no use for and this one is often searched *by*.
    ``chrom`` is constrained first so PostgreSQL skips the other 24 contigs: measured
    1.7 s against 5.5 s for the same window unconstrained.
    """
    bare = normalise_contig(chrom)
    start, end = max(int(start), 1), int(end)
    if start > end:
        raise Unparseable(f"start {start:,} is past end {end:,}")
    check_span(start, end)

    found = queries.fetch(settings, """
        SELECT pos, id, ref, alt, qual, filter, format, sample_call
        FROM pg.warehouse.variants_raw
        WHERE chrom = ? AND CAST(pos AS BIGINT) BETWEEN ? AND ?
        ORDER BY CAST(pos AS BIGINT)
    """, [bare, start, end])

    return {"chrom": bare, "start": start, "end": end, "n": len(found),
            "variants": [_variant(row) for row in found]}


def normalise_contig(chrom: str) -> str:
    """A contig name in the callset's spelling, or :class:`Unparseable`."""
    if not CONTIG_RE.match((chrom or "").strip()):
        raise Unparseable(f"{chrom!r} is not a contig this callset could spell "
                          f"(1..22, X, Y, M/MT, with or without a chr prefix)")
    return to_vcf_contig(chrom.strip())


def _variant(row: dict) -> dict:
    call = genotype.decode(row.get("format"), row.get("sample_call"))
    return {
        "pos": int(row["pos"]),
        # '.' is the VCF's "no name here"; null renders as the gap it is.
        "id": None if row["id"] in (None, ".", "") else row["id"],
        "ref": row["ref"],
        # Multiallelic ALT stays comma-packed, exactly as /api/panel/locus keeps it.
        "alt": row["alt"],
        "qual": _float(row["qual"]),
        "filter": row["filter"],
        **call.as_dict(),
    }


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
