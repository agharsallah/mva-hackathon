"""The panel routes: the candidate genes, and the one view that reads the callset.

Split out of :mod:`mva.viz.routes_warehouse` because it is the largest group of routes
there by far, and the only one with a data-handling rule of its own: ``/api/panel/locus``
is the single route in the service that touches ``variants_raw`` (the five-million-row
raw callset), so it is filtered to one chromosome, and its responses carry **real patient
positions**. Those go to the browser, which is the point, and they are cached under
gitignored ``build/`` — never anywhere the repository can pick up.

Registered by :func:`add_routes`, the idiom :mod:`mva.viz.routes_search` and
:mod:`mva.viz.science` already use.
"""

from fastapi import APIRouter, HTTPException, Query

from . import genestructure, phase, queries
from .cache import Cache, safe_key
from .response import Envelope, cached, live


def add_routes(api: APIRouter, settings, cache: Cache) -> None:
    """Register every warehouse-backed ``/panel/*`` route onto ``api``."""
    _whole_panel_routes(api, settings)
    _one_gene_routes(api, settings, cache)


def _whole_panel_routes(api: APIRouter, settings) -> None:
    """The panel as a set: every gene at once, no gene parameter to narrow it."""

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


def _one_gene_routes(api: APIRouter, settings, cache: Cache) -> None:
    """One gene in detail. Two of these are cached; ``locus`` is the callset reader."""

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
