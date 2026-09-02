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

from . import catalog, genestructure, phase, queries, routes_search, science
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

    @api.get("/panel/genes", response_model=Envelope, tags=["panel"])
    def panel_genes() -> dict:
        """The eight candidate genes: interval, density, PASS rate, and why each is here."""
        return live(
            queries.panel_genes(settings),
            "pg.results.panel_gene_density + pg.warehouse.panel_variant_counts "
            "+ ressources/data-profile/mva_panel_grch38.bed",
        )

    @api.get("/panel/constraint", response_model=Envelope, tags=["panel"])
    def panel_constraint() -> dict:
        """Each candidate gene against gnomAD constraint and ClinVar's verdicts.

        A missing gnomAD row leaves the constraint columns **null**, never zero — the
        constraint file covers autosomes only, and an absent gene is not a tolerant one.
        """
        return live(
            queries.panel_constraint(settings),
            "pg.results.panel_gene_constraint + ressources/data-profile/mva_panel_grch38.bed",
        )

    @api.get("/panel/annotations", response_model=Envelope, tags=["panel"])
    def panel_annotations(
        gene: str | None = Query(
            default=None,
            description="panel gene symbol, e.g. BUB1B; omit for every annotated "
            "allele in the panel",
        ),
    ) -> dict:
        """Every VEP-annotated panel allele with the callset's genotype evidence for it.

        Live: the join to the callset is already done by the ``panel_candidates``
        derivation, so the request reads a few hundred rows.
        """
        try:
            found = queries.panel_candidates(settings, gene)
        except LookupError as unknown:
            raise HTTPException(
                status_code=404, detail=f"no panel gene {unknown.args[0]!r}"
            ) from unknown
        return live(found, "pg.results.panel_candidates")

    @api.get("/panel/locus", response_model=Envelope, tags=["panel"])
    def panel_locus(
        gene: str = Query(description="panel gene symbol, e.g. BUB1B"), refresh: bool = False
    ) -> dict:
        """Every variant inside one candidate gene, with its genotype evidence.

        The one route that reads ``variants_raw``. It constrains ``chrom`` so the server
        skips the other contigs (~4.4 s), then caches the result.
        """
        try:
            key = safe_key("locus", gene)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail=str(bad)) from bad
        try:
            entry = cache.get_or_build(key, lambda: queries.locus(settings, gene), refresh)
        except LookupError as unknown:
            raise HTTPException(
                status_code=404, detail=f"no panel gene {unknown.args[0]!r}"
            ) from unknown
        return cached(entry, "pg.warehouse.variants_raw (chrom pushdown)")

    @api.get("/panel/gene-structure", response_model=Envelope, tags=["panel"])
    def panel_gene_structure(
        gene: str = Query(description="panel gene symbol, e.g. BUB1B"), refresh: bool = False
    ) -> dict:
        """One gene's exons, protein domains and protein-altering alleles.

        Three Ensembl REST calls behind a disk cache, because gene structure is static
        reference data. A ``502`` means Ensembl was unreachable or refused — never a
        fixture-shaped stand-in. Unlike ``/panel/locus`` this payload carries **no**
        patient genomic coordinate: alleles are placed in amino-acid space.
        """
        try:
            key = safe_key("gene-structure", gene)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail=str(bad)) from bad
        try:
            entry = cache.get_or_build(
                key, lambda: genestructure.structure(gene, settings), refresh
            )
        except LookupError as unknown:
            raise HTTPException(
                status_code=404, detail=f"no panel gene {unknown.args[0]!r}"
            ) from unknown
        except genestructure.EnsemblError as down:
            raise HTTPException(status_code=502, detail=str(down)) from down
        return cached(entry, genestructure.SOURCE)

    @api.get("/panel/het-pairs", response_model=Envelope, tags=["panel"])
    def panel_het_pairs(gene: str = Query(description="panel gene symbol, e.g. BUB1B")) -> dict:
        """One gene's compound-heterozygous pair matrix: the axis, and what phase resolves.

        ``variants`` is one row per heterozygous PASS ALT allele, ordered by position —
        that order **is** both axes of the matrix, so a cell is addressed by index.
        ``pairs`` holds only the cells physical phasing resolves; short-read phasing
        reaches ~300 bp, so on a real gene that is single digits out of thousands and
        every unlisted cell is *unknown*. ``summary`` carries the counts that make the
        emptiness legible instead of invisible.
        """
        try:
            variants = queries.het_pairs(settings, gene)
        except LookupError as unknown:
            raise HTTPException(
                status_code=404, detail=f"no panel gene {unknown.args[0]!r}"
            ) from unknown
        return live(phase.matrix(gene, variants), "pg.results.panel_het_pairs")

    @api.get("/panel/clinvar-presence", response_model=Envelope, tags=["panel"])
    def panel_clinvar_presence(
        gene: str | None = Query(
            default=None, description="panel gene symbol, e.g. BUB1B; omit for all eight"
        ),
    ) -> dict:
        """Every ClinVar pathogenic / likely-pathogenic panel site, present here or not.

        The inward direction of the reference join: instead of asking what the world knows
        about an allele the callset has, it asks whether the callset contains a site the
        world has already classified. ``summary`` is one row per panel gene — a gene with
        no P/LP record at all still appears, with ``n_plp = 0``. ``sites`` lists only the
        rows that are **present** or **uncomparable** (ClinVar states no alternate
        allele); measured absences live in the counts, because two thousand rows of
        "nothing called here" add nothing to them.

        ``present`` is a **lower bound**. Matching is exact on (chrom, pos, ref) plus ALT
        list membership, with no left-alignment on either side, so the same indel spelled
        differently in the two sources reads as absent.
        """
        try:
            found = queries.clinvar_presence(settings, gene)
        except LookupError as unknown:
            raise HTTPException(
                status_code=404, detail=f"no panel gene {unknown.args[0]!r}"
            ) from unknown
        return live(found, "pg.results.clinvar_presence + pg.warehouse.mva_panel_grch38")

    @api.get("/panel/suppressed", response_model=Envelope, tags=["panel"])
    def panel_suppressed(
        gene: str | None = Query(
            default=None,
            description="panel gene symbol, e.g. TRIP13; omit for every suppressed "
            "record in the panel",
        ),
    ) -> dict:
        """The calls the caller kept but flagged inside the candidate panel.

        Two grains in one payload, because the exhibit needs both at once. ``census`` is
        **always the whole panel** — one row per gene per FILTER value, PASS included — so
        a chart can put PASS next to each suppression reason without a second request.
        ``records`` is the non-PASS records themselves, narrowed to ``gene`` when it is
        given. A panel gene with an empty ``records`` list is not an error: nothing
        suppressed there is the good outcome, and only a name the census does not know is
        a 404.

        Live: 20 census rows and 20 records for this panel, both off derived tables.
        """
        census = queries.panel_filter_census(settings)
        if gene is not None and gene not in {row["gene"] for row in census}:
            raise HTTPException(status_code=404, detail=f"no panel gene {gene!r}")
        return live(
            {"gene": gene, "census": census, "records": queries.panel_suppressed(settings, gene)},
            "pg.results.panel_filter_census + pg.results.panel_suppressed",
        )

    routes_search.add_routes(api, settings, cache)
    science.add_routes(api, settings)
    return api


def _add_table_route(api: APIRouter, path: str, function, source: str, settings) -> None:
    """Register one plain table read. A closure per route, so the loop variable is bound."""
    tag = path.strip("/").split("/")[0]

    @api.get(
        path, response_model=Envelope, tags=[tag], name=path.strip("/"), summary=f"read {source}"
    )
    def route() -> dict:
        return live(function(settings), source)
