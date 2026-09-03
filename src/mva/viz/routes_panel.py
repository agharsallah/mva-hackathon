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

from . import geneset, genestructure, phase, proteinstructure, queries
from .cache import Built, Cache, safe_key
from .response import Envelope, cached, describe, live


def add_routes(api: APIRouter, settings, cache: Cache) -> None:
    """Register every warehouse-backed ``/panel/*`` route onto ``api``."""
    _whole_panel_routes(api, settings)
    _one_gene_routes(api, settings, cache)
    _reference_structure_routes(api, settings, cache)


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
    """One gene in detail, off the warehouse. ``locus`` is the callset reader."""

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


def _reference_structure_routes(api: APIRouter, settings, cache: Cache) -> None:
    """The two routes that read no warehouse table at all.

    Both assemble one gene's anatomy from public reference APIs — Ensembl for the exons and
    domains, AlphaFold DB for the fold — behind the same disk cache, because reference data
    is static. Neither payload carries a patient genomic coordinate: alleles are placed in
    amino-acid space, so a screenshot of either exhibit is publishable as-is. They are
    grouped apart from ``_one_gene_routes`` for that reason, and because they are the only
    panel routes whose failure mode is an upstream outage rather than a missing table.

    ``/panel/structure-genes`` is the index the other two are addressed by: it reads one
    committed TSV, so it is ``live`` rather than cached, and it is the route the frontend
    calls first to learn which symbols exist and which of them carry patient alleles.
    """

    @api.get("/panel/structure-genes", response_model=Envelope, tags=["panel"])
    def panel_structure_genes() -> dict:
        """The curated gene set the structure explorer can show, in display order.

        Three groups (``panel``, ``mva-sac``, ``extended``) and two flags that decide what
        an exhibit may claim: ``in_panel`` — derived from the panel BED, not stored twice —
        says whether the proband's annotated alleles exist for this gene at all, and
        ``coding`` says whether ``/panel/protein-structure`` can answer for it or will
        return 422. Public reference facts only: symbol, stable id, biotype.
        """
        return live(geneset.genes(), describe(geneset.SOURCE, geneset.provenance()))

    @api.get("/panel/gene-structure", response_model=Envelope, tags=["panel"])
    def panel_gene_structure(
        gene: str = Query(description="panel gene symbol, e.g. BUB1B"), refresh: bool = False
    ) -> dict:
        """One gene's exons, protein domains and protein-altering alleles.

        Accepts any symbol in the curated set (``/panel/structure-genes``), not only the
        annotated eight: ``in_panel`` in the payload says which, and an off-panel gene
        comes back with ``candidates: []`` because no annotation was ever run there. A
        non-coding gene comes back with real exons, ``protein: null`` and no domains.

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
            entry = cache.get_or_build(key, lambda: _gene_structure(gene, settings), refresh)
        except LookupError as unknown:
            raise HTTPException(status_code=404, detail=_unknown(unknown)) from unknown
        except genestructure.EnsemblError as down:
            raise HTTPException(status_code=502, detail=str(down)) from down
        return cached(entry, genestructure.SOURCE, cache_key=key)

    @api.get("/panel/protein-structure", response_model=Envelope, tags=["panel"])
    def panel_protein_structure(
        gene: str = Query(description="panel gene symbol, e.g. BUB1B"), refresh: bool = False
    ) -> dict:
        """One gene's folded protein as an alpha-carbon (Cα) trace, from AlphaFold DB.

        A ``422`` means the gene makes no protein — a lncRNA in the set has no translation
        to fold, which will never resolve, so it is not a 502 to retry. Use
        ``/panel/gene-structure``, which still returns that gene's real exons.

        The 3D counterpart to ``/panel/gene-structure``, and it deliberately shares that
        route's residue axis: ``protein`` here **must** equal the gene-structure payload's
        ``protein``, or every allele painted from ``candidates[].protein_pos`` lands on a
        different sequence. Four upstream calls (two Ensembl, one AlphaFold API, one
        coordinate file of ~1 MB) behind the same disk cache, because a folded model is
        static reference data. A ``502`` means an upstream was unreachable — never a
        fixture-shaped stand-in. Carries **no** patient data of any kind: it is the same
        model for every human, so this payload is publishable as-is.
        """
        try:
            key = safe_key("protein-structure", gene)
        except ValueError as bad:
            raise HTTPException(status_code=422, detail=str(bad)) from bad
        try:
            entry = cache.get_or_build(key, lambda: _protein_structure(gene, settings), refresh)
        except LookupError as unknown:
            raise HTTPException(status_code=404, detail=_unknown(unknown)) from unknown
        except proteinstructure.NoProteinError as none:
            raise HTTPException(status_code=422, detail=str(none)) from none
        except proteinstructure.UPSTREAM_ERRORS as down:
            raise HTTPException(status_code=502, detail=str(down)) from down
        return cached(entry, proteinstructure.SOURCE, cache_key=key)


# ── per-reply provenance ─────────────────────────────────────────────────────────────
#
# The module ``SOURCE`` constants say which upstreams a route *may* call. That is not
# enough to trace a figure back to its bytes: the same route answers from Ensembl release
# 115 and 116, and from AlphaFold model v4 and v6, with no visible difference. So each
# build wraps its payload in a :class:`mva.viz.cache.Built`, whose provenance dict is
# stored beside the payload in the cache entry and rendered into ``source`` on every
# reply — a cache hit included, which is the case that matters, because that is the reply
# a reader actually screenshots.
#
# It goes beside the payload rather than inside it because the client contracts in
# ``app/src/api/types/`` are frozen: ``ProteinStructure`` has a ``provenance`` field, but
# it is the string ``"alphafold"``, not a manifest, and widening it would break the type.
#
# **Why the Ensembl release is the one recorded at gene-set build time** and not asked
# live. Ensembl REST publishes the release only at ``/info/data``; no reply header carries
# it. Asking it inside a request handler would put an extra round trip and an extra
# failure surface on the one route whose value is that its answer is already on disk, and
# would make the hermetic test suite reach the network. So the release named here is the
# one ``tools/build_gene_set.py`` recorded when it resolved these gene ids — the release
# the committed set *is* — and the key says so rather than implying it was asked now.
# ``tools/build_gene_set.py`` and ``tools/build_protein_fixture.py`` do ask live, through
# :func:`mva.viz.ensembl.release`, because there the round trip is one per build.


def _release() -> str | None:
    """The Ensembl release the committed gene set was resolved against, or ``None``."""
    return geneset.provenance().get("ensembl_release")


def _gene_structure(gene: str, settings) -> Built:
    """One gene's anatomy, plus which Ensembl release and gene record produced it."""
    payload = genestructure.structure(gene, settings)
    return Built(
        payload,
        {
            "ensembl_release_at_gene_set_build": _release(),
            "ensembl_gene": payload.get("ensembl_id"),
            "ensembl_transcript": payload.get("transcript"),
        },
    )


def _protein_structure(gene: str, settings) -> Built:
    """One gene's fold, plus the exact model file and version the trace was parsed from.

    ``model_url`` already carries the version in its filename
    (``AF-O60566-F1-model_v6.cif``), and ``alphafold_version`` states it separately anyway:
    the URL is the *location* and the version is the *fact*, and AlphaFold has changed a
    file's contents at a fixed URL before.
    """
    payload = proteinstructure.structure(gene, settings)
    return Built(
        payload,
        {
            "ensembl_release_at_gene_set_build": _release(),
            "uniprot": payload.get("uniprot"),
            "alphafold_model": payload.get("model_url"),
            "alphafold_version": payload.get("version"),
        },
    )


def _unknown(unknown: LookupError) -> str:
    """The 404 detail for a symbol the structure explorer does not carry.

    Names both sources, because "no panel gene X" stopped being the whole truth once the
    explorer accepted a curated superset: a reader who typed a real gene symbol needs to
    know it is missing from the *set*, not that the gene does not exist.
    """
    return f"no structure gene {unknown.args[0]!r}: not in {geneset.SOURCE}"
