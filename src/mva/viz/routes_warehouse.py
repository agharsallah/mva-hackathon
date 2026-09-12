"""Routes backed by the PostgreSQL warehouse: the callset, the panel, the provenance.

Almost all read a derived table and answer in well under a second. Two exceptions, both
cached: ``/api/panel/locus``, the only route in the service that touches ``variants_raw``
and therefore filtered to one chromosome (see :mod:`mva.viz.queries` for why that
matters), and ``/api/catalog/tables``, which counts every row in both schemas.

``/api/panel/locus`` responses contain **real patient positions**. They are served to the
browser, which is the point, and they are cached under gitignored ``build/`` — but they
must never be written anywhere the repository can pick up.
"""

from fastapi import APIRouter, Query

from . import (
    catalog,
    phenotype,
    queries,
    refprovenance,
    routes_panel,
    routes_search,
    science,
    steps,
    steps_it2,
    submissions,
    track2,
)
from .cache import Cache
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
    "/callset/observed-expected": (queries.observed_expected, "pg.results.qc_observed_expected"),
    "/callset/funnel": (queries.candidate_funnel, "pg.results.candidate_funnel"),
    "/callset/zygosity-split": (queries.zygosity_split, "pg.results.stats_af"),
    "/callset/fields": (queries.vcf_fields, "pg.warehouse.vcf_fields"),
    "/panel/background": (queries.panel_background, "pg.results.panel_gene_background"),
    "/reads/yield": (queries.sequencing_yield, "pg.results.sequencing_yield"),
    "/provenance/lineage": (queries.lineage, "pg.warehouse.data_lineage"),
    "/provenance/derivations": (queries.derivations, "pg.results.derivation_runs"),
    "/provenance/sources": (queries.sources, "pg.warehouse.source_objects"),
    "/probe/ledger": (queries.probe_ledger, "pg.warehouse.probe_ledger"),
}

#: Tag → the tables it reads, for the ``/docs`` grouping and the overview's source string.
OVERVIEW_SOURCE = (
    "pg.results.stats_sn + stats_tstv + allele_balance_flags, "
    "pg.warehouse.filter_gt_counts + contig_counts + profile_scalars + "
    "source_objects + probe_ledger, s3 runs.parquet"
)

#: What the two catalogue endpoints read, for the envelope's ``source`` field.
CATALOG_OBJECTS_SOURCE = "pg.warehouse.source_objects + source_files"
CATALOG_TABLES_SOURCE = (
    "pg.information_schema.tables, pg.warehouse.warehouse_catalog + "
    "data_lineage, pg.results.derivation_runs, "
    "mva.viz.catalog_semantics"
)
CATALOG_COLUMNS_SOURCE = "pg.information_schema.columns + mva.viz.catalog_columns"

#: Cache key for the table catalogue. Named, not derived, because it takes no parameters.
CATALOG_TABLES_KEY = "catalog-tables"

#: What ``/provenance/reference`` reads: manifests on disk, no database at all.
REFERENCE_PROVENANCE_SOURCE = (
    "ressources/reference/*provenance.json + app/src/fixtures/data/**/_provenance.json"
)


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
        ``created_by`` names the verb that writes the table and whether it replaces or
        appends; ``why`` is the one sentence saying what the table is for. Both come from
        the registry in ``mva.viz.catalog_semantics`` and are **null** for a table it does
        not know — a state a hermetic test refuses to let a *declared* table reach.
        """
        entry = cache.get_or_build(CATALOG_TABLES_KEY, lambda: catalog.tables(settings), refresh)
        return cached(entry, CATALOG_TABLES_SOURCE)

    @api.get("/catalog/columns", response_model=Envelope, tags=["catalog"])
    def catalog_columns() -> dict:
        """Every column of every table in both managed schemas, with what it means.

        Live: ``information_schema.columns`` is metadata, so the whole warehouse's column
        list is one round trip over a few hundred rows (0.95–1.6 s over HTTP, much of it
        the ``ATTACH``) rather than a scan of anything. ``meaning`` is **null** wherever
        nothing in ``mva.viz.catalog_columns`` describes the column — rendered as a
        visible gap, never filled with a guess.
        """
        return live(catalog.columns(settings), CATALOG_COLUMNS_SOURCE)

    for path, (function, source) in TABLES.items():
        _add_table_route(api, path, function, source, settings)

    @api.get("/genome/density-bins", response_model=Envelope, tags=["genome"])
    def density_bins(
        chrom: str | None = Query(
            default=None,
            description='bare contig name as the callset spells it, e.g. "15"; '
            "omit for the whole genome",
        ),
    ) -> dict:
        """Variant count, PASS count, low-quality count and mean QUAL per 1 Mb bin.

        Precomputed by the ``variant_density_bins`` derivation — the request never scans
        the callset. 2,961 bins cover all 25 canonical contigs.
        """
        return live(queries.density_bins(settings, chrom), "pg.results.variant_density_bins")

    @api.get("/genome/baf-bins", response_model=Envelope, tags=["genome"])
    def baf_bins(
        chrom: str | None = Query(
            default=None,
            description='bare contig name as the callset spells it, e.g. "15"; '
            "omit for the whole genome",
        ),
    ) -> dict:
        """B-allele fraction and read depth of heterozygous PASS calls per 1 Mb bin.

        The karyogram view of allele balance: ``/genome/allele-balance`` averages a whole
        chromosome, which hides a shifted segment. Precomputed by the ``baf_bins``
        derivation, so the request never scans the callset. A bin with fewer than 20
        heterozygous calls carries ``low_confidence = true`` and must be rendered as
        unmeasured, not as signal.
        """
        return live(queries.baf_bins(settings, chrom), "pg.results.baf_bins")

    @api.get("/provenance/reference", response_model=Envelope, tags=["provenance"])
    def provenance_reference() -> dict:
        """Every committed reference table and offline fixture, and where it came from.

        The other three ``/provenance/*`` routes read ``warehouse.data_lineage``, which
        records *derivations*: which table was computed from which object, by which
        transform. Reference data has none of that — a gnomAD table, an HPO release, an
        Ensembl gene record and an AlphaFold model are **fetched**, so an edge claiming
        a transform produced them would be fabricated. What they have instead is a
        manifest committed beside the bytes, and this route is the list of those.

        Read off disk, so it needs no database and answers on a bare checkout. A
        directory that does not exist contributes no rows rather than an error: a
        checkout whose reference tables were never built has nothing to declare, which
        is a true statement about it.
        """
        return live(refprovenance.rows(), REFERENCE_PROVENANCE_SOURCE)

    routes_panel.add_routes(api, settings, cache)
    routes_search.add_routes(api, settings, cache)
    science.add_routes(api, settings)
    steps.add_routes(api, settings)
    steps_it2.add_routes(api, settings)
    phenotype.add_routes(api)
    submissions.add_routes(api, settings, cache)
    track2.add_routes(api, settings, cache)
    return api


def _add_table_route(api: APIRouter, path: str, function, source: str, settings) -> None:
    """Register one plain table read. A closure per route, so the loop variable is bound."""
    tag = path.strip("/").split("/")[0]

    @api.get(
        path, response_model=Envelope, tags=[tag], name=path.strip("/"), summary=f"read {source}"
    )
    def route() -> dict:
        return live(function(settings), source)
