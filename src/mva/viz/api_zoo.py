"""``/api/zoo/*`` — the model zoo as JSON: the roster, the scores, the ranking, the merge.

Iteration 4 runs a **zoo**: several published variant-effect predictors (models that score
how damaging one DNA change is) over the same callset, each in its own lane, and then merges
their verdicts. :mod:`mva.zoo` owns that machinery; this router is the read-only window onto
what it produced — the warehouse tables it wrote and the run manifests and reports it
committed. No route here triggers a computation.

**Nothing in this file is about this child.** The confirmed gene, the schemas, the table
prefix and every docs path are resolved per request from the zoo's run configuration
(:mod:`mva.viz.api_zoo_case`), so the same routes serve the next case by pointing
``MVA_ZOO_CONFIG`` at another file. ``GET /api/zoo/case`` says which values a reply was built
with, so a dashboard shows the case it received rather than one it assumed.

**Coordinate-free by construction.** Every payload is built from ``allele_id`` hashes, gene
symbols, consequence classes, HGVS spellings and scores. An allele's position exists only in
``<out_dir>/records.parquet``, which no route here opens.

Module split — one concern each, and the reason they are separate files is the 400-line rule:

* :mod:`mva.viz.api_zoo_case` — the case: config resolution and the per-route source lines.
* :mod:`mva.viz.api_zoo_reads` — the record table and the score cache.
* :mod:`mva.viz.api_zoo_ranks` — the ranking table and the zoo's lineage edges.
* :mod:`mva.viz.api_zoo_docs` — the committed run manifests and the rendered reports.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi import Path as PathParam

from ..warehouse.settings import Postgres
from ..zoo import registry
from . import api_zoo_docs as docs
from . import api_zoo_ranks as ranks
from . import api_zoo_reads as reads
from .api_zoo_case import Case, case_config, sources
from .cache import Cache
from .response import Envelope, cached, live

__all__ = ["GENE_LIMIT", "router"]

#: How many allele records one gene request may return before it is truncated.
GENE_LIMIT = 500

#: What resolves the case for a request. Production calls :func:`case_config`; a test hands
#: in a fixed case pointing at its own config and schema.
Resolver = Callable[[], Case]


def router(settings: Postgres, cache: Cache, case: Case | None = None) -> APIRouter:
    """Build the zoo routes. ``case`` pins one case; omitted, each request resolves its own."""
    api = APIRouter(prefix="/api/zoo", tags=["zoo"])
    resolve: Resolver = (lambda: case) if case is not None else case_config
    _add_case_routes(api, settings, cache, resolve)
    _add_score_routes(api, settings, resolve)
    _add_ranking_routes(api, settings, cache, resolve)
    _add_document_routes(api, resolve)
    return api


def _add_case_routes(api: APIRouter, settings: Postgres, cache: Cache, resolve: Resolver) -> None:
    """``/case`` and ``/models`` — what is being served, and by which lanes."""

    @api.get("/case", response_model=Envelope, summary="which case these routes are serving")
    def zoo_case() -> dict:
        """The configuration every other zoo route was built from.

        ``gene`` is the confirmed answer's symbol and is **null** for a case that declares
        none — the normal state of an unsolved case. ``gene_source`` says which of the two
        it is. ``tables`` are the four warehouse tables this case's prefix names.
        """
        current = resolve()
        return live(current.as_dict(), sources(current)["case"])

    @api.get("/models", response_model=Envelope, summary="the roster, with measured coverage")
    def zoo_models(refresh: bool = False) -> dict:
        """Every declared model card plus how much of the record set it actually scored.

        Cards come from the roster (``src/mva/zoo/models.toml`` + ``models.d/*.toml``);
        ``coverage`` is measured by joining the score cache to the record table, per
        consequence class. ``coverage`` is **null** for a lane that has never written a
        score — declared, not run — which is a different statement from a coverage of zero.

        Cached: two aggregates over the whole record set and score cache on a hosted
        database. ``?refresh=true`` rebuilds.
        """
        current = resolve()
        cards = registry.load()

        def build() -> list[dict[str, Any]]:
            with reads.connect(settings) as connection:
                return reads.models_payload(connection, cards, current.tables)

        entry = cache.get_or_build(f"zoo-models-{current.tables.records}", build, refresh)
        return cached(entry, sources(current)["models"])


def _add_score_routes(api: APIRouter, settings: Postgres, resolve: Resolver) -> None:
    """``/scores`` and ``/scores/gene/{symbol}`` — one allele, or one gene's worth."""

    @api.get("/scores", response_model=Envelope, summary="one allele, every lane's verdict")
    def zoo_scores(
        allele_id: str = Query(
            ..., min_length=4, max_length=64, description="the zoo's coordinate-free allele key"
        ),
    ) -> dict:
        """One allele's record and every model's row for it.

        ``rows`` is empty when no lane could score it — a lane blind spot, not a zero.
        ``aux`` is the model's own extra output (classes, per-site deltas), parsed from the
        JSON text the cache stores it as. 404 when neither table knows the id.
        """
        current = resolve()
        with reads.connect(settings) as connection:
            payload = reads.scores_payload(connection, current.tables, allele_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"no record or score for {allele_id!r}")
        return live(payload, sources(current)["scores"])

    @api.get(
        "/scores/gene/{symbol}",
        response_model=Envelope,
        summary="every allele of one gene, every lane's verdict",
    )
    def zoo_scores_gene(
        symbol: str = PathParam(..., min_length=1, max_length=64),
        limit: int = Query(GENE_LIMIT, ge=1, le=GENE_LIMIT),
    ) -> dict:
        """The per-gene view. The symbol is a request parameter, so no gene is privileged.

        ``scored_records`` is how many of the gene's alleles at least one lane could score;
        ``models`` is which lanes spoke about this gene at all. 404 when the record table
        holds no allele of that symbol.
        """
        current = resolve()
        with reads.connect(settings) as connection:
            payload = reads.gene_payload(connection, current.tables, symbol, limit)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"no allele record for gene {symbol!r}")
        return live(payload, sources(current)["scores"])


def _add_ranking_routes(
    api: APIRouter, settings: Postgres, cache: Cache, resolve: Resolver
) -> None:
    """``/ranks``, ``/merge`` and ``/lineage`` — what the lanes concluded, and from what."""

    @api.get("/ranks", response_model=Envelope, summary="one run's ranking, lane by lane")
    def zoo_ranks(
        run_id: str | None = Query(default=None, description="omit for the most recent run"),
        top: int = Query(10, ge=0, le=100),
    ) -> dict:
        """Each lane's ranking of the callset's biallelic pairs, and the confirmed pair's place.

        ``unscored_pairs`` is served beside ``n_ranked`` because a lane that could not score
        half a pair is **excluded** from that pair, never credited with a zero it did not
        earn. A percentile is a position from the top, in percent — smaller is better.
        ``skipped_genes`` is ``[]`` with ``skipped_genes_recorded: false``: the pair builder
        counts the genes over its call cap, but the rank stage does not persist the list.
        """
        current = resolve()
        document = docs.merged_document(current.config.out_dir) or {}
        with reads.connect(settings) as connection:
            payload = ranks.ranks_payload(
                connection,
                current.tables,
                run_id=run_id,
                cards=registry.load(),
                lanes=docs.lanes_by_model(document),
                lanes_run_id=document.get("run_id"),
                top=top,
            )
        if payload is None:
            detail = f"no ranking rows for run {run_id!r}" if run_id else "no run has been ranked"
            raise HTTPException(status_code=404, detail=detail)
        payload["case"] = current.as_dict()
        return live(payload, sources(current)["ranks"])

    @api.get("/merge", response_model=Envelope, summary="the agreement matrix and the consensus")
    def zoo_merge(
        run_id: str | None = Query(default=None, description="omit for the run on disk"),
        refresh: bool = False,
    ) -> dict:
        """How the lanes agree, what the fusion concluded, and where they disagree most.

        ``matrix`` is Spearman ρ between every lane pair over the alleles both scored; a cell
        is **null** where too few alleles are shared — an absent correlation, not a zero one.
        ``consensus`` is reciprocal rank fusion run twice: once over every lane, once with
        the catalogue-adjacent lanes excluded, because a model trained on a variant
        catalogue may have seen the answer. ``disagreements`` gains its gene symbols from
        the record table; the merge step keys on ``allele_id`` and stores no symbol.
        """
        current = resolve()
        document = docs.merged_document(current.config.out_dir)
        if document is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"no merged report at {current.config.out_dir}/merged.json — run `mva-zoo run`"
                ),
            )
        if run_id and document.get("run_id") != run_id:
            found = document.get("run_id")
            raise HTTPException(
                status_code=404,
                detail=f"the merged report on disk is run {found!r}, not {run_id!r}",
            )

        def build() -> dict[str, Any]:
            with reads.connect(settings) as connection:
                genes = reads.genes_of(
                    connection, current.tables, docs.disagreement_alleles(document)
                )
            return docs.merge_payload(document, genes)

        entry = cache.get_or_build(f"zoo-merge-{document.get('run_id')}", build, refresh)
        return cached(entry, sources(current)["merge"])

    @api.get("/lineage", response_model=Envelope, summary="the zoo tables' lineage edges")
    def zoo_lineage(
        table: str | None = Query(default=None, description="one of this case's zoo tables"),
    ) -> dict:
        """``warehouse.data_lineage`` narrowed to the four tables the zoo writes.

        Each edge says which table was written, from which source, by which transform and
        tool — the audit trail behind every number the other routes serve. 422 for a table
        outside the zoo's own set, because the whole ledger is ``/api/provenance/lineage``.
        """
        current = resolve()
        known = current.tables.names
        if table and table not in known:
            raise HTTPException(
                status_code=422,
                detail=f"unknown zoo table {table!r}; known: {', '.join(known)}",
            )
        with reads.connect(settings) as connection:
            rows = ranks.lineage_rows(connection, current.tables, table)
        return live(
            {"tables": list(known), "table": table, "rows": rows},
            sources(current)["lineage"],
        )


def _add_document_routes(api: APIRouter, resolve: Resolver) -> None:
    """``/runs``, ``/reports`` and ``/reports/{key}`` — the files a run committed. No database."""

    @api.get("/runs", response_model=Envelope, summary="every committed run manifest")
    def zoo_runs() -> dict:
        """What ran, when, for how long and at what cost — the coordinate-free manifests.

        Written by the workflow itself (:meth:`mva.zoo.workflow_types.Manifest.public`), so
        ``config_digest`` identifies the configuration a run was made from: the same config
        re-run is the same ``run_id``. An empty list means no run has been committed here.
        """
        current = resolve()
        return live(docs.runs(current.config.docs_runs_dir), sources(current)["runs"])

    @api.get("/reports", response_model=Envelope, summary="the reports that exist")
    def zoo_reports() -> dict:
        """One entry per rendered report — a lane's, plus ``merged`` for the whole zoo.

        The index carries no Markdown: a page lists these, then asks for the one report a
        reader opened.
        """
        current = resolve()
        return live(
            docs.report_keys(current.config.reports_dir, current.config.merged_path),
            sources(current)["reports"],
        )

    @api.get("/reports/{key}", response_model=Envelope, summary="one report as Markdown")
    def zoo_report(key: str = PathParam(..., min_length=1, max_length=64)) -> dict:
        """One report's Markdown and the figures it links. ``merged`` is the whole-zoo one."""
        current = resolve()
        payload = docs.read_report(current.config.reports_dir, current.config.merged_path, key)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"no report {key!r}")
        return live(payload, sources(current)["reports"])
