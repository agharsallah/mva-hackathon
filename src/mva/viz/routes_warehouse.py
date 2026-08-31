"""Routes backed by the PostgreSQL warehouse: the callset, the panel, the provenance.

Almost all read a derived table and answer in well under a second. Two exceptions, both
cached: ``/api/panel/locus``, the only route in the service that touches ``variants_raw``
and therefore filtered to one chromosome (see :mod:`mva.viz.queries` for why that
matters), and ``/api/catalog/tables``, which counts every row in both schemas.

``/api/panel/locus`` responses contain **real patient positions**. They are served to the
browser, which is the point, and they are cached under gitignored ``build/`` — but they
must never be written anywhere the repository can pick up.
"""

from fastapi import APIRouter, HTTPException, Query

from . import catalog, queries
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
    "/callset/observed-expected": (queries.observed_expected,
                                   "pg.results.qc_observed_expected"),
    "/provenance/lineage": (queries.lineage, "pg.warehouse.data_lineage"),
    "/provenance/derivations": (queries.derivations, "pg.results.derivation_runs"),
    "/provenance/sources": (queries.sources, "pg.warehouse.source_objects"),
    "/probe/ledger": (queries.probe_ledger, "pg.warehouse.probe_ledger"),
}

#: Tag → the tables it reads, for the ``/docs`` grouping and the overview's source string.
OVERVIEW_SOURCE = ("pg.results.stats_sn + stats_tstv + allele_balance_flags, "
                   "pg.warehouse.filter_gt_counts + contig_counts + profile_scalars + "
                   "source_objects + probe_ledger, s3 runs.parquet")

#: What the two catalogue endpoints read, for the envelope's ``source`` field.
CATALOG_OBJECTS_SOURCE = "pg.warehouse.source_objects + source_files"
CATALOG_TABLES_SOURCE = ("pg.information_schema.tables, pg.warehouse.warehouse_catalog + "
                         "data_lineage, pg.results.derivation_runs")

#: Cache key for the table catalogue. Named, not derived, because it takes no parameters.
CATALOG_TABLES_KEY = "catalog-tables"


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

    @api.get("/catalog/objects", response_model=Envelope, tags=["catalog"])
    def catalog_objects() -> dict:
        """Every object in the delivery, with what it holds and where it lives.

        Live: twelve rows off an inventory that ``mva-warehouse source-check`` replaces
        wholesale, so caching it would only hide a fresh survey. ``first_uploaded_at`` is
        **null** for an object with no upload-ledger row — one fetched straight from the
        publisher, or one that predates the ledger.
        """
        return live(catalog.objects(settings), CATALOG_OBJECTS_SOURCE)

    @api.get("/catalog/tables", response_model=Envelope, tags=["catalog"])
    def catalog_tables(refresh: bool = False) -> dict:
        """Every table in both managed schemas, with its description, size and lineage.

        ``rows`` is an **exact** ``count(*)``, not an estimate — see
        :func:`mva.viz.catalog._counts` for why the cheap estimate is unusable here. That
        costs seconds over the whole warehouse, which is what the cache is for.
        ``produced_at``, ``source_kind``, ``source_ref`` and ``tool`` are **null** for a
        table with no lineage edge; the ledgers and the staged tables have none.
        """
        entry = cache.get_or_build(CATALOG_TABLES_KEY,
                                   lambda: catalog.tables(settings), refresh)
        return cached(entry, CATALOG_TABLES_SOURCE)

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

    @api.get("/panel/constraint", response_model=Envelope, tags=["panel"])
    def panel_constraint() -> dict:
        """Each candidate gene against gnomAD constraint and ClinVar's verdicts.

        A missing gnomAD row leaves the constraint columns **null**, never zero — the
        constraint file covers autosomes only, and an absent gene is not a tolerant one.
        """
        return live(queries.panel_constraint(settings),
                    "pg.results.panel_gene_constraint "
                    "+ ressources/data-profile/mva_panel_grch38.bed")

    @api.get("/panel/annotations", response_model=Envelope, tags=["panel"])
    def panel_annotations(gene: str | None = Query(
            default=None,
            description="panel gene symbol, e.g. BUB1B; omit for every annotated "
                        "allele in the panel")) -> dict:
        """Every VEP-annotated panel allele with the callset's genotype evidence for it.

        Live: the join to the callset is already done by the ``panel_candidates``
        derivation, so the request reads a few hundred rows.
        """
        try:
            found = queries.panel_candidates(settings, gene)
        except LookupError as unknown:
            raise HTTPException(status_code=404,
                                detail=f"no panel gene {unknown.args[0]!r}") from unknown
        return live(found, "pg.results.panel_candidates")

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
