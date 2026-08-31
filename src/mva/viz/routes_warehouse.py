"""Routes backed by the PostgreSQL warehouse: the callset, the panel, the provenance.

All but one read a derived table and answer in well under a second. The exception is
``/api/panel/locus``, the only route in the service that touches ``variants_raw``, and it
is both filtered to one chromosome and cached — see :mod:`mva.viz.queries` for why that
matters.

``/api/panel/locus`` responses contain **real patient positions**. They are served to the
browser, which is the point, and they are cached under gitignored ``build/`` — but they
must never be written anywhere the repository can pick up.
"""

from fastapi import APIRouter, HTTPException, Query

from . import queries
from .cache import Cache, safe_key
from .overview import overview
from .response import Envelope, cached, live

#: Endpoints whose payload is a plain table read, as ``route → (function, source)``.
#: Data, not code: a new chart over an existing table is one line here.
TABLES = {
    "/genome/allele-balance": (queries.allele_balance, "pg.results.allele_balance_flags"),
    "/genome/contig-density": (queries.contig_density, "pg.results.contig_density"),
    "/callset/filters": (queries.filters, "pg.results.filter_impact"),
    "/callset/genotypes": (queries.genotypes, "pg.warehouse.filter_gt_counts"),
    "/callset/depth-distribution": (queries.depth_distribution, "pg.results.stats_dp"),
    "/callset/substitutions": (queries.substitutions, "pg.results.stats_st"),
    "/callset/indel-lengths": (queries.indel_lengths, "pg.results.stats_idd"),
    "/callset/tstv": (queries.tstv, "pg.results.stats_tstv"),
    "/provenance/lineage": (queries.lineage, "pg.warehouse.data_lineage"),
    "/provenance/derivations": (queries.derivations, "pg.results.derivation_runs"),
    "/provenance/sources": (queries.sources, "pg.warehouse.source_objects"),
    "/probe/ledger": (queries.probe_ledger, "pg.warehouse.probe_ledger"),
}

#: Tag → the tables it reads, for the ``/docs`` grouping and the overview's source string.
OVERVIEW_SOURCE = ("pg.results.stats_sn + stats_tstv + allele_balance_flags, "
                   "pg.warehouse.filter_gt_counts + contig_counts + profile_scalars + "
                   "source_objects + probe_ledger, s3 runs.parquet")


def router(settings, cache: Cache) -> APIRouter:
    """Build the warehouse routes against one settings object and one cache."""
    api = APIRouter(prefix="/api")

    @api.get("/overview", response_model=Envelope, tags=["overview"])
    def get_overview(refresh: bool = False) -> dict:
        """Every headline number for the landing page, in one object.

        Nine small tables plus the read store's dimension table. Cached because it is
        nine round trips to a hosted database, not because any one of them is slow.
        """
        entry = cache.get_or_build("overview", lambda: overview(settings), refresh)
        return cached(entry, OVERVIEW_SOURCE)

    for path, (function, source) in TABLES.items():
        _add_table_route(api, path, function, source, settings)

    @api.get("/genome/density-bins", response_model=Envelope, tags=["genome"])
    def density_bins(chrom: str | None = Query(
            default=None,
            description="bare contig name as the callset spells it, e.g. \"15\"; "
                        "omit for the whole genome")) -> dict:
        """Variant count, PASS count, low-quality count and mean QUAL per 1 Mb bin.

        Precomputed by the ``variant_density_bins`` derivation — the request never scans
        the callset. 2,961 bins cover all 25 canonical contigs.
        """
        return live(queries.density_bins(settings, chrom),
                    "pg.results.variant_density_bins")

    @api.get("/panel/genes", response_model=Envelope, tags=["panel"])
    def panel_genes() -> dict:
        """The eight candidate genes: interval, density, PASS rate, and why each is here."""
        return live(queries.panel_genes(settings),
                    "pg.results.panel_gene_density + pg.warehouse.panel_variant_counts "
                    "+ ressources/data-profile/mva_panel_grch38.bed")

    @api.get("/panel/locus", response_model=Envelope, tags=["panel"])
    def panel_locus(gene: str = Query(description="panel gene symbol, e.g. BUB1B"),
                    refresh: bool = False) -> dict:
        """Every variant inside one candidate gene, with its genotype evidence.

        The one route that reads ``variants_raw``. It constrains ``chrom`` so the server
        skips the other contigs (~4.4 s), then caches the result.
        """
        try:
            key = safe_key("locus", gene)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail=str(bad)) from bad
        try:
            entry = cache.get_or_build(key, lambda: queries.locus(settings, gene),
                                       refresh)
        except LookupError as unknown:
            raise HTTPException(status_code=404,
                                detail=f"no panel gene {unknown.args[0]!r}") from unknown
        return cached(entry, "pg.warehouse.variants_raw (chrom pushdown)")

    return api


def _add_table_route(api: APIRouter, path: str, function, source: str, settings) -> None:
    """Register one plain table read. A closure per route, so the loop variable is bound."""
    tag = path.strip("/").split("/")[0]

    @api.get(path, response_model=Envelope, tags=[tag], name=path.strip("/"),
             summary=f"read {source}")
    def route() -> dict:
        return live(function(settings), source)
