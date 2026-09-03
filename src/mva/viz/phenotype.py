"""The phenotype ranking as JSON: the terms, the ranking, and one gene's breakdown.

Every other route in this package answers from PostgreSQL or the object store. These read
the **committed reference tables** in ``ressources/reference/`` instead, for the same
reason :mod:`mva.viz.panelbed` reads the panel BED directly: those files are the source of
truth for this ranking rather than a copy of something in the database, they are public
non-patient data, and the pages must render on a checkout where nobody has run
``pg-ingest``.

The tables are *also* declared as staging specs in :mod:`mva.warehouse.reference`, so the
same numbers land in the warehouse whenever an ingest runs. Nothing here depends on that
having happened.

**No genomic position ever reaches this surface.** The ranking is over genes and HPO terms
- a gene symbol and an ontology id - so unlike ``/api/panel/locus`` there is no coordinate
to withhold in the first place.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..phenotype import terms as term_module
from .response import Envelope, live

#: Relative to the repository root, which is where the API is started from.
DEFAULT_ROOT = Path("ressources/reference")

TERM_IC_FILE = "hpo_term_ic.tsv"
GENE_SCORES_FILE = "hpo_gene_scores.tsv"

SOURCE = f"ressources/reference/{GENE_SCORES_FILE}"

#: The candidate panel, used **only** to mark rows in the response. The ranking itself
#: never saw this list, and the flag exists so a reader can see the agreement without a
#: second lookup - not so the ranking can be filtered by it.
PANEL = frozenset({"BUB1B", "CENPE", "CEP192", "CEP57", "DICER1", "SMC5", "TP53", "TRIP13"})


@dataclass(frozen=True)
class Tables:
    """The two committed tables, read once per request path."""

    scores: list[dict[str, str]]
    term_ic: dict[str, dict[str, str]]


def read_tables(root: Path | None = None) -> Tables:
    """Load both reference tables, or raise 503 naming the command that writes them."""
    base = Path(root) if root else DEFAULT_ROOT
    scores = _read_tsv(base / GENE_SCORES_FILE)
    ic_rows = _read_tsv(base / TERM_IC_FILE)
    if not scores:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{base / GENE_SCORES_FILE} is missing or empty. "
                "Run: uv run tools/build_phenotype_data.py"
            ),
        )
    return Tables(scores=scores, term_ic={row["hpo_id"]: row for row in ic_rows})


def _read_tsv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter="\t"))
    except OSError:
        return []


def _row(record: dict[str, str]) -> dict:
    """One ranked gene, typed for the browser."""
    return {
        "gene": record["gene_symbol"],
        "entrez_id": record["entrez_id"] or None,
        "rank": int(record["rank"]),
        "score": float(record["score"]),
        "forward": float(record["forward"]),
        "reverse": float(record["reverse"]),
        "curated_terms": int(record["curated_terms"]),
        "best_term": record["best_term"] or None,
        "best_common_ancestor": record["best_common_ancestor"] or None,
        "best_ic": float(record["best_ic"]) if record["best_ic"] else None,
        "in_panel": record["gene_symbol"] in PANEL,
    }


def add_routes(api: APIRouter) -> None:
    """Register the phenotype routes on the warehouse router."""

    @api.get(
        "/phenotype/terms",
        response_model=Envelope,
        tags=["phenotype"],
        summary="the child's HPO terms, and the two sets they form",
    )
    def phenotype_terms() -> dict:
        """The delivered phenotype, and the one modelling choice inside it.

        Eight terms arrived. Seven describe the child; ``HP:0200067`` (recurrent
        spontaneous abortion) is the **parents'** reproductive history. Every phenotype
        ranker assumes each term describes the patient, so including it is a choice rather
        than a data entry - and both readings are served, with ``proband`` marking which
        terms belong to which set.

        ``notably_absent`` carries the two features a textbook would expect for this
        disease and the document does not list. They are never scored: a plain HPO term
        list cannot say "asked and not present". They are here so the page can show the
        tension rather than let the ranking quietly override it.
        """
        tables = read_tables()
        rows = [
            {
                "hpo_id": term.hpo_id,
                "label": term.label,
                "note": term.note,
                "proband": term.proband,
                "information_content": _ic_of(tables, term.hpo_id),
            }
            for term in term_module.TERMS
        ]
        return live(
            {
                "terms": rows,
                "sets": [
                    {
                        "name": term_set.name,
                        "size": len(term_set),
                        "rationale": term_set.rationale,
                        "ids": list(term_set.ids),
                    }
                    for term_set in term_module.TERM_SETS
                ],
                "notably_absent": [
                    {"hpo_id": hpo_id, "label": label}
                    for hpo_id, label in term_module.NOTABLY_ABSENT
                ],
            },
            source="src/mva/phenotype/terms.py",
        )

    @api.get(
        "/phenotype/genes",
        response_model=Envelope,
        tags=["phenotype"],
        summary=f"read {SOURCE}",
    )
    def phenotype_genes(
        term_set: str = Query("proband-only"),
        limit: int = Query(50, ge=1, le=500),
    ) -> dict:
        """The ranking: every gene scored against the child's symptoms, best first.

        Produced by a scorer that reads two public ontology files and **never** the
        callset, the candidate panel, or a variant. ``in_panel`` marks which rows happen
        to be candidate-panel genes so the agreement is visible; it played no part in the
        ordering.

        ``considered`` is the population a rank is quoted against and includes genes that
        scored zero and are therefore absent from ``rows`` - "rank 6 of 5,267" is the
        honest sentence.
        """
        tables = read_tables()
        selected = [row for row in tables.scores if row["term_set"] == term_set]
        if not selected:
            raise HTTPException(
                status_code=422,
                detail=f"unknown term set {term_set!r}; "
                f"known: {', '.join(s.name for s in term_module.TERM_SETS)}",
            )
        return live(
            {
                "term_set": term_set,
                "considered": _considered(tables, term_set),
                "scored": len(selected),
                "rows": [_row(row) for row in selected[:limit]],
                "panel": sorted(PANEL),
            },
            source=SOURCE,
        )

    @api.get(
        "/phenotype/gene",
        response_model=Envelope,
        tags=["phenotype"],
        summary="why one gene ranked where it did",
    )
    def phenotype_gene(
        symbol: str = Query(..., min_length=1, max_length=64),
        term_set: str = Query("proband-only"),
    ) -> dict:
        """One gene's standing in both term sets, and what moved between them.

        A bare score cannot be argued with. ``delta`` is where the gene sits with all eight
        terms against where it sits on the child's seven, which is the measured cost of
        treating a parental feature as the patient's.
        """
        wanted = symbol.upper()
        tables = read_tables()
        found = {
            row["term_set"]: _row(row) for row in tables.scores if row["gene_symbol"] == wanted
        }
        if not found:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"{wanted} carries no curated phenotype annotation in this HPO "
                    "release - an absence of knowledge, not evidence against the gene."
                ),
            )
        ranks = {name: row["rank"] for name, row in found.items()}
        with_parental = ranks.get(term_module.WITH_PARENTAL.name)
        without = ranks.get(term_module.PROBAND_ONLY.name)
        return live(
            {
                "gene": wanted,
                "in_panel": wanted in PANEL,
                "term_set": term_set,
                "by_term_set": found,
                "delta": {
                    "with_parental": with_parental,
                    "proband_only": without,
                    "moved": (with_parental - without)
                    if with_parental is not None and without is not None
                    else None,
                },
            },
            source=SOURCE,
        )

    @api.get(
        "/phenotype/delta",
        response_model=Envelope,
        tags=["phenotype"],
        summary="what the parental term costs, per panel gene",
    )
    def phenotype_delta() -> dict:
        """Every candidate-panel gene's rank with and without the parental term.

        The roadmap listed this as an open question. A positive ``moved`` means the gene
        **rose** when ``HP:0200067`` was removed.
        """
        tables = read_tables()
        by_gene: dict[str, dict[str, int]] = {}
        for row in tables.scores:
            if row["gene_symbol"] in PANEL:
                by_gene.setdefault(row["gene_symbol"], {})[row["term_set"]] = int(row["rank"])

        rows = []
        for gene in sorted(PANEL):
            ranks = by_gene.get(gene, {})
            before = ranks.get(term_module.WITH_PARENTAL.name)
            after = ranks.get(term_module.PROBAND_ONLY.name)
            rows.append(
                {
                    "gene": gene,
                    "with_parental": before,
                    "proband_only": after,
                    "moved": (before - after) if before is not None and after is not None else None,
                    "curated": gene in by_gene,
                }
            )
        return live(
            {
                "parental_term": term_module.PARENTAL_TERM,
                "parental_label": term_module.by_id(term_module.PARENTAL_TERM).label,
                "considered": _considered(tables, term_module.PROBAND_ONLY.name),
                "rows": rows,
            },
            source=SOURCE,
        )


def _ic_of(tables: Tables, hpo_id: str) -> float | None:
    record = tables.term_ic.get(hpo_id)
    return float(record["information_content"]) if record else None


def _considered(tables: Tables, term_set: str) -> int:
    """How many genes were scored for this term set - the denominator a rank is quoted against.

    Read from the table's own ``genes_considered`` column rather than inferred from the
    highest rank present. Genes scoring zero are not written, so the widest rank is the
    count of genes with signal and is **smaller** than the population - inferring from it
    would quietly flatter every rank by dropping the genes it beat.
    """
    for row in tables.scores:
        if row["term_set"] == term_set:
            return int(row["genes_considered"])
    return 0
